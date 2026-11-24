#!/usr/bin/env python3
"""harmonic_clean.py — TTS ki "kharaash" kam, awaaz saaf (insaan jaisi).

Naap (asli insaan ka norm): jitter 0.14-0.5%, shimmer 1.6-3.3%, HNR 20-26 dB.
Piper ka raw output: jitter ~3.5%, shimmer ~11%, HNR ~11 dB — isi se robotic lagta hai.

Yahan harmaani (sur ke gunaaharon) ko ubhaara jaata hai aur shor ko dabaya jaata hai:
  • har frame ka sur (F0) naapo
  • sur ke gunaaharon ke aas-paas ke bins ko +6..+10 dB
  • baaki (shor) ko -6..-12 dB
Isse periodicity badhti hai (HNR upar), kharaash kam hoti hai.

  python tools/harmonic_clean.py --file in.wav --out out.wav
  python tools/harmonic_clean.py --selftest
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


def f0_track(x, sr, n_fft=2048, hop=512):
    f0 = np.zeros(1 + (len(x) - n_fft) // hop)
    for i in range(len(f0)):
        seg = x[i * hop:i * hop + n_fft]
        if np.sqrt((seg ** 2).mean()) < 0.01:
            continue
        ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
        lo, hi = int(sr / 450), min(int(sr / 70), len(ac) - 1)
        if hi <= lo:
            continue
        lag = np.argmax(ac[lo:hi]) + lo
        f0[i] = sr / (lag + 1e-9)
    return f0


def clean(x, sr, boost_db=8.0, cut_db=-9.0, n_fft=2048, hop=512):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(1)
    f0 = f0_track(x, sr, n_fft, hop)
    win = np.hanning(n_fft)
    freqs = np.fft.rfftfreq(n_fft, 1 / sr)
    out = np.zeros(len(x) + n_fft)
    wsum = np.zeros(len(x) + n_fft)
    for i in range(len(f0)):
        seg = x[i * hop:i * hop + n_fft]
        if len(seg) < n_fft:
            break
        X = np.fft.rfft(seg * win)
        f = f0[i]
        mask = np.full(len(freqs), 10 ** (cut_db / 20.0))
        if f > 60:
            k = 1
            while k * f < sr / 2 - 200 and k < 40:
                c = k * f
                bw = max(30.0, f * 0.18)
                m = np.abs(freqs - c) < bw
                mask[m] = np.maximum(mask[m], 10 ** (boost_db / 20.0))
                k += 1
        y = np.fft.irfft(X * mask, n=n_fft) * win
        out[i * hop:i * hop + n_fft] += y
        wsum[i * hop:i * hop + n_fft] += win ** 2
    y = out[:len(x)] / np.maximum(wsum[:len(x)], 1e-6)
    return y / (np.max(np.abs(y)) + 1e-9) * 0.95


def measure(path):
    import parselmouth
    from parselmouth.praat import call
    snd = parselmouth.Sound(str(path))
    pp = call(snd, "To PointProcess (periodic, cc)", 70, 450)
    jit = call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
    shim = call([snd, pp], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    harm = call(snd, "To Harmonicity (cc)", 0.01, 70, 0.1, 1.0)
    return {"jitter": round(jit * 100, 3), "shimmer": round(shim * 100, 2),
            "hnr": round(call(harm, "Get mean", 0, 0), 1)}


def selftest():
    import soundfile as sf
    src = Path("/tmp/raw_pratham.wav")
    if not src.exists():
        print("test clip nahi mila (/tmp/raw_pratham.wav)"); return 1
    y, sr = sf.read(str(src))
    y = y.mean(1) if y.ndim > 1 else y
    print("pehle:", measure(src))
    for b, c in ((6, -6), (8, -9), (10, -12)):
        y2 = clean(y, sr, b, c)
        out = Path(f"/tmp/hc_{b}_{c}.wav")
        sf.write(str(out), y2.astype("float32"), sr)
        print(f"boost +{b} / cut {c}:", measure(out))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--out", default="/tmp/harmonic_out.wav")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest or not a.file:
        return selftest()
    import soundfile as sf
    y, sr = sf.read(a.file)
    y2 = clean(y, sr)
    sf.write(a.out, y2.astype("float32"), sr)
    print("saved:", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
