#!/usr/bin/env python3
"""
ASTRA — Make Missing: jo sounds internet par theek nahi milte, khud banao.

Yahan 6 sounds banti hain (pure synth, koi download nahi):
  1. rope        — rassi khinchne/khulne ki awaaz (stick-slip + friction)
  2. rope_knot   — gaandh kasne ki awaaz
  3. cloth_rustle— kapde ki sar-sarahat
  4. leaves_dry  — sookhe patton par kadam (crunch)
  5. ladder_wood — lakdi ki seedhi ki char-char
  6. wood_creak  — purana lakdi ka darwaza/farsh

Chalao:
  python3 astra/make_missing.py            # sab banao
  python3 astra/make_missing.py rope       # ek
"""
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library")
SR = 44100
rng = np.random.default_rng(7)


def ff():
    import shutil
    e = shutil.which("ffmpeg")
    if e:
        return e
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def env_adsr(n, a=0.01, d=0.1, s=0.6, r=0.2):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    s_n = max(0, n - a_n - d_n - r_n)
    e = np.concatenate([
        np.linspace(0, 1, max(1, a_n)),
        np.linspace(1, s, max(1, d_n)),
        np.full(s_n, s),
        np.linspace(s, 0, max(1, r_n)),
    ])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def band_noise(n, lo, hi, slope=1.0):
    """Band-limited noise — friction/cloth ke liye."""
    x = rng.normal(0, 1, n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    mask = np.zeros_like(f)
    band = (f >= lo) & (f <= hi)
    mask[band] = 1.0
    # narm kinare
    if band.any():
        idx = np.where(band)[0]
        w = max(1, len(idx) // 8)
        mask[idx[:w]] *= np.linspace(0, 1, w)
        mask[idx[-w:]] *= np.linspace(1, 0, w)
    y = np.fft.irfft(X * mask, n)
    y = y / (np.abs(y).max() + 1e-9)
    return y * slope


def stick_slip(dur=1.6, base=90, jitter=0.35, clicks=26):
    """Rassi/lakdi ki char-char — chhote stick-slip impulses."""
    n = int(SR * dur)
    out = np.zeros(n, np.float32)
    t = 0.0
    for i in range(clicks):
        gap = rng.uniform(0.035, 0.085) * (1 + jitter * rng.normal())
        t += max(0.02, gap)
        if t >= dur - 0.05:
            break
        pos = int(t * SR)
        ln = int(SR * rng.uniform(0.05, 0.12))
        f0 = base * rng.uniform(0.75, 1.35)
        tt = np.arange(ln) / SR
        # damped resonance (lakdi/rasool ka "tak")
        click = np.sin(2 * np.pi * f0 * tt) * np.exp(-tt * 28)
        click += 0.4 * band_noise(ln, 400, 2600) * np.exp(-tt * 40)
        e = env_adsr(ln, 0.002, 0.01, 0.35, 0.05)
        out[pos:pos + ln] += (click * e * rng.uniform(0.5, 1.0))[:len(out[pos:pos + ln])]
    return out


def rope(dur=2.2):
    """Rassi khinchne/khulne ki awaaz: friction + stick-slip."""
    n = int(SR * dur)
    fr = band_noise(n, 250, 4200) * 0.55
    # khinchne ka badhta-jhukta envelope
    t = np.linspace(0, 1, n)
    swell = np.sin(np.pi * t) ** 0.7
    fr *= swell
    # dheere-dheere tez khinch (speed up)
    fr *= (0.7 + 0.5 * t)
    ss = stick_slip(dur, base=110, clicks=22) * 0.5
    x = fr + ss
    x = np.tanh(x * 1.4) * 0.8
    return x


def rope_knot(dur=1.1):
    """Gaandh kasne ki awaaz — chhoti khinch + tak."""
    n = int(SR * dur)
    fr = band_noise(n, 300, 3800) * env_adsr(n, 0.01, 0.08, 0.5, 0.4) * 0.5
    ss = stick_slip(dur, base=140, clicks=9) * 0.7
    x = np.tanh((fr + ss) * 1.6) * 0.8
    return x


def cloth_rustle(dur=1.4):
    """Kapde ki sar-sarahat — tez, patli noise, chhote jhatke."""
    n = int(SR * dur)
    base = band_noise(n, 900, 9000, 0.5)
    mod = np.zeros(n)
    t = 0
    while t < n:
        ln = int(SR * rng.uniform(0.04, 0.14))
        mod[t:t + ln] = np.linspace(0.2, rng.uniform(0.6, 1.0), len(mod[t:t + ln]))
        t += ln + int(SR * rng.uniform(0.01, 0.06))
    x = base * mod
    x *= env_adsr(n, 0.02, 0.15, 0.7, 0.35)
    return np.tanh(x * 1.2) * 0.75


def leaves_dry(dur=2.0, steps=5):
    """Sookhe patton par kadam — har kadam par crunch (chhote dane)."""
    n = int(SR * dur)
    out = np.zeros(n, np.float32)
    for i in range(steps):
        pos = int(SR * (0.15 + i * (dur - 0.3) / steps))
        ln = int(SR * rng.uniform(0.16, 0.26))
        cr = band_noise(ln, 1200, 11000) * np.exp(-np.arange(ln) / (SR * 0.06))
        # dane (granular)
        grains = np.zeros(ln)
        for _ in range(int(rng.integers(18, 34))):
            g = int(rng.integers(0, max(1, ln - 200)))
            gl = int(rng.integers(60, 240))
            grains[g:g + gl] += rng.uniform(0.3, 1.0) * np.exp(-np.arange(gl) / (SR * 0.01))
        x = (cr * 0.7 + grains * 0.6)
        out[pos:pos + ln] += (x * env_adsr(ln, 0.002, 0.03, 0.3, 0.08))[:len(out[pos:pos + ln])]
    return np.tanh(out * 1.5) * 0.8


def ladder_wood(dur=1.8):
    """Lakdi ki seedhi — char-char + pair rakhne ka thap."""
    n = int(SR * dur)
    creak = stick_slip(dur, base=180, jitter=0.5, clicks=14) * 0.8
    out = np.zeros(n, np.float32)
    out[:len(creak)] += creak
    for i, tt in enumerate((0.15, 0.95)):
        pos = int(SR * tt)
        ln = int(SR * 0.22)
        thud = np.sin(2 * np.pi * 95 * np.arange(ln) / SR) * np.exp(-np.arange(ln) / (SR * 0.05))
        thud += 0.5 * band_noise(ln, 200, 1800) * np.exp(-np.arange(ln) / (SR * 0.04))
        out[pos:pos + ln] += (thud * 0.7)[:len(out[pos:pos + ln])]
    return np.tanh(out * 1.3) * 0.8


def wood_creak(dur=2.4):
    """Purana lakdi ka darwaza/farsh — dheemi char-char."""
    n = int(SR * dur)
    creak = stick_slip(dur, base=70, jitter=0.6, clicks=10)
    creak *= np.linspace(0.4, 1.0, n)[:len(creak)]
    air = band_noise(n, 120, 1400) * env_adsr(n, 0.2, 0.4, 0.5, 0.6) * 0.18
    x = creak + air
    return np.tanh(x * 1.4) * 0.8


MAKERS = {
    "rope": (rope, "foley"),
    "rope_knot": (rope_knot, "foley"),
    "cloth_rustle": (cloth_rustle, "foley"),
    "leaves_dry": (leaves_dry, "footsteps"),
    "ladder_wood": (ladder_wood, "footsteps"),
    "wood_creak": (wood_creak, "door"),
}


def save(name, x, folder):
    outdir = os.path.join(LIB, folder)
    os.makedirs(outdir, exist_ok=True)
    wav = os.path.join(outdir, f".{name}.wav")
    x = np.asarray(x, dtype=np.float32)
    x = x / (np.abs(x).max() + 1e-9) * 0.92
    import wave
    with wave.open(wav, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    mp3 = os.path.join(outdir, f"{name}.mp3")
    subprocess.run([ff(), "-loglevel", "error", "-y", "-i", wav,
                    "-af", "highpass=f=60,alimiter=limit=0.95,loudnorm=I=-19:TP=-2:LRA=9",
                    "-ac", "1", "-ar", "44100", "-b:a", "64k", mp3], check=True)
    os.remove(wav)
    return mp3


def main():
    want = sys.argv[1:] or list(MAKERS)
    for name in want:
        if name not in MAKERS:
            print("pata nahi:", name)
            continue
        fn, folder = MAKERS[name]
        x = fn()
        p = save(name, x, folder)
        print("BANA", os.path.relpath(p, LIB), round(len(x) / SR, 2), "s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
