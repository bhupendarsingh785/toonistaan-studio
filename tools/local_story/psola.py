#!/usr/bin/env python3
"""psola.py — TD-PSOLA: sur (F0) badlo, awaaz ka rang (formant) waisa hi rahe.

Formant shift se awaaz robot banti hai (naap liya). PSOLA pitch-synchronous grains
ko naye period par rakhta hai — isliye timbre nahi badalta.

  y2 = shift(y, sr, contour)   # contour = function(t_sec) -> semitone offset
"""
from __future__ import annotations
import numpy as np


def f0_track(y, sr, hop=160, win=640, fmin=70, fmax=420):
    """Har hop par F0 (Hz), 0 = unvoiced."""
    out = np.zeros(max(0, (len(y) - win) // hop + 1), dtype=np.float32)
    lo, hi = int(sr / fmax), int(sr / fmin)
    for i in range(0, len(y) - win, hop):
        fr = y[i:i + win]
        if float(np.sqrt((fr ** 2).mean())) < 0.008:
            continue
        fr = fr - fr.mean()
        ac = np.correlate(fr, fr, "full")[win - 1:]
        seg = ac[lo:hi]
        if not len(seg):
            continue
        lag = lo + int(np.argmax(seg))
        if ac[lag] > 0.30 * ac[0]:
            out[i // hop] = sr / lag
    # chhote gaps bharo
    for i in range(1, len(out) - 1):
        if out[i] == 0 and out[i - 1] > 0 and out[i + 1] > 0:
            out[i] = (out[i - 1] + out[i + 1]) / 2
    return out


def shift(y, sr, contour, hop=160, win=640):
    """TD-PSOLA. contour(t_sec) -> semitone (jaise +1.5)."""
    y = np.asarray(y, dtype=np.float32)
    f0 = f0_track(y, sr, hop, win)
    out = np.zeros(len(y) + sr // 2, dtype=np.float32)
    wsum = np.zeros_like(out)
    n_win = int(0.040 * sr)                     # 40 ms Hann grain
    hann = np.hanning(n_win).astype(np.float32)
    i = n_win // 2
    while i < len(y) - n_win // 2:
        t = i / sr
        f = f0[min(len(f0) - 1, i // hop)]
        if f <= 0:                              # unvoiced: jaisa hai waisa
            g = y[i - n_win // 2:i + n_win // 2] * hann
            out[i - n_win // 2:i + n_win // 2] += g
            wsum[i - n_win // 2:i + n_win // 2] += hann
            i += n_win // 2
            continue
        period = sr / f
        st = float(contour(t))
        ratio = 2 ** (st / 12)
        new_period = period / ratio             # sur upar = chhota period
        g = y[i - n_win // 2:i + n_win // 2] * hann
        out[i - n_win // 2:i + n_win // 2] += g
        wsum[i - n_win // 2:i + n_win // 2] += hann
        i += max(20, int(round(new_period)))
    nz = wsum > 1e-6
    out[nz] /= wsum[nz]
    return out[:len(y)]
