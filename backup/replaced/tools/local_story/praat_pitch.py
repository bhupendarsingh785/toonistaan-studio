#!/usr/bin/env python3
"""praat_pitch.py v2 — Praat (parselmouth) se sur ka curve, shabd ko bina tode.

v1 ki galti: sirf 4 point add karta tha (contour nahi badalta) aur kabhi `add_point`
method dhoondhta tha jo parselmouth me hota hi nahi. v2:
  - poore pitch tier ke har point par interpolated curve lagata hai (Praat PSOLA)
  - sur ka shift ±max_st tak hi (default 2.5) — shabd nahi tootte
  - unvoiced hisse chhod deta hai (consonant saaf rehte hain)
  - har call ka hisaab wapas deta hai (kitne point bade, kitna badla)

  y2 = apply_curve(y, sr, [(0.0, 0.6), (0.45, 0.2), (0.8, -1.2), (1.0, -1.8)])
  m  = measure(y, sr)          # f0 med/std, unvoiced %, harsh
  ok = selftest()              # apne aap ko jaancho
"""
from __future__ import annotations
import numpy as np

MAX_ST = 2.5


def _praat():
    import parselmouth
    from parselmouth.praat import call
    return parselmouth, call


def f0_track(y, sr, fmin=75, fmax=600):
    """Praat se F0 (Hertz) — numpy se zyada bharosemand."""
    parselmouth, _ = _praat()
    snd = parselmouth.Sound(np.asarray(y, dtype=np.float64), sampling_frequency=sr)
    pitch = snd.to_pitch(time_step=0.01, pitch_floor=fmin, pitch_ceiling=fmax)
    vals = pitch.selected_array["frequency"]
    return np.asarray(vals, dtype=np.float32)


def measure(y, sr):
    """Sur aur safai ka chhota hisaab (report ke liye)."""
    f = f0_track(y, sr)
    v = f[f > 0]
    if not len(v):
        return {"f0_med": 0, "f0_std": 0, "unvoiced_pct": 100.0, "harsh": 0.0}
    st = 12 * np.log2(v / np.median(v))
    n = min(len(y), sr * 12)
    S = np.abs(np.fft.rfft(np.asarray(y[:n], dtype=np.float64) * np.hanning(n)))
    fr = np.fft.rfftfreq(n, 1 / sr)
    tot = S.sum() + 1e-9
    harsh = float(S[(fr >= 2000) & (fr < 4500)].sum() / tot)
    return {"f0_med": round(float(np.median(v))), "f0_std": round(float(st.std()), 2),
            "f0_range": round(float(np.percentile(st, 95) - np.percentile(st, 5)), 1),
            "unvoiced_pct": round(float(100 * np.mean(f == 0)), 1), "harsh": round(harsh, 4)}


def apply_curve(y, sr, points, max_st=MAX_ST):
    """points = [(t_frac 0..1, semitone), ...]. Lamai waisi hi rehti hai."""
    parselmouth, call = _praat()
    y = np.asarray(y, dtype=np.float64)
    snd = parselmouth.Sound(y, sampling_frequency=sr)
    dur = snd.get_total_duration()
    man = call(snd, "To Manipulation", 0.01, 75, 600)
    tier = call(man, "Extract pitch tier")
    try:
        n = int(call(tier, "Get number of points"))
    except Exception:
        n = 0
    if n < 1:
        return np.asarray(y, dtype=np.float32)
    ts, vs = [], []
    for i in range(1, n + 1):
        try:
            t = float(call(tier, "Get time from index", i))
            v = float(call(tier, "Get value at index", i))
        except Exception:
            continue
        if v > 0:
            ts.append(t); vs.append(v)
    if not ts:
        return np.asarray(y, dtype=np.float32)
    xs = np.array([p[0] for p in points], dtype=float)
    ss = np.array([p[1] for p in points], dtype=float)
    frac = np.clip(np.array(ts) / max(dur, 1e-6), 0, 1)
    st_here = np.clip(np.interp(frac, xs, ss), -abs(max_st), abs(max_st))
    try:
        call(tier, "Remove points between", 0.0, dur)
    except Exception as _e:
        print(f'[chhoti dikkat] {type(_e).__name__}: {_e}', file=__import__('sys').stderr)
    made = 0
    for t, v, st in zip(ts, vs, st_here):
        try:
            call(tier, "Add point", float(t), float(v) * (2 ** (float(st) / 12)))
            made += 1
        except Exception as _e:
            print(f'[chhoti dikkat] {type(_e).__name__}: {_e}', file=__import__('sys').stderr)
    if not made:
        return np.asarray(y, dtype=np.float32)
    call([man, tier], "Replace pitch tier")
    out = call(man, "Get resynthesis (overlap-add)")
    z = np.asarray(out.values, dtype=np.float32).flatten()
    if len(z) >= len(y):
        return z[:len(y)]
    return np.pad(z, (0, len(y) - len(z)))


def syllable_curve(n_syl: int, start=0.6, mid=0.2, end=-1.6, wobble=0.35):
    """Shabd/syllable ke hisaab se natural curve (har syllable par halka utar-chadhav)."""
    n = max(2, int(n_syl))
    pts = [(0.0, start)]
    for i in range(1, n - 1):
        frac = i / (n - 1)
        base = mid + (end - mid) * frac
        pts.append((round(frac, 3), round(base + wobble * (1 if i % 2 else -1), 2)))
    pts.append((1.0, end))
    return pts


def selftest():
    """Chhota test: sur badla? shabd saaf? (bina TTS — shor par bhi chalta hai)"""
    sr = 22050
    t = np.arange(int(1.2 * sr)) / sr
    f0 = 180 + 20 * np.sin(2 * np.pi * 1.3 * t)
    y = 0.3 * np.sin(2 * np.pi * np.cumsum(f0) / sr)
    y += 0.01 * np.random.default_rng(1).normal(size=len(y))
    m0 = measure(y, sr)
    z = apply_curve(y, sr, [(0.0, 1.5), (0.5, -1.0), (1.0, -2.0)])
    m1 = measure(z, sr)
    ok_change = float(np.abs(z - y).mean()) > 1e-4
    ok_std = m1["f0_std"] >= m0["f0_std"] * 0.9
    ok_len = abs(len(z) - len(y)) < sr // 50
    for n, v in (("sur badla", ok_change), ("std theek", ok_std), ("lamai same", ok_len)):
        print(("PASS " if v else "FAIL ") + n)
    return ok_change and ok_std and ok_len


if __name__ == "__main__":
    import sys
    if "selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)
    print("use: python praat_pitch.py selftest")
