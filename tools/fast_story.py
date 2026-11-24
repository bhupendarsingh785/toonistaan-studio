#!/usr/bin/env python3
"""fast_story.py — kahani ko JALDI banao (user ko intezaar na karna pade).

Purana raasta: har line ka world engine + 8 layer + reverb + QA = minute lag jaate the.
Naya raasta (fast mode):
  1. saari lines EK SAATH (parallel) banao — piper per-thread
  2. background ek hi loop (jagah ke hisaab se) — loop_maker se, cache me
  3. halka duck + loudness + peak guard
  4. QA sirf maangne par (--qa)

  python tools/fast_story.py script.txt out.mp3
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "world"))
SR = 24000
CACHE = Path("/scratch/work/fast_cache")
CACHE.mkdir(parents=True, exist_ok=True)


def _lines(path: Path):
    out = []
    for l in path.read_text(encoding="utf-8").splitlines():
        if ":" in l:
            who, t = l.split(":", 1)
            t = t.strip()
            if t:
                out.append((who.strip(), t))
    return out


_LOCAL = {}
_CFG = {"गौरी": (205, "f"), "कमला": (186, "f"), "माई": (168, "f"), "मोहन": (275, "m"),
        "हरिदास": (104, "m"), "ऋषि": (96, "m"), "भेड़िया": (88, "m"),
        "सरपंच": (118, "m"), "वाचक": (112, "m")}


def _tts_fast(who: str, text: str, dst: Path, base_ls: float = 1.30) -> bool:
    """piper se line banao aur sur target par le jao — ek hi resample (tez).

    Trick: piper ko f guna DHEEMA bolo, phir resample se f guna chhota karo —
    sur upar, lambai wahi. ffmpeg/SOLA ki zaroorat nahi (10x tez).
    """
    import threading
    import wave
    from math import gcd
    from scipy.signal import resample_poly
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    tgt, g = _CFG.get(who, (150, "m"))
    # female/child ke liye ASLI female model (priyamvada) — bada shift = robotic/bachcha lagta tha
    use_female = g == "f" or who in ("मोहन", "बच्चा", "बच्ची")
    model = Path("/scratch/work/voices") / ("hi_IN-priyamvada-medium.onnx" if use_female else "hi_IN-pratham-medium.onnx")
    v = _LOCAL.get(str(model))        # har model ek baar (memory bachao)
    if v is None:
        v = PiperVoice.load(str(model), config_path=str(model) + ".json")
        _LOCAL[str(model)] = v
    base_hz = 200.0 if use_female else 110.0
    f = max(0.85, min(1.45, tgt / base_hz))     # chhota shift = smooth awaaz
    tmp = dst.with_suffix(".raw.wav")
    try:
        with wave.open(str(tmp), "wb") as w:
            v.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=base_ls * f))
        y, sr = sf.read(str(tmp))
        y = y.mean(1) if y.ndim > 1 else y
        up, down = 100, int(round(f * 100))
        gg = gcd(up, down)
        z = resample_poly(y, up // gg, down // gg)
        z = z / (np.max(np.abs(z)) + 1e-9) * 0.95
        sf.write(str(dst), z.astype("float32"), sr)
        tmp.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _voice(who: str, text: str) -> Path:
    """Ek line ki awaaz (cache ke saath)."""
    import hashlib
    key = hashlib.sha1(f"{who}|{text}".encode("utf-8")).hexdigest()[:16]
    dst = CACHE / f"{key}.wav"
    if dst.exists() and dst.stat().st_size > 2000:
        return dst
    ok = _tts_fast(who, text, dst)
    if not ok:
        raise RuntimeError(f"voice fail: {who}")
    return dst
    return dst


def _bed(name: str, sec: float) -> np.ndarray:
    """Ek loop background (cache me)."""
    import loop_maker as LM
    key = CACHE / f"bed_{name}.wav"
    if key.exists():
        y, sr = sf.read(str(key))
        y = y.mean(1) if y.ndim > 1 else y
    else:
        y = LM.make(name, sec=20).astype(np.float64)
        sf.write(str(key), y.astype("float32"), LM.SR)
        sr = LM.SR
    n = int(sec * sr)
    reps = int(np.ceil(n / max(1, len(y))))
    out = np.tile(y, reps)[:n]
    return out, sr


def build(script: Path, out: Path, gap=0.28, scene_gap=0.55) -> dict:
    t0 = time.time()
    lines = _lines(script)
    if not lines:
        raise SystemExit("script khaali hai")
    # 1) saari lines parallel
    with ThreadPoolExecutor(max_workers=1) as ex:
        wavs = list(ex.map(lambda wl: _voice(wl[0], wl[1]), lines))
    t_voice = time.time() - t0
    # 2) jodo
    pieces, times = [], []
    t = 0.0
    prev_loc = None
    for (who, text), w in zip(lines, wavs):
        y, sr = sf.read(str(w))
        y = y.mean(1) if y.ndim > 1 else y
        if sr != SR:
            idx = (np.arange(int(len(y) * SR / sr)) * sr / SR).astype(int)
            y = y[np.clip(idx, 0, len(y) - 1)]
        g = scene_gap if prev_loc and prev_loc != _loc(text) else gap
        pieces.append(y.astype(np.float64))
        times.append((t, t + len(y) / SR, who, text))
        t += len(y) / SR + g
        pieces.append(np.zeros(int(g * SR)))
        prev_loc = _loc(text)
    voice = np.concatenate(pieces)
    total = len(voice) / SR
    # 3) background: jagah ke hisaab se ek loop
    import scene_env as SE
    st = SE.analyse(" ".join(t for _, t in lines))
    bed_name = "crickets" if st["time"] in ("raat", "shaam") else "wind"
    if st["loc"] == "jungle" and st["time"] in ("din", "subah"):
        bed_name = "birds"
    if st["loc"] in ("nadi",):
        bed_name = "river"
    elif st["loc"] in ("kamra", "ghar", "society"):
        bed_name = "room" if st["time"] == "raat" else "wind"
    bed, bsr = _bed(bed_name, total)
    if bsr != SR:
        idx = (np.arange(int(len(bed) * SR / bsr)) * bsr / SR).astype(int)
        bed = bed[np.clip(idx, 0, len(bed) - 1)]
    if len(bed) < len(voice):
        bed = np.pad(bed, (0, len(voice) - len(bed)))
    bed = bed[: len(voice)]
    # 4) duck (voice ke hisaab se) + mix
    n = len(voice)
    k = int(0.06 * SR)
    env = np.convolve(np.abs(voice), np.ones(k) / k, mode="same")
    act = np.clip(env / (np.percentile(env, 95) + 1e-9), 0, 1)
    bed_gain = (1.0 - 0.55 * act)
    if len(bed_gain) < len(voice):
        bed_gain = np.pad(bed_gain, (0, len(voice) - len(bed_gain)))
    bed_gain = bed_gain[: len(voice)]
    bed = bed / (np.sqrt((bed ** 2).mean()) + 1e-9) * (10 ** (-30 / 20))
    mixd = voice + bed * bed_gain
    # 5) loudness + peak
    try:
        import pyloudnorm as ln
        meter = ln.Meter(SR)
        loud = meter.integrated_loudness(mixd)
        mixd = ln.normalize.loudness(mixd, loud, -16.0)
    except Exception:
        mixd = mixd / (np.sqrt((mixd ** 2).mean()) + 1e-9) * (10 ** (-16 / 20))
    pk = float(np.max(np.abs(mixd)))
    if pk > 0.95:
        mixd = mixd * (0.95 / pk)
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.with_suffix(".wav")
    sf.write(str(wav), mixd.astype("float32"), SR)
    # 6) mp3
    try:
        import ffbin
        ff = ffbin.ensure() or "ffmpeg"
        subprocess.run([ff, "-v", "error", "-y", "-i", str(wav), "-b:a", "128k", str(out)], check=True)
    except Exception:
        pass
    info = {"lines": len(lines), "dur": round(total, 1), "bed": bed_name,
            "voice_sec": round(t_voice, 1), "total_sec": round(time.time() - t0, 1),
            "peak": round(float(np.max(np.abs(mixd))), 3), "out": str(out)}
    (out.parent / "fast_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def _loc(text: str) -> str:
    try:
        import scene_env as SE
        return SE.analyse(text)["loc"]
    except Exception:
        return "jungle"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("out")
    a = ap.parse_args()
    info = build(Path(a.script), Path(a.out))
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
