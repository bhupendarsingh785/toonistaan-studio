#!/usr/bin/env python3
"""clarity.py — awaaz ko saaf/crisp karne ki chain (naap par tika hua).

Kyun: MMS 16 kHz model hai — 1-4 kHz (jahan shabd saaf sunai dete hain) sirf 4%,
4-8 kHz lagbhag 0%. Isliye "dabbi/bhrrr" lagti hai.

Chain:
  1. 100 Hz high-pass        — rumble (bhrrr) hatao
  2. harmonic exciter 6/0.7  — 2-8 kHz me naye harmonics (clarity)
  3. presence +3 dB (1.8-4.2 kHz)
  4. de-ess 6-8.5 kHz        — s/sh ki chamak niyantrit
  5. loudness -16 LUFS + peak 0.95

Naap (hamari file): articulation 4.4% -> 40.3% (asli insaan ~40%), 4-8k 0.1% -> 5.1%, boom 29% -> 17%
"""
from __future__ import annotations
import argparse
import numpy as np
import soundfile as sf
from scipy import signal as ss


def clarity(x, sr, hp=100, drive=6.0, amt=0.7, pres_db=3.0, deess=0.35):
    x = np.asarray(x, dtype=np.float64)
    sos = ss.butter(4, hp / (sr / 2), btype="high", output="sos")
    z = ss.sosfilt(sos, x)
    # exciter
    sh = ss.butter(4, 2000 / (sr / 2), btype="high", output="sos")
    hpp = ss.sosfilt(sh, z)
    hf = np.tanh(drive * hpp / (np.max(np.abs(hpp)) + 1e-9))
    sb = ss.butter(4, [2000 / (sr / 2), min(0.95, 8500 / (sr / 2))], btype="band", output="sos")
    hf = ss.sosfilt(sb, hf)
    hf = hf / (np.max(np.abs(hf)) + 1e-9) * np.max(np.abs(z))
    z = z + amt * hf
    # presence
    sp = ss.butter(2, [1800 / (sr / 2), 4200 / (sr / 2)], btype="band", output="sos")
    z = z + (10 ** (pres_db / 20) - 1) * ss.sosfilt(sp, z)
    # de-ess
    sd = ss.butter(2, [6000 / (sr / 2), min(0.95, 8500 / (sr / 2))], btype="band", output="sos")
    z = z - deess * ss.sosfilt(sd, z)
    return z / (np.max(np.abs(z)) + 1e-9) * 0.9


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    a = ap.parse_args()
    y, sr = sf.read(a.inp)
    y = y.mean(1) if y.ndim > 1 else y
    z = clarity(y, sr)
    try:
        import pyloudnorm as ln
        m = ln.Meter(sr)
        z = ln.normalize.loudness(z, m.integrated_loudness(z), -16.0)
    except Exception:
        pass
    pk = float(np.max(np.abs(z)))
    if pk > 0.95:
        z = z * (0.95 / pk)
    sf.write(a.out, z.astype("float32"), sr)
    print("likha:", a.out, "| dur", round(len(z) / sr, 1), "| peak", round(float(np.max(np.abs(z))), 3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
