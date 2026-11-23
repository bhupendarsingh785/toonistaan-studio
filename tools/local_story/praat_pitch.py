#!/usr/bin/env python3
"""praat_pitch.py — Praat (parselmouth) se sur ka curve lagao.

PSOLA ka sahi implementation (Praat ka Manipulation) — grain alignment,
phase continuity aur duration sab sambhalta hai. Shift chhota rakho (±3 st).
"""
from __future__ import annotations
import numpy as np


def apply_curve(y, sr, points, max_st=3.0):
    """points = [(t_frac, semitone), ...] — 0..1 ke beech. Duration waisi hi rehti hai."""
    import parselmouth
    from parselmouth.praat import call
    y = np.asarray(y, dtype=np.float64)
    snd = parselmouth.Sound(y, sampling_frequency=sr)
    try:
        man = call(snd, "To Manipulation", 0.01, 75, 600)
        tier = call(man, "Extract pitch tier")
    except Exception:
        return y.astype(np.float32)
    dur = snd.get_total_duration()
    # poore contour ko badlo (sirf 4 point add karne se sur nahi ghoomta — naap se mila)
    try:
        npts = int(call(tier, "Get number of points"))
    except Exception:
        npts = 0
    if npts == 0:
        return y.astype(np.float32)
    ts, vs = [], []
    for i in range(1, npts + 1):
        try:
            t = float(call(tier, "Get time from index", i))
            v = float(call(tier, "Get value at index", i))
        except Exception:
            continue
        if v > 0:
            ts.append(t); vs.append(v)
    if not ts:
        return y.astype(np.float32)
    xs = np.array([f for f, _ in points]); ss = np.array([s for _, s in points])
    fracs = np.clip(np.array(ts) / max(dur, 1e-6), 0, 1)
    st_here = np.interp(fracs, xs, ss)
    st_here = np.clip(st_here, -max_st, max_st)
    try:
        call(tier, "Remove points between", 0, dur)
    except Exception:
        pass
    for t, v, st in zip(ts, vs, st_here):
        try:
            call(tier, "Add point", float(t), float(v) * (2 ** (float(st) / 12)))   # parselmouth me add_point nahi hota
        except Exception:
            pass
    try:
        call([man, tier], "Replace pitch tier")
        out = call(man, "Get resynthesis (overlap-add)")
        z = np.asarray(out.values, dtype=np.float32).flatten()
        return z[:len(y)] if len(z) >= len(y) else np.pad(z, (0, len(y) - len(z)))
    except Exception:
        return y.astype(np.float32)
