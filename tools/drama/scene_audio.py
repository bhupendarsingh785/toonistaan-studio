#!/usr/bin/env python3
"""scene_audio.py — layer 5: duniya ki layers (base + close + far + movement)."""
from __future__ import annotations
import subprocess
from pathlib import Path
import numpy as np

SR = 22050
SCENES = {
    "nadi_kinare": {"base": [("river", 0.60)], "close": [("crickets", 0.18)], "far": [("birds", 0.10)], "movement": [("leaves", 0.10)]},
    "jungle_raat": {"base": [("jungle", 0.55), ("river", 0.20)], "close": [("crickets", 0.22)], "far": [("wind", 0.12)], "movement": [("leaves", 0.12)]},
    "ghar":        {"base": [("room", 0.25)], "close": [], "far": [("wind", 0.08)], "movement": [("wood", 0.08)]},
}
PATS = {
    "river": ["gugunxyz-flowing-water", "loswin23-flowing-river"],
    "crickets": ["crickets", "jheengur"],
    "birds": ["birds-chirping", "bird-chirps", "forest-birds"],
    "jungle": ["jungle-in-maharashtra", "jungle-nature", "night-forest-soundscape"],
    "wind": ["soft-wind", "mountain-wind", "howling-wind"],
    "leaves": ["leaves-rustl", "dry-grass-rustl", "grass-rustling"],
    "room": ["room-tone", "room-ambience"],
    "wood": ["wood", "wooden"],
}
LIB = Path("/scratch/input")


def _ff():
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()


def find(kind, k=3):
    pats = PATS.get(kind, [kind])
    out = []
    for p in LIB.glob("*"):
        if p.suffix.lower() not in (".mp3", ".wav", ".ogg", ".ogx"): continue
        n = p.name.lower()
        if any(x in n for t in pats for x in (t,)) and p.stat().st_size > 40_000:
            out.append(p)
    return out[:k]


def load(p, t=25):
    raw = subprocess.run([_ff(), "-v", "quiet", "-t", str(t), "-i", str(p), "-f", "f32le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def loop_to(x, n):
    if len(x) >= n: return x[:n]
    y = np.tile(x, int(np.ceil(n / len(x))))[:n]
    f = min(int(len(x) * 0.2), n // 4)
    if f > 100:
        r = np.linspace(0, 1, f)
        for k in range(1, int(np.ceil(n / len(x)))):
            i = k * len(x)
            if i - f >= 0 and i + f <= len(y):
                y[i - f:i] = y[i - f:i] * (1 - r) + y[i - f:i] * r
    return y


def build(scene: str, n: int, rng=None):
    """Layer-wise bed banao. Har layer ka apna level + pan."""
    lay = SCENES.get(scene, SCENES["nadi_kinare"])
    L = np.zeros(n, dtype=np.float32); R = np.zeros(n, dtype=np.float32)
    used = []
    pans = {"base": 0.0, "close": 0.35, "far": -0.45, "movement": 0.2}
    for layer, items in lay.items():
        for kind, w in items:
            cands = find(kind)
            if not cands: continue
            p = cands[0]
            x = load(p)
            if len(x) < SR: continue
            x = loop_to(x, n)
            x = x / (np.max(np.abs(x)) + 1e-9) * w
            pan = pans.get(layer, 0.0)
            gl, gr = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
            L += x * gl; R += x * gr
            used.append({"layer": layer, "kind": kind, "file": p.name[:44], "pan": pan, "w": w})
    return L, R, used
