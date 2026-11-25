#!/usr/bin/env python3
"""recognize.py — training ka ASLI istemaal: awaaz sun kar batao kya hai.

Teen model ek saath:
  • sound-type  (janwar / prakriti / harkat / music / darwaza / insaan)
  • creature    (kaunsa jeev — fine + mote group)
  • voice       (insaan ki tarah: man/woman/bachcha/budhi/baby) + F0 se umar ka niyam

  python tools/recognize.py path/to/audio.mp3
  python tools/recognize.py --selftest          # library ke jaane-pehchane clips par jaanch
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
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
SR = 22050


def _load(name):
    p = K / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _decode(path: Path, sec=6.0, sr=SR):
    import ffbin
    ff = ffbin.ensure() or "ffmpeg"
    raw = subprocess.run([ff, "-v", "quiet", "-t", str(sec), "-i", str(path),
                          "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True).stdout
    if len(raw) < sr // 2:
        return None
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return x / (np.max(np.abs(x)) + 1e-9)


def feats(x, sr=SR):
    """Wahi features jo training me the (warna model kaam nahi karega)."""
    n = 1024
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::512]
    X = np.abs(np.fft.rfft(fr * np.hanning(n), axis=1)) + 1e-10
    f = np.fft.rfftfreq(n, 1 / sr)
    edges = np.geomspace(50, min(10000, sr / 2 - 200), 21)
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
    seg = x[: min(len(x), sr)]
    ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
    lo, hi = int(sr / 500), min(int(sr / 70), len(ac) - 1)
    f0 = sr / (np.argmax(ac[lo:hi]) + lo + 1e-9) if hi > lo else 0.0
    onset = float((np.diff(e) > 0.08 * (np.max(e) + 1e-9)).mean())
    return np.concatenate([M.mean(0), M.std(0), d, np.abs(M).mean(0)[:6],
                           [np.log(f0 + 1e-6), np.log(cent + 1e-6), flat, onset,
                            float(np.percentile(e, 90) / (np.percentile(e, 20) + 1e-9))]]).astype(np.float32), f0


def _predict(model, feat):
    mu = np.array(model["mu"]); sd = np.array(model["sd"])
    W = np.array(model["W"]); b = np.array(model["b"])
    z = (feat - mu) / sd
    logits = z @ W + b
    logits -= logits.max()
    P = np.exp(logits); P /= P.sum()
    i = int(np.argmax(P))
    return model["labels"][i], float(P[i]), {l: round(float(p), 2) for l, p in zip(model["labels"], P)}


def rule_label(x) -> tuple[str | None, float, str]:
    """Niyam se label — saboot saaf, model se pehle (model ka bharosa kam hai)."""
    try:
        import auto_label as AL
    except Exception:
        return None, 0.0, "auto_label nahi mila"
    ev = AL.evidence(x)
    has_words, _txt = (None, "")
    if ev["speech_mod"] > 0.35 or (70 < ev["f0"] < 330 and ev["harm"] < 0.4):
        has_words, _txt = AL.asr_has_words(x)
    return AL.decide(ev, bool(has_words))


def recognize(path: Path) -> dict:
    x = _decode(path)
    if x is None:
        return {"file": path.name, "ok": False, "why": "decode fail"}
    feat, f0 = feats(x)
    out = {"file": path.name, "ok": True, "f0_hz": round(float(f0), 1)}
    rl, rc, rwhy = rule_label(x)
    out["rule"] = {"label": rl, "conf": round(rc, 2), "why": rwhy}
    m = _load("private-model/sound-type-model.json")
    if m:
        lab, conf, _ = _predict(m, feat)
        out["model_guess"] = {"label": lab, "conf": round(conf, 2)}
    # faisla: niyam pehle (saboot saaf), model sirf sahayak
    if rl:
        out["sound_type"] = {"label": rl, "conf": round(max(rc, 0.5), 2), "by": "rule"}
    elif m:
        out["sound_type"] = {"label": lab, "conf": round(conf, 2), "by": "model"}
    cm = _load("creature-model.json")
    if cm:
        try:                      # creature model ke apne features (warna dimension mismatch)
            import creature_train as CT
            cf = CT.features(x)
        except Exception:
            cf = None
        if cf is not None:
            lab, conf, _ = _predict(cm["fine"], cf)
            out["creature"] = {"label": lab, "conf": round(conf, 2)}
            lab2, conf2, _ = _predict(cm["coarse"], cf)
            out["creature_group"] = {"label": lab2, "conf": round(conf2, 2)}
    vm = _load("voice-model.json")
    if vm:
        try:                      # voice model ke apne features
            import voice_train as VT
            vf = VT.feats(x)
        except Exception:
            vf = None
        if vf is not None:
            lab, conf, _ = _predict(vm, vf)
            out["voice"] = {"label": lab, "conf": round(conf, 2)}
    # umar ka niyam (F0) — model ka confusion theek karta hai
    try:
        import voice_train as VT
        out["age_rule"] = VT.decide(float(f0))
    except Exception:
        pass
    return out


def selftest(n: int = 8) -> int:
    """Jaane-pehchane clips par jaanch — model sach me kaam kar raha hai?"""
    idx = K / "audio-content-index.json"
    tags = json.loads(idx.read_text(encoding="utf-8"))["tags"] if idx.exists() else {}
    tests = []
    for tag, want in (("water", "prakriti"), ("footsteps", "harkat"), ("speech/voice", "insaan"),
                      ("animals", "janwar"), ("music", "music"), ("door", "darwaza")):
        for rec in tags.get(tag, [])[:2]:
            p = _AP.INPUT / rec["file"]
            if not p.exists():
                p = (_AP.WORK / "library_extra") / rec["file"]
            if p.exists():
                tests.append((p, want))
    ok = 0
    for p, want in tests[:n]:
        r = recognize(p)
        got = (r.get("sound_type") or {}).get("label")
        good = got == want
        ok += good
        print(f"  {'OK ' if good else 'XX '} {p.name[:38]:38s} chahiye {want:9s} mila {str(got):9s} f0 {r.get('f0_hz')}")
    print(f"\n{ok}/{min(n, len(tests))} sahi")
    return 0 if ok >= max(1, min(n, len(tests)) * 0.5) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest or not a.path:
        return selftest()
    print(json.dumps(recognize(Path(a.path)), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
