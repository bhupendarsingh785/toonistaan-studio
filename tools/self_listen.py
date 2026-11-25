#!/usr/bin/env python3
"""Self Listen — apni audio ko KHUD sun kar jaancho (ASR + acoustics).

Kya karta hai (per line, marks ke hisaab se):
  1) **ASR** (faster-whisper, Hindi) → jo bola gaya woh text
  2) Script se **word-level diff** → WER, kaun shabd galat bole
  3) **Acoustics**: F0 band, HNR (kharos), pace (akshar/s), clipping, sibilance, echo
  4) Har line ka **verdict** + poore file ka **report** (JSON + Hindi summary)

CLI:
  python tools/self_listen.py --audio out.mp3 --script story.json --marks story_local.json \
         --out report.json
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from difflib import SequenceMatcher
from pathlib import Path
try:
    import astra_paths as _AP
except ImportError:
    import sys as _s, pathlib as _pl
    _s.path.insert(0, str(_pl.Path(__file__).resolve().parent)); import astra_paths as _AP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR = 16000


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def decode(path: str):
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", path, "-f", "f32le",
                        "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def norm(t: str) -> str:
    """Devanagari normalize — comparison ke liye (nukta/matra variations ek jaisa)."""
    t = re.sub(r"[^\u0900-\u097F\s]", " ", t)
    t = t.replace("ऩ", "न").replace("ऱ", "र").replace("ऴ", "ळ")
    t = re.sub(r"[।॥]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def words(t: str) -> list[str]:
    return [w for w in norm(t).split() if w]


def wer(ref: list[str], hyp: list[str]) -> tuple[float, list[dict]]:
    sm = SequenceMatcher(a=ref, b=hyp, autojunk=False)
    errs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        errs.append({"type": tag, "script": ref[i1:i2], "bola": hyp[j1:j2]})
    edits = sum((i2 - i1) if tag == "delete" else (j2 - j1) if tag == "insert"
                else max(i2 - i1, j2 - j1)
                for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
    return (edits / max(1, len(ref))), errs


def f0_of(seg):
    """Gayak ka sur — 150 Hz HPF ke baad (bass/bed ka asar hataya)."""
    import numpy as np
    n = len(seg)
    if n < 2048:
        return 0
    X = np.fft.rfft(seg); f = np.fft.rfftfreq(n, 1 / SR)
    seg = np.fft.irfft(X * (1 / (1 + (150 / (f + 1e-9)) ** 4)), n)
    vals = []
    for i in range(0, n - 2048, 1024):
        v = _f0_frame(seg[i:i + 2048])
        if v > 0:
            vals.append(v)
    if not vals:
        return 0
    return int(np.median(vals))


def _f0_frame(seg):
    import numpy as np
    s = seg - seg.mean()
    if len(s) < 400 or float(np.sqrt((s ** 2).mean())) < 0.01:
        return 0
    ac = np.correlate(s, s, "full")[len(s) - 1:]
    ac = ac / (ac[0] + 1e-12)
    lo, hi = int(SR / 450), int(SR / 70)
    band = ac[lo:min(hi, len(s) - 2)]
    if len(band) < 3 or band.max() < 0.25:
        return 0
    ii = np.arange(1, len(band) - 1)
    loc = ii[(band[ii] >= band[ii - 1]) & (band[ii] >= band[ii + 1])]
    st = [i for i in loc if band[i] >= 0.9 * band.max()]
    return int(SR / (lo + (int(st[0]) if st else int(np.argmax(band)))))


def acoustics(seg):
    import numpy as np
    if len(seg) < 1024:
        return {}
    S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    f = np.fft.rfftfreq(len(seg), 1 / SR)
    tot = S.sum() + 1e-9
    sib = float(S[(f >= 4000) & (f < 8000)].sum() / tot * 100)
    low = float(S[f < 300].sum() / tot * 100)
    rms = float(np.sqrt((seg ** 2).mean()))
    peak = float(np.max(np.abs(seg)))
    clip = float((np.abs(seg) > 0.985).mean() * 100)
    # HNR (dB) — periodic vs noise
    s = seg - seg.mean()
    ac = np.correlate(s, s, "full")[len(s) - 1:]
    ac = ac / (ac[0] + 1e-12)
    lo, hi = int(SR / 450), int(SR / 70)
    band = ac[lo:min(hi, len(s) - 2)]
    hnr = 0.0
    if len(band) > 3:
        pk = float(band.max())
        hnr = round(10 * float(np.log10(max(1e-6, pk / max(1e-6, 1 - pk)))), 1)
    # echo: envelope me 17–31 ms par repeat (comb ka nishan) — speech se alag karne ke liye
    k = 16   # 1 ms envelope bins (17–31 ms lag = 17–31 bins)
    env = np.array([np.abs(seg[i:i + k]).mean() for i in range(0, max(1, len(seg) - k), k)])
    echo = 0.0
    if len(env) > 60:
        e = env - env.mean()
        a = np.correlate(e, e, "full")[len(e) - 1:]
        a = a / (a[0] + 1e-12)
        step = k / SR
        l, h = int(0.017 / step), int(0.031 / step)
        if h > l:
            echo = round(float(np.max(np.abs(a[l:h + 1]))), 3)
    return {"sibilance_pct": round(sib, 1), "low_pct": round(low, 1),
            "rms_dbfs": round(20 * float(np.log10(max(1e-9, rms))), 1),
            "peak": round(peak, 2), "clip_pct": round(clip, 2), "hnr_db": hnr, "echo": echo}


def asr(audio_np, model_size="small"):
    from faster_whisper import WhisperModel
    m = WhisperModel(model_size, device="cpu", compute_type="int8",
                     download_root=str(_AP.WORK / "whisper"))
    segs, _ = m.transcribe(audio_np, language="hi", vad_filter=False, beam_size=5)
    return [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]


def run(audio: str, lines: list[dict], model="small") -> dict:
    x = decode(audio)
    dur = len(x) / SR
    heard = asr(x, model)
    rep = {"audio": audio, "dur": round(dur, 1), "asr_lines": heard, "lines": []}
    for L in lines:
        a = int(L["start"] * SR); b = int((L["start"] + L["dur"]) * SR)
        seg = x[a:min(b, len(x))]
        # us line ke ASR tukde (time overlap)
        txt = " ".join(h["text"] for h in heard
                       if h["end"] > L["start"] + 0.15 and h["start"] < L["start"] + L["dur"] - 0.15)
        ref_w, hyp_w = words(L["text"]), words(txt)
        w, errs = wer(ref_w, hyp_w)
        ac = acoustics(seg)
        f0 = f0_of(seg) if len(seg) > 2048 else 0
        pace = round(len(ref_w) * 5.0 / max(0.3, len(seg) / SR), 2)   # andaazan akshar/s
        rep["lines"].append({"who": L["who"], "start": L["start"], "script": L["text"],
                             "bola": txt, "wer": round(w, 3), "errors": errs,
                             "f0": f0, "chars_per_s": pace, **ac})
    ws = [l["wer"] for l in rep["lines"]]
    rep["wer_mean"] = round(sum(ws) / max(1, len(ws)), 3)
    bad = [l for l in rep["lines"] if l["wer"] > 0.25]
    rep["bad_lines"] = len(bad)
    rep["top_errors"] = [e for l in bad for e in l["errors"]][:20]
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--lines", default="", help="JSON: [{who,text,start,dur},...]")
    ap.add_argument("--marks", default="", help="story_local.json (marks se lines banao)")
    ap.add_argument("--script", default="", help="story script json (text ke saath)")
    ap.add_argument("--model", default="small")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.lines:
        lines = json.loads(Path(a.lines).read_text(encoding="utf-8"))
    elif a.marks:
        info = json.loads(Path(a.marks).read_text(encoding="utf-8"))
        src = json.loads(Path(a.script).read_text(encoding="utf-8")) if a.script else None
        lines = []
        for i, m in enumerate(info["marks"]):
            txt = src[i]["text"] if src and i < len(src) else ""
            lines.append({"who": m["who"], "start": m["start"], "dur": m["dur"], "text": txt})
    else:
        ap.error("--lines ya --marks+--script chahiye")
    rep = run(a.audio, lines, a.model)
    if a.out:
        Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"dur": rep["dur"], "wer_mean": rep["wer_mean"],
                      "bad_lines": rep["bad_lines"], "lines": len(rep["lines"]),
                      "top_errors": rep["top_errors"][:8]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
