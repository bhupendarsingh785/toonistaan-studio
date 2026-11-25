#!/usr/bin/env python3
"""voice_train.py — insaan ki har tarah ki awaaz par training (man/woman/bachcha/budha/baby...).

Do tarah ka data:
  1. **Apni TTS se banaya** (piper hi_IN priyamvada=stri, pratham=purush) — sur aur raftaar
     badal kar bachcha / budhi aurat / budha aadmi banao. Label pakka, shor nahi.
  2. **Asli library clips** (baby, bheed, hansi, cheekh, rona) — naam se sakhti se chhaante hue.

Model: F0 + formant + mel + raftaar → softmax. Split FILE ke hisaab se.

  python tools/voice_train.py
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "world"))
K = ROOT / "knowledge"
INP = Path("/scratch/input")
VOICES = Path("/scratch/work/voices")
SR = 22050

SENTENCES = [
    "शाम ढल रही थी और नदी बह रही थी।",
    "सुनो, जंगल में कोई है क्या?",
    "मैं घर जा रहा हूँ, देर हो गई।",
    "यह आवाज़ कहाँ से आ रही है?",
    "मेरा नाम सीतल है।",
    "बाहर बारिश हो रही है।",
]

TAX = {
    "aadmi":   {"hindi": ["आदमी", "पुरुष", "मर्द"], "f0": (95, 155)},
    "stri":    {"hindi": ["औरत", "महिला", "लड़की"], "f0": (165, 260)},
    "bachcha": {"hindi": ["बच्चा", "बच्ची", "लड़का", "लड़की"], "f0": (250, 400)},
    "budha":   {"hindi": ["बूढ़ा", "दादा", "नाना"], "f0": (80, 120)},
    "budhi":   {"hindi": ["बूढ़ी", "दादी", "नानी"], "f0": (150, 210)},
    "baby":    {"hindi": ["शिशु", "नन्हा बच्चा", "रोता बच्चा"], "f0": (300, 600)},
    "bheed":   {"hindi": ["भीड़", "लोग", "मेला"], "f0": (100, 300)},
    "hansi":   {"hindi": ["हँसी", "हंसना"], "f0": (120, 350)},
    "cheekh":  {"hindi": ["चीख", "चिल्लाना"], "f0": (150, 500)},
    "rona":    {"hindi": ["रोना", "रो रहा"], "f0": (150, 450)},
}


def _piper(text: str, model: Path, out: Path, length_scale=1.0, noise=0.667):
    try:
        from piper import PiperVoice
        from piper.config import SynthesisConfig
        v = PiperVoice.load(str(model), config_path=str(model) + ".json")
        with __import__("wave").open(str(out), "wb") as w:
            v.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=length_scale, noise_scale=noise, noise_w_scale=0.8))
        return out.exists() and out.stat().st_size > 3000
    except Exception as e:
        print("  TTS fail:", type(e).__name__, str(e)[:60])
        return False


def _load(p: Path, sr=SR, sec=8.0):
    import ffbin
    ff = ffbin.ensure() or "ffmpeg"
    raw = subprocess.run([ff, "-v", "quiet", "-t", str(sec), "-i", str(p),
                          "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True).stdout
    if len(raw) < sr // 2:
        return None
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return x / (np.max(np.abs(x)) + 1e-9)


def _shift(x, factor):
    """Sur badlo (bachcha = upar, budha = neeche) — resample se."""
    from scipy.signal import resample_poly
    from math import gcd
    f = float(factor)
    up, down = int(round(f * 100)), 100
    g = gcd(up, down)
    return resample_poly(x, up // g, down // g)


def feats(x, sr=SR):
    n = 1024
    if len(x) < n * 2:
        return None
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::512]
    X = np.abs(np.fft.rfft(fr * np.hanning(n), axis=1)) + 1e-10
    f = np.fft.rfftfreq(n, 1 / sr)
    edges = np.geomspace(60, min(10000, sr / 2 - 200), 21)
    mel = []
    for i in range(20):
        m = (f >= edges[i]) & (f < edges[i + 1])
        mel.append(np.log(X[:, m].sum(1) + 1e-9) if m.any() else np.zeros(len(X)))
    M = np.stack(mel, 1)
    e = np.sqrt((fr ** 2).mean(1))
    # F0 track (autocorrelation, har 0.25s)
    f0s = []
    win = int(0.05 * sr)
    for i in range(0, len(x) - win, int(0.05 * sr)):
        seg = x[i:i + win]
        if np.sqrt((seg ** 2).mean()) < 0.01:
            continue
        ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
        lo, hi = int(sr / 500), int(sr / 70)
        if hi >= len(ac):
            continue
        lag = np.argmax(ac[lo:hi]) + lo
        f0s.append(sr / (lag + 1e-9))
    f0 = np.median(f0s) if f0s else 0.0
    # formant-ish: spectral centroid aur do peaks
    spec = X.mean(0)
    cent = float((spec * f).sum() / (spec.sum() + 1e-12))
    hi_ratio = float(spec[f > 3000].sum() / (spec.sum() + 1e-12))
    return np.concatenate([
        M.mean(0), M.std(0),
        [np.log(f0 + 1e-6), np.log(cent + 1e-6), hi_ratio,
         float(np.percentile(e, 90) / (np.percentile(e, 20) + 1e-9))],
    ]).astype(np.float32)


def tts_rows():
    rows = []
    male = VOICES / "hi_IN-pratham-medium.onnx"
    female = VOICES / "hi_IN-priyamvada-medium.onnx"
    tmp = Path("/scratch/work/tts_lab")
    tmp.mkdir(parents=True, exist_ok=True)
    plan = []
    for model, base in ((female, "stri"), (male, "aadmi")):
        if not model.exists():
            continue
        for i, text in enumerate(SENTENCES):
            plan.append((model, base, text, i, 1.0))
    for model, base, text, i, ls in plan:
        out = tmp / f"{base}_{i}.wav"
        if not out.exists() and not _piper(text, model, out, length_scale=ls):
            continue
        x = _load(out)
        if x is None:
            continue
        rows.append((base, x, f"tts_{base}_{i}"))
        # bachcha (sur ~1.55x), budhi (0.88x, dheemi), budha (0.80x, dheemi)
        if base == "stri":
            rows.append(("bachcha", _shift(x, 1.55), f"tts_bachcha_{i}"))
            rows.append(("budhi", _shift(x, 0.84), f"tts_budhi_{i}a"))
            rows.append(("budhi", _shift(x, 0.90), f"tts_budhi_{i}b"))
            rows.append(("budhi", _shift(x, 0.94), f"tts_budhi_{i}c"))
        else:
            rows.append(("budha", _shift(x, 0.80), f"tts_budha_{i}a"))
            rows.append(("budha", _shift(x, 0.86), f"tts_budha_{i}b"))
    return rows


STRICT = {
    "baby": (["baby-cry", "baby-crying", "baby-laugh", "baby-babble", "baby-giggl", "baby-noises",
              "crying-baby", "baby-shout", "baby-cry-"], []),
    "bheed": (["crowd-cheer", "crowd-noise", "crowd-shout", "crowd-boo", "stadium", "market",
               "crowd-chatter", "crowd-laugh", "crowd-clap", "crowd"], []),
    "hansi": (["laugh", "giggle"], ["crowd"]),
    "cheekh": (["scream", "shout", "yell"], ["crowd", "woman-screaming"]),
    "rona": (["crying", "cry-", "sob"], ["crowd", "baby"]),
}


def real_rows():
    rows = []
    files = [p for p in INP.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".ogx")]
    for label, (keys, block) in STRICT.items():
        got = [p for p in files if any(k in p.name.lower() for k in keys)
               and not any(b in p.name.lower() for b in block)]
        for p in got[:12]:
            x = _load(p, sec=6.0)
            if x is not None:
                rows.append((label, x, p.name))
    return rows


def decide(f0: float, hi_ratio: float = 0.0) -> str:
    """Model ka confusion theek karne ka niyam: stri vs budhi (dono aurat) sirf sur se.

    Model "kaunsi tarah ki awaaz" batata hai; umar ka faisla sur (F0) se hota hai —
    isliye dadi ki awaaz kabhi ladki jaisi nahi lagti.
    """
    if f0 <= 0:
        return "pata_nahi"
    if f0 < 90:
        return "budha"
    if f0 < 125:
        return "aadmi"
    if f0 < 165:
        return "budhi"
    if f0 < 250:
        return "stri"
    if f0 < 320:
        return "bachcha"
    return "baby"


def main() -> int:
    rows = tts_rows() + real_rows()
    print("clip:", len(rows), "| categories:", sorted({r[0] for r in rows}))
    X, y, names = [], [], []
    for label, x, src in rows:
        n = int(2.0 * SR)
        if len(x) < n:
            continue
        for i in range(0, min(len(x) - n, 3 * n), n):
            f = feats(x[i:i + n])
            if f is not None and np.isfinite(f).all():
                X.append(f); y.append(label); names.append(src)   # src = clip ki pehchaan
    X, y, names = np.array(X), np.array(y), np.array(names)
    print("windows:", len(X))
    rng = np.random.default_rng(7)
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
    mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
    Z = (X - mu) / sd
    lab2i = {l: i for i, l in enumerate(labels)}
    ytr = np.array([lab2i[v] for v in y[tr]])
    W = np.zeros((Z.shape[1], len(labels))); b = np.zeros(len(labels))
    for _ in range(700):
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
    acc = correct / max(1, len(te))
    print(f"accuracy: {acc*100:.1f}%  (train {len(tr)}, test {len(te)}, {len(labels)} category)")
    print("per category:", {k: f"{np.mean(v)*100:.0f}%" for k, v in sorted(conf.items())})
    (K / "voice-model.json").write_text(json.dumps(
        {"mu": mu.tolist(), "sd": sd.tolist(), "W": W.tolist(), "b": b.tolist(), "labels": labels}), encoding="utf-8")
    (K / "voice-taxonomy.json").write_text(json.dumps(TAX, ensure_ascii=False, indent=1), encoding="utf-8")
    (K / "voice-report.json").write_text(json.dumps(
        {"acc": round(acc, 3), "train": len(tr), "test": len(te), "labels": labels,
         "per_class": {k: round(float(np.mean(v)), 2) for k, v in conf.items()}}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print("model:", K / "voice-model.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
