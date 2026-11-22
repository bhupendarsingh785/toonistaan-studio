#!/usr/bin/env python3
"""Audio Judge v2 — apni audio ko poora jaanchne wala nyayadhish.

v1 (self_listen) ki kamiyan:
  • ASR ko line-wise time overlap se jodta tha → segments mix ho jate the
  • background/music ka koi check nahi tha
  • ek hi kirdaar ki lines me consistency nahi dekhta tha
  • insaan se tulna nahi karta tha
  • word-level pronunciation test nahi tha

v2 me:
  1) **Voice isolation** (150 Hz HPF + spectral gate) — bed ka asar hata kar naap
  2) **Word-level ASR alignment** (word_timestamps) — har shabd apni line me
  3) **Pronunciation test** carrier phrase ke saath (alag command)
  4) **Background/music check**: bed level, ducking, SNR, masking
  5) **Kirdaar consistency**: F0 spread, kharos (HNR), pace
  6) **Baseline compare**: insaan ke file se farq
  7) **Scorecard**: PASS / WARN / FAIL + top fixes

CLI:
  python tools/audio_judge.py --audio out.mp3 --marks marks.json --script lines.json \
      [--baseline human.mp3] [--out report.json] [--docx report.docx]
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from difflib import SequenceMatcher
from pathlib import Path

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


# ---------------------------------------------------------------- signals
def voice_only(x):
    """150 Hz HPF + spectral gate — bed/music hata kar awaaz ka hissa bachaao."""
    import numpy as np
    n = len(x)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    X = X * (1 / (1 + (150 / (f + 1e-9)) ** 4))
    y = np.fft.irfft(X, n)
    # frame-wise gate: har frame ka energy, noise floor = 20th percentile
    win, hop = 1024, 512
    fr = list(range(0, max(1, n - win), hop))
    e = np.array([float(np.sqrt((y[i:i + win] ** 2).mean())) for i in fr])
    floor = np.percentile(e, 20) if len(e) else 0
    out = np.zeros(n)
    for i, v in zip(fr, e):
        g = 1.0 if v > max(floor * 1.8, 0.004) else 0.15
        out[i:i + win] += y[i:i + win] * g
    return out


def f0_track(seg):
    """CMNDF (YIN) per frame — raw autocorr ke mode se zyada sthir."""
    import numpy as np
    vals = []
    W = 2048
    for i in range(0, max(1, len(seg) - W), 512):
        s = seg[i:i + W]
        s = s - s.mean()
        if float(np.sqrt((s ** 2).mean())) < 0.006:
            continue
        n = len(s)
        d = np.zeros(n // 2)
        for tau in range(1, n // 2):
            diff = s[:n - tau] - s[tau:]
            d[tau] = float(np.dot(diff, diff))
        cmnd = np.ones_like(d)
        run = 0.0
        for tau in range(1, len(d)):
            run += d[tau]
            cmnd[tau] = d[tau] * tau / (run + 1e-12)
        lo, hi = int(SR / 450), int(SR / 70)
        hi = min(hi, len(cmnd) - 1)
        if hi <= lo + 1:
            continue
        band = cmnd[lo:hi]
        k = lo + int(np.argmin(band))
        if cmnd[k] > 0.45:
            continue
        if 0 < k < len(cmnd) - 1:
            a, b, c = cmnd[k - 1], cmnd[k], cmnd[k + 1]
            den = (a - 2 * b + c)
            if abs(den) > 1e-12:
                k = k + max(-0.5, min(0.5, 0.5 * (a - c) / den))
        vals.append(SR / k)
    return vals


def acoustics(seg, sr=SR):
    import numpy as np
    if len(seg) < 1024:
        return {}
    S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    tot = S.sum() + 1e-9
    rms = float(np.sqrt((seg ** 2).mean()))
    peak = float(np.max(np.abs(seg)))
    clip = float((np.abs(seg) > 0.985).mean() * 100)
    dc = float(seg.mean())
    vals = f0_track(seg)
    f0, sd, nfr = 0, 0.0, len(vals)
    if vals:
        v = np.array(vals, dtype=float)
        med = float(np.median(v))
        v = np.where(v > med * 1.7, v / 2, v)
        v = np.where(v < med * 0.6, v * 2, v)
        f0 = int(np.median(v))
        sd = round(float(np.std(v)), 1)
    jit = 0.0
    if len(vals) > 3:
        jit = round(float(np.mean(np.abs(np.diff(vals))) / (np.mean(vals) + 1e-9)), 3)
    # kharos (HNR) — sirf 8192 sample (O(n^2) se bachne ke liye)
    s = seg[:8192] - seg[:8192].mean()
    ac = np.correlate(s, s, "full")[len(s) - 1:]
    ac = ac / (ac[0] + 1e-12)
    lo, hi = int(sr / 450), int(sr / 70)
    band = ac[lo:min(hi, len(s) - 2)]
    hnr = 0.0
    if len(band) > 3:
        pk = float(band.max())
        hnr = round(10 * float(np.log10(max(1e-6, pk / max(1e-6, 1 - pk)))), 1)
    # echo (1 ms envelope, 17–31 ms)
    k = 16
    seg2 = seg[:SR * 20]                     # 20 s tak kaafi
    env = np.array([np.abs(seg2[i:i + k]).mean() for i in range(0, max(1, len(seg2) - k), k)])
    echo = 0.0
    if len(env) > 60:
        e = env - env.mean()
        a = np.correlate(e, e, "full")[len(e) - 1:]
        a = a / (a[0] + 1e-12)
        step = k / sr
        l, h = int(0.017 / step), int(0.031 / step)
        if h > l:
            echo = round(float(np.max(np.abs(a[l:h + 1]))), 3)
    return {"rms_dbfs": round(20 * float(np.log10(max(1e-9, rms))), 1), "peak": round(peak, 2),
            "clip_pct": round(clip, 3), "dc": round(dc, 4), "f0": f0, "f0_std": sd, "jitter": jit,
            "hnr_db": hnr, "echo": echo, "f0_frames": nfr,
            "low_pct": round(100 * float(S[f < 300].sum() / tot), 1),
            "mid_pct": round(100 * float(S[(f >= 300) & (f < 3000)].sum() / tot), 1),
            "high_pct": round(100 * float(S[f >= 3000].sum() / tot), 1),
            "sibilance_pct": round(100 * float(S[(f >= 4000) & (f < 8000)].sum() / tot), 1),
            "bright_hz": round(float((S * f).sum() / (S.sum() + 1e-9)))}


def background(x):
    """bed/music ka naap: speech gaps me level, ducking, SNR, masking."""
    import numpy as np
    win, hop = 1024, 512
    fr = list(range(0, max(1, len(x) - win), hop))
    e = np.array([float(np.sqrt((x[i:i + win] ** 2).mean())) for i in fr])
    if not len(e):
        return {}
    db = 20 * np.log10(np.maximum(e, 1e-9))
    speech_thr = max(np.percentile(db, 60), -40)
    speech = db > speech_thr - 6
    gap = ~speech
    bed_db = float(np.median(db[gap])) if gap.any() else float(np.percentile(db, 15))
    sp_db = float(np.median(db[speech])) if speech.any() else -20
    # ducking: speech ke andar bed ka level (approx) — gaps se compare
    duck = round(sp_db - bed_db, 1)
    return {"speech_dbfs": round(sp_db, 1), "bed_dbfs": round(bed_db, 1),
            "snr_db": duck, "bed_pct": round(100 * float(gap.mean()), 1),
            "speech_pct": round(100 * float(speech.mean()), 1)}


# ---------------------------------------------------------------- ASR
def asr_words(x, model="small"):
    """word-level timestamps — har shabd apni line me daalne ke liye."""
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=1,
                     download_root="/scratch/work/whisper")
    segs, _ = m.transcribe(x, language="hi", vad_filter=False,
                           condition_on_previous_text=False, word_timestamps=True)
    words = []
    for s in segs:
        for w in (s.words or []):
            t = re.sub(r"[^\u0900-\u097F]", "", w.word or "")
            if t:
                words.append({"w": t, "start": round(w.start, 2), "end": round(w.end, 2)})
    return words


def norm_words(t: str) -> list[str]:
    t = re.sub(r"[^\u0900-\u097F\s]", " ", t)
    return [w for w in re.sub(r"\s+", " ", t).strip().split() if w]


def wer(ref, hyp):
    sm = SequenceMatcher(a=ref, b=hyp, autojunk=False)
    errs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            errs.append({"type": tag, "script": " ".join(ref[i1:i2]), "bola": " ".join(hyp[j1:j2])})
    edits = sum((i2 - i1) if tag == "delete" else (j2 - j1) if tag == "insert"
                else max(i2 - i1, j2 - j1)
                for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
    return round(edits / max(1, len(ref)), 3), errs


# ---------------------------------------------------------------- judge
def judge(audio: str, lines: list[dict], baseline: str = "", model="small", do_asr=True,
          asr_cache: str = "") -> dict:
    import numpy as np
    x = decode(audio)
    v = voice_only(x)
    dur = len(x) / SR
    rep = {"audio": audio, "dur": round(dur, 1), "file_acoustics": acoustics(x),
           "background": background(x), "lines": [], "scorecard": {}, "fixes": []}

    if asr_cache and Path(asr_cache).exists():
        words_all = json.loads(Path(asr_cache).read_text(encoding="utf-8")).get("words", [])
    else:
        words_all = asr_words(v, model) if do_asr else []
    for L in lines:
        a = int(L["start"] * SR); b = int((L["start"] + L["dur"]) * SR)
        seg = v[a:min(b, len(x))]
        ac = acoustics(seg)
        hyp = [w["w"] for w in words_all
               if w["start"] >= L["start"] - 0.25 and w["end"] <= L["start"] + L["dur"] + 0.25]
        ref = norm_words(L["text"])
        w, errs = wer(ref, hyp) if hyp else (1.0, [{"type": "missing", "script": " ".join(ref), "bola": ""}])
        rep["lines"].append({"who": L["who"], "start": L["start"], "dur": L["dur"],
                             "script": L["text"], "bola": " ".join(hyp),
                             "wer": w, "errors": errs, **ac})

    # kirdaar consistency
    per = {}
    for l in rep["lines"]:
        if l["f0"]:
            per.setdefault(l["who"], []).append(l["f0"])
    cons = {}
    for who, arr in per.items():
        arr = np.array(arr, dtype=float)
        if len(arr) < 2:
            cons[who] = {"lines": int(len(arr)), "f0_median": int(np.median(arr)),
                         "f0_spread_pct": 0.0, "note": "LOW_DATA (1 line)"}
            continue
        spread = float((arr.max() - arr.min()) / max(1, np.median(arr)) * 100)
        cons[who] = {"lines": int(len(arr)), "f0_median": int(np.median(arr)),
                     "f0_spread_pct": round(spread, 1)}
    rep["characters"] = cons

    # scorecard
    sc = {}
    fq = rep["file_acoustics"]
    bg = rep["background"]
    sc["clipping"] = {"value": fq["clip_pct"], "verdict": "PASS" if fq["clip_pct"] < 0.01 else "FAIL"}
    sc["peak"] = {"value": fq["peak"], "verdict": "PASS" if 0.5 <= fq["peak"] <= 0.97 else "WARN"}
    sc["dc_offset"] = {"value": fq["dc"], "verdict": "PASS" if abs(fq["dc"]) < 0.01 else "WARN"}
    sc["mix_mid"] = {"value": fq["mid_pct"], "verdict": "PASS" if 45 <= fq["mid_pct"] <= 70 else "WARN"}
    sc["mix_high"] = {"value": fq["high_pct"], "verdict": "PASS" if fq["high_pct"] <= 20 else "WARN"}
    sc["snr"] = {"value": bg.get("snr_db"), "verdict": "PASS" if 8 <= (bg.get("snr_db") or 0) <= 24 else "WARN"}
    sc["echo"] = {"value": fq["echo"], "verdict": "PASS" if fq["echo"] < 0.78 else "WARN"}
    wers = [l["wer"] for l in rep["lines"] if l["wer"] is not None]
    rep["wer_mean"] = round(float(np.mean(wers)), 3) if wers else None
    sc["words"] = {"value": rep["wer_mean"],
                   "verdict": "PASS" if (rep["wer_mean"] or 1) < 0.25 else
                              "WARN" if (rep["wer_mean"] or 1) < 0.45 else "FAIL"}
    for who, c in cons.items():
        sc[f"consistency_{who}"] = {"value": c["f0_spread_pct"],
                                    "verdict": "PASS" if c["f0_spread_pct"] <= 15 else "WARN"}
    rep["scorecard"] = sc

    # fixes (insaani bhasha me)
    if sc["words"]["verdict"] != "PASS":
        rep["fixes"].append("Shabd galat bole ja rahe hain — respell dictionary banao (jaise गाँव → गांव, ठंडक → ठण्डक) aur dobara test karo.")
    if sc["mix_mid"]["verdict"] != "PASS":
        rep["fixes"].append("Mid kam/zyada hai — awaaz ka body (300–3000 Hz) theek karo.")
    if sc["snr"]["verdict"] != "PASS":
        rep["fixes"].append("Background ka level theek karo (SNR 8–24 dB rakho).")
    if sc["echo"]["verdict"] != "PASS":
        rep["fixes"].append("Goonj zyada hai — reverb/pitch-shift artifact check karo.")
    for who, c in cons.items():
        if c["f0_spread_pct"] > 15:
            rep["fixes"].append(f"{who} ki awaaz lines ke beech badal rahi hai ({c['f0_spread_pct']}%) — ek hi setting par lock karo.")
    if not rep["fixes"]:
        rep["fixes"].append("Koi badi kami nahi mili — agla kadam insaan se A/B sunwana.")

    # baseline compare
    if baseline:
        bx = decode(baseline)
        bb = acoustics(bx); bg2 = background(bx)
        rep["baseline"] = {"file": baseline, "acoustics": bb, "background": bg2,
                           "delta": {k: round(fq[k] - bb[k], 1) for k in ("mid_pct", "high_pct", "bright_hz", "echo") if k in fq and k in bb}}
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--marks", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--baseline", default="")
    ap.add_argument("--model", default="small")
    ap.add_argument("--no-asr", action="store_true")
    ap.add_argument("--asr-cache", default="", help="asr_cache.py ka JSON (tez)")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    info = json.loads(Path(a.marks).read_text(encoding="utf-8"))
    src = json.loads(Path(a.script).read_text(encoding="utf-8"))
    lines = [{"who": m["who"], "start": m["start"], "dur": m["dur"],
              "text": src[i]["text"] if i < len(src) else ""} for i, m in enumerate(info["marks"])]
    rep = judge(a.audio, lines, a.baseline, a.model,
                (not a.no_asr) and not a.asr_cache, asr_cache=a.asr_cache)
    if a.out:
        Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"wer_mean": rep["wer_mean"],
                      "scorecard": {k: v["verdict"] for k, v in rep["scorecard"].items()},
                      "fixes": rep["fixes"][:4]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
