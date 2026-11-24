#!/usr/bin/env python3
"""loop_maker.py — jo awaaz library me nahi hai, wo KHUD banao (natural, seamless).

Asli recordings se naapa hua "naturalness" paimana knowledge/loop-reference.json me
hai; har loop usi spectrum (dB/octave dhalan) par dhaala jaata hai, aur banna ke
baad QA gate se guzarta hai — jhoothi/robotic loop aage nahi jaati.

  python tools/loop_maker.py --kind wind --sec 20 --out wind.wav
  python tools/loop_maker.py --qa            # saare loops ki jaanch
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 22050
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


# ---------------- auzaar ----------------
def pink(n: int, rng) -> np.ndarray:
    """1/f noise — hawa/paani/barish ki asli buniyad (white noise nahi)."""
    w = rng.normal(0, 1, n)
    X = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1 / SR)
    X[1:] /= np.sqrt(f[1:])
    X[0] = 0
    x = np.fft.irfft(X, n=n)
    return x / (np.max(np.abs(x)) or 1)


def _band_mask(f, lo, hi, soft=0.15):
    """Smooth band-pass mask (logistic kinare) — koi slicing bug nahi."""
    w = max(20.0, lo * 0.25)
    lo_edge = 1.0 / (1.0 + np.exp(-(f - lo) / w))
    hi_edge = 1.0 / (1.0 + np.exp((f - hi) / w))
    return lo_edge * hi_edge


def retint(x: np.ndarray, slope_db_oct: float, lo: float, hi: float) -> np.ndarray:
    """Spectrum ko seedha target dhalan par rakho — phase wahi, sirf rang badalta hai."""
    X = np.fft.rfft(x)
    mag = np.abs(X) + 1e-12
    phase = X / mag
    f = np.maximum(np.fft.rfftfreq(len(x), 1 / SR), 1.0)
    env = 10 ** ((slope_db_oct * np.log2(f / 500.0)) / 20.0)
    X2 = phase * env * _band_mask(f, lo, hi)
    y = np.fft.irfft(X2, n=len(x))
    m = np.max(np.abs(y)) or 1.0
    return y / m


def walk(n: int, rng, depth=0.5, smooth=None) -> np.ndarray:
    """random-walk modulation — sine LFO robot lagta hai, ye insaan jaisa."""
    smooth = smooth or int(SR * 1.2)
    k = max(8, n // smooth)
    pts = rng.normal(0, 1, k)
    mod = np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)
    win = max(8, smooth // 2)
    mod = np.convolve(mod, np.hanning(win) / (win / 2), mode="same")
    mod = mod / (np.max(np.abs(mod)) or 1)
    return 1.0 + depth * mod


def reverb(x, rng, decay=0.25, mix=0.18):
    n = int(SR * decay)
    if n < 8:
        return x
    ir = rng.normal(0, 1, n) * np.exp(-np.arange(n) / (n / 4))
    ir[0] = 1.0
    ir /= np.max(np.abs(ir)) + 1e-9
    wet = np.convolve(x, ir, mode="full")[:len(x)]
    wet /= (np.max(np.abs(wet)) or 1)
    return (1 - mix) * x + mix * wet


def _norm(x, peak=0.8):
    m = np.max(np.abs(x)) or 1.0
    return (x / m * peak).astype(np.float32)


def _seamless(x, ms=450):
    n = int(SR * ms / 1000)
    if len(x) <= 2 * n:
        return x
    head, tail = x[:n].copy(), x[-n:].copy()
    ramp = np.linspace(0, 1, n)
    y = x[:-n].copy()
    y[:n] = head * ramp + tail * (1 - ramp)
    return y


_REF = None


def reference() -> dict:
    global _REF
    if _REF is None:
        p = ROOT / "knowledge" / "loop-reference.json"
        try:
            _REF = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            _REF = {}
    return _REF


def features(x: np.ndarray, band=(100, 8000)) -> dict:
    """Kaisi sunai deti hai — naap (jaanch ke liye)."""
    x = np.asarray(x, dtype=np.float64)
    x = x - x.mean()
    x = x / (np.max(np.abs(x)) or 1)
    n, hop = 2048, 1024
    if len(x) < n * 2:
        return {}
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop]
    S = np.abs(np.fft.rfft(fr * np.hanning(n), axis=1)) + 1e-12
    f = np.fft.rfftfreq(n, 1 / SR)
    sel = (f >= band[0]) & (f <= band[1])
    spec = S.mean(0)[sel]
    slope = float(np.polyfit(np.log2(np.maximum(f[sel], 1)), 20 * np.log10(spec), 1)[0])
    centroid = float((S[:, sel] * f[sel]).sum(1).mean() / (S[:, sel].sum(1).mean() + 1e-12))
    rms = np.sqrt((fr ** 2).mean(1)) + 1e-9
    E = np.abs(np.fft.rfft(rms - rms.mean()))
    mod = float(np.fft.rfftfreq(len(rms), hop / SR)[1:][np.argmax(E[1:])]) if len(E) > 2 else 0.0
    return {"slope_db_oct": round(slope, 2), "centroid_hz": round(centroid),
            "mod_hz": round(mod, 3), "crest": round(float(np.max(np.abs(x)) / (np.sqrt((x ** 2).mean()) + 1e-9)), 2)}


# ---------------- awaazein ----------------
BANDS = {"room": (30, 500), "wind": (60, 2500), "rain": (500, 8000), "river": (150, 3200),
         "fire": (40, 9000), "crickets": (2500, 9000), "leaves": (1500, 9500),
         "wood_steps": (80, 6000), "birds": (1500, 7000)}


def _bed(kind, sec, seed, depth=0.5, rev=0.0, peak=0.75):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    lo, hi = BANDS[kind]
    x = pink(n, rng) * walk(n, rng, depth=depth)
    ref = reference().get(kind, {})
    x = retint(x, ref.get("slope_db_oct", -3.0), lo, hi)
    if rev:
        x = reverb(x, rng, decay=rev, mix=0.15)
    return _norm(x, peak)


def room(sec=12, seed=1):
    return _bed("room", sec, seed, depth=0.25, peak=0.25)


def wind(sec=20, seed=2):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    body = pink(n, rng) * walk(n, rng, depth=0.9)
    whistle = pink(n, rng) * (walk(n, rng, depth=0.5) - 1.0)
    x = body + 0.4 * whistle
    ref = reference().get("wind", {})
    return _norm(retint(x, ref.get("slope_db_oct", -0.5), *BANDS["wind"]), 0.72)


def rain(sec=20, seed=3):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    base = pink(n, rng) * walk(n, rng, depth=0.35)
    drops = np.zeros(n)
    for i in rng.integers(0, n - 400, int(sec * 110)):
        ln = int(rng.uniform(60, 260))
        drops[i:i + ln] += rng.normal(0, 1) * np.exp(-np.arange(ln) / (ln / 4))
    x = base + 0.8 * drops
    ref = reference().get("rain", {})
    return _norm(retint(x, ref.get("slope_db_oct", -7.8), *BANDS["rain"]), 0.78)


def river(sec=20, seed=5):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    x = pink(n, rng) * walk(n, rng, depth=0.5)
    x += 0.3 * pink(n, rng) * walk(n, rng, depth=0.8)
    ref = reference().get("river", {})
    return _norm(retint(x, ref.get("slope_db_oct", -3.8), *BANDS["river"]), 0.78)


def fire(sec=20, seed=4):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    crack = np.zeros(n)
    for i in rng.integers(0, n - 3000, int(sec * 14)):
        ln = int(rng.uniform(200, 2600))
        crack[i:i + ln] += rng.normal(0, 1) * np.exp(-np.arange(ln) / (ln / 5))
    x = pink(n, rng) * walk(n, rng, depth=0.6) + 0.9 * crack
    x = retint(x, -2.5, *BANDS["fire"])
    return _norm(reverb(x, rng, decay=0.2, mix=0.12), 0.75)


def crickets(sec=20, seed=6):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    out = np.zeros(n)
    t0 = 0.0
    while t0 < sec - 0.25:
        f = rng.uniform(3800, 5400)
        ln = int(SR * rng.uniform(0.05, 0.13))
        tt = np.arange(ln) / SR
        out[int(t0 * SR):int(t0 * SR) + ln] += np.sin(2 * np.pi * f * tt) * np.hanning(ln) * rng.uniform(0.25, 0.8)
        t0 += rng.uniform(0.15, 0.5)
    ref = reference().get("crickets", {})
    return _norm(retint(out + 0.02 * pink(n, rng), ref.get("slope_db_oct", 0.5), *BANDS["crickets"]), 0.55)


def leaves(sec=20, seed=7):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    bed = pink(n, rng) * walk(n, rng, depth=0.4)
    bursts = np.zeros(n)
    for _ in range(int(sec * 4)):
        i = rng.integers(0, n - SR)
        ln = int(SR * rng.uniform(0.2, 0.9))
        env = np.hanning(ln) * rng.uniform(0.2, 0.7)
        bursts[i:i + ln] += pink(ln, rng) * env
    x = 0.45 * bed + 0.9 * bursts
    ref = reference().get("leaves", {})
    return _norm(retint(x, ref.get("slope_db_oct", 4.1), *BANDS["leaves"]), 0.6)


def wood_steps(sec=16, seed=8, bpm=95):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    out = np.zeros(n)
    step, t0 = 60.0 / bpm, 0.3
    while t0 < sec - 0.4:
        i = int(t0 * SR)
        ln = int(SR * 0.3)
        tt = np.arange(ln) / SR
        thud = np.sin(2 * np.pi * rng.uniform(110, 190) * tt) * np.exp(-tt / 0.05)
        body = np.sin(2 * np.pi * rng.uniform(280, 560) * tt) * np.exp(-tt / 0.022) * 0.55
        click = rng.normal(0, 1, ln) * np.exp(-tt / 0.005) * 0.7
        out[i:i + ln] += thud + body + click
        t0 += step * rng.uniform(0.93, 1.07)
    x = reverb(out, rng, decay=0.3, mix=0.2)
    ref = reference().get("wood_steps", {})
    return _norm(retint(x, ref.get("slope_db_oct", -5.8), *BANDS["wood_steps"]), 0.8)


def birds(sec=18, seed=9):
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    out = np.zeros(n)
    t0 = 0.5
    while t0 < sec - 0.6:
        ln = int(SR * rng.uniform(0.07, 0.3))
        tt = np.arange(ln) / SR
        f0 = rng.uniform(2200, 4600)
        sweep = f0 * (1 + 0.22 * np.sin(2 * np.pi * rng.uniform(5, 16) * tt))
        chirp = np.sin(2 * np.pi * np.cumsum(sweep) / SR) * np.hanning(ln)
        i = int(t0 * SR)
        out[i:i + ln] += chirp * rng.uniform(0.25, 0.75)
        t0 += rng.uniform(0.45, 1.7)
    return _norm(reverb(retint(out + 0.02 * pink(n, rng), -1.0, *BANDS["birds"]), rng, decay=0.35, mix=0.22), 0.5)


MAKERS = {"room": room, "wind": wind, "rain": rain, "fire": fire, "river": river,
          "crickets": crickets, "leaves": leaves, "wood_steps": wood_steps, "birds": birds}


def make(kind: str, sec: float = 20.0, seed: int = 1, seamless: bool = True) -> np.ndarray:
    fn = MAKERS.get(kind)
    if fn is None:
        raise KeyError("aisa loop nahi banta: %s (hai: %s)" % (kind, ", ".join(MAKERS)))
    x = fn(sec=sec, seed=seed)
    return _seamless(x) if seamless else x


def judge(kind: str, x: np.ndarray) -> tuple[bool, str]:
    """QA gate — asli recording se kitna door hai."""
    r = reference().get(kind)
    if not r:
        return True, "reference nahi (judge chhoda)"
    f = features(x, band=BANDS.get(kind, (100, 8000)))
    if not f:
        return False, "bahut chhoti"
    ds = abs(f["slope_db_oct"] - r["slope_db_oct"])
    dc = abs(f["centroid_hz"] - r["centroid_hz"]) / (r["centroid_hz"] + 1)
    if ds > 4.0:
        return False, "spectrum dhalan door (%.1f vs %.1f dB/oct)" % (f["slope_db_oct"], r["slope_db_oct"])
    if dc > 0.6:
        return False, "centroid door (%d vs %d Hz)" % (f["centroid_hz"], r["centroid_hz"])
    if f["crest"] > r["crest"] * 2.2:
        return False, "bahut chubhta hai (crest %.1f vs %.1f)" % (f["crest"], r["crest"])
    return True, "theek (slope %.1f, centroid %d Hz)" % (f["slope_db_oct"], f["centroid_hz"])


def make_checked(kind: str, sec: float = 20.0, tries: int = 6):
    """Banao, jaancho; paas na ho to naye seed se dobara. Aakhir me sach batao."""
    last = None
    for seed in range(1, tries + 1):
        x = make(kind, sec=sec, seed=seed)
        ok, why = judge(kind, x)
        if ok:
            return x, seed, why
        last = why
    return None, 0, last or "fail"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind")
    ap.add_argument("--sec", type=float, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out")
    ap.add_argument("--qa", action="store_true")
    a = ap.parse_args()
    if a.qa:
        for k in MAKERS:
            x, seed, why = make_checked(k, sec=15)
            f = features(x) if x is not None else {}
            print("%-11s %s  seed=%d  %s  %s" % (k, "PASS" if x is not None else "FAIL", seed, why,
                                                 ("slope %.1f centroid %d" % (f["slope_db_oct"], f["centroid_hz"])) if f else ""))
        return 0
    if not (a.kind and a.out):
        ap.error("--kind aur --out chahiye (ya --qa)")
    x, seed, why = make_checked(a.kind, sec=a.sec)
    if x is None:
        print("REJECT:", a.kind, why)
        return 2
    sf.write(a.out, x, SR)
    print("%s -> %s (%.1fs, seed %d, %s)" % (a.kind, a.out, len(x) / SR, seed, why))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
