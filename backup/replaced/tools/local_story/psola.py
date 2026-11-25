#!/usr/bin/env python3
"""psola.py — TD-PSOLA (sahi tareeka): sur badlo, awaaz ka rang waisa hi rahe.

Pehla version galat tha: grain padhne aur likhne ki jagah ek hi thi (isliye F0 hila hi nahi).
Ab do cursor hain: `rd` (source, asli period se) aur `wr` (output, naye period se).

  y2 = shift(y, sr, contour)     # contour(t_sec) -> semitone
"""
from __future__ import annotations
import numpy as np


def f0_track(y, sr, hop=160, win=640, fmin=70, fmax=450):
    out = np.zeros(max(1, (len(y) - win) // hop + 1), dtype=np.float32)
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
    for i in range(1, len(out) - 1):        # chhote gaps bharo
        if out[i] == 0 and out[i - 1] > 0 and out[i + 1] > 0:
            out[i] = (out[i - 1] + out[i + 1]) / 2
    return out


def shift(y, sr, contour, win_s=0.040):
    """TD-PSOLA. contour(t) -> semitone. Lamai waisi hi rehti hai."""
    y = np.asarray(y, dtype=np.float32)
    f0 = f0_track(y, sr)
    hop = 160
    nw = int(win_s * sr)
    hann = np.hanning(nw).astype(np.float32)
    out = np.zeros(len(y) + sr, dtype=np.float32)
    wsum = np.zeros_like(out)
    rd = 0
    wr = 0
    while rd < len(y) - nw and wr < len(out) - nw:
        t = rd / sr
        f = float(f0[min(len(f0) - 1, rd // hop)])
        if f <= 0:                                   # unvoiced: seedha copy
            g = y[rd:rd + nw]
            out[wr:wr + len(g)] += g
            wsum[wr:wr + len(g)] += 1.0
            rd += nw // 2
            wr += nw // 2
            continue
        period = sr / f
        st = float(contour(t))
        new_period = period / (2 ** (st / 12))       # sur upar = chhota period
        src = int(rd - nw // 2)
        if src >= 0 and src + nw < len(y):
            g = y[src:src + nw] * hann
            dst = int(wr - nw // 2)
            if dst >= 0:
                out[dst:dst + nw] += g
                wsum[dst:dst + nw] += hann
        rd += max(20, int(round(period)))            # source: asli period
        wr += max(20, int(round(new_period)))        # output: naya period
    nz = wsum > 1e-6
    out[nz] /= wsum[nz]
    return out[:len(y)]
