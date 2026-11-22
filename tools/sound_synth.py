#!/usr/bin/env python3
"""Sound Synth — apni awaaz khud banao (kisi sample ke bina), signature ke hisaab se.

Har generator parameters se banta hai jo asli sounds ke naap se nikle:
  wolf growl, dog bark, cricket chirp, rain, river, leaves-footsteps

CLI: python tools/sound_synth.py --out pack.mp3 [--verify]
"""
from __future__ import annotations
import argparse, json, subprocess, sys, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR = 44100


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def _band(x, lo, hi):
    import numpy as np
    n = len(x); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    m = 1 / (1 + (lo / (f + 1e-9)) ** 4) * 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, n)


def wolf_growl(dur=2.5, seed=1):
    """bhediya — dheema growl: F0 90–180 Hz, AM 6–9 Hz, formant 500/1500."""
    import numpy as np
    n = int(SR * dur); t = np.arange(n) / SR
    f0 = 110 + 35 * np.sin(2 * np.pi * 0.35 * t)
    ph = 2 * np.pi * np.cumsum(f0) / SR
    src = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.3 * np.sin(3 * ph)
    growl = src * (0.6 + 0.4 * np.sin(2 * np.pi * 7.5 * t))
    body = _band(growl, 80, 900) + 0.6 * _band(growl, 900, 2500)
    rng = np.random.default_rng(seed)
    breath = _band(rng.normal(0, 1, n), 300, 3000) * 0.05
    env = np.minimum(1, t / 0.3) * np.minimum(1, (dur - t) / 0.6)
    return (body + breath) * env * 0.5


def dog_bark(dur=1.6, seed=2):
    """kutta — 3 tez bark: 150–400 Hz, sharp attack, AM 3–5 Hz."""
    import numpy as np
    n = int(SR * dur); out = np.zeros(n); rng = np.random.default_rng(seed)
    for k, st in enumerate((0.0, 0.45, 0.95)):
        L = int(0.18 * SR); i = int(st * SR); t = np.arange(L) / SR
        f = 300 * (1 + 0.8 * np.exp(-t * 40))
        b = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 22)
        nz = _band(rng.normal(0, 1, L), 400, 4000) * np.exp(-t * 30) * 0.4
        out[i:i + L] += (b + nz) * 0.5
    return out


def cricket(dur=3.0, seed=3):
    """jheengur — 4.5 kHz tone, 5 Hz pulse."""
    import numpy as np
    n = int(SR * dur); t = np.arange(n) / SR
    pulse = (np.sin(2 * np.pi * 5 * t) > 0.7).astype(float)
    tone = np.sin(2 * np.pi * 4500 * t) * 0.5 + np.sin(2 * np.pi * 5100 * t) * 0.3
    env = np.convolve(pulse, np.hanning(int(0.008 * SR)), mode="same")
    return tone * env * 0.12


def rain(dur=4.0, seed=4):
    """barish — high-passed noise + slow LFO."""
    import numpy as np
    n = int(SR * dur); x = np.random.default_rng(seed).normal(0, 1, n)
    x = _band(x, 800, 12000)
    lfo = 0.85 + 0.15 * np.sin(2 * np.pi * 0.07 * np.arange(n) / SR)
    return x * lfo * 0.16


def river(dur=4.0, seed=5):
    """nadi — mid noise + flow modulation."""
    import numpy as np
    n = int(SR * dur); x = np.random.default_rng(seed).normal(0, 1, n)
    x = _band(x, 120, 3500)
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * 0.13 * np.arange(n) / SR)
    return x * lfo * 0.22


def leaves_steps(dur=3.0, seed=6):
    """sookhe patte — 3 step, broadband 2.5–11 kHz rustle."""
    import numpy as np
    n = int(SR * dur); out = np.zeros(n); rng = np.random.default_rng(seed)
    for st in (0.1, 1.0, 1.9):
        L = int(0.25 * SR); i = int(st * SR); t = np.arange(L) / SR
        nz = _band(rng.normal(0, 1, L), 2500, 11000)
        env = np.exp(-t * 10) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 16 * t)))
        out[i:i + L] += nz * env * 0.35
    return out


PACK = [("wolf", wolf_growl), ("dog", dog_bark), ("cricket", cricket),
        ("rain", rain), ("river", river), ("leaves-steps", leaves_steps)]


def main() -> int:
    import numpy as np
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sound-pack.mp3")
    ap.add_argument("--dir", default="/scratch/work/synthpack")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    d = Path(a.dir); d.mkdir(parents=True, exist_ok=True)
    tracks, names = [], []
    for name, fn in PACK:
        x = fn().astype("float32")
        peak = float(np.max(np.abs(x))) + 1e-9
        x = x / peak * 0.85
        p = d / f"{name}.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype("int16").tobytes())
        tracks.append(x); names.append(name)
    gap = np.zeros(int(0.35 * SR), dtype="float32")
    full = np.concatenate([np.concatenate([t, gap]) for t in tracks])
    full = np.tanh(full * 1.02)
    full *= (10 ** (-17 / 20)) / max(1e-9, float(np.sqrt((full ** 2).mean())))
    wav = d / "pack.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(full, -1, 1) * 32767).astype("int16").tobytes())
    subprocess.run([ffmpeg(), "-v", "quiet", "-y", "-i", str(wav), "-codec:a", "libmp3lame",
                    "-b:a", "192k", a.out], check=False)
    print(json.dumps({"file": a.out, "dur": round(len(full) / SR, 1), "sounds": names}, ensure_ascii=False))
    if a.verify:
        from tools.sound_id import features, load
        sig = json.loads((ROOT / "knowledge" / "sound-signatures.json").read_text(encoding="utf-8"))
        for name, fn in PACK:
            x = fn()
            f = features(x.astype("float32"))
            if not f:
                continue
            print(f"  {name:12s} centroid {f['centroid_hz']:5d} Hz | harm {f['harmonicity']:.2f} | am {f['am_rate_hz']:4.1f} Hz | attack {f['attack_ms']:5.1f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
