#!/usr/bin/env python3
"""space.py — jagah ki asliyyat: doori, disha aur goonj (गूंज).

Asli duniya ke niyam (naap se):
  1. Doori se awaaz **dheemi** (1/d), **dhundhli** (hawa upar ki frequency kha jaati hai),
     aur **der se** pahunchti hai (d / 343 m/s).
  2. Doori badhne par **goonj ka hissa** badhta hai (direct-to-reverb ratio girti hai).
  3. Goonj jagah par nirbhar: khula maidan (0.5s) < kamra (0.5s) < jungle (1.1s) < hall (2.4s).
  4. Disha: equal-power pan; door awaaz thodi chaudi (dhundhli) hoti hai.

  python tools/space.py --test        # naap ke saath saabit karo
"""
from __future__ import annotations
import argparse
import numpy as np

SR = 44100
C_AIR = 343.0

# jagah -> (RT60 sec, shuru ki deri ms, goonj ka rang (brightness), diffusion)
SPACES = {
    "khula":   {"rt": 0.45, "pre_ms": 8,  "bright": 0.55, "diff": 0.25},
    "kamra":   {"rt": 0.55, "pre_ms": 12, "bright": 0.45, "diff": 0.45},
    "jungle":  {"rt": 1.10, "pre_ms": 18, "bright": 0.35, "diff": 0.75},
    "hall":    {"rt": 2.40, "pre_ms": 28, "bright": 0.40, "diff": 0.70},
    "gufa":    {"rt": 2.80, "pre_ms": 22, "bright": 0.25, "diff": 0.85},
}


def _lp(x, fc, sr=SR, order=2):
    """Zero-phase low-pass (FFT) — tez aur saaf."""
    if fc >= sr / 2 * 0.95:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    H = 1.0 / np.sqrt(1.0 + (f / max(fc, 20.0)) ** (2 * order))
    return np.fft.irfft(X * H, n=len(x))


def air_cutoff(dist: float) -> float:
    """Doori se upar ki frequency girna (hawa ka absorption) — 1 m par ~18 kHz, 30 m par ~3 kHz."""
    return 18000.0 / (1.0 + max(0.0, dist - 1.0) / 3.2)


def _ir(space: str, seed=7, sr=SR):
    """Jagah ki goonj (impulse response): decaying noise, stereo, pre-delay ke saath."""
    p = SPACES.get(space, SPACES["kamra"])
    n = int(p["rt"] * sr)
    rng = np.random.default_rng(seed)
    pre = int(p["pre_ms"] / 1000 * sr)
    t = np.arange(n) / sr
    env = np.exp(-6.9 * t / p["rt"])                 # -60 dB par khatam
    ir = []
    for ch in range(2):
        noise = rng.normal(0, 1, n)
        noise = _lp(noise, 800 + 6000 * p["bright"], sr)   # goonj ka rang
        h = noise * env * p["diff"]
        h = np.concatenate([np.zeros(pre), h])
        h[pre] += 1.0                                       # seedha (direct) hissa
        ir.append(h / (np.max(np.abs(h)) + 1e-9))
    return ir


def place_acoustic(x: np.ndarray, dist: float = 1.0, pan: float = 0.0,
                   space: str = "khula", sr: int = SR) -> np.ndarray:
    """Mono awaaz -> stereo, asli doori/disha/goonj ke saath."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=0)
    d = max(0.4, float(dist))

    # 1) hawa: door = dhundhli
    y = _lp(x, air_cutoff(d), sr)

    # 2) deri: awaaz ko pahunchne me waqt lagta hai
    delay = int(d / C_AIR * sr)
    if delay > 0:
        y = np.concatenate([np.zeros(delay), y])

    # 3) doori se level (1/d), par 1 m par hi sabse zyada
    y = y / d

    # 4) goonj: jagah ke hisaab se; door awaaz me goonj ka hissa zyada
    ir_l, ir_r = _ir(space, sr=sr)
    wet_gain = float(np.clip(0.10 + 0.22 * np.log1p(d), 0.08, 0.85)) / np.sqrt(d)  # door par goonj hawi na ho
    wet_l = np.convolve(y, ir_l)[: len(y)] * wet_gain
    wet_r = np.convolve(y, ir_r)[: len(y)] * wet_gain

    # 5) disha: equal-power pan (+ door awaaz thodi chaudi)
    p = float(np.clip(pan, -1.0, 1.0))
    ang = (p + 1) * np.pi / 4
    gl, gr = np.cos(ang), np.sin(ang)
    width = float(np.clip(0.02 + 0.03 * d, 0.02, 0.12))
    l = y * gl + wet_l * gl          # goonj bhi usi disha se aati hai
    r = y * gr + wet_r * gr
    l += width * wet_r * 0.3
    r += width * wet_l * 0.3
    st = np.vstack([l, r])
    peak = float(np.max(np.abs(st))) or 1.0
    if peak > 0.98:
        st = st / peak * 0.98
    return st


# ---------------- naap (saabit karne ke liye) ----------------
def measure(st: np.ndarray, sr: int = SR) -> dict:
    m = st.mean(axis=0) if st.ndim > 1 else st
    rms = float(np.sqrt((m ** 2).mean()) + 1e-12)
    X = np.abs(np.fft.rfft(m)) + 1e-12
    f = np.fft.rfftfreq(len(m), 1 / sr)
    hf = float(X[(f > 4000) & (f < 12000)].sum())
    lf = float(X[(f > 100) & (f < 1000)].sum())
    # RT60 ka andaza: energy decay curve
    e = np.cumsum((m[::-1] ** 2))[::-1]
    e_db = 10 * np.log10(e / (e[0] + 1e-12) + 1e-12)
    try:
        i5 = int(np.argmax(e_db <= -5))
        i25 = int(np.argmax(e_db <= -25))
        rt = float((i25 - i5) / sr * 2)
    except Exception:
        rt = 0.0
    if st.ndim > 1:
        side = float(np.sqrt(((st[0] - st[1]) ** 2).mean()))
        pan = float((np.sqrt((st[1] ** 2).mean()) - np.sqrt((st[0] ** 2).mean())) /
                    (np.sqrt((st[1] ** 2).mean()) + np.sqrt((st[0] ** 2).mean()) + 1e-12))
    else:
        side, pan = 0.0, 0.0
    return {"level_db": round(20 * np.log10(rms), 1), "hf_lf": round(hf / lf, 4),
            "rt60_s": round(rt, 2), "pan": round(pan, 2), "side": round(side, 4)}


def _test():
    sr = SR
    t = np.arange(int(1.2 * sr)) / sr
    burst = np.random.default_rng(3).normal(0, 1, len(t)) * np.exp(-t / 0.05)
    print("doori ka asar (khula maidan):")
    for d in (1, 5, 15, 40):
        st = place_acoustic(burst, dist=d, space="khula", sr=sr)
        m = measure(st, sr)
        print(f"  d={d:>2} m | level {m['level_db']:>6} dB | HF/LF {m['hf_lf']:.4f} | RT60 {m['rt60_s']}s")
    print("jagah ka asar (d=8 m):")
    for s in SPACES:
        st = place_acoustic(burst, dist=8, space=s, sr=sr)
        m = measure(st, sr)
        print(f"  {s:<7} | RT60 {m['rt60_s']}s | HF/LF {m['hf_lf']:.4f} | side {m['side']}")
    print("disha (d=5 m):")
    for p in (-1.0, -0.5, 0.0, 0.5, 1.0):
        m = measure(place_acoustic(burst, dist=5, pan=p, space="jungle", sr=sr), sr)
        print(f"  pan {p:+.1f} -> naapa pan {m['pan']:+.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    _test()
