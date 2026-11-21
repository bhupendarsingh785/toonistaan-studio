#!/usr/bin/env python3
"""Emotion Read — asli insaan ke bhaav: darr, hasi, gussa, dukh, josh, normal.

Chunked (lambe file safe). Har 3 s window par:
  • sur (F0) + uska utar-chadhav (jitter)
  • zor (dB) aur high-band (3kHz+) — darr/scream me zyada
  • envelope modulation 3–8 Hz — **hasi** ka asli signal (bursts)
  • rukne ka pattern — darr me saans rukti hai

Phir har window ko bhaav diya jata hai + timeline + summary.
CLI: python tools/emotion_read.py --audio x.mp3 [--json o.json] [--step 3]
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from collections import Counter
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
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", path, "-f", "s16le",
                        "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768.0


def f0_med(seg):
    """YIN-lite: frames ka median F0 (octave-safe)."""
    import numpy as np
    from tools import audio_read6 as ar
    vals = ar.f0_track(seg, hop=512, win=1024)
    if not vals:
        return 0, 0, 0
    v = np.array(vals)
    jitter = float(np.mean(np.abs(np.diff(v))) / (np.mean(v) + 1e-9)) if len(v) > 2 else 0.0
    return int(np.median(v)), round(float(np.std(v)), 1), round(jitter, 3)


def modulation(env, sr=SR, lo=3.0, hi=8.0):
    """envelope ka 3–8 Hz modulation — hasi/rona ka signal."""
    import numpy as np
    e = np.abs(env)
    w = max(1, len(e) // 200)
    e = np.array([e[i:i + w].mean() for i in range(0, max(1, len(e) - w), w)])
    if len(e) < 16:
        return 0.0
    e = e - e.mean()
    F = np.abs(np.fft.rfft(e))
    f = np.fft.rfftfreq(len(e), (len(env) / len(e)) / sr)
    m = (f >= lo) & (f <= hi)
    return float(F[m].sum() / (F.sum() + 1e-9))


def emotion_of(f0, sd, jit, rms_db, high_pct, mod, speech_pct):
    if rms_db < -40 and speech_pct < 10:
        return "khamoshi"
    if mod > 0.28 and rms_db > -28:
        return "hasi/khilkhilana"
    if rms_db > -20 and high_pct > 22 and (sd > 45 or jit > 0.06):
        return "cheekh/darr ka jhatka"
    if sd > 50 and rms_db > -26:
        return "gussa/tez"
    if jit > 0.05 and high_pct > 18:
        return "darr (kaanpta hua)"
    if f0 and f0 < 165 and rms_db < -26:
        return "dukh/thehra"
    if speech_pct > 35:
        return "normal baat"
    return "mahaul/chalu"


def read(path: str, step: int = 3) -> dict:
    import numpy as np
    x = decode(path)
    if len(x) == 0:
        return {"ok": False, "why": "decode fail"}
    dur = len(x) / SR
    n = int(step * SR)
    rows = []
    for i in range(0, len(x) - n + 1, n):
        seg = x[i:i + n]
        rms = float(np.sqrt((seg ** 2).mean()))
        N = 1024
        S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f = np.fft.rfftfreq(len(seg), 1 / SR)
        tot = S.sum() + 1e-9
        high_pct = float(S[f >= 3000].sum() / tot * 100)
        e = np.array([np.sqrt((seg[j:j + N] ** 2).mean()) for j in range(0, max(1, len(seg) - N), 512)])
        speech_pct = float((e > max(0.006, np.percentile(e, 15) * 2)).mean() * 100) if len(e) else 0
        f0, sd, jit = f0_med(seg)
        mod = modulation(seg)
        emo = emotion_of(f0, sd, jit, round(20 * float(np.log10(max(1e-9, rms))), 1),
                         high_pct, mod, speech_pct)
        rows.append({"at": i // SR, "emo": emo, "f0": f0, "sd": sd, "jitter": jit,
                     "rms_db": round(20 * float(np.log10(max(1e-9, rms))), 1),
                     "high_pct": round(high_pct, 1), "mod": round(mod, 3),
                     "speech_pct": round(speech_pct, 1)})
    # merge consecutive same emotion
    merged = []
    for r in rows:
        if merged and merged[-1]["emo"] == r["emo"]:
            merged[-1]["to"] = r["at"] + step
        else:
            merged.append({"from": r["at"], "to": r["at"] + step, "emo": r["emo"]})
    cnt = Counter(r["emo"] for r in rows)
    return {"ok": True, "file": Path(path).name, "dur": round(dur, 1), "step_s": step,
            "blocks": len(rows), "emotions": dict(cnt),
            "timeline": merged, "raw": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--json", default="")
    ap.add_argument("--step", type=int, default=3)
    a = ap.parse_args()
    rep = read(a.audio, a.step)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: rep.get(k) for k in ("ok", "dur", "blocks", "emotions")}
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
