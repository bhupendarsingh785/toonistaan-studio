"""Compatibility sound module for ASTRA's older audio-studio imports.

This keeps the existing `import sfx` call sites working without adding a
third-party dependency or requiring a paid API. Audio is generated locally.
"""
from __future__ import annotations

import os
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASTRA_DIR = ROOT / "astra"
if str(ASTRA_DIR) not in sys.path:
    sys.path.insert(0, str(ASTRA_DIR))

SR = 44100


def t(seconds: float) -> np.ndarray:
    n = max(0, int(SR * max(0.0, float(seconds))))
    return np.arange(n, dtype=np.float32) / SR


def noise(seconds: float) -> np.ndarray:
    n = max(0, int(SR * max(0.0, float(seconds))))
    return np.random.default_rng().normal(0.0, 1.0, n).astype(np.float32)


def lowpass(samples: np.ndarray, cutoff: float = 1200.0) -> np.ndarray:
    x = np.asarray(samples, dtype=np.float32)
    if not len(x):
        return x.copy()
    cutoff = max(20.0, min(float(cutoff), SR * 0.45))
    width = max(1, int(SR / cutoff))
    if width % 2 == 0:
        width += 1
    kernel = np.ones(width, dtype=np.float32) / width
    return np.convolve(x, kernel, mode="same").astype(np.float32)


def wind(seconds: float = 5.0) -> np.ndarray:
    x = lowpass(noise(seconds), 650.0)
    tt = t(seconds)
    if len(x) != len(tt):
        x = x[:len(tt)]
    modulation = 0.55 + 0.45 * np.sin(2 * np.pi * 0.12 * tt)
    return (x * modulation * 0.35).astype(np.float32)


def music(mood: str = "calm", seconds: float = 10.0) -> np.ndarray:
    """Generate original local music and return mono float32 samples at 44.1 kHz."""
    import music_engine

    aliases = {
        "calm": "meditation", "happy": "adventure", "sad": "emotional",
        "romantic": "romance", "scary": "horror", "thriller": "suspense",
    }
    selected = aliases.get(str(mood or "calm").strip().lower(), str(mood or "calm").strip().lower())
    if selected not in music_engine.PROFILES:
        selected = "meditation"
    requested = max(0.5, float(seconds))
    generated_seconds = min(180.0, max(8.0, requested))
    path, _meta = music_engine.generate_music(selected, generated_seconds)
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        raw = raw.reshape(-1, channels).mean(axis=1)
    if rate != SR and len(raw):
        new_len = max(1, int(round(len(raw) * SR / rate)))
        raw = np.interp(np.linspace(0, len(raw) - 1, new_len), np.arange(len(raw)), raw).astype(np.float32)
    target = int(SR * requested)
    if len(raw) < target and len(raw):
        raw = np.tile(raw, int(np.ceil(target / len(raw))))
    return raw[:target].astype(np.float32, copy=False)
