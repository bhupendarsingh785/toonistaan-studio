#!/usr/bin/env python3
"""bhaav_v2.py — bhaav ko GEHRA karo: 4 knob se 12 knob, aur character ke hisaab se.

Purana (bhavna.py): sur, raftaar, zor, rukna — 11 bhaav.
Naya (yahi): har bhaav ke liye:
  • sur_med     — sur ka beech (semi)
  • sur_range   — sur kitna upar-neeche ghoomta hai (bhaav ki jaan)
  • raftaar     — kitna tez/dheema
  • zor         — kitna zor se
  • saans       — kharaash/hawa (HNR)
  • kaanp        — sur me kaanp (dar/rona)
  • aarambh     — shuruaat ka zor (gussa = dhamaka, dukh = dheema)
  • ant         — ant me sur girta/uthta hai
  • rukna       — pause kitna
  • saans_len   — pause ke beech saans
  • jhurri      — awaaz ki "umar" (formant tilt)
  • bolne_ka_%  — kitna hissa bolne me

Character (age/gender) se in par asar: dadi ki khushi = dheemi, bachche ki khushi = tez.

  python tools/bhaav_v2.py list
  python tools/bhaav_v2.py style --emotion dar --character dadi
  python tools/bhaav_v2.py test            # 6 bhaav, naap ke saath
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
SR = 24000

BASE = {
    "neutral": dict(sur_med=1.00, sur_range=1.00, raftaar=1.00, zor=1.00, saans=0.0,
                    kaanp=0.0, aarambh=1.00, ant=-0.02, rukna=1.00, saans_len=0.25, jhurri=0.0),
    "khushi": dict(sur_med=1.08, sur_range=1.25, raftaar=1.10, zor=1.06, saans=0.05,
                   kaanp=0.0, aarambh=1.10, ant=+0.10, rukna=0.75, saans_len=0.18, jhurri=0.0),
    "dukh": dict(sur_med=0.94, sur_range=0.75, raftaar=0.86, zor=0.88, saans=0.10,
                 kaanp=0.03, aarambh=0.95, ant=-0.12, rukna=1.35, saans_len=0.40, jhurri=0.0),
    "gussa": dict(sur_med=1.05, sur_range=1.15, raftaar=1.12, zor=1.18, saans=0.08,
                  kaanp=0.05, aarambh=1.25, ant=-0.08, rukna=0.70, saans_len=0.15, jhurri=0.0),
    "dar": dict(sur_med=1.06, sur_range=1.35, raftaar=1.10, zor=0.85, saans=0.15,
                kaanp=0.10, aarambh=1.15, ant=+0.06, rukna=0.95, saans_len=0.35, jhurri=0.0),
    "pyaar": dict(sur_med=1.01, sur_range=0.85, raftaar=0.92, zor=0.94, saans=0.08,
                  kaanp=0.0, aarambh=0.97, ant=-0.06, rukna=1.20, saans_len=0.30, jhurri=0.0),
    "rona": dict(sur_med=0.92, sur_range=0.80, raftaar=0.80, zor=0.86, saans=0.20,
                 kaanp=0.12, aarambh=0.98, ant=-0.14, rukna=1.50, saans_len=0.45, jhurri=0.0),
    "hairan": dict(sur_med=1.10, sur_range=1.45, raftaar=1.02, zor=1.00, saans=0.05,
                   kaanp=0.02, aarambh=1.15, ant=+0.16, rukna=1.05, saans_len=0.22, jhurri=0.0),
    "thakan": dict(sur_med=0.96, sur_range=0.70, raftaar=0.82, zor=0.84, saans=0.18,
                   kaanp=0.0, aarambh=0.92, ant=-0.10, rukna=1.40, saans_len=0.50, jhurri=0.0),
    "sharam": dict(sur_med=1.00, sur_range=0.90, raftaar=0.88, zor=0.80, saans=0.12,
                   kaanp=0.04, aarambh=0.94, ant=-0.04, rukna=1.25, saans_len=0.35, jhurri=0.0),
}

# character: (sur_med guna, raftaar guna, zor guna, saans jod, jhurri)
CHAR = {
    "bachcha": (1.35, 1.12, 0.92, +0.06, -0.10),
    "bachchi": (1.40, 1.12, 0.90, +0.06, -0.10),
    "ladki":   (1.12, 1.03, 0.98, +0.02, -0.04),
    "ladka":   (1.02, 1.02, 1.02, 0.0, -0.02),
    "aadmi":   (0.92, 1.00, 1.05, 0.0, 0.0),
    "stri":    (1.08, 1.00, 0.98, +0.01, 0.0),
    "budhi":   (0.86, 0.90, 0.88, +0.10, +0.14),
    "budha":   (0.80, 0.88, 0.92, +0.12, +0.16),
    "vachak":  (0.95, 0.97, 1.00, +0.02, +0.02),
}


def style(emotion: str = "neutral", character: str = "vachak") -> dict:
    base = dict(BASE.get(emotion, BASE["neutral"]))
    cs, cr, cz, csaans, cjh = CHAR.get(character, CHAR["vachak"])
    base["sur_med"] = round(base["sur_med"] * cs, 3)
    base["raftaar"] = round(base["raftaar"] * cr, 3)
    base["zor"] = round(base["zor"] * cz, 3)
    base["saans"] = round(min(0.35, base["saans"] + csaans), 3)
    base["jhurri"] = round(base["jhurri"] + cjh, 3)
    base["emotion"], base["character"] = emotion, character
    # TTS ko dene layak seedhe param
    base["tts"] = {
        "length_scale": round(1.0 / max(0.6, base["raftaar"]), 3),
        "noise_scale": round(0.60 + base["saans"] * 0.7, 3),
        "noise_w": round(0.70 + base["sur_range"] * 0.12 + base["kaanp"] * 0.8, 3),
        "volume": round(min(1.25, base["zor"]), 3),
    }
    return base


def _piper(text: str, out: Path, st: dict, model="hi_IN-priyamvada-medium.onnx") -> bool:
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    import wave
    m = Path("/scratch/work/voices") / model
    if not m.exists():
        return False
    v = PiperVoice.load(str(m), config_path=str(m) + ".json")
    cfg = SynthesisConfig(length_scale=st["tts"]["length_scale"],
                          noise_scale=st["tts"]["noise_scale"],
                          noise_w_scale=st["tts"]["noise_w"],
                          volume=st["tts"]["volume"])
    with wave.open(str(out), "wb") as w:
        v.synthesize_wav(text, w, syn_config=cfg)
    return out.exists() and out.stat().st_size > 2000


def apply_prosody(y, sr, st):
    """TTS ke baad asli bhaav: sur, kaanp, saans, shuruaat/ant ka zor."""
    import voice_clone_lite as VL
    y = np.asarray(y, dtype=np.float64)
    if y.ndim > 1:
        y = y.mean(1)
    # 1) sur (bhaav + character)
    if abs(st["sur_med"] - 1.0) > 0.01:
        y = VL._pitch_shift(y, float(st["sur_med"]), sr)
    # 2) kaanp (dar/rona) — halka vibrato
    if st["kaanp"] > 0.01:
        t = np.arange(len(y)) / sr
        vib = 1.0 + st["kaanp"] * np.sin(2 * np.pi * 5.5 * t)
        idx = np.clip((np.cumsum(vib) - vib[0]).astype(int), 0, len(y) - 1)
        y = y[idx]
    # 3) saans (hawa) — bolne ke hisse me halka noise
    if st["saans"] > 0.02:
        rng = np.random.default_rng(9)
        n = rng.normal(0, 1, len(y))
        w = int(0.02 * sr)
        env = np.array([np.sqrt((y[i:i + w] ** 2).mean()) for i in range(0, max(1, len(y) - w), w)])
        env = np.interp(np.arange(len(y)), np.arange(0, max(1, len(y) - w), w), env)
        y = y + n * (env / (env.max() + 1e-9)) * (st["saans"] * 0.18)
    # 4) shuruaat ka zor + ant ka jhukav
    if len(y) > int(0.15 * sr):
        a = int(0.08 * sr)
        y[:a] *= np.linspace(max(0.7, 2 - st["aarambh"]), 1.0, a)
        y[-a:] *= np.linspace(1.0, max(0.55, 1.0 + st["ant"] * 2), a)
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.95
    return y


def _measure(path: Path) -> dict:
    import soundfile as sf
    y, sr = sf.read(str(path))
    if y.ndim > 1:
        y = y.mean(1)
    y = y.astype(np.float64)
    # sur
    win, hop = int(0.04 * sr), int(0.02 * sr)
    f0s = []
    for i in range(0, max(1, len(y) - win), hop):
        s = y[i:i + win]
        if np.sqrt((s ** 2).mean()) < 0.01:
            continue
        ac = np.correlate(s, s, "full")[len(s) - 1:]
        lo, hi = int(sr / 500), min(int(sr / 70), len(ac) - 1)
        if hi > lo:
            f0s.append(sr / (np.argmax(ac[lo:hi]) + lo + 1e-9))
    f0 = np.array(f0s) if f0s else np.array([0.0])
    e = np.sqrt((y ** 2).mean())
    return {"f0_med": round(float(np.median(f0)), 1),
            "f0_range": round(float(np.percentile(f0, 90) - np.percentile(f0, 10)), 1),
            "rms_db": round(float(20 * np.log10(e + 1e-9)), 1),
            "dur": round(len(y) / sr, 2)}


def test() -> int:
    line = "मैं यह बात कह रहा हूँ, तुम सुन रहे हो ना?"
    out = Path("/scratch/work/bhaav_test")
    out.mkdir(exist_ok=True)
    rows = []
    for emo in ("neutral", "khushi", "dukh", "gussa", "dar", "rona", "thakan"):
        st = style(emo, "vachak")
        p = out / f"{emo}.wav"
        if not _piper(line, p, st):
            print("piper fail"); return 1
        import soundfile as sf
        y, sr = sf.read(str(p))
        y = apply_prosody(y, sr, st)
        sf.write(str(p), y.astype("float32"), sr)
        m = _measure(p)
        rows.append((emo, st, m))
        print(f"{emo:8s} sur×{st['sur_med']:.2f} raftaar×{st['raftaar']:.2f} zor×{st['zor']:.2f} -> "
              f"f0 {m['f0_med']} Hz, range {m['f0_range']}, {m['rms_db']} dB, {m['dur']}s")
    # jaanch: bhaav ek jaise nahi hone chahiye
    f0s = [r[2]["f0_med"] for r in rows]
    durs = [r[2]["dur"] for r in rows]
    print(f"\nf0 failaav: {min(f0s)}-{max(f0s)} Hz | lambai: {min(durs)}-{max(durs)}s")
    ok = (max(f0s) - min(f0s) > 8) and (max(durs) - min(durs) > 0.3)
    print("PASS — har bhaav ka apna sur/raftaar" if ok else "FAIL — bhaav alag nahi lag rahe")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "style", "test"])
    ap.add_argument("--emotion", default="neutral")
    ap.add_argument("--character", default="vachak")
    a = ap.parse_args()
    if a.cmd == "list":
        for e in BASE:
            print(e, "->", json.dumps(style(e, "vachak")["tts"], ensure_ascii=False))
        return 0
    if a.cmd == "style":
        print(json.dumps(style(a.emotion, a.character), ensure_ascii=False, indent=1))
        return 0
    return test()


if __name__ == "__main__":
    raise SystemExit(main())
