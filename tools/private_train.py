#!/usr/bin/env python3
"""private_train.py — apne PRIVATE system ko poori library par train karo.

Data: knowledge/audio-content-index.json (har clip ka content tag, 2000+ clips)
Kaam: har clip ka "chehra" (mel-band + sur + flatness + dhang) -> softmax model
      (kis tarah ki awaaz hai: janwar, paani, kadam, music, darwaze, horror...)
Split: FILE ke hisaab se (ek clip ke windows dono taraf nahi)
Bachav: kuch bhi bahar nahi jaata — model sirf knowledge/private-model/ me rehta hai

  python tools/private_train.py --clips 300
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
try:
    import astra_paths as _AP
except ImportError:
    import sys as _s, pathlib as _pl
    _s.path.insert(0, str(_pl.Path(__file__).resolve().parent)); import astra_paths as _AP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
K = ROOT / "knowledge"
INP = _AP.INPUT
EXTRA = (_AP.WORK / "library_extra")
OUT = K / "private-model"
SR = 22050

# tag -> kaam ka naam (mote group — chhote group par accuracy jhoothi lagti hai)
CLASSES = {
    "animals": "janwar", "water": "prakriti", "ambience/drone": "prakriti",
    "footsteps": "harkat", "wood": "harkat", "foley/impact": "harkat",
    "music": "music", "music/tonal": "music",
    "door": "darwaza", "horror": "darwaza",
    "speech/voice": "insaan", "voice": "insaan",
}


def load_audited(min_conf=0.6):
    """Sun kar lagaye gaye label (auto_label.py) — naam par bharosa nahi."""
    p = K / "labels-audited.jsonl"
    if not p.exists():
        return []
    rows, seen = [], set()
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if not r.get("label") or r.get("conf", 0) < min_conf or r["file"] in seen:
            continue
        f = INP / r["file"]
        if not f.exists():
            f2 = EXTRA / r["file"]
            if not f2.exists():
                continue
            f = f2
        seen.add(r["file"])
        rows.append((r["label"], f))
    return rows


def load_clips(max_clips=300, per_tag=60):
    idx = json.loads((K / "audio-content-index.json").read_text(encoding="utf-8")).get("tags", {})
    picked = {}
    for tag, label in CLASSES.items():
        for rec in idx.get(tag, []):
            f = INP / rec["file"]
            if not f.exists():
                f2 = EXTRA / rec["file"]
                if f2.exists():
                    f = f2
                else:
                    continue
            if rec.get("sec", 0) < 1.5:
                continue
            picked.setdefault(label, [])
            if len(picked[label]) < per_tag and f not in picked[label]:
                picked[label].append(f)
    # round-robin: har class ko barabar mauka (warna pehli class hi sab le jaati hai)
    rows, i = [], 0
    while len(rows) < max_clips:
        added = False
        for lab, fs in picked.items():
            if i < len(fs) and len(rows) < max_clips:
                rows.append((lab, fs[i])); added = True
        if not added:
            break
        i += 1
    return rows, {lab: len(fs) for lab, fs in picked.items()}


def decode(path: Path, sec=6.0):
    import ffbin
    ff = ffbin.ensure() or "ffmpeg"
    raw = subprocess.run([ff, "-v", "quiet", "-t", str(sec), "-i", str(path),
                          "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    if len(raw) < SR // 2:
        return None
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return x / (np.max(np.abs(x)) + 1e-9)


def feats(x):
    n = 1024
    if len(x) < n * 2:
        return None
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::512]
    X = np.abs(np.fft.rfft(fr * np.hanning(n), axis=1)) + 1e-10
    f = np.fft.rfftfreq(n, 1 / SR)
    edges = np.geomspace(50, min(10000, SR / 2 - 200), 21)
    mel = []
    for i in range(20):
        m = (f >= edges[i]) & (f < edges[i + 1])
        mel.append(np.log(X[:, m].sum(1) + 1e-9) if m.any() else np.zeros(len(X)))
    M = np.stack(mel, 1)
    d = np.abs(np.diff(M, axis=0)).mean(0) if len(M) > 2 else np.zeros(M.shape[1])
    e = np.sqrt((fr ** 2).mean(1))
    spec = X.mean(0)
    flat = float(np.exp(np.log(spec + 1e-12).mean()) / (spec.mean() + 1e-12))
    cent = float((spec * f).sum() / (spec.sum() + 1e-12))
    # sur
    seg = x[:min(len(x), SR)]
    ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
    lo, hi = int(SR / 500), min(int(SR / 70), len(ac) - 1)
    f0 = SR / (np.argmax(ac[lo:hi]) + lo + 1e-9) if hi > lo else 0.0
    onset = float((np.diff(e) > 0.08 * (np.max(e) + 1e-9)).mean())
    return np.concatenate([M.mean(0), M.std(0), d, np.abs(M).mean(0)[:6],
                           [np.log(f0 + 1e-6), np.log(cent + 1e-6), flat, onset,
                            float(np.percentile(e, 90) / (np.percentile(e, 20) + 1e-9))]]).astype(np.float32)


def train(X, y, names, seed=7):
    rng = np.random.default_rng(seed)
    labels = sorted(set(y))
    tr, te = [], []
    for lab in labels:
        uniq = sorted({n for n, yy in zip(names, y) if yy == lab})
        rng.shuffle(uniq)
        cut = max(1, int(len(uniq) * 0.7))
        keep = set(uniq[:cut])
        for i in np.flatnonzero(y == lab):
            (tr if names[i] in keep else te).append(i)
    tr, te = np.array(tr), np.array(te)
    if len(tr) < 10 or len(te) < 5:
        return None
    mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
    Z = (X - mu) / sd
    lab2i = {l: i for i, l in enumerate(labels)}
    ytr = np.array([lab2i[v] for v in y[tr]])
    W = np.zeros((Z.shape[1], len(labels))); b = np.zeros(len(labels))
    for _ in range(800):
        lo = Z[tr] @ W + b
        lo -= lo.max(1, keepdims=True)
        P = np.exp(lo); P /= P.sum(1, keepdims=True)
        P[np.arange(len(ytr)), ytr] -= 1
        W -= 0.4 * (Z[tr].T @ P) / len(ytr) + 1e-4 * W
        b -= 0.4 * P.mean(0)
    conf, correct = {}, 0
    for i in te:
        pred = labels[int(np.argmax(Z[i] @ W + b))]
        conf.setdefault(y[i], []).append(pred == y[i])
        correct += int(pred == y[i])
    return {"acc": correct / max(1, len(te)), "labels": labels, "train": len(tr), "test": len(te),
            "per_class": {k: float(np.mean(v)) for k, v in conf.items()},
            "model": {"mu": mu.tolist(), "sd": sd.tolist(), "W": W.tolist(), "b": b.tolist(),
                      "labels": labels, "features": int(Z.shape[1])}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", type=int, default=300)
    ap.add_argument("--offset", type=int, default=0, help="batch me chalane ke liye")
    ap.add_argument("--train-only", action="store_true", help="cache se sirf train karo")
    ap.add_argument("--audited", action="store_true", help="sun kar lagaye gaye label se train")
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / "features.npz"
    if a.audited:
        rows = load_audited()
        per_label = {}
        for lab, _ in rows:
            per_label[lab] = per_label.get(lab, 0) + 1
        cache = OUT / "features-audited.npz"
    else:
        rows, per_label = load_clips(a.clips + a.offset)
        rows = rows[a.offset:]
    if a.train_only:
        rows = []
    print("clips:", len(rows), "| per class:", per_label)
    X, y, names, secs = [], [], [], 0.0
    for lab, p in rows:
        x = decode(p)
        if x is None:
            continue
        secs += len(x) / SR
        win = int(2.0 * SR)
        for i in range(0, max(1, len(x) - win + 1), win):
            f = feats(x[i:i + win])
            if f is not None and np.isfinite(f).all():
                X.append(f); y.append(lab); names.append(p.name)
    X, y, names = np.array(X), np.array(y), np.array(names)
    # cache me jodo (batch-batch me chalane ke liye)
    if len(X):
        if cache.exists():
            d = np.load(cache, allow_pickle=True)
            X = np.vstack([d["X"], X]); y = np.concatenate([d["y"], y]); names = np.concatenate([d["names"], names])
        np.savez_compressed(cache, X=X, y=y, names=names)
    elif cache.exists():
        d = np.load(cache, allow_pickle=True)
        X, y, names = d["X"], d["y"], d["names"]
    # purane cache ke label naye group me badlo
    REMAP = {"paani": "prakriti", "mahaul": "prakriti", "kadam": "harkat", "lakdi": "harkat", "chot": "harkat"}
    if len(y):
        y = np.array([REMAP.get(str(v), str(v)) for v in y])
    print("cache windows:", len(X))
    print(f"windows: {len(X)} | audio: {secs/60:.1f} min | features: {X.shape[1] if len(X) else 0}")
    res = train(X, y, names)
    if res is None:
        print("data kam — model nahi bana")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sound-type-model.json").write_text(json.dumps(res["model"]), encoding="utf-8")
    (OUT / "report.json").write_text(json.dumps(
        {"acc": round(res["acc"], 3), "train": res["train"], "test": res["test"],
         "labels": res["labels"], "per_class": {k: round(v, 2) for k, v in res["per_class"].items()},
         "clips": len(rows), "windows": int(len(X)), "audio_minutes": round(secs / 60, 1),
         "seconds_taken": round(time.time() - t0, 1), "split": "file-level"}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"accuracy: {res['acc']*100:.1f}%  (train {res['train']}, test {res['test']}, {len(res['labels'])} class)")
    print("per class:", {k: f"{v*100:.0f}%" for k, v in sorted(res["per_class"].items())})
    print("model:", OUT / "sound-type-model.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
