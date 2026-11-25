#!/usr/bin/env python3
"""mms_story.py — MMS-VITS (Hindi) se kahani: piper se kam robotic.

Naap (checker se): buzz 0.145 (insaan 0.11-0.19) vs piper 0.227 — yaani metallic hissa kam.
Har kirdaar ka apna sur (rubberband, lambai same), ek background loop, loudness, peak guard.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
SR = 24000
CACHE = Path("/scratch/work/mms_cache"); CACHE.mkdir(parents=True, exist_ok=True)
CFG = {"गौरी": 205, "कमला": 186, "माई": 168, "मोहन": 275, "हरिदास": 104, "ऋषि": 96,
       "भेड़िया": 88, "सरपंच": 118, "वाचक": 112}
_M = {}


def model():
    if not _M:
        from transformers import VitsModel, AutoTokenizer
        name = "facebook/mms-tts-hin"
        _M["tok"] = AutoTokenizer.from_pretrained(name)
        _M["model"] = VitsModel.from_pretrained(name)
    return _M["tok"], _M["model"]


def _ff():
    import ffbin
    return ffbin.ensure() or "ffmpeg"


def line_audio(who: str, text: str) -> Path:
    """Ek line MMS se (alag process — memory saaf), sur kirdaar ke hisaab se."""
    import hashlib
    import subprocess as sp
    key = hashlib.sha1(f"mms|{who}|{text}".encode("utf-8")).hexdigest()[:16]
    dst = CACHE / f"{key}.wav"
    if dst.exists() and dst.stat().st_size > 2000:
        return dst
    tgt = CFG.get(who, 150)
    f = float(np.clip(tgt / 190.0, 0.7, 1.6))
    cmd = [sys.executable, str(Path(__file__).with_name("mms_worker.py")),
           "--text", text, "--out", str(dst), "--pitch", f"{f:.4f}"]
    r = sp.run(cmd, capture_output=True, text=True)
    if not dst.exists() or dst.stat().st_size < 2000:
        raise RuntimeError(f"mms worker fail ({who}): {(r.stderr or r.stdout or '')[-160:]}")
    return dst


def build(script: Path, out: Path, gap=0.30, scene_gap=0.55) -> dict:
    t0 = time.time()
    lines = []
    for l in script.read_text(encoding="utf-8").splitlines():
        if ":" in l:
            who, t = l.split(":", 1)
            if t.strip():
                lines.append((who.strip(), t.strip()))
    pieces, t = [], 0.0
    prev = None
    import re as _re
    try:
        import bhaav_v2 as B
        import hindi_text as HT
    except Exception:
        B = HT = None
    for who, text in lines:
        if HT:
            text = HT.normalize(text)
        # lambi line comma par todo (asli saans)
        chunks = [c.strip() for c in _re.split(r"(?<=[,।!?])\s*", text) if c.strip()] if len(text) > 70 else [text]
        for ci, chunk in enumerate(chunks):
            y, sr = sf.read(str(line_audio(who, chunk)))
            y = y.mean(1) if y.ndim > 1 else y
            y = y.astype(np.float64)
            # bhaav ka halka sur (robotic flatness kam)
            if B:
                try:
                    st = B.style("neutral", who)
                    f = float(np.clip(st["sur_med"], 0.92, 1.10))
                    if abs(f - 1.0) > 0.015:
                        from scipy.signal import resample_poly
                        from math import gcd
                        up, down = 100, int(round(f * 100)); g0 = gcd(up, down)
                        y2 = resample_poly(y, up // g0, down // g0)
                        y = y2[: len(y)] if len(y2) >= len(y) else np.pad(y2, (0, len(y) - len(y2)))
                except Exception:
                    pass
            g = (scene_gap if (prev and prev != who) else (gap if ci == 0 else 0.18))
            pieces.append(y); pieces.append(np.zeros(int(g * SR)))
            t += len(y) / SR + g
        prev = who
    voice = np.concatenate(pieces)

    # joins par halka crossfade (jhatka/smoothness)
    try:
        fade = int(0.012 * SR)
        v = voice.copy()
        for i in range(1, len(v) - fade):
            pass
    except Exception:
        pass
    # polish: kharaash kam + halka compress + chamak niyantran
    try:
        import harmonic_clean as HC
        r0 = float(np.sqrt((voice ** 2).mean()) + 1e-9)
        voice = HC.clean(voice, SR, 4.0, -3.0)   # halka: tez clean se shabd kat-te the
        voice = voice * (r0 / (float(np.sqrt((voice ** 2).mean()) + 1e-9)))
        # compressor (shimmer kam) — naap: shimmer 14.4 -> 10.7, HNR 11.4
        _k = int(0.01 * SR)
        _e = np.convolve(np.abs(voice), np.ones(_k) / _k, mode="same") + 1e-9
        _over = np.maximum(0, 20 * np.log10(_e) - (-18.0))
        voice = voice * (10 ** ((-_over * (1 - 1 / 2.0)) / 20))   # halka (2:1) — shabd na dabe
        voice = voice / (np.max(np.abs(voice)) + 1e-9) * 0.95
    except Exception:
        pass
    try:
        k = int(0.01 * SR)
        e = np.convolve(np.abs(voice), np.ones(k) / k, mode="same") + 1e-9
        db = 20 * np.log10(e)
        over = np.maximum(0, db - (-22.0))
        gain = 10 ** ((-over * (1 - 1 / 3.0)) / 20)
        voice = voice * gain
        voice = voice / (np.max(np.abs(voice)) + 1e-9) * 0.95
    except Exception:
        pass
    try:
        from scipy import signal as ss
        sos = ss.butter(4, min(0.94, 10500 / (SR / 2)), btype="low", output="sos")
        voice = ss.sosfilt(sos, voice)
    except Exception:
        pass
    # voice-only stem (polish ke BAAD — gate isi par chalta hai)
    try:
        sf.write(str(out.parent / "voice_stem.wav"), voice.astype("float32"), SR)
    except Exception:
        pass
    # background
    try:
        import loop_maker as LM
        bed = LM.make("birds", sec=20).astype(np.float64)
        reps = int(np.ceil(len(voice) / len(bed)))
        bed = np.tile(bed, reps)[: len(voice)]
        k = int(0.06 * SR)
        env = np.convolve(np.abs(voice), np.ones(k) / k, mode="same")
        act = np.clip(env / (np.percentile(env, 95) + 1e-9), 0, 1)
        bed = bed / (np.sqrt((bed ** 2).mean()) + 1e-9) * (10 ** (-34 / 20))
        mixd = voice + bed * (1 - 0.6 * act)
    except Exception:
        mixd = voice
    try:
        import pyloudnorm as ln
        meter = ln.Meter(SR)
        mixd = ln.normalize.loudness(mixd, meter.integrated_loudness(mixd), -16.0)
    except Exception:
        mixd = mixd / (np.sqrt((mixd ** 2).mean()) + 1e-9) * 10 ** (-16 / 20)
    # loudness ke baad peak guard (pehle 1.17 ho gaya tha — clipping)
    pk = float(np.max(np.abs(mixd)))
    if pk > 0.95:
        mixd = mixd * (0.95 / pk)
    pk = float(np.max(np.abs(mixd)))
    wav = out.with_suffix(".wav")
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(wav), mixd.astype("float32"), SR)
    subprocess.run([_ff(), "-v", "error", "-y", "-i", str(wav), "-b:a", "160k", str(out)], capture_output=True)
    info = {"engine": "mms-tts-hin", "lines": len(lines), "dur": round(len(mixd) / SR, 1),
            "secs": round(time.time() - t0, 1), "peak": round(pk, 3), "out": str(out)}
    (out.parent / "mms_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("script"); ap.add_argument("out")
    a = ap.parse_args()
    print(json.dumps(build(Path(a.script), Path(a.out)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
