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
    for who, text in lines:
        y, sr = sf.read(str(line_audio(who, text)))
        y = y.mean(1) if y.ndim > 1 else y
        g = scene_gap if (prev and prev != who) else gap
        pieces.append(y.astype(np.float64)); pieces.append(np.zeros(int(g * SR)))
        t += len(y) / SR + g
        prev = who
    voice = np.concatenate(pieces)
    # voice-only stem (gate isi par chalta hai — background robot-paime me nahi ginta)
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
