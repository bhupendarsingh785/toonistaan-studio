#!/usr/bin/env python3
"""creature_train.py — jeev-jantu/pakshi/kide ki awaaz se system ko train karo.

Kaam:
  1. Library me se har jeev ki clips chhaanto (naam se, par sakhti se — 'crowd' != 'crow')
  2. Har clip ka "chehra" (mel-band energy + sur + bolne ka dhang)
  3. Nearest-centroid classifier train + test (70/30 split) — accuracy naapo
  4. Model + taxonomy (Hindi naam) knowledge/ me save

  python tools/creature_train.py --limit 220
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
INP = Path("/scratch/input")
K = ROOT / "knowledge"
SR = 22050

TAXONOMY = {
    "wolf": {"hindi": ["भेड़िया", "भेड़िये", "बhediya"], "english": "wolf", "kind": "janwar"},
    "dog": {"hindi": ["कुत्ता", "कुत्ते", "kutta"], "english": "dog", "kind": "janwar"},
    "cat": {"hindi": ["बिल्ली", "बिल्ला"], "english": "cat", "kind": "janwar"},
    "lion": {"hindi": ["शेर", "बाघ", "sher", "bagh"], "english": "lion/tiger", "kind": "janwar"},
    "bird": {"hindi": ["चिड़िया", "पक्षी", "मैना", "कबूतर", "कौवा", "मोर"], "english": "bird", "kind": "pakshi"},
    "cricket": {"hindi": ["झींगुर", "चींटी", "कीड़ा", "मच्छर"], "english": "insect", "kind": "keeda"},
    "frog": {"hindi": ["मेंढक", "टर्र"], "english": "frog", "kind": "janwar"},
    "monkey": {"hindi": ["बंदर", "वानर"], "english": "monkey", "kind": "janwar"},
    "elephant": {"hindi": ["हाथी"], "english": "elephant", "kind": "janwar"},
    "horse": {"hindi": ["घोड़ा", "घोड़े", "टाप"], "english": "horse", "kind": "janwar"},
    "snake": {"hindi": ["सांप", "साँप", "अजगर"], "english": "snake", "kind": "janwar"},
    "boar": {"hindi": ["सूअर", "जंगली सूअर"], "english": "boar", "kind": "janwar"},
    "camel": {"hindi": ["ऊंट"], "english": "camel", "kind": "janwar"},
    "zebra": {"hindi": ["ज़ेबरा"], "english": "zebra", "kind": "janwar"},
    "rhino": {"hindi": ["गैंडा"], "english": "rhino", "kind": "janwar"},
    "panda": {"hindi": ["पांडा"], "english": "panda", "kind": "janwar"},
    "kangaroo": {"hindi": ["कंगारू"], "english": "kangaroo", "kind": "janwar"},
    "mouse_rat": {"hindi": ["चूहा", "चूहे"], "english": "mouse/rat", "kind": "janwar"},
    "wombat": {"hindi": ["वोम्बैट"], "english": "wombat", "kind": "janwar"},
    "cow_buffalo": {"hindi": ["गाय", "भैंस", "बछड़ा"], "english": "cow/buffalo", "kind": "janwar"},
}
# naam me ye shabd ho to clip kisi aur cheez ki hai
BLOCK = ["crowd", "cheer", "clap", "applause", "stadium", "booing", "riser", "loop-", "music",
         "guitar", "drum", "trailer", "logo", "cinematic", "bass", "trap", "phonk", "beat"]


def keywords():
    out = {}
    for k, v in TAXONOMY.items():
        keys = {
            "wolf": ["wolf", "howl", "dingo", "coyote"],
            "dog": ["dog", "bark", "puppy"],
            "cat": ["cat-meow", "meow", "kitten", "cat_"],
            "lion": ["lion", "tiger", "roar"],
            "bird": ["bird", "chirp", "myna", "sparrow", "warbler", "dove", "crow", "peacock", "owl",
                     "koel", "whipbird", "cockatoo", "thornbill", "robin", "tern", "hawk", "gannet",
                     "tinamou", "quail", "sunbittern", "myna"],
            "cricket": ["cricket", "cicada", "grasshopper", "insect", "mosquito", "koor"],
            "frog": ["frog", "toad", "croak", "kikker", "pad_", "boomkikker"],
            "monkey": ["monkey", "chimp", "langur"],
            "elephant": ["elephant"],
            "horse": ["horse", "neigh", "hoof", "hooves"],
            "snake": ["snake", "python", "cobra", "hiss"],
            "boar": ["boar"],
            "camel": ["camel"],
            "zebra": ["zebra"],
            "rhino": ["rhino"],
            "panda": ["panda"],
            "kangaroo": ["kangaroo"],
            "mouse_rat": ["mouse", "rat-", "rodent", "squeak"],
            "wombat": ["wombat"],
            "cow_buffalo": ["cow", "buffalo", "cattle"],
        }[k]
        out[k] = keys
    return out


def decode(path: Path, sec=2.0, sr=SR):
    import ffbin
    ff = ffbin.ensure() or "ffmpeg"
    raw = subprocess.run([ff, "-v", "quiet", "-t", str(sec), "-i", str(path),
                          "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True).stdout
    if len(raw) < sr:                      # 0.5s se chhoti
        return None
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return x / (np.max(np.abs(x)) + 1e-9)


def features_multi(x, sr=SR, win=2.0, hop=1.0):
    """Ek clip se kai 2s window — data 3-4x, aur har window ka apna chehra."""
    n = int(win * sr)
    step = int(hop * sr)
    out = []
    if len(x) < n:
        f = features(x, sr)
        return [f] if f is not None else []
    for i in range(0, len(x) - n + 1, step):
        f = features(x[i:i + n], sr)
        if f is not None and np.isfinite(f).all():
            out.append(f)
        if len(out) >= 3:
            break
    return out


def features(x, sr=SR):
    n = 1024
    if len(x) < n * 2:
        return None
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::512]
    X = np.abs(np.fft.rfft(fr * np.hanning(n), axis=1)) + 1e-10
    f = np.fft.rfftfreq(n, 1 / sr)
    edges = np.geomspace(60, min(10000, sr / 2 - 200), 25)
    mel = []
    for i in range(24):
        m = (f >= edges[i]) & (f < edges[i + 1])
        mel.append(np.log(X[:, m].sum(1) + 1e-9) if m.any() else np.zeros(len(X)))
    M = np.stack(mel, 1)                       # (frames, 24)
    e = np.sqrt((fr ** 2).mean(1))
    # sur (F0) ka andaza: autocorrelation ka shikhar
    seg = x[: min(len(x), sr)]
    ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
    lo, hi = int(sr / 8000), min(int(sr / 50), len(ac) - 1)
    f0 = sr / (np.argmax(ac[lo:hi]) + lo + 1e-9) if hi > lo else 0.0
    # bolne ka dhang: kitni jaldi-jaldi awaaz ubharti hai
    onset = float((np.diff(e) > 0.08 * (np.max(e) + 1e-9)).mean())
    d = np.diff(M, axis=0) if len(M) > 2 else np.zeros((1, M.shape[1]))
    spec = X.sum(1) + 1e-12
    flat = float(np.exp(np.log(spec + 1e-12).mean()) / (spec.mean() + 1e-12))   # flatness
    feat = np.concatenate([
        M.mean(0), M.std(0),                       # rang (48)
        np.abs(d).mean(0)[:12],                    # badalne ka dhang (12)
        [np.log(f0 + 1e-6), np.log(len(x) / sr), onset, flat,
         float(np.max(e)), float(np.percentile(e, 50))],
    ])
    return feat.astype(np.float32)


def build(limit=220):
    kw = keywords()
    extra = Path("/scratch/work/creature_extra")
    src = list(INP.glob("*")) + (list(extra.glob("*")) if extra.exists() else [])
    files = [p for p in sorted(src)
             if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".ogx", ".flac")
             and not any(b in p.name.lower() for b in BLOCK)]
    # ek clip me ek hi jeev ho (warna label hi ganda hota hai)
    def labels_in(name: str):
        low = name.lower()
        return [lab for lab, keys in kw.items() if any(k in low for k in keys)]
    rows = []
    for label, keys in kw.items():
        got = [p for p in files if any(k in p.name.lower() for k in keys) and labels_in(p.name) == [label]]
        for p in got[:max(3, limit // len(kw))]:
            rows.append((label, p))
    print(f"clips mile: {len(rows)} | jeev: {len(set(r[0] for r in rows))}")
    X, y, names = [], [], []
    for label, p in rows:
        x = decode(p, sec=6.0)
        if x is None:
            continue
        for f in features_multi(x):
            X.append(f); y.append(label); names.append(p.name)
    return np.array(X), np.array(y), names


def train(X, y, names, seed=7, min_per_class=8):
    rng = np.random.default_rng(seed)
    counts = {lab: int((y == lab).sum()) for lab in set(y)}
    keep = [lab for lab, c in counts.items() if c >= min_per_class]
    mask = np.isin(y, keep)
    X, y, names = X[mask], y[mask], [n for n, m in zip(names, mask) if m]
    labels = sorted(set(y))
    # split FILE ke hisaab se (ek hi clip ke windows dono taraf na jaayein — warna accuracy jhoothi)
    names = np.array(names)
    tr_idx, te_idx = [], []
    for lab in labels:
        files = sorted({n for n, yy in zip(names, y) if yy == lab})
        rng.shuffle(files)
        cut = max(1, int(len(files) * 0.7))
        tr_files = set(files[:cut])
        for i in np.flatnonzero(y == lab):
            (tr_idx if names[i] in tr_files else te_idx).append(i)
    tr_idx, te_idx = np.array(tr_idx), np.array(te_idx)
    mu, sd = X[tr_idx].mean(0), X[tr_idx].std(0) + 1e-6
    Z = (X - mu) / sd
    # softmax regression (numpy, gradient descent) — centroid se kaafi behtar
    L = len(labels)
    lab2i = {lab: i for i, lab in enumerate(labels)}
    ytr = np.array([lab2i[v] for v in y[tr_idx]])
    W = np.zeros((Z.shape[1], L))
    b = np.zeros(L)
    Xtr = Z[tr_idx]
    for _ in range(600):
        logits = Xtr @ W + b
        logits -= logits.max(1, keepdims=True)
        P = np.exp(logits); P /= P.sum(1, keepdims=True)
        P[np.arange(len(ytr)), ytr] -= 1.0
        W -= 0.35 * (Xtr.T @ P) / len(ytr) + 1e-4 * W
        b -= 0.35 * P.mean(0)
    cent = {lab: W[:, i] for lab, i in lab2i.items()}
    correct = 0
    conf = {}
    for i in te_idx:
        logit = Z[i] @ W + b
        pred = labels[int(np.argmax(logit))]
        conf.setdefault(y[i], []).append(pred == y[i])
        correct += int(pred == y[i])
    acc = correct / max(1, len(te_idx))
    per = {lab: round(float(np.mean(v)), 2) for lab, v in conf.items()}
    return {"acc": round(acc, 3), "test": len(te_idx), "train": len(tr_idx),
            "per_class": per, "labels": labels,
            "model": {"mu": mu.tolist(), "sd": sd.tolist(),
                      "W": W.tolist(), "b": b.tolist(), "labels": labels}}


GROUP = {
    "wolf": "bada_janwar", "dog": "chhota_janwar", "cat": "chhota_janwar", "lion": "bada_janwar",
    "bird": "pakshi", "cricket": "keeda", "frog": "chhota_janwar", "monkey": "bada_janwar",
    "elephant": "bada_janwar", "horse": "bada_janwar", "snake": "sarpan", "boar": "bada_janwar",
    "camel": "bada_janwar", "zebra": "bada_janwar", "rhino": "bada_janwar", "panda": "bada_janwar",
    "kangaroo": "bada_janwar", "mouse_rat": "chhota_janwar", "wombat": "chhota_janwar",
    "cow_buffalo": "bada_janwar",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=220)
    a = ap.parse_args()
    X, y, names = build(a.limit)
    if len(X) < 20:
        print("bahut kam clips — kuch nahi kiya")
        return 1
    res = train(X, y, names)
    # mote group (bada janwar / pakshi / keeda...) — kahani me sound chunne ke liye yahi kaam aata hai
    yg = np.array([GROUP.get(v, "anya") for v in y])
    res_g = train(X, yg, names, min_per_class=10)
    print(f"\naccuracy: {res['acc']*100:.1f}%  (train {res['train']}, test {res['test']})")
    print("per jeev:", {k: f"{v*100:.0f}%" for k, v in sorted(res["per_class"].items())})
    print(f"mote group accuracy: {res_g['acc']*100:.1f}%  ({len(res_g['labels'])} group, test {res_g['test']})")
    (K / "creature-model.json").write_text(json.dumps(
        {"fine": res["model"], "coarse": res_g["model"]}), encoding="utf-8")
    (K / "creature-taxonomy.json").write_text(json.dumps(TAXONOMY, ensure_ascii=False, indent=1), encoding="utf-8")
    (K / "creature-report.json").write_text(json.dumps(
        {"fine": {k: v for k, v in res.items() if k != "model"},
         "coarse": {k: v for k, v in res_g.items() if k != "model"}}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("model:", K / "creature-model.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
