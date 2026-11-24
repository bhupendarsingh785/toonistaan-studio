#!/usr/bin/env python3
"""smooth_real.py — TTS ki robotic feel hatao, asli insaan jaisa "dhang" laao.

Asli profile (prosody_real.py) se 4 cheezein match karte hain:
  1. **sur ka failaav** — robotic = ek hi sur par atka; asli = upar-neeche ghoomta hai
  2. **dheema drift** — insaan ka sur kabhi bilkul seedha nahi rehta
  3. **buzz kam** — 7.5 kHz ke baad halka cut + halki smoothing
  4. **shuruaat/ant saaf** — click nahi, dheema fade

  python tools/smooth_real.py --file in.wav --out out.wav
  python tools/smooth_real.py --selftest
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
K = ROOT / "knowledge"


def _profile():
    p = K / "real-speech-profile.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))["agg"]
    return {"f0_range": 60.0, "centroid": 1600.0}


def pitch_drift(x, sr, depth=0.012, rate=0.9, seed=3):
    """Halka organic drift — sur bilkul seedha nahi rehta (insaan jaisa)."""
    t = np.arange(len(x)) / sr
    rng = np.random.default_rng(seed)
    f1, f2 = rate, rate * rng.uniform(1.6, 2.4)
    mod = 1.0 + depth * (np.sin(2 * np.pi * f1 * t) + 0.5 * np.sin(2 * np.pi * f2 * t + 1.1))
    idx = np.clip(np.cumsum(mod) - mod[0], 0, len(x) - 1).astype(int)
    return x[idx]


def debuzz(x, sr):
    """Robotic buzz: 7.5k ke baad dheema cut + halka smoothing."""
    from scipy import signal as ss
    sos = ss.butter(4, min(0.9, 6500 / (sr / 2)), btype="low", output="sos")
    y = ss.sosfilt(sos, x)
    # 2-5 kHz ka tez hissa halka neeche (robotic "dana" isi se aata hai)
    sos2 = ss.butter(2, [1800 / (sr / 2), min(0.95, 5200 / (sr / 2))], btype="band", output="sos")
    y = y - 0.18 * ss.sosfilt(sos2, y)
    # halki smoothing (3-tap) — "dana-dana" khatam
    y = np.convolve(y, np.array([0.2, 0.6, 0.2]), mode="same")
    return y


def widen_pitch(x, sr, target_range=None):
    """Sur ka failaav badhao — chhote hisson ko halka upar/neeche shift karke."""
    if target_range is None:
        target_range = _profile().get("f0_range", 60.0)
    win, hop = int(0.20 * sr), int(0.10 * sr)
    if len(x) < win * 3:
        return x
    out = np.zeros(len(x) + win)
    wsum = np.zeros(len(x) + win)
    hann = np.hanning(win)
    for i in range(0, len(x) - win, hop):
        seg = x[i:i + win]
        # us hisse ka sur
        ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
        lo, hi = int(sr / 450), min(int(sr / 70), len(ac) - 1)
        f0 = sr / (np.argmax(ac[lo:hi]) + lo + 1e-9) if hi > lo else 0
        if f0 <= 0:
            g = 1.0
        else:
            # dheere-dheere upar-neeche (2.5 s ka cycle) — asli baat-cheet jaisa
            phase = (i / sr) * 2 * np.pi / 2.5
            g = 1.0 + 0.045 * np.sin(phase)
        n_new = max(2, int(len(seg) / g))
        seg2 = np.interp(np.linspace(0, len(seg) - 1, n_new), np.arange(len(seg)), seg)
        seg2 = np.interp(np.linspace(0, n_new - 1, len(seg)), np.arange(n_new), seg2)
        out[i:i + win] += seg2 * hann
        wsum[i:i + win] += hann
    y = (out[:len(x)] / np.maximum(wsum[:len(x)], 1e-3))
    return y


def trim_short_gaps(x, sr, keep_gap=0.10):
    """Chhote chhote gap (ruka-ruka feel) hatao — asli baat-cheet me aisa nahi hota."""
    n = int(0.01 * sr)
    if len(x) < n * 4:
        return x
    e = np.array([np.sqrt((x[i:i + n] ** 2).mean()) for i in range(0, len(x) - n, n)])
    thr = 0.06 * (np.percentile(e, 95) + 1e-9)
    voiced = e > thr
    pieces, start, run = [], 0, 0
    keep = int(keep_gap / 0.01)
    for i, v in enumerate(voiced):
        if v:
            if run and run >= keep:          # asli ruk (rakho)
                pieces.append((start, i - run + run))
                start = i
            run = 0
        else:
            run += 1
    pieces.append((start, len(voiced)))
    out = []
    for a, b in pieces:
        seg = x[a * n:min(len(x), b * n + n)]
        if len(seg):
            out.append(seg)
            out.append(np.zeros(int(0.02 * sr)))     # 20ms saans
    return np.concatenate(out) if out else x


def smooth(x, sr, widen=True):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(1)
    y = trim_short_gaps(x, sr)
    y = debuzz(y, sr)
    y = pitch_drift(y, sr)
    if widen:
        y = widen_pitch(y, sr)
    # fade (click nahi)
    a = int(0.02 * sr)
    if len(y) > 2 * a:
        y[:a] *= np.linspace(0, 1, a)
        y[-a:] *= np.linspace(1, 0, a)
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.95
    return y


def _measure(x, sr):
    win, hop = int(0.04 * sr), int(0.02 * sr)
    f0 = []
    for i in range(0, max(1, len(x) - win), hop):
        s = x[i:i + win]
        if np.sqrt((s ** 2).mean()) < 0.012:
            continue
        ac = np.correlate(s, s, "full")[len(s) - 1:]
        lo, hi = int(sr / 450), min(int(sr / 70), len(ac) - 1)
        if hi > lo:
            f0.append(sr / (np.argmax(ac[lo:hi]) + lo + 1e-9))
    f0 = np.array([v for v in f0 if 70 < v < 450]) if f0 else np.array([0.0])
    n = 1024
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[:: n // 2]
    X = np.abs(np.fft.rfft(fr * np.hanning(n), axis=1)) + 1e-10
    f = np.fft.rfftfreq(n, 1 / sr)
    spec = X.mean(0)
    return {"f0_range": round(float(np.percentile(f0, 90) - np.percentile(f0, 10)), 1),
            "centroid": round(float((spec * f).sum() / (spec.sum() + 1e-12)), 0)}


def selftest():
    import soundfile as sf
    src = Path("/scratch/work/pov14/kahani.wav")
    if not src.exists():
        print("test clip nahi mila"); return 1
    y, sr = sf.read(str(src))
    seg = y[: int(6 * sr)]
    before = _measure(seg.mean(1) if seg.ndim > 1 else seg, sr)
    after_y = smooth(seg, sr)
    after = _measure(after_y, sr)
    print("pehle:", before)
    print("baad :", after)
    out = Path("/scratch/work/smooth_test.wav")
    sf.write(str(out), after_y.astype("float32"), sr)
    print("saved:", out)
    ok = after["f0_range"] >= before["f0_range"] * 1.05
    print("PASS — sur ka failaav badha (kam robotic)" if ok else "FAIL — failaav nahi badha")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest or not a.file:
        return selftest()
    import soundfile as sf
    y, sr = sf.read(a.file)
    y2 = smooth(y, sr)
    sf.write(a.out or "/scratch/work/smooth_out.wav", y2.astype("float32"), sr)
    print("saved:", a.out or "/scratch/work/smooth_out.wav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
