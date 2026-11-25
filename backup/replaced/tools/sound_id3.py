#!/usr/bin/env python3
"""Sound ID v3 — MFCC + spectral contrast + chroma + F0 contour (category pehchan).

v2 (54%) me sirf MFCC+band tha. v3 me contrast/chroma/F0 contour jodte hain,
aur train/test alag rakhte hain (honest accuracy).

CLI:
  python tools/sound_id3.py --train --catalog c.json --model m3.json [--per-class 140] [--n 30]
  python tools/sound_id3.py --test  --catalog c.json --model m3.json
"""
from __future__ import annotations
import argparse, json, random, subprocess, sys
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


_FB = None
def _fb():
    global _FB
    import numpy as np
    if _FB is not None:
        return _FB
    def hz2mel(f): return 2595 * np.log10(1 + f / 700)
    def mel2hz(m): return 700 * (10 ** (m / 2595) - 1)
    pts = mel2hz(np.linspace(hz2mel(50), hz2mel(SR / 2), NMEL + 2))
    bins = np.floor((NFFT + 1) * pts / SR).astype(int)
    fb = np.zeros((NMEL, NFFT // 2 + 1))
    for i in range(NMEL):
        a, b, c = bins[i], bins[i + 1], bins[i + 2]
        for k in range(a, min(b, fb.shape[1])):
            fb[i, k] = (k - a) / max(1, b - a)
        for k in range(b, min(c, fb.shape[1])):
            fb[i, k] = (c - k) / max(1, c - b)
    _FB = fb
    return fb


def features(x) -> list[float] | None:
    import numpy as np
    if len(x) < SR // 4:
        return None
    x = x - x.mean()
    n = len(x)
    frames = [x[i:i + NFFT] * np.hanning(NFFT) for i in range(0, max(1, n - NFFT), HOP)]
    if len(frames) < 3:
        return None
    S = np.abs(np.fft.rfft(np.array(frames), axis=1)) + 1e-9
    logmel = np.log(S @ _fb().T)
    k = np.arange(NMFCC)[:, None]; m = np.arange(NMEL)[None, :]
    dct = np.cos(np.pi * k * (2 * m + 1) / (2 * NMEL)) * np.sqrt(2 / NMEL)
    mfcc = logmel @ dct.T
    f = np.fft.rfftfreq(NFFT, 1 / SR)
    # spectral contrast (7 bands): peak-valley dB
    edges = np.geomspace(80, SR / 2 - 200, 8)
    contrast = []
    for i in range(7):
        msk = (f >= edges[i]) & (f < edges[i + 1])
        if not msk.any():
            contrast.append(0.0); continue
        band = S[:, msk]
        contrast.append(float(np.mean(np.log10(band.max(1) + 1e-9) - np.log10(band.min(1) + 1e-9))))
    # chroma (12) — 55 Hz ke upar
    mask = (f >= 55) & (f <= 2000)
    pc = np.round(12 * np.log2(f[mask] / 261.63)).astype(int) % 12
    ch = np.zeros(12)
    for i, p in enumerate(pc):
        ch[p] += float(S[:, mask][:, i].mean())
    ch = ch / (ch.sum() + 1e-9)
    # F0 contour stats (CMNDF, coarse)
    f0s = []
    for i in range(0, n - 2048, 2048):
        s = x[i:i + 2048]
        if float(np.sqrt((s ** 2).mean())) < 0.006:
            continue
        mlen = len(s); d = np.zeros(mlen // 2)
        for tau in range(1, mlen // 2):
            diff = s[:mlen - tau] - s[tau:]
            d[tau] = float(np.dot(diff, diff))
        cm = np.ones_like(d); run = 0.0
        for tau in range(1, len(d)):
            run += d[tau]; cm[tau] = d[tau] * tau / (run + 1e-12)
        lo, hi = int(SR / 450), min(int(SR / 60), len(cm) - 1)
        if hi <= lo + 1:
            continue
        kk = lo + int(np.argmin(cm[lo:hi]))
        if cm[kk] < 0.5:
            f0s.append(SR / kk)
    if f0s:
        f0 = np.array(f0s); f0_stats = [float(np.log10(np.median(f0) + 1)),
                                        float(np.log10(np.std(f0) + 1)),
                                        float(len(f0) / max(1, n / 2048))]
    else:
        f0_stats = [0.0, 0.0, 0.0]
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
    sil = float((e < e.max() * 0.05).mean() * 100)
    return [round(float(v), 4) for v in
            list(mfcc.mean(0)) + list(mfcc.std(0)) + contrast + list(ch) + f0_stats +
            [am, attack / 100, zcr / 10, sil / 10]]


def knn(Xtr, ytr, v, k=5):
    import numpy as np
    d = np.sqrt(((Xtr - v) ** 2).sum(1))
    nn = np.argsort(d)[:min(k, len(d))]
    votes = {}
    for j in nn:
        votes[ytr[j]] = votes.get(ytr[j], 0) + 1
    best = max(votes.items(), key=lambda kv: kv[1])
    return best[0], round(best[1] / len(nn), 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true"); ap.add_argument("--test", action="store_true")
    ap.add_argument("--catalog", required=True); ap.add_argument("--model", required=True)
    ap.add_argument("--base", default="/scratch/input")
    ap.add_argument("--per-class", type=int, default=140); ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args()
    cat = json.loads(Path(a.catalog).read_text(encoding="utf-8"))
    if a.train:
        random.seed(21)
        held = set(r["file"] for r in random.sample(cat["items"], min(a.n, len(cat["items"]))))
        by = {}
        for r in cat["items"]:
            if r["file"] in held:
                continue
            by.setdefault(r["cat"], []).append(r["file"])
        import numpy as np
        X, y = [], []
        for c, files in by.items():
            for fn in files[:a.per_class]:
                p = Path(a.base) / fn
                if not p.exists():
                    continue
                f = features(load(str(p)))
                if f:
                    X.append(f); y.append(c)
        X = np.array(X); mu, sd = X.mean(0), X.std(0) + 1e-6
        model = {"classes": sorted(set(y)), "mu": mu.tolist(), "sd": sd.tolist(),
                 "X": ((X - mu) / sd).round(3).tolist(), "y": y, "n": len(y)}
        Path(a.model).write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
        Path(a.model + ".heldout.json").write_text(json.dumps(sorted(held)), encoding="utf-8")
        print(json.dumps({"trained": len(y), "classes": model["classes"]}, ensure_ascii=False))
    if a.test:
        import numpy as np
        model = json.loads(Path(a.model).read_text(encoding="utf-8"))
        held = json.loads(Path(a.model + ".heldout.json").read_text(encoding="utf-8"))
        truth = {r["file"]: r["cat"] for r in cat["items"]}
        Xtr = np.array(model["X"]); ytr = np.array(model["y"])
        mu = np.array(model["mu"]); sd = np.array(model["sd"])
        ok = 0; rows = []
        for fn in held:
            f = features(load(str(Path(a.base) / fn)))
            if not f:
                continue
            g, conf = knn(Xtr, ytr, (np.array(f) - mu) / sd)
            hit = (g == truth[fn]); ok += hit
            rows.append((fn[:34], truth[fn], g, conf))
        for r in rows:
            print(f"  {'✅' if r[1]==r[2] else '❌'} {r[0]:36s} asli={r[1]:10s} bola={r[2]:10s} conf={r[3]}")
        print(f"\naccuracy: {ok}/{len(rows)} = {round(100*ok/max(1,len(rows)))}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
