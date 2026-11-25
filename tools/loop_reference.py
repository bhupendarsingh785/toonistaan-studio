#!/usr/bin/env python3
"""loop_reference.py — asli recordings se naap le, ki "natural" kaisa hota hai.

Har kind ke liye: spectral slope, centroid, modulation rate, crest factor.
Yehi naap synthetic loop ko jaanchne ka paimana banega.

  python tools/loop_reference.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
try:
    import astra_paths as _AP
except ImportError:
    import sys as _s, pathlib as _pl
    _s.path.insert(0, str(_pl.Path(__file__).resolve().parent)); import astra_paths as _AP

SR = 22050
try:
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parent))
    from loop_maker import BANDS
except Exception:
    BANDS = {}

KIND_FILES = {
    "rain": ["echogatestudios-soft-sounds-of-rain", "celeronbeats-cozy-bedroom-rain", "mixkit-rain-and-thunder"],
    "river": ["gugunxyz-flowing-water", "loswin23-flowing-river"],
    "wind": ["pwlpl-mountain-wind", "mightuser-sound-of-howling-wind", "storegraphic-soft-wind"],
    "wood_steps": ["footsteps-on-wooden-flooring", "walking-on-a-wooden-floor", "creaking-wooden-floor-footsteps"],
    "crickets": ["crickets-at-night", "jungle-crickets-noise"],
    "leaves": ["leaves-rustl", "grass-rustling"],
}


def features(x: np.ndarray, band=(100, 8000)) -> dict:
    x = x - x.mean()
    if np.max(np.abs(x)) > 0:
        x = x / np.max(np.abs(x))
    n = 2048
    hop = 1024
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop]
    S = np.abs(np.fft.rfft(frames * np.hanning(n), axis=1)) + 1e-10
    f = np.fft.rfftfreq(n, 1 / SR)
    # spectral slope (dB per octave) — usi band me jisme awaaz rehti hai
    sel = (f >= band[0]) & (f <= band[1])
    mean_spec = S.mean(0)[sel]
    lf = np.log2(np.maximum(f[sel], 1))
    slope = float(np.polyfit(lf, 20 * np.log10(mean_spec), 1)[0])
    centroid = float((S[:, sel] * f[sel]).sum(1).mean() / (S[:, sel].sum(1).mean() + 1e-12))
    rms = np.sqrt((frames ** 2).mean(1)) + 1e-9
    env = rms - rms.mean()
    E = np.abs(np.fft.rfft(env))
    fr = np.fft.rfftfreq(len(env), hop / SR)
    mod_peak = float(fr[1:][np.argmax(E[1:])]) if len(E) > 2 else 0.0
    crest = float(np.max(np.abs(x)) / (np.sqrt((x ** 2).mean()) + 1e-9))
    return {"slope_db_oct": round(slope, 2), "centroid_hz": round(centroid, 0),
            "mod_hz": round(mod_peak, 3), "crest": round(crest, 2),
            "rms": round(float(np.sqrt((x ** 2).mean())), 4)}


def main() -> int:
    inp = _AP.INPUT
    out = {}
    for kind, pats in KIND_FILES.items():
        vals = []
        for p in sorted(inp.glob("*")):
            if p.suffix.lower() not in (".mp3", ".wav", ".ogg", ".webm"):
                continue
            if not any(t in p.name.lower() for t in pats):
                continue
            try:
                x, sr = sf.read(str(p), frames=SR * 20, dtype="float32", always_2d=False)
            except Exception:
                continue
            if x is None or len(x) < SR * 3:
                continue
            if x.ndim > 1:
                x = x.mean(axis=1)
            if sr != SR:
                idx = np.linspace(0, len(x) - 1, int(len(x) * SR / sr)).astype(np.int64)
                x = x[idx]
            vals.append(features(x, band=BANDS.get(kind, (100, 8000))))
            if len(vals) >= 4:
                break
        if vals:
            out[kind] = {k: round(float(np.median([v[k] for v in vals])), 3) for k in vals[0]}
            out[kind]["n"] = len(vals)
    Path("knowledge/loop-reference.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k, v in out.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
