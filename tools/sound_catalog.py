#!/usr/bin/env python3
"""Sound Catalog — Swag ke bheje hue saare background sounds ko padho aur suchi banao.

Har file ka: category, duration, zor, centroid, band balance, loop-able, quality score.
Isse pipeline ko pata chalta hai: kis kaam ke liye kaunsi file best hai.

CLI: python tools/sound_catalog.py --dir /scratch/input --out catalog.json [--limit N] [--only cat1,cat2]
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path
try:
    import astra_paths as _AP
except ImportError:
    import sys as _s, pathlib as _pl
    _s.path.insert(0, str(_pl.Path(__file__).resolve().parent)); import astra_paths as _AP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR = 8000
AUD = (".mp3", ".wav", ".ogg", ".ogx", ".oga", ".webm", ".m4a")

CATS = [
 ("footsteps", ["step", "foot", "walk", "pasos", "gravel", "grass", "leaf", "leaves", "stairs", "boots", "shoe", "puddle"]),
 ("insects", ["cricket", "insect", "cicada", "mosquito", "bee", "fly", "frog", "toad", "kikker", "pad", "bug"]),
 ("creatures", ["wolf", "lion", "tiger", "dog", "cat", "horse", "elephant", "monkey", "bear", "snake", "python",
                "boar", "camel", "rhino", "zebra", "kangaroo", "dingo", "wombat", "panda", "chimp", "roar", "growl", "howl"]),
 ("birds", ["bird", "chirp", "myna", "warbler", "whipbird", "dove", "hawk", "tern", "gannet", "cockatoo", "galah", "crow"]),
 ("water", ["river", "water", "stream", "flow", "splash", "waterfall", "pour", "boil", "bubble", "rain"]),
 ("rain", ["rain", "thunder", "storm", "lightning"]),
 ("wind", ["wind", "blizzard", "howling", "gust"]),
 ("human", ["man", "woman", "baby", "cry", "laugh", "breath", "scream", "voice", "kiss", "cough", "sigh"]),
 ("horror", ["horror", "scary", "ghost", "monster", "vampire", "eerie", "creepy", "haunted", "spooky"]),
 ("music", ["music", "beat", "loop", "song", "instrumental", "bpm", "melody", "dhol", "tabla", "trailer", "riser", "drone"]),
 ("doors", ["door", "gate", "lock", "knock", "creak", "drawer", "window", "closet"]),
 ("city", ["city", "traffic", "crowd", "station", "train", "car", "horn", "market", "metro", "ambience"]),
 ("foley", ["paper", "coin", "glass", "kitchen", "office", "typing", "coin", "clink", "click", "snap"]),
]


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def feats(p: Path, seconds: float = 2.0) -> dict | None:
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-t", str(seconds), "-i", str(p),
                        "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.float32).copy()
    if len(x) < SR // 4:
        return None
    n = len(x)
    S = np.abs(np.fft.rfft(x * np.hanning(n))); f = np.fft.rfftfreq(n, 1 / SR); tot = S.sum() + 1e-9
    rms = float(np.sqrt((x ** 2).mean()))
    # loop-able: shuru-aakhir ka level farq kam ho
    head = float(np.sqrt((x[:SR // 4] ** 2).mean())); tail = float(np.sqrt((x[-SR // 4:] ** 2).mean()))
    loop = abs(head - tail) / max(1e-6, max(head, tail))
    return {"dur_s": round(n / SR, 2), "rms_dbfs": round(20 * float(np.log10(max(1e-9, rms))), 1),
            "centroid_hz": round(float((S * f).sum() / tot)),
            "low_pct": round(100 * float(S[f < 300].sum() / tot)),
            "mid_pct": round(100 * float(S[(f >= 300) & (f < 3000)].sum() / tot)),
            "high_pct": round(100 * float(S[f >= 3000].sum() / tot)),
            "loopable": round(1 - min(1.0, loop), 2)}


def cat_of(name: str) -> str:
    n = name.lower()
    for c, keys in CATS:
        if any(k in n for k in keys):
            return c
    return "other"


def quality(f: dict) -> float:
    """0–1: zor theek, silence nahi, clip nahi, band balance."""
    q = 1.0
    if f["rms_dbfs"] < -40: q -= 0.4
    if f["rms_dbfs"] > -6: q -= 0.2
    if f["high_pct"] < 3: q -= 0.1
    if f["dur_s"] < 0.4: q -= 0.2
    return round(max(0.0, min(1.0, q)), 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(_AP.INPUT))
    ap.add_argument("--out", default="catalog.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--cache", default="")
    a = ap.parse_args()
    d = Path(a.dir)
    cache = Path(a.cache) if a.cache else None
    done = {}
    if cache and cache.exists():
        done = json.loads(cache.read_text(encoding="utf-8"))
    only = set(a.only.split(",")) if a.only else None
    files = [p for p in sorted(d.iterdir()) if p.is_file() and p.suffix.lower() in AUD]
    if only:
        files = [p for p in files if cat_of(p.name) in only]
    if a.limit:
        files = files[:a.limit]
    out = []
    for i, p in enumerate(files):
        key = p.name
        if key in done:
            out.append(done[key]); continue
        f = feats(p)
        if not f:
            continue
        c = cat_of(p.name)
        rec = {"file": p.name, "cat": c, **f, "quality": quality(f)}
        done[key] = rec
        out.append(rec)
        if cache and i % 50 == 0:
            cache.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    if cache:
        cache.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    summary = Counter(r["cat"] for r in out)
    Path(a.out).write_text(json.dumps({"count": len(out), "by_cat": dict(summary), "items": out},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"count": len(out), "by_cat": dict(summary)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
