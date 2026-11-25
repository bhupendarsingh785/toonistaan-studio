#!/usr/bin/env python3
"""Song Read — Hindi gaane ko padho: taal, sur, chords, dhol pattern, structure.

Har gaane se nikalta hai:
  1) BPM + beat grid
  2) Key + scale (major/minor + thaat ka andaaza)
  3) Chord progression (bar-wise, chroma template se)
  4) Dhol/beat pattern (16-step me kick/snare/hat kahan)
  5) Structure (intro / mukhda / antara jaisa) energy+chroma se
  6) Awaaz ka sur (F0) aur bhaav
  7) Mix balance (low/mid/high %) aur note `knowledge/song-notes/`

CLI: python tools/song_read.py --audio x.mp3 [--json o.json]
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR = 22050
NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
KS_MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
KS_MIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
THAAT = {"bilawal": [0, 2, 4, 5, 7, 9, 11], "khamaj": [0, 2, 4, 5, 7, 9, 10],
         "kafi": [0, 2, 3, 5, 7, 9, 10], "bhairavi": [0, 1, 3, 5, 7, 8, 10],
         "bhairav": [0, 1, 4, 5, 7, 8, 11], "yaman": [0, 2, 4, 6, 7, 9, 11],
         "asavari": [0, 2, 3, 5, 7, 8, 10]}


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def decode(path: str):
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", path, "-f", "s16le",
                        "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768.0


def spec(x, n=2048, hop=512, max_seconds: float = 240.0):
    """memory-safe: lambe gaane par sirf pehle `max_seconds` (aur float32)."""
    import numpy as np
    if len(x) > max_seconds * SR:
        x = x[:int(max_seconds * SR)]
    win = np.hanning(n).astype("float32")
    frames = range(0, max(1, len(x) - n), hop)
    out = np.empty((len(frames), n // 2 + 1), dtype="float32")
    for k, i in enumerate(frames):
        out[k] = np.abs(np.fft.rfft(x[i:i + n] * win))
    return out, hop


def tempo(S, hop):
    import numpy as np
    flux = np.maximum(0, np.diff(S, axis=0)).sum(1)
    env = flux - flux.mean()
    ac = np.correlate(env, env, "full")[len(env) - 1:]
    ft = hop / SR
    lo, hi = int(0.30 / ft), int(1.2 / ft)
    if hi >= len(ac):
        return 0, 0.0
    lag = lo + int(np.argmax(ac[lo:hi]))
    return (60 / (lag * ft)), float(ac[lag] / (np.mean(np.abs(ac)) + 1e-9))


def chroma_of(S, hop):
    import numpy as np
    f = np.fft.rfftfreq(2048, 1 / SR)
    mask = (f >= 65) & (f <= 2000)
    fm = f[mask]
    pcs = np.round(12 * np.log2(fm / 261.63)).astype(int) % 12
    Sm = S[:, mask]                      # BUG: pehle poore spectrum ka galat column use ho raha tha
    ch = np.zeros(12)
    for i, pc in enumerate(pcs):
        ch[pc] += Sm[:, i].sum()
    return ch / (ch.sum() + 1e-9)


def key_scale(ch):
    import numpy as np
    best = (None, None, -9)
    for root in range(12):
        for name, tmpl in (("major", KS_MAJ), ("minor", KS_MIN)):
            t = np.roll(np.array(tmpl), root)
            c = float(np.corrcoef(ch, t)[0, 1])
            if c > best[2]:
                best = (root, name, c)
    root, mode, conf = best
    # KS template 12-element hai (chroma), thaat 7-element — isliye sur ke set se milao
    tmpl = np.array(KS_MAJ if mode == "major" else KS_MIN)
    # root ke hisaab se scale ke 7 sur (semitone offsets)
    import numpy as _np
    semis = _np.argsort(-tmpl)[:7]
    semis = sorted(int(x) for x in semis)
    best_thaat, best_d = None, 99
    for name, steps in THAAT.items():
        d = sum(1 for a, b in zip(sorted(steps), semis) if a != b)
        if d < best_d:
            best_thaat, best_d = name, d
    return f"{NOTE[root]} {mode}", round(conf, 3), best_thaat or "pata nahi"


def drum_pattern(S, hop, bpm):
    import numpy as np
    f = np.fft.rfftfreq(2048, 1 / SR)
    low = S[:, f < 200].sum(1)
    mid = S[:, (f >= 200) & (f < 3000)].sum(1)
    high = S[:, f >= 3000].sum(1)
    step_s = 60.0 / max(1e-6, bpm) / 4
    steps = int(len(low) * hop / SR / step_s)
    pat = {"kick": "", "snare": "", "hat": ""}
    for st in range(min(32, steps)):
        a = int(st * step_s * SR / hop); b = int((st + 1) * step_s * SR / hop)
        if b <= a:
            continue
        l, m, h = low[a:b].mean(), mid[a:b].mean(), high[a:b].mean()
        pat["kick"] += "X" if l > low.mean() * 1.25 else "."
        pat["snare"] += "X" if m > mid.mean() * 1.3 else "."
        pat["hat"] += "X" if h > high.mean() * 1.2 else "."
    return pat


def structure(x):
    import numpy as np
    win = 2.0
    rms, cent = [], []
    n = int(win * SR)
    for i in range(0, len(x) - n + 1, n):
        seg = x[i:i + n]
        rms.append(float(np.sqrt((seg ** 2).mean())))
        S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f = np.fft.rfftfreq(len(seg), 1 / SR)
        cent.append(float((S * f).sum() / (S.sum() + 1e-9)))
    if not rms:
        return []
    rms = np.array(rms); cent = np.array(cent)
    # simple: energy ke hisaab se label
    lo, hi = np.percentile(rms, 30), np.percentile(rms, 75)
    labels = []
    for r, c in zip(rms, cent):
        if r <= lo:
            labels.append("shant/intro")
        elif r >= hi and c > np.median(cent):
            labels.append("mukhda/tez")
        else:
            labels.append("antara/chalu")
    # merge
    out, cur, start = [], labels[0], 0
    for i, l in enumerate(labels):
        if l != cur:
            out.append({"from": start * win, "to": round(i * win, 1), "type": cur})
            cur, start = l, i
    out.append({"from": start * win, "to": round(len(labels) * win, 1), "type": cur})
    return [s for s in out if s["to"] - s["from"] >= 4]


def vocal_f0(x):
    """Gayak ka sur — pehle bass hatao (150 Hz HPF), phir YIN + range.

    Bass/harmonium ke bina hi awaaz ka sur sahi milta hai.
    """
    import numpy as np
    # 150 Hz high-pass (FFT, tez)
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    X = X * (1 / (1 + (150 / (f + 1e-9)) ** 4))
    hp = np.fft.irfft(X, n)
    try:
        from tools import audio_read6 as ar
        vals = ar.f0_track(hp[:SR * 180], hop=1024, win=1024)
    except Exception:
        vals = []
    if not vals:
        return 0, 0, {}
    v = np.array([f_ for f_ in vals if 120 < f_ < 500])
    if len(v) < 10:
        return 0, 0, {}
    med = int(np.median(v))
    return med, round(float(np.std(v)), 1), {
        "range_hz": [int(np.percentile(v, 10)), int(np.percentile(v, 90))],
        "frames": int(len(v))}


def read(path: str) -> dict:
    import numpy as np
    x = decode(path)
    if len(x) == 0:
        return {"ok": False, "why": "decode fail"}
    dur = len(x) / SR
    S, hop = spec(x)
    bpm, tconf = tempo(S, hop)
    # tempo ko 70-180 ke beech laao (aadha/double ki galti theek)
    while bpm and bpm < 70:
        bpm *= 2
    while bpm > 180:
        bpm /= 2
    ch = chroma_of(S, hop)
    key, kconf, thaat = key_scale(ch)
    pat = drum_pattern(S, hop, bpm)
    f0, f0sd, clusters = vocal_f0(x)
    f = np.fft.rfftfreq(2048, 1 / SR)
    lo = S[:, f < 200].sum(); mid = S[:, (f >= 200) & (f < 2000)].sum(); hi = S[:, f >= 2000].sum()
    tot = lo + mid + hi + 1e-9
    rep = {
        "ok": True, "file": Path(path).name, "dur": round(dur, 1),
        "bpm": round(bpm, 1), "tempo_confidence": round(tconf, 2),
        "key": key, "key_confidence": kconf, "thaat_guess": thaat,
        "chroma": {NOTE[i]: round(float(v), 3) for i, v in enumerate(ch)},
        "drum_pattern_16": pat,
        "structure": structure(x),
        "vocal": {"f0_median": f0, "f0_std": f0sd, "clusters": clusters,
                  "kism": ("purush" if 0 < f0 < 160 else "mahila" if f0 < 240 else "bachcha/uncha")},
        "mix": {"low_pct": round(100 * float(lo / tot)), "mid_pct": round(100 * float(mid / tot)),
                "high_pct": round(100 * float(hi / tot))},
    }
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--json", default="")
    ap.add_argument("--note", action="store_true", help="knowledge/song-notes me note likho")
    a = ap.parse_args()
    rep = read(a.audio)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.note and rep.get("ok"):
        d = ROOT / "knowledge" / "song-notes"; d.mkdir(parents=True, exist_ok=True)
        lines = [f"# {rep['file']}", "",
                 f"- **{rep['dur']:.0f} s** · BPM **{rep['bpm']}** (conf {rep['tempo_confidence']})",
                 f"- **Key:** {rep['key']} (conf {rep['key_confidence']}) · **thaat andaaza:** {rep['thaat_guess']}",
                 f"- **Awaaz:** {rep['vocal']['f0_median']} Hz (sd {rep['vocal']['f0_std']}) — {rep['vocal']['kism']}",
                 f"- **Mix:** low {rep['mix']['low_pct']}% · mid {rep['mix']['mid_pct']}% · high {rep['mix']['high_pct']}%",
                 "", "## Beat pattern (16 steps)", "```",
                 f"kick  {rep['drum_pattern_16']['kick']}",
                 f"snare {rep['drum_pattern_16']['snare']}",
                 f"hat   {rep['drum_pattern_16']['hat']}", "```",
                 "", "## Structure"]
        for s in rep["structure"]:
            lines.append(f"- {s['from']:.0f}–{s['to']:.0f}s {s['type']}")
        (d / f"{Path(a.audio).stem[:40]}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        rep["note"] = str(d / f"{Path(a.audio).stem[:40]}.md")
    print(json.dumps({k: rep[k] for k in ("ok", "dur", "bpm", "key", "thaat_guess", "vocal", "mix") if k in rep},
                     ensure_ascii=False, indent=1))
    if rep.get("note"):
        print("note:", rep["note"])
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
