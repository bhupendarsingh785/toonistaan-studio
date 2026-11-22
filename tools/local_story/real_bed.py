#!/usr/bin/env python3
"""Real Bed — asli recordings se background (synthetic nahi).

Swag ke diye 2000+ files me se shabd ke hisaab se file chunta hai (river/rain/birds/
crickets/wind/footsteps), loop karta hai, stereo banata hai, aur awaaz ke neeche duck karta hai.
Naap: gap me bed kitna sunai deta hai (target: awaaz se ~15 dB neeche, par 0 nahi).
"""
from __future__ import annotations
import subprocess, wave
from pathlib import Path
import numpy as np

LIB = Path("/scratch/input")
CACHE = Path("/scratch/work/bedcache")

# shabd -> file me dhoondhne wale patterns (pehla match jeetta hai)
PATTERNS = {
    "river":   ["flowing-river", "river", "nadi", "stream", "water-flow", "gugunxyz-flowing"],
    "rain":    ["gentle-rain", "rain-", "rain", "barish", "rainfall"],
    "birds":   ["birds-chirping", "bird-chirp", "birds-in-the-forest", "chirping"],
    "crickets": ["crickets", "jheengur", "night-cricket"],
    "wind":    ["soft-wind", "wind", "hawa"],
    "leaves":  ["leaves-rustl", "rustle", "grass-rustl"],
    "steps":   ["footsteps-dirt", "footsteps-on-gravel", "soil-steps", "footsteps"],
    "jungle":  ["jungle-nature", "jungle-in-maharashtra", "night-forest-soundscape", "forest-sounds"],
    "wolf":    ["wolf-howling", "wolf-crying-howl", "lone-wolf-cries", "wolf"],
}


BLACKLIST = ("train", "window", "dragon", "brain", "terrain", "constrain", "drain", "sprain",
             "whistle", "horn", "engine", "station")


def find(kind: str, k: int = 3) -> list[Path]:
    """Sirf saaf match: 'rain' me 'train'/'window' nahi ginay jaate."""
    import re
    pats = PATTERNS.get(kind, [kind])
    out = []
    files = list(LIB.glob("*.mp3")) + list(LIB.glob("*.wav"))
    for p in files:
        name = p.name.lower()
        if any(b in name for b in BLACKLIST):
            continue
        ok = False
        for pt in pats:
            if re.search(rf"(^|[-_ ]){re.escape(pt)}", name):
                ok = True; break
        if ok and p.stat().st_size > 40_000:
            out.append(p)
    out.sort(key=lambda p: p.stat().st_size)      # chhoti files pehle (tez load)
    return out[:k]


def _ff():
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def load_mono(path: Path, sr: int, max_s: float = 18.0):
    FF = _ff()
    raw = subprocess.run([FF, "-v", "quiet", "-t", str(max_s), "-i", str(path),
                          "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).copy()
    if len(x) < sr:
        return None
    return x


def loop_to(x, n):
    if len(x) >= n:
        return x[:n].copy()
    reps = int(np.ceil(n / len(x)))
    y = np.tile(x, reps)[:n]
    # seam crossfade (chup-chaap loop)
    f = min(int(len(x) * 0.15), n // 4)
    if f > 100:
        ramp = np.linspace(0, 1, f)
        for r in range(1, reps):
            i = r * len(x)
            if i - f >= 0 and i + f <= len(y):
                y[i - f:i] = y[i - f:i] * (1 - ramp) + y[i - f:i] * ramp
    return y


def band(x, sr, lo=80, hi=9000):
    n = len(x); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / sr)
    g = 1 / (1 + (lo / (f + 1e-9)) ** 4) / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * g, n)


def make_bed(kinds, n, sr, level_db=-26, seed=11):
    """kinds = [(naam, wazan)] — asli files se bed; na mile to None."""
    rng = np.random.default_rng(seed)
    bed = np.zeros(n, dtype=np.float32)
    used = []
    for kind, w in kinds:
        cands = find(kind)
        if not cands:
            continue
        p = cands[int(rng.integers(0, len(cands)))]
        x = load_mono(p, sr)
        if x is None:
            continue
        x = band(x, sr)
        x = loop_to(x, n)
        x = x / (np.max(np.abs(x)) + 1e-9) * (10 ** (level_db / 20)) * w
        bed += x.astype(np.float32)
        del x
        used.append({"kind": kind, "file": p.name, "w": w})
    if not used:
        return None, []
    return bed, used
