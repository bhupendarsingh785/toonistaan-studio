#!/usr/bin/env python3
"""Beat Engine v2 — majboot, layered, stereo, arrangement ke saath.

v1 se aage (jo kamzor tha):
  • DRUMS layered: kick = sub + body + click; snare = tone + noise + clap layer;
    hat = 6-square 808 style + noise; tabla = resonant modes; clap = 4 bursts
  • GROOVE: swing, velocity humanize, ghost notes, fills har 8 bar
  • CHORDS: har mood ka 4-chord progression + voice-leading pads
  • BASS: chord root follow karta hai, rhythm ke saath (sirf drone nahi)
  • STEREO: hats L/R, pads Haas widen, stereo reverb
  • ARRANGEMENT: intro → build → drop → break → drop → outro (+ riser, impact)
  • MIX: HPF, shelf EQ, bus compress, limiter, -14 LUFS

CLI: python tools/music_make2.py --mood horror --bars 32 --out x.mp3
"""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

SR = 44100
NOTE = {"C": 261.63, "C#": 277.18, "D": 293.66, "D#": 311.13, "E": 329.63, "F": 349.23,
        "F#": 369.99, "G": 392.0, "G#": 415.3, "A": 440.0, "A#": 466.16, "B": 493.88}
SWAR = ["Sa", "Re", "Ga", "Ma", "Pa", "Dha", "Ni"]
SCALES = {"bilawal": [0, 2, 4, 5, 7, 9, 11], "khamaj": [0, 2, 4, 5, 7, 9, 10],
          "kafi": [0, 2, 3, 5, 7, 9, 10], "bhairavi": [0, 1, 3, 5, 7, 8, 10],
          "bhairav": [0, 1, 4, 5, 7, 8, 11], "yaman": [0, 2, 4, 6, 7, 9, 11],
          "asavari": [0, 2, 3, 5, 7, 8, 10]}
PATTERNS = {
    "keherwa":    {"kick": "X.......X.......", "snare": "....X.......X...", "hat": "X.X.X.X.X.X.X.X.", "bpm": 92},
    "dadra":      {"kick": "X.....X.........", "snare": "......X.....X...", "hat": "X...X...X...X...", "bpm": 84},
    "teen":       {"kick": "X.....X.....X...", "snare": "....X.......X..X", "hat": "X.X.X.X.X.X.X.X.", "bpm": 100},
    "four_floor": {"kick": "X...X...X...X...", "snare": "....X.......X...", "hat": "..X...X...X...X.", "bpm": 124},
    "boom_bap":   {"kick": "X.....X..X......", "snare": "....X.......X...", "hat": "X.X.X.X.X.X.X.X.", "bpm": 90},
    "trap":       {"kick": "X.......X...X...", "snare": "....X.......X...", "hat": "X.XXX.XXX.XXX.XX", "bpm": 140},
    "breakbeat":  {"kick": "X..X....X.X.....", "snare": "....X.......X...", "hat": "X.X.X.X.X.X.X.X.", "bpm": 165},
    "one_drop":   {"kick": "........X.......", "snare": "....X.......X...", "hat": "X.X.X.X.X.X.X.X.", "bpm": 78},
    "afrobeat":   {"kick": "X..X..X...X..X..", "snare": "..X..X..X..X..X.", "hat": "X.XX.X.XX.XX.X.X", "bpm": 108},
    # asli naap se (Hum Bewafa unwind): kick 1/9-10/13/16, snare 1/8/13/15-16, hat kam
    # asli naap (Ganga Ke Kinare): kick 7-10/12-13, snare 13-16, hat 10-12 = laggi
    "bhakti":     {"kick": "......XXXX.XX...", "snare": "............XXXX", "hat": ".........XXX....", "bpm": 132},
    "unwind":     {"kick": "X.......XX..X..X", "snare": "X......X....X.XX", "hat": "X.X..X......XX..", "bpm": 76},
}
# mood → pattern, scale, progression (scale degrees 1..7), swing, energy
MOODS = {
    "epic":     {"pat": "teen", "scale": "bilawal", "prog": [1, 5, 6, 4], "swing": 0.0, "energy": 1.0, "pad": "wide"},
    "horror":   {"pat": "one_drop", "scale": "bhairavi", "prog": [1, 6, 1, 7], "swing": 0.0, "energy": 0.7, "pad": "dark"},
    "sad":      {"pat": "dadra", "scale": "asavari", "prog": [1, 4, 6, 5], "swing": 0.05, "energy": 0.5, "pad": "soft"},
    "romantic": {"pat": "keherwa", "scale": "khamaj", "prog": [1, 6, 4, 5], "swing": 0.12, "energy": 0.7, "pad": "warm"},
    "action":   {"pat": "breakbeat", "scale": "bhairav", "prog": [1, 7, 6, 5], "swing": 0.0, "energy": 1.2, "pad": "wide"},
    "happy":    {"pat": "afrobeat", "scale": "bilawal", "prog": [1, 5, 6, 4], "swing": 0.10, "energy": 1.1, "pad": "warm"},
    "lofi":     {"pat": "boom_bap", "scale": "kafi", "prog": [1, 6, 2, 5], "swing": 0.18, "energy": 0.6, "pad": "soft"},
    "trap":     {"pat": "trap", "scale": "kafi", "prog": [1, 6, 5, 6], "swing": 0.0, "energy": 1.2, "pad": "dark"},
    # 3 unwind gaano ke naap se (Saagar Kinare / Hum Bewafa / Bade Acche): 76-80 BPM, minor, sparse
    # Ganga Ke Kinare (132 BPM) ke naap se — laggi-style dholak
    "bhakti":   {"pat": "bhakti", "scale": "bilawal", "prog": [1, 5, 4, 5], "swing": 0.06, "energy": 0.9, "pad": "warm"},
    "unwind":   {"pat": "unwind", "scale": "asavari", "prog": [1, 5, 4, 1], "swing": 0.10, "energy": 0.45, "pad": "soft"},
}


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


# ---------------------------------------------------------------- drum voices
def kick(dur=0.5, f_hi=120, f_lo=44, click=0.3, seed=1):
    import numpy as np
    t = np.arange(int(SR * dur)) / SR
    f = f_lo + (f_hi - f_lo) * np.exp(-t * 32)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6.5)
    body = np.sin(2 * np.pi * np.cumsum(f * 2.1) / SR) * np.exp(-t * 18) * 0.35
    clk = np.random.default_rng(seed).normal(0, 1, len(t)) * np.exp(-t * 260) * click
    out = sub + body + clk
    return out / (np.max(np.abs(out)) + 1e-9) * 0.95


def snare(dur=0.28, seed=2, clap=False):
    import numpy as np
    t = np.arange(int(SR * dur)) / SR
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, len(t)) * np.exp(-t * 22)
    # band-pass flavour: difference + smooth
    noise = np.convolve(noise, np.ones(4) / 4, mode="same")
    tone = (np.sin(2 * np.pi * 180 * t) + 0.6 * np.sin(2 * np.pi * 330 * t)) * np.exp(-t * 34) * 0.5
    if clap:
        bursts = np.zeros(len(t))
        for d in (0.0, 0.012, 0.026, 0.041):
            i = int(d * SR)
            n = min(len(t) - i, int(0.03 * SR))
            bursts[i:i + n] += rng.normal(0, 1, n) * np.exp(-np.arange(n) / SR * 90)
        noise = bursts
    out = noise * 0.6 + tone
    return out / (np.max(np.abs(out)) + 1e-9) * 0.85


def hat(dur=0.08, open_=False, seed=3):
    import numpy as np
    d = 0.30 if open_ else dur
    t = np.arange(int(SR * d)) / SR
    # 808-style: 6 square waves (metallic) + noise
    metal = np.zeros(len(t))
    for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0):
        metal += np.sign(np.sin(2 * np.pi * f * t))
    metal /= 6
    noise = np.random.default_rng(seed).normal(0, 1, len(t))
    sig = (metal * 0.7 + noise * 0.3)
    sig = np.diff(np.concatenate([[0], sig]))          # high-pass
    env = np.exp(-t * (10 if open_ else 60))
    out = sig * env
    return out / (np.max(np.abs(out)) + 1e-9) * 0.5


def tabla(dur=0.22, high=False):
    import numpy as np
    t = np.arange(int(SR * dur)) / SR
    f0 = 330 if high else 155
    f = f0 * (1 + 0.7 * np.exp(-t * 45))
    modes = (np.sin(2 * np.pi * np.cumsum(f) / SR) +
             0.4 * np.sin(2 * np.pi * f0 * 2.02 * t) +
             0.2 * np.sin(2 * np.pi * f0 * 3.4 * t))
    out = modes * np.exp(-t * 12)
    return out / (np.max(np.abs(out)) + 1e-9) * 0.7


# ---------------------------------------------------------------- tonal voices
_PLUCK_CACHE: dict = {}


def pluck(freq, dur=0.7, bright=0.6, seed=0):
    import numpy as np
    key = (round(freq, 1), round(dur, 2), round(bright, 2))
    if key in _PLUCK_CACHE:
        return _PLUCK_CACHE[key]
    n = max(2, int(SR / freq))
    rng = np.random.default_rng(seed + int(freq) % 997)
    buf = rng.normal(0, 1, n)
    out = np.zeros(int(SR * dur))
    damp = 0.5 * (0.994 - 0.05 * (1 - bright))
    for i in range(len(out)):
        out[i] = buf[i % n]
        buf[i % n] = (buf[i % n] + buf[(i + 1) % n]) * damp
    out = out * np.exp(-np.arange(len(out)) / SR * 2.2)
    _PLUCK_CACHE[key] = out
    return out


def pad_chord(freqs, dur, kind="wide", seed=0):
    import numpy as np
    t = np.arange(int(SR * dur)) / SR
    out = np.zeros(len(t))
    for i, f in enumerate(freqs):
        for det in (-0.004, 0.0, 0.004):          # 3 detuned layers = chorus
            out += np.sin(2 * np.pi * f * (1 + det) * t) * 0.33
        out += np.sin(2 * np.pi * f * 2 * t) * 0.10
        out += np.sin(2 * np.pi * f * 3 * t) * 0.05
    out /= max(1, len(freqs) * 1.5)
    lfo = 0.88 + 0.12 * np.sin(2 * np.pi * 0.13 * t + seed)
    env = np.minimum(1, t / 0.5) * np.minimum(1, (dur - t) / 0.7)
    out = out * lfo * env
    if kind == "dark":
        out = np.tanh(out * 1.6) * 0.85
    return out


def riser(dur=2.0, seed=5):
    import numpy as np
    t = np.arange(int(SR * dur)) / SR
    noise = np.random.default_rng(seed).normal(0, 1, len(t))
    noise = np.convolve(noise, np.ones(3) / 3, mode="same")
    sweep = np.sin(2 * np.pi * (200 + 2200 * (t / dur) ** 2) * t) * 0.25
    env = (t / dur) ** 2
    return (noise * 0.5 + sweep) * env * 0.5


def impact(dur=1.6, seed=6):
    import numpy as np
    k = kick(0.8, 150, 38, 0.5, seed)
    t = np.arange(int(SR * dur)) / SR
    tail = np.random.default_rng(seed).normal(0, 1, len(t)) * np.exp(-t * 3.0) * 0.25
    out = np.zeros(len(t)); out[:len(k)] += k
    out += tail
    return out / (np.max(np.abs(out)) + 1e-9) * 0.9


# ---------------------------------------------------------------- mix helpers
def shelf(x, fc=6000, gain_db=2.0):
    """FFT shelf — tez aur safe (per-sample loop nahi)."""
    import numpy as np
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    curve = 1 + (10 ** (gain_db / 20) - 1) / (1 + (fc / (f + 1e-9)) ** 2)
    return np.fft.irfft(X * curve, n)


def hpf(x, fc=28):
    import numpy as np
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    curve = 1 / (1 + (fc / (f + 1e-9)) ** 2)
    return np.fft.irfft(X * curve, n)


def compress(x, thresh_db=-14, ratio=3.0, block=256):
    """block-wise envelope compressor (vectorized, tez)."""
    import numpy as np
    n = len(x)
    pad = (-n) % block
    xp = np.pad(x, (0, pad))
    blocks = xp.reshape(-1, block)
    env = np.sqrt((blocks ** 2).mean(1)) + 1e-9
    # smooth envelope
    k = np.ones(4) / 4
    env = np.convolve(env, k, mode="same")
    th = 10 ** (thresh_db / 20)
    gain = np.ones_like(env)
    m = env > th
    gain[m] = (th / env[m]) ** (1 - 1 / ratio)
    g = np.repeat(gain, block)[:n]
    return x * g


def stereo_widen(x, amount=0.35):
    import numpy as np
    d = int(0.012 * SR)
    left = x.copy()
    right = np.concatenate([np.zeros(d), x[:-d]]) * (1 + amount)
    left = left * (1 - amount * 0.3)
    return np.stack([left, right], axis=1)


def _fftconv(a, b, n):
    import numpy as np
    L = 1 << int(np.ceil(np.log2(len(a) + len(b) - 1)))
    return np.fft.irfft(np.fft.rfft(a, L) * np.fft.rfft(b, L), L)[:n]


def reverb_stereo(x, wet=0.25, seed=7):
    """FFT convolution — tez (loop nahi)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    n = len(x)
    out = np.zeros((n, 2))
    for ch, delays in enumerate([(0.0297, 0.0371, 0.0411), (0.0313, 0.0397, 0.0437)]):
        acc = x.copy()
        for dly in delays:
            d = int(SR * dly)
            tail = rng.normal(0, 1, d) * np.exp(-np.arange(d) / (d * 0.45))
            acc = acc + _fftconv(x, tail, n) * wet * 0.5
        out[:, ch] = acc
    return out


# ---------------------------------------------------------------- build
def build(mood="epic", bars=32, root="C", bpm=None, pattern=None, scale=None, seed=0):
    import numpy as np
    m = MOODS.get(mood, MOODS["epic"])
    pat = PATTERNS[pattern or m["pat"]]
    bpm = bpm or pat["bpm"]
    scale = scale or m["scale"]
    steps = SCALES[scale]
    base = NOTE[root]
    step = 60.0 / bpm / 4
    total_steps = bars * 16
    n = int(total_steps * step * SR) + SR
    drums = np.zeros(n); bass = np.zeros(n); lead = np.zeros(n); pads = np.zeros(n); fx = np.zeros(n)
    rng = np.random.default_rng(seed)

    K = kick(); S = snare(); C = snare(clap=True, seed=9); H = hat(); HO = hat(open_=True)
    T1 = tabla(); T2 = tabla(high=True)

    def note_hz(deg, octave=4):
        # deg 1..7 (scale degree) → Hz
        idx = (deg - 1) % 7
        oct_shift = (deg - 1) // 7
        semi = steps[idx] + 12 * (octave - 4 + oct_shift)
        return base * (2 ** (semi / 12))

    sections = []
    for b in range(bars):
        if b < max(2, bars // 8):
            sections.append("intro")
        elif b < bars // 2:
            sections.append("build")
        elif b < bars // 2 + max(1, bars // 16):
            sections.append("break")
        elif b < bars - max(1, bars // 12):
            sections.append("drop")
        else:
            sections.append("outro")

    for bar in range(bars):
        sec = sections[bar]
        chord_deg = m["prog"][bar % len(m["prog"])]
        energy = m["energy"] * {"intro": 0.45, "build": 0.8, "break": 0.35, "drop": 1.0, "outro": 0.5}[sec]
        for st in range(16):
            swing = m["swing"] * step * (1 if st % 2 else 0)
            i = int((bar * 16 + st) * step * SR + swing * SR)
            if i >= n - 4096:
                continue
            vel = 1.0 - 0.18 * rng.random()                     # humanize
            if pat["kick"][st] == "X" and energy > 0.5:
                drums[i:i + len(K)] += K * 0.95 * vel
            if pat["snare"][st] == "X":
                drums[i:i + len(S)] += S * 0.8 * vel
                if sec in ("drop", "build") and bar % 4 == 3:
                    drums[i:i + len(C)] += C * 0.35 * vel
            if pat["hat"][st] == "X":
                gain = (0.55 if st % 4 else 0.75) * (0.6 + 0.4 * energy)
                drums[i:i + len(H)] += H * gain * vel
                if st == 14 and bar % 4 == 3:
                    drums[i:i + len(HO)] += HO * 0.35
            # ghost notes
            if rng.random() < 0.06 * energy:
                drums[i:i + len(H)] += H * 0.18
            if st in (0, 8) and bar % 4 == 0:
                drums[i:i + len(T1)] += T1 * 0.55
            if st == 12 and bar % 2 == 1:
                drums[i:i + len(T2)] += T2 * 0.45 * energy
        # bass: chord root + rhythm (drop me 8th, warna half)
        root_hz = note_hz(chord_deg, 2)
        fifth_hz = note_hz(chord_deg + 4, 2)
        for st in range(16):
            hit = (st % 4 == 0) if sec != "drop" else (st % 2 == 0)
            if not hit:
                continue
            i = int((bar * 16 + st) * step * SR)
            dur = int(step * (3.4 if sec != "drop" else 1.6) * SR)
            t = np.arange(dur) / SR
            f = root_hz if (st // 4) % 2 == 0 else fifth_hz
            env = np.minimum(1, t / 0.01) * np.exp(-t * 2.2)
            bs = (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 2 * t)) * env
            if i + dur < n:
                bass[i:i + dur] += bs * 0.5 * energy
        # pad: 3-note chord (root, third, fifth of the scale degree)
        chord = [note_hz(chord_deg, 4), note_hz(chord_deg + 2, 4), note_hz(chord_deg + 4, 4)]
        p = pad_chord(chord, 16 * step, m["pad"], seed=bar)
        i = int(bar * 16 * step * SR)
        if i + len(p) < n:
            pads[i:i + len(p)] += p * 0.30 * (0.6 + 0.4 * energy)
        # melody: motif (same rhythm, changing notes) — random nahi
        motif = [0, 2, 4, 2] if bar % 2 == 0 else [4, 3, 2, 1]
        if sec in ("drop", "build") and rng.random() < 0.85:
            for bi, deg_off in enumerate(motif):
                j = int((bar * 16 + bi * 4) * step * SR)
                if j + 4096 < n:
                    f = note_hz(chord_deg + deg_off, 5)
                    pl = pluck(f, 0.7, 0.6, seed=bar * 10 + bi)
                    lead[j:j + len(pl)] += pl * 0.26 * energy
        # fills har 8 bar
        if bar % 8 == 7 and sec != "intro":
            for k in range(4):
                i = int((bar * 16 + 12 + k) * step * SR)
                if i + len(T2) < n:
                    drums[i:i + len(T2)] += T2 * (0.35 + 0.1 * k)

    # riser + impact at section changes
    for bar in range(1, bars):
        if sections[bar] != sections[bar - 1]:
            i = int(bar * 16 * step * SR)
            r = riser(1.8, seed=bar)
            j = max(0, i - len(r))
            fx[j:j + len(r)] += r * 0.5
            imp = impact(1.8, seed=bar + 3)
            if i + len(imp) < n:
                fx[i:i + len(imp)] += imp * 0.55

    # sidechain duck (pads+bass) on kick
    duck = np.ones(n)
    for bar in range(bars):
        for st in (0, 8):
            i = int((bar * 16 + st) * step * SR)
            ln = int(0.16 * SR)
            if i + ln < n:
                duck[i:i + ln] = np.minimum(duck[i:i + ln], np.linspace(0.42, 1.0, ln))
    pads *= duck
    bass *= duck

    # ---- mix: stereo
    dr_l = drums + fx * 0.8
    hats_only = drums * 0.0            # keep simple: pan whole drums slightly wide
    dr_st = stereo_widen(dr_l, 0.18)
    bass_st = np.stack([bass, bass], axis=1)
    lead_st = stereo_widen(lead, 0.45)
    pad_st = reverb_stereo(pads, wet=0.3)
    pad_st[:, 0] += pads * 0.5
    pad_st[:, 1] += pads * 0.5

    L = dr_st[:, 0] * 0.9 + bass_st[:, 0] * 0.85 + lead_st[:, 0] * 0.8 + pad_st[:, 0] * 0.75
    R = dr_st[:, 1] * 0.9 + bass_st[:, 1] * 0.85 + lead_st[:, 1] * 0.8 + pad_st[:, 1] * 0.75
    out = np.stack([L, R], axis=1)
    # HPF → compress → EQ → limit
    out[:, 0] = shelf(compress(hpf(out[:, 0])), 6000, 2.0)
    out[:, 1] = shelf(compress(hpf(out[:, 1])), 6000, 2.0)
    out = np.tanh(out * 1.15)
    rms = float(np.sqrt((out ** 2).mean())) + 1e-9
    out *= (10 ** (-14 / 20)) / rms
    out = out / max(1.0, float(np.max(np.abs(out))) / 0.89)
    nf = int(0.2 * SR)
    out[:nf] *= np.linspace(0, 1, nf)[:, None]
    out[-nf:] *= np.linspace(1, 0, nf)[:, None]
    info = {"mood": mood, "pattern": m["pat"] if not pattern else pattern, "scale": scale,
            "bpm": bpm, "bars": bars, "root": root, "dur": round(len(out) / SR, 2),
            "progression": m["prog"], "sections": sections,
            "swar": SWAR, "scale_steps": steps, "stereo": True}
    return out, info


def write(sig, out: Path):
    import numpy as np, wave
    wav = out.with_suffix(".wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(sig, -1, 1) * 32767).astype("int16").tobytes())
    if out.suffix.lower() == ".mp3":
        subprocess.run([ffmpeg(), "-v", "quiet", "-y", "-i", str(wav),
                        "-codec:a", "libmp3lame", "-b:a", "192k", str(out)], check=False)
        wav.unlink(missing_ok=True)
        return out
    return wav


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mood", default="epic")
    ap.add_argument("--bars", type=int, default=32)
    ap.add_argument("--root", default="C")
    ap.add_argument("--bpm", type=int, default=0)
    ap.add_argument("--pattern", default="")
    ap.add_argument("--scale", default="")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="music/out.mp3")
    a = ap.parse_args()
    sig, info = build(a.mood, a.bars, a.root, a.bpm or None, a.pattern or None, a.scale or None, a.seed)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    p = write(sig, out)
    import numpy as np
    info.update({"file": str(p), "peak": round(float(np.max(np.abs(sig))), 2),
                 "rms_dbfs": round(20 * float(np.log10(max(1e-9, float(np.sqrt((sig ** 2).mean()))))), 1)})
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
