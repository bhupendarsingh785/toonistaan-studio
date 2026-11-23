#!/usr/bin/env python3
"""render_final.py — insaan jaisi kahani: piper + PSOLA intonation + micro-variation + nadi bed."""
import json, subprocess, sys, wave
from pathlib import Path
import numpy as np
from piper import PiperVoice
from piper.config import SynthesisConfig
from imageio_ffmpeg import get_ffmpeg_exe
sys.path.insert(0, "/scratch/work/src/tools/local_story")
import psola

FF = get_ffmpeg_exe(); SR = 22050
CAST = {"narrator": ("rohan", 1.00, 0.42), "bhediya": ("pratham", 1.05, 0.46), "stree": ("priyamvada", 1.05, 0.40)}
GAIN = {"narrator": 1.0, "bhediya": 1.0, "stree": 1.24}      # ladki ki awaaz 2 dB upar
import os as _os
_D = float(_os.environ.get("PSOLA_DEPTH", "0"))     # 0 = PSOLA band (samajh bani rahe)
DEPTH = {k: _D for k in ("pyaar", "dukh", "dar", "hairani", "khushi", "gussa", "neutral")}
_c = {}

def voice(m):
    if m not in _c:
        p = f"/scratch/work/voices/hi_IN-{m}-medium.onnx"
        _c[m] = PiperVoice.load(p, config_path=p + ".json")
    return _c[m]

def load(p, t=None):
    cmd = [FF, "-v", "quiet"] + (["-t", str(t)] if t else []) + ["-i", str(p), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, dtype=np.float32).copy()

def synth(txt, model, ls, out):
    w = wave.open(out, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    voice(model).synthesize_wav(txt, w, syn_config=SynthesisConfig(length_scale=ls, noise_scale=0.62, noise_w_scale=0.75))
    w.close()
    return load(out)

def trim(y):
    a = np.abs(y); i = np.where(a > a.max() * 0.02)[0]
    return y[max(0, i[0] - 800): i[-1] + 800] if len(i) else y

def contour_for(y, depth, rng):
    dur = len(y) / SR
    ph = rng.uniform(0, 6.28, 3)
    def c(t):
        q = t / max(dur, 0.01)
        return depth * (1.4 * np.sin(2 * np.pi * q * 0.8 + ph[0]) + 0.9 * np.sin(2 * np.pi * q * 2.1 + ph[1])) - 1.5 * q * depth
    return c

def micro(y, rng, jitter_st=0.12, breath=0.012):
    """insaan ki chhoti kampan (jitter) + halki saans — robot-pan khatam."""
    n = len(y)
    t = np.arange(n) / SR
    # jitter: dheema random walk (0.05-0.2 st)
    steps = rng.normal(0, 1, n // 400 + 2)
    walk = np.cumsum(steps) * 0.03
    walk = np.interp(np.arange(n), np.linspace(0, n, len(walk)), walk)
    # sur ki micro-kampan PSOLA se aa rahi hai; yahan sirf halka amplitude + saans
    y2 = y * (1 + 0.025 * np.sin(2 * np.pi * 4.7 * t + rng.uniform(0, 6)) + 0.012 * walk)
    # saans: band-passed noise, awaaz ke hisaab se
    noise = rng.normal(0, 1, n).astype(np.float32)
    S = np.fft.rfft(noise); f = np.fft.rfftfreq(n, 1 / SR)
    noise = np.fft.irfft(S * (np.exp(-((f - 2500) ** 2) / (2 * 1400 ** 2))), n).astype(np.float32)
    env = np.abs(y2); env = np.convolve(env, np.ones(512) / 512, mode="same")
    return (y2 + noise * env * breath * 4).astype(np.float32)

def river_bed(n):
    src = [("/scratch/input/gugunxyz-flowing-water-02-464647.mp3", 0.55),
           ("/scratch/input/gugunxyz-flowing-water-03-464668-2.mp3", 0.30),
           ("/scratch/input/loswin23-flowing-river-623417.mp3", 0.35)]
    bed = np.zeros(n, dtype=np.float32)
    for p, w in src:
        if not Path(p).exists(): continue
        x = load(p, 30)
        if len(x) < SR: continue
        y = np.tile(x, int(np.ceil(n / len(x))))[:n]
        bed += y / (np.max(np.abs(y)) + 1e-9) * w
    S = np.fft.rfft(bed); f = np.fft.rfftfreq(n, 1 / SR)
    bed = np.fft.irfft(S * (1 + 0.35 * np.exp(-((f - 1800) ** 2) / (2 * 900 ** 2))), n).astype(np.float32)
    return bed

def main():
    out = sys.argv[1]; script = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    bed_db = float(sys.argv[3]) if len(sys.argv) > 3 else -8.0
    work = Path("/scratch/work/rfin"); work.mkdir(exist_ok=True)
    rng = np.random.default_rng(7)
    parts, marks, t = [], [], 0.0
    for i, row in enumerate(script):
        who = row.get("who", "narrator"); txt = row["text"]; bhaav = row.get("bhaav", "neutral")
        m, ls, pause = CAST.get(who, CAST["narrator"])
        y = synth(txt, m, ls, str(work / f"l{i:02d}.wav"))
        y = trim(y)
        _dep = DEPTH.get(bhaav, 0.0)
        if _dep > 0.05:
            y = psola.shift(y, SR, contour_for(y, _dep, rng))
        y = micro(y, rng)
        y = y * GAIN.get(who, 1.0)
        if who == "stree":                       # garam (low shelf) + halka air
            S = np.fft.rfft(y); f = np.fft.rfftfreq(len(y), 1 / SR)
            g = 1 + 0.55 * np.exp(-((f - 260) ** 2) / (2 * 180 ** 2)) + 0.18 * np.exp(-((f - 7000) ** 2) / (2 * 2500 ** 2))
            y = np.fft.irfft(S * g, len(y)).astype(np.float32)
        pk = np.abs(y).max()
        if pk > 0: y = y / pk * 0.9
        parts.append(y); marks.append({"who": who, "text": txt, "bhaav": bhaav, "start": round(t, 2), "dur": round(len(y) / SR, 2)})
        g = np.zeros(int(pause * SR), dtype=np.float32); parts.append(g); t += (len(y) + len(g)) / SR
    voice_track = np.concatenate(parts)
    bed = river_bed(len(voice_track))
    vr = float(np.sqrt((voice_track ** 2).mean())) + 1e-9
    br = float(np.sqrt((bed ** 2).mean())) + 1e-9
    bed *= (vr * 10 ** (bed_db / 20)) / br
    L = voice_track * 0.95 + bed * 1.05
    R = voice_track * 0.95 + bed * 0.95
    pk = max(np.abs(L).max(), np.abs(R).max()); L *= 0.90 / pk; R *= 0.90 / pk
    tmp = work / "pre.wav"
    w = wave.open(str(tmp), "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(np.stack([L, R], 1), -1, 1) * 32767).astype("<i2").tobytes()); w.close()
    subprocess.run([FF, "-v", "error", "-y", "-i", str(tmp), "-af",
                    "equalizer=f=3500:width_type=q:w=1.3:g=-2.0,loudnorm=I=-16:TP=-2.5:LRA=11,volume=0.85,alimiter=limit=0.80",
                    "-c:a", "libmp3lame", "-b:a", "160k", out], check=True)
    (work / "marks.json").write_text(json.dumps({"dur": round(len(voice_track) / SR, 2), "marks": marks}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"out": out, "dur": round(len(voice_track) / SR, 2)}))

if __name__ == "__main__":
    main()
