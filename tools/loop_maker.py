#!/usr/bin/env python3
"""loop_maker.py — jo awaaz library me nahi hai, wo KHUD banao (seamless loop).

Koi sample nahi, koi internet nahi — sirf ganit se awaz:
  room, wind, rain, fire, river, crickets, leaves, wood_steps, birds

  python tools/loop_maker.py --kind wind --sec 20 --out /tmp/wind.wav
"""
from __future__ import annotations
import argparse
import numpy as np
import soundfile as sf

SR = 22050


def _t(sec):
    return np.arange(int(SR * sec)) / SR


def _bp(x, lo, hi):
    """FFT se band-pass — saaf aur tez."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    mask = (f >= lo) & (f <= hi)
    X[~mask] = 0
    return np.fft.irfft(X, n=len(x))


def _lp(x, cut):
    return _bp(x, 5, cut)


def _norm(x, peak=0.9):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def _seamless(x, ms=450):
    """Aakhir ko shuru me crossfade karo — loop par click na ho."""
    n = int(SR * ms / 1000)
    if len(x) <= 2 * n:
        return x
    head, tail = x[:n].copy(), x[-n:].copy()
    ramp = np.linspace(0, 1, n)
    x = x[:-n].copy()
    x[:n] = head * ramp + tail * (1 - ramp)
    return x


def room(sec=12, seed=1):
    rng = np.random.default_rng(seed)
    x = _lp(rng.normal(0, 1, int(SR * sec)), 500)
    return _norm(x, 0.25)


def wind(sec=20, seed=2):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    x = rng.normal(0, 1, n)
    t = np.arange(n) / SR
    # dheere badalte gust: 2 alag LFO
    lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.07 * t) * np.sin(2 * np.pi * 0.021 * t + 1.1)
    body = _bp(x, 60, 900) * lfo
    whistle = _bp(x, 900, 2200) * (0.25 * lfo ** 2)
    return _norm(body + whistle, 0.7)


def rain(sec=20, seed=3):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    base = _bp(rng.normal(0, 1, n), 800, 7000) * 0.5
    drops = np.zeros(n)
    idx = rng.integers(0, n - 400, int(sec * 90))
    for i in idx:
        drops[i:i + 200] += rng.normal(0, 1) * np.exp(-np.arange(200) / 35)
    return _norm(base + _bp(drops, 1200, 6000), 0.8)


def fire(sec=20, seed=4):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    rumble = _lp(rng.normal(0, 1, n), 250) * 0.5
    crack = np.zeros(n)
    idx = rng.integers(0, n - 3000, int(sec * 12))
    for i in idx:
        ln = rng.integers(200, 2500)
        crack[i:i + ln] += rng.normal(0, 1) * np.exp(-np.arange(ln) / (ln / 5))
    return _norm(rumble + _bp(crack, 700, 8000), 0.75)


def river(sec=20, seed=5):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    x = _bp(rng.normal(0, 1, n), 180, 2600)
    t = np.arange(n) / SR
    mod = 0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t) + 0.08 * np.sin(2 * np.pi * 0.7 * t)
    return _norm(x * mod, 0.8)


def crickets(sec=20, seed=6):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    out = np.zeros(n)
    t0 = 0.0
    while t0 < sec - 0.2:
        f = rng.uniform(3800, 5200)
        ln = rng.uniform(0.05, 0.12)
        tt = np.arange(int(SR * ln)) / SR
        burst = np.sin(2 * np.pi * f * tt) * np.hanning(len(tt)) * rng.uniform(0.3, 0.8)
        i = int(t0 * SR)
        out[i:i + len(burst)] += burst
        t0 += rng.uniform(0.18, 0.45)
    return _norm(out, 0.55)


def leaves(sec=20, seed=7):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    x = np.zeros(n)
    for _ in range(int(sec * 3)):
        i = rng.integers(0, n - SR)
        ln = int(SR * rng.uniform(0.25, 0.8))
        env = np.hanning(ln) * rng.uniform(0.2, 0.6)
        x[i:i + ln] += _bp(rng.normal(0, 1, ln), 1800, 9000) * env
    return _norm(x, 0.6)


def wood_steps(sec=16, seed=8, bpm=95):
    """lakdi ke farsh par kadam: tak + lakdi ki goonj."""
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    out = np.zeros(n)
    step = 60.0 / bpm
    t0 = 0.3
    while t0 < sec - 0.4:
        i = int(t0 * SR)
        ln = int(SR * 0.28)
        tt = np.arange(ln) / SR
        thud = np.sin(2 * np.pi * rng.uniform(120, 180) * tt) * np.exp(-tt / 0.045)
        body = np.sin(2 * np.pi * rng.uniform(300, 520) * tt) * np.exp(-tt / 0.02) * 0.5
        click = rng.normal(0, 1, ln) * np.exp(-tt / 0.006) * 0.6
        out[i:i + ln] += thud + body + click
        t0 += step * rng.uniform(0.94, 1.06)
    return _norm(out, 0.8)


def birds(sec=18, seed=9):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    out = np.zeros(n)
    t0 = 0.5
    while t0 < sec - 0.5:
        ln = int(SR * rng.uniform(0.08, 0.25))
        tt = np.arange(ln) / SR
        f0 = rng.uniform(2200, 4200)
        sweep = f0 * (1 + 0.25 * np.sin(2 * np.pi * rng.uniform(6, 14) * tt))
        chirp = np.sin(2 * np.pi * np.cumsum(sweep) / SR) * np.hanning(ln)
        i = int(t0 * SR)
        out[i:i + ln] += chirp * rng.uniform(0.25, 0.7)
        t0 += rng.uniform(0.5, 1.6)
    return _norm(out, 0.5)


MAKERS = {"room": room, "wind": wind, "rain": rain, "fire": fire, "river": river,
          "crickets": crickets, "leaves": leaves, "wood_steps": wood_steps, "birds": birds}


def make(kind: str, sec: float = 20.0, seed: int = 1, seamless: bool = True) -> np.ndarray:
    fn = MAKERS.get(kind)
    if fn is None:
        raise KeyError("aisa loop nahi banta: %s (hai: %s)" % (kind, ", ".join(MAKERS)))
    x = fn(sec=sec, seed=seed).astype(np.float32)
    return _seamless(x) if seamless else x


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--sec", type=float, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    x = make(a.kind, a.sec, a.seed)
    sf.write(a.out, x, SR)
    print("%s -> %s (%.1fs, peak %.2f)" % (a.kind, a.out, len(x) / SR, float(np.max(np.abs(x)))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
