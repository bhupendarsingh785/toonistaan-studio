#!/usr/bin/env python3
"""Beat + Sur engine — apni beats aur apne saaton swar (bina kisi sample ke).

Kya hai isme:
  1) DRUMS      — kick, snare, clap, hat, tabla-na (sab **synthesis**, koi sample nahi)
  2) TAAL       — keherwa, dadra, teen taal (Indian) + four-on-floor, boom-bap, trap,
                  breakbeat, one-drop, afrobeat (world)
  3) SAAT SWAR  — Sa Re Ga Ma Pa Dha Ni + komal/tivra; scales: Bilawal (major), Khamaj,
                  Kafi, Bhairav, Bhairavi, Yaman, Asavari
  4) MELODY     — Karplus-Strong pluck + additive pad (raag ke sur, seedha nahi)
  5) MIX        — sidechain duck, reverb, limiter, loudnorm

CLI:
  python tools/music_make.py --mood epic --bars 16 --out x.mp3
  python tools/music_make.py --list                 # sab patterns/scales
"""
from __future__ import annotations
import argparse, json, math, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SR = 44100
NOTE_BASE = {"C": 261.63, "C#": 277.18, "D": 293.66, "D#": 311.13, "E": 329.63,
             "F": 349.23, "F#": 369.99, "G": 392.00, "G#": 415.30, "A": 440.00,
             "A#": 466.16, "B": 493.88}

# ---------- 7 swar (sargam) ----------
SWAR = ["Sa", "Re", "Ga", "Ma", "Pa", "Dha", "Ni"]
# har scale = 12 semitone grid me swaron ke index (0=Sa)
SCALES = {
    "bilawal":   [0, 2, 4, 5, 7, 9, 11],   # major
    "khamaj":    [0, 2, 4, 5, 7, 9, 10],
    "kafi":      [0, 2, 3, 5, 7, 9, 10],
    "bhairavi":  [0, 1, 3, 5, 7, 8, 10],
    "bhairav":   [0, 1, 4, 5, 7, 8, 11],
    "yaman":     [0, 2, 4, 6, 7, 9, 11],   # teevra Ma
    "asavari":   [0, 2, 3, 5, 7, 8, 10],
}

# ---------- taal / patterns (16 steps = 1 bar) ----------
# X = hit, . = khaali; har pattern 16 steps
PATTERNS = {
    "keherwa":     {"kick": "X.......X.......", "snare": "....X.......X...", "hat": "X.X.X.X.X.X.X.X.", "bpm": 92},
    "dadra":       {"kick": "X.....X.........", "snare": "......X.....X...", "hat": "X...X...X...X...", "bpm": 84},
    "teen":        {"kick": "X.....X.....X...", "snare": "....X.......X..X", "hat": "X.X.X.X.X.X.X.X.", "bpm": 100},
    "four_floor":  {"kick": "X...X...X...X...", "snare": "....X.......X...", "hat": "..X...X...X...X.", "bpm": 124},
    "boom_bap":    {"kick": "X.....X..X......", "snare": "....X.......X...", "hat": "X.X.X.X.X.X.X.X.", "bpm": 90},
    "trap":        {"kick": "X.......X...X...", "snare": "....X.......X...", "hat": "X.XXX.XXX.XXX.XX", "bpm": 140},
    "breakbeat":   {"kick": "X..X....X.X.....", "snare": "....X.......X...", "hat": "X.X.X.X.X.X.X.X.", "bpm": 165},
    "one_drop":    {"kick": "........X.......", "snare": "....X.......X...", "hat": "X.X.X.X.X.X.X.X.", "bpm": 78},
    "afrobeat":    {"kick": "X..X..X...X..X..", "snare": "..X..X..X..X..X.", "hat": "X.XX.X.XX.XX.X.X", "bpm": 108},
}

MOODS = {   # mood → (pattern, scale, energy, bass_style, pad)
    "epic":     {"pattern": "teen",       "scale": "bilawal",  "energy": 1.0, "bass": "root_fifth", "pad": "wide"},
    "horror":   {"pattern": "one_drop",   "scale": "bhairavi", "energy": 0.6, "bass": "drone",      "pad": "dark"},
    "sad":      {"pattern": "dadra",      "scale": "asavari",  "energy": 0.5, "bass": "root",       "pad": "soft"},
    "romantic": {"pattern": "keherwa",    "scale": "khamaj",   "energy": 0.7, "bass": "root_fifth", "pad": "warm"},
    "action":   {"pattern": "breakbeat",  "scale": "bhairav",  "energy": 1.2, "bass": "root_fifth", "pad": "wide"},
    "happy":    {"pattern": "afrobeat",   "scale": "bilawal",  "energy": 1.1, "bass": "root_fifth", "pad": "warm"},
    "lofi":     {"pattern": "boom_bap",   "scale": "kafi",     "energy": 0.6, "bass": "root",       "pad": "soft"},
    "trap":     {"pattern": "trap",       "scale": "kafi",     "energy": 1.2, "bass": "drone",      "pad": "dark"},
}


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


# ---------- synthesis ----------
def kick(dur=0.42):
    import numpy as np
    t = np.arange(int(SR * dur)) / SR
    f = 110 * np.exp(-t * 28) + 45
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    click = np.random.default_rng(1).normal(0, 1, len(t)) * np.exp(-t * 220) * 0.25
    return (body + click) * 0.9


def snare(dur=0.22):
    import numpy as np
    t = np.arange(int(SR * dur)) / SR
    noise = np.random.default_rng(2).normal(0, 1, len(t)) * np.exp(-t * 26)
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 30) * 0.4
    return (noise * 0.5 + tone) * 0.8


def hat(dur=0.06, open_=False):
    import numpy as np
    d = 0.22 if open_ else dur
    t = np.arange(int(SR * d)) / SR
    n = np.random.default_rng(3).normal(0, 1, len(t))
    # high-pass by differencing
    n = np.diff(np.concatenate([[0], n]))
    return n * np.exp(-t * (12 if open_ else 70)) * 0.35


def tabla(dur=0.18, high=False):
    import numpy as np
    t = np.arange(int(SR * dur)) / SR
    f0 = 320 if high else 150
    f = f0 * (1 + 0.6 * np.exp(-t * 40))
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)
    ring = np.sin(2 * np.pi * f0 * 2.2 * t) * np.exp(-t * 24) * 0.3
    return (tone + ring) * 0.7


def pluck(freq, dur=0.6, bright=0.6):
    """Karplus-Strong — asli taar jaisa, sample ke bina."""
    import numpy as np
    n = max(2, int(SR / freq))
    rng = np.random.default_rng(int(freq) % 9999)
    buf = rng.normal(0, 1, n)
    out = np.zeros(int(SR * dur))
    for i in range(len(out)):
        out[i] = buf[i % n]
        buf[i % n] = (buf[i % n] + buf[(i + 1) % n]) * 0.5 * (0.995 - 0.05 * (1 - bright))
    return out * np.exp(-np.arange(len(out)) / SR * 2.0)


def pad(freqs, dur, kind="wide"):
    import numpy as np
    t = np.arange(int(SR * dur)) / SR
    sig = np.zeros(len(t))
    for i, f in enumerate(freqs):
        det = 1 + (0.002 * (i - len(freqs) / 2))
        sig += np.sin(2 * np.pi * f * det * t) * (0.6 if i == 0 else 0.35)
        sig += np.sin(2 * np.pi * f * 2 * t) * 0.12
    lfo = 0.85 + 0.15 * np.sin(2 * np.pi * 0.15 * t)
    env = np.minimum(1, t / 0.6) * np.minimum(1, (dur - t) / 0.8)
    out = sig * lfo * env / max(1, len(freqs))
    if kind == "dark":
        out = np.tanh(out * 1.4) * 0.8
    return out


def reverb(x, wet=0.22, decay=0.45):
    import numpy as np
    delays = [int(SR * d) for d in (0.0297, 0.0371, 0.0411, 0.0437)]
    out = x.copy()
    for d in delays:
        ir = np.zeros(d)
        ir[0] = 1.0
        tail = np.random.default_rng(7).normal(0, 1, d) * np.exp(-np.arange(d) / (d * decay))
        out[:len(x)] += np.convolve(x, np.concatenate([ir[:1], tail * wet]))[:len(x)]
    return out


# ---------- music build ----------
def scale_freqs(root: str, scale: str, octaves=(3, 4, 5)):
    base = NOTE_BASE[root]
    steps = SCALES[scale]
    out = []
    for o in octaves:
        for s in steps:
            out.append(base * (2 ** ((s + 12 * (o - 4)) / 12)))
    return out


def build(mood: str, bars: int = 16, root: str = "C", bpm: int | None = None,
          pattern: str | None = None, scale: str | None = None, seed: int = 0):
    import numpy as np
    m = MOODS.get(mood, MOODS["epic"])
    pat_name = pattern or m["pattern"]
    pat = PATTERNS[pat_name]
    bpm = bpm or pat["bpm"]
    sc_name = scale or m["scale"]
    step_dur = 60.0 / bpm / 4            # 16th note
    total = int(bars * 16 * step_dur * SR) + SR
    mix = np.zeros(total)
    drums = np.zeros(total)
    bass = np.zeros(total)
    lead = np.zeros(total)
    pads = np.zeros(total)
    rng = np.random.default_rng(seed)
    freqs = scale_freqs(root, sc_name)

    k, s, h, t_lo, t_hi = kick(), snare(), hat(), tabla(), tabla(high=True)
    open_hat = hat(open_=True)

    for bar in range(bars):
        for step in range(16):
            i = int((bar * 16 + step) * step_dur * SR)
            if i + len(k) > total:
                break
            ch_k = pat["kick"][step] == "X"
            ch_s = pat["snare"][step] == "X"
            ch_h = pat["hat"][step] == "X"
            if ch_k:
                drums[i:i + len(k)] += k * 0.95
            if ch_s:
                drums[i:i + len(s)] += s * 0.75
                if bar % 2 == 1 and step == 12:
                    drums[i:i + len(t_hi)] += t_hi * 0.5     # tabla ka jawab
            if ch_h:
                drums[i:i + len(h)] += h * (0.55 if step % 4 else 0.8)
                if step == 14 and bar % 4 == 3:
                    drums[i:i + len(open_hat)] += open_hat * 0.4
            if step in (0, 8) and bar % 4 == 0:
                drums[i:i + len(t_lo)] += t_lo * 0.6

        # bass: har bar ke shuru me root (+ fifth kabhi)
        root_f = freqs[0] / 2
        fifth_f = freqs[4] / 2
        i = int(bar * 16 * step_dur * SR)
        blen = int(16 * step_dur * SR)
        t = np.arange(blen) / SR
        if m["bass"] == "drone":
            bsig = np.sin(2 * np.pi * root_f * t) * (0.9 + 0.1 * np.sin(2 * np.pi * 0.2 * t))
        elif m["bass"] == "root_fifth":
            bsig = np.sin(2 * np.pi * root_f * t) * 0.8
            bsig[blen // 2:] = np.sin(2 * np.pi * fifth_f * t[:blen - blen // 2]) * 0.7
        else:
            bsig = np.sin(2 * np.pi * root_f * t) * 0.75
        env = np.minimum(1, t / 0.02) * np.exp(-t * 1.2)
        bass[i:i + blen] += bsig * env * 0.6

        # melody: raag ke sur, seedha nahi — thoda upar-neeche
        for beat in range(4):
            if rng.random() < 0.55 * m["energy"]:
                deg = int(rng.integers(0, len(freqs)))
                f = freqs[deg]
                j = int((bar * 16 + beat * 4 + int(rng.integers(0, 3))) * step_dur * SR)
                p = pluck(f, dur=min(0.9, step_dur * 6), bright=0.55 + 0.2 * rng.random())
                if j + len(p) < total:
                    lead[j:j + len(p)] += p * 0.35

        # pad: poore bar
        chord = [freqs[0], freqs[2], freqs[4]] if bar % 2 == 0 else [freqs[1], freqs[3], freqs[5]]
        p = pad(chord, 16 * step_dur, m["pad"])
        pads[i:i + min(len(p), total - i)] += p[:max(0, min(len(p), total - i))] * 0.22

    # sidechain: drums ke waqt pad/bass ko dabao
    duck = np.ones(total)
    for bar in range(bars):
        for step in (0, 8):
            i = int((bar * 16 + step) * step_dur * SR)
            n = int(0.18 * SR)
            if i + n < total:
                duck[i:i + n] = np.minimum(duck[i:i + n], np.linspace(0.45, 1.0, n))
    pads *= duck
    bass *= duck

    out = drums * 0.9 + bass * 0.8 + lead * 0.8 + reverb(pads, 0.3) * 0.7
    out = out[:int(bars * 16 * step_dur * SR)]
    # limiter + normalize
    out = np.tanh(out * 1.1)
    # level: RMS -14 dBFS (bed ke liye theek), peak 0.90 se neeche
    rms = float(np.sqrt((out ** 2).mean())) + 1e-9
    target = 10 ** (-14 / 20)
    out = out * (target / rms)
    out = out / max(1.0, float(np.max(np.abs(out))) / 0.90)
    # fade in/out
    n_f = int(0.15 * SR)
    out[:n_f] *= np.linspace(0, 1, n_f)
    out[-n_f:] *= np.linspace(1, 0, n_f)
    info = {"mood": mood, "pattern": pat_name, "scale": sc_name, "bpm": bpm,
            "bars": bars, "dur": round(len(out) / SR, 2), "root": root,
            "swar": SWAR, "scale_steps": SCALES[sc_name]}
    return out, info


def write_audio(sig, out: Path):
    import numpy as np
    wav = out.with_suffix(".wav")
    import wave
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
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
    ap.add_argument("--bars", type=int, default=16)
    ap.add_argument("--root", default="C")
    ap.add_argument("--bpm", type=int, default=0)
    ap.add_argument("--pattern", default="")
    ap.add_argument("--scale", default="")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="music/out.mp3")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        print(json.dumps({"moods": list(MOODS), "patterns": PATTERNS, "scales": SCALES,
                          "swar": SWAR}, ensure_ascii=False, indent=1))
        return 0
    sig, info = build(a.mood, a.bars, a.root, a.bpm or None,
                      a.pattern or None, a.scale or None, a.seed)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    p = write_audio(sig, out)
    import numpy as np
    info.update({"file": str(p), "peak": round(float(np.max(np.abs(sig))), 2),
                 "rms_dbfs": round(20 * float(np.log10(max(1e-9, float(np.sqrt((sig ** 2).mean()))))), 1)})
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
