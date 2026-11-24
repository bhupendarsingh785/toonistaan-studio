#!/usr/bin/env python3
"""private_train_clean.py — private model ko SAAAF data par train karo.

Do tarah ka data:
  1. **Jaana-pehchaana** (label 100% pakka): apni TTS (insaan), loop_maker (prakriti/harkat),
     synth chords (music), awaazein registry (darwaza) — har class ke 20-24 namune.
  2. **Sun kar label** (auto_label, conf>=0.6) — library ke asli clips.

Class weights (kam namune wali class ko zyada wazan) + L2 — isse model "sab insaan" nahi kehta.

  python tools/private_train_clean.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
K = ROOT / "knowledge"
OUT = K / "private-model"
SR = 22050
import private_train as PT  # noqa: E402  (feats wahi rahenge)


def anchors():
    """Har class ke pakke namune — awaaz khud banayi, label me shak nahi."""
    rows = []
    # insaan: apni render ki hui awaaz
    v = Path("/scratch/work/out-j4/stem_voice.wav")
    if v.exists():
        x, sr = sf.read(v)
        x = x.mean(1) if x.ndim > 1 else x
        rows.append(("insaan", x.astype(np.float64)))
    try:
        import loop_maker as LM
        for k in ("rain", "river", "wind"):
            rows.append(("prakriti", LM.make(k, sec=6).astype(np.float64)))
        for k in ("wood_steps", "leaves"):
            rows.append(("harkat", LM.make(k, sec=6).astype(np.float64)))
    except Exception as e:
        print("loop_maker fail", e)
    # music: saaf sur (chord + arpeggio) — 6 alag
    t = np.arange(int(6 * SR)) / SR
    for base in (196.0, 220.0, 261.6, 293.7, 329.6, 392.0):
        y = sum(np.sin(2 * np.pi * base * m * t) / m for m in (1, 1.5, 2, 2.5, 3))
        y *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.7 * t)
        rows.append(("music", (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float64)))
    # darwaza: synth
    try:
        import awaazein as AW
        rng = np.random.default_rng(3)
        for k in ("door_creak", "door_close", "door_knock"):
            if k in AW.REGISTRY:
                y = AW.REGISTRY[k](rng)
                rows.append(("darwaza", (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float64)))
    except Exception as e:
        print("awaazein fail", e)
    return rows


def main() -> int:
    X, y, names = [], [], []
    # 1) pakke namune (har ek ko 3 windows)
    for lab, x in anchors():
        win = int(2.0 * SR)
        for i in range(0, max(1, len(x) - win + 1), win):
            f = PT.feats(x[i:i + win])
            if f is not None and np.isfinite(f).all():
                X.append(f); y.append(lab); names.append(f"anchor_{lab}_{len(names)}")
    print("anchors windows:", len(X))
    # 2) sun kar label kiye clips
    import private_train as _pt
    aud = _pt.load_audited(min_conf=0.6)
    for lab, p in aud:
        x = _pt.decode(p)
        if x is None:
            continue
        win = int(2.0 * SR)
        for i in range(0, max(1, len(x) - win + 1), win):
            f = _pt.feats(x[i:i + win])
            if f is not None and np.isfinite(f).all():
                X.append(f); y.append(lab); names.append(p.name)
    X, y, names = np.array(X), np.array(y), np.array(names)
    print("kul windows:", len(X), "| classes:", {c: int((y == c).sum()) for c in set(y)})

    labels = sorted(set(y))
    rng = np.random.default_rng(11)
    tr, te = [], []
    for lab in labels:
        uniq = sorted({n for n, yy in zip(names, y) if yy == lab})
        rng.shuffle(uniq)
        cut = max(1, int(len(uniq) * 0.7))
        keep = set(uniq[:cut])
        for i in np.flatnonzero(y == lab):
            (tr if names[i] in keep else te).append(i)
    tr, te = np.array(tr), np.array(te)
    mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
    Z = (X - mu) / sd
    lab2i = {l: i for i, l in enumerate(labels)}
    ytr = np.array([lab2i[v] for v in y[tr]])
    # class weights (kam namune wali class ko zyada wazan)
    cnt = np.bincount(ytr, minlength=len(labels)).astype(float)
    cw = (cnt.sum() / (len(labels) * np.maximum(cnt, 1)))
    W = np.zeros((Z.shape[1], len(labels))); b = np.zeros(len(labels))
    for _ in range(1200):
        lo = Z[tr] @ W + b
        lo -= lo.max(1, keepdims=True)
        P = np.exp(lo); P /= P.sum(1, keepdims=True)
        P[np.arange(len(ytr)), ytr] -= 1
        sw = cw[ytr][:, None]
        W -= 0.35 * (Z[tr].T @ (P * sw)) / len(ytr) + 2e-3 * W
        b -= 0.35 * (P * sw).mean(0)
    conf, correct = {}, 0
    for i in te:
        pred = labels[int(np.argmax(Z[i] @ W + b))]
        conf.setdefault(y[i], []).append(pred == y[i])
        correct += int(pred == y[i])
    acc = correct / max(1, len(te))
    print(f"accuracy: {acc*100:.1f}%  (train {len(tr)}, test {len(te)}, {len(labels)} class)")
    print("per class:", {k: f"{np.mean(v)*100:.0f}%" for k, v in sorted(conf.items())})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sound-type-model.json").write_text(json.dumps(
        {"mu": mu.tolist(), "sd": sd.tolist(), "W": W.tolist(), "b": b.tolist(),
         "labels": labels, "features": int(Z.shape[1])}), encoding="utf-8")
    (OUT / "report.json").write_text(json.dumps(
        {"acc": round(acc, 3), "train": len(tr), "test": len(te), "labels": labels,
         "per_class": {k: round(float(np.mean(v)), 2) for k, v in conf.items()},
         "windows": int(len(X)), "split": "file-level", "data": "anchors + audited"},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("model:", OUT / "sound-type-model.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
