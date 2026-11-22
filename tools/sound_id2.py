#!/usr/bin/env python3
"""Sound ID v2 — MFCC + band energies + kNN (asli pehchan, naap ke saath).

v1 (sirf centroid/harm/am) sirf 29% sahi tha. v2 me timbre (MFCC) + 8 band + timing.
Train: catalog ki files → z-score → kNN (k=5). Test: held-out files (training me nahi).

CLI:
  python tools/sound_id2.py --train --catalog c.json --out model.json [--per-class 80]
  python tools/sound_id2.py --test  --model model.json --n 20
  python tools/sound_id2.py --id --audio x.mp3 --model model.json
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR = 16000
NFFT, HOP, NMEL, NMFCC = 512, 160, 26, 13


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def load(p: str, seconds: float = 2.0):
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-t", str(seconds), "-i", str(p),
                        "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def _mel_filterbank():
    import numpy as np
    def hz2mel(f): return 2595 * np.log10(1 + f / 700)
    def mel2hz(m): return 700 * (10 ** (m / 2595) - 1)
    lo, hi = hz2mel(50), hz2mel(SR / 2)
    pts = mel2hz(np.linspace(lo, hi, NMEL + 2))
    bins = np.floor((NFFT + 1) * pts / SR).astype(int)
    fb = np.zeros((NMEL, NFFT // 2 + 1))
    for i in range(NMEL):
        a, b, c = bins[i], bins[i + 1], bins[i + 2]
        for k in range(a, min(b, fb.shape[1])):
            fb[i, k] = (k - a) / max(1, b - a)
        for k in range(b, min(c, fb.shape[1])):
            fb[i, k] = (c - k) / max(1, c - b)
    return fb


FB = None


def features(x) -> list[float] | None:
    import numpy as np
    global FB
    if FB is None:
        FB = _mel_filterbank()
    if len(x) < SR // 4:
        return None
    x = x - x.mean()
    n = len(x)
    # STFT
    frames = [x[i:i + NFFT] * np.hanning(NFFT) for i in range(0, max(1, n - NFFT), HOP)]
    if len(frames) < 3:
        return None
    S = np.abs(np.fft.rfft(np.array(frames), axis=1))
    mel = S @ FB.T
    logmel = np.log(mel + 1e-9)
    # DCT-II → MFCC
    k = np.arange(NMFCC)[:, None]; m = np.arange(NMEL)[None, :]
    dct = np.cos(np.pi * k * (2 * m + 1) / (2 * NMEL)) * np.sqrt(2 / NMEL)
    mfcc = logmel @ dct.T
    mfcc_mean = mfcc.mean(0); mfcc_std = mfcc.std(0)
    # 8 band energies (log-spaced)
    f = np.fft.rfftfreq(NFFT, 1 / SR)
    bands = np.geomspace(60, SR / 2 - 100, 9)
    be = []
    for i in range(8):
        msk = (f >= bands[i]) & (f < bands[i + 1])
        be.append(float(np.log(S[:, msk].sum(1).mean() + 1e-9)))
    # timing
    env = np.abs(x); w = 64
    e = np.array([env[i:i + w].mean() for i in range(0, max(1, n - w), w)])
    am = 0.0
    if len(e) > 32:
        ee = e - e.mean(); F = np.abs(np.fft.rfft(ee)); fr = np.fft.rfftfreq(len(e), w / SR)
        msk = (fr >= 1) & (fr <= 20)
        if msk.any():
            am = float(fr[msk][np.argmax(F[msk])])
    peak = float(np.max(np.abs(x))) + 1e-9
    idx = np.where(np.abs(x) > 0.1 * peak)[0]
    attack = 1000 * (idx[0] / SR) if len(idx) else 0
    zcr = float(np.mean(np.abs(np.diff(np.sign(x))) > 0) * 100)
    return [round(float(v), 4) for v in list(mfcc_mean) + list(mfcc_std) + be +
            [am, attack / 100, zcr / 10]]


def train(catalog: dict, base: str, per_class: int = 80, skip: set | None = None) -> dict:
    import numpy as np
    by = {}
    for r in catalog["items"]:
        if skip and r["file"] in skip:
            continue
        by.setdefault(r["cat"], []).append(r["file"])
    X, y = [], []
    for cat, files in by.items():
        for fn in files[:per_class]:
            p = Path(base) / fn
            if not p.exists():
                continue
            f = features(load(str(p)))
            if f:
                X.append(f); y.append(cat)
    X = np.array(X, dtype=float)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    return {"classes": sorted(set(y)), "mu": mu.tolist(), "sd": sd.tolist(),
            "X": ((X - mu) / sd).round(3).tolist(), "y": y, "n": len(y)}


def knn(model: dict, f: list[float], k: int = 5) -> dict:
    import numpy as np
    mu = np.array(model["mu"]); sd = np.array(model["sd"])
    X = np.array(model["X"]); y = np.array(model["y"])
    v = (np.array(f) - mu) / sd
    d = np.sqrt(((X - v) ** 2).sum(1))
    idx = np.argsort(d)[:k]
    votes = {}
    for i in idx:
        votes[y[i]] = votes.get(y[i], 0) + 1
    best = max(votes.items(), key=lambda kv: kv[1])
    conf = round(best[1] / k, 2)
    return {"guess": best[0] if conf >= 0.4 else "pata nahi", "confidence": conf,
            "votes": votes, "nearest_dist": round(float(d[idx[0]]), 2)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true"); ap.add_argument("--test", action="store_true")
    ap.add_argument("--id", action="store_true")
    ap.add_argument("--catalog", default=""); ap.add_argument("--model", default="model.json")
    ap.add_argument("--base", default="/scratch/input"); ap.add_argument("--per-class", type=int, default=80)
    ap.add_argument("--n", type=int, default=20); ap.add_argument("--audio", default="")
    a = ap.parse_args()
    if a.train:
        cat = json.loads(Path(a.catalog).read_text(encoding="utf-8"))
        # test ke liye 20 files alag rakho
        import random
        random.seed(11)
        held = set(r["file"] for r in random.sample(cat["items"], a.n))
        model = train(cat, a.base, a.per_class, skip=held)
        Path(a.model).write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
        Path(a.model + ".heldout.json").write_text(json.dumps(sorted(held)), encoding="utf-8")
        print(json.dumps({"trained": model["n"], "classes": model["classes"]}, ensure_ascii=False))
    if a.test:
        model = json.loads(Path(a.model).read_text(encoding="utf-8"))
        cat = json.loads(Path(a.catalog).read_text(encoding="utf-8"))
        held = json.loads(Path(a.model + ".heldout.json").read_text(encoding="utf-8"))
        truth = {r["file"]: r["cat"] for r in cat["items"]}
        ok = 0; rows = []
        for fn in held:
            f = features(load(str(Path(a.base) / fn)))
            if not f:
                continue
            r = knn(model, f)
            hit = r["guess"] == truth[fn]
            ok += hit
            rows.append((fn[:34], truth[fn], r["guess"], r["confidence"]))
        for row in rows:
            print(f"  {'✅' if row[1]==row[2] else '❌'} {row[0]:36s} asli={row[1]:10s} bola={row[2]:10s} conf={row[3]}")
        print(f"\naccuracy: {ok}/{len(rows)} = {round(100*ok/max(1,len(rows)))}%")
    if a.id:
        model = json.loads(Path(a.model).read_text(encoding="utf-8"))
        f = features(load(a.audio))
        print(json.dumps(knn(model, f) if f else {"error": "audio chhota"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
