#!/usr/bin/env python3
"""render_river.py — kahani + nadi (kal-kal) background, seedha aur saaf."""
import json, subprocess, sys, wave
from pathlib import Path
import numpy as np
from piper import PiperVoice
from piper.config import SynthesisConfig
from imageio_ffmpeg import get_ffmpeg_exe

FF = get_ffmpeg_exe(); SR = 22050
V = {"narrator": ("rohan", 1.00, 0.42), "bhediya": ("pratham", 1.05, 0.46), "stree": ("priyamvada", 1.02, 0.40)}
MODEL = {v: f"/scratch/work/voices/hi_IN-{v}-medium.onnx" for v in ("rohan", "pratham", "priyamvada")}
_cache = {}

def voice(m):
    if m not in _cache:
        _cache[m] = PiperVoice.load(MODEL[m], config_path=MODEL[m] + ".json")
    return _cache[m]

def load(p, t=None):
    cmd = [FF, "-v", "quiet"] + (["-t", str(t)] if t else []) + ["-i", str(p), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, dtype=np.float32).copy()

def trim(y):
    a = np.abs(y); idx = np.where(a > a.max() * 0.02)[0]
    return y[max(0, idx[0] - 1000): idx[-1] + 1000] if len(idx) else y

def loop(x, n):
    if len(x) >= n: return x[:n]
    y = np.tile(x, int(np.ceil(n / len(x))))[:n]
    f = min(int(len(x) * 0.2), n // 4)
    if f > 100:
        r = np.linspace(0, 1, f)
        for k in range(1, int(np.ceil(n / len(x)))):
            i = k * len(x)
            if i - f >= 0 and i + f <= len(y):
                y[i - f:i] = y[i - f:i] * (1 - r) + y[i - f:i] * r
    return y

def river_bed(n):
    src = ["/scratch/input/gugunxyz-flowing-water-02-464647.mp3",
           "/scratch/input/gugunxyz-flowing-water-03-464668-2.mp3",
           "/scratch/input/loswin23-flowing-river-623417.mp3"]
    w = [0.55, 0.30, 0.35]
    bed = np.zeros(n, dtype=np.float32)
    for p, ww in zip(src, w):
        if not Path(p).exists(): continue
        x = loop(load(p, 30), n)
        bed += x / (np.max(np.abs(x)) + 1e-9) * ww
    S = np.fft.rfft(bed); f = np.fft.rfftfreq(n, 1 / SR)
    bed = np.fft.irfft(S * (1 + 0.35 * np.exp(-((f - 1800) ** 2) / (2 * 900 ** 2))), n).astype(np.float32)
    return bed

def main():
    out = sys.argv[1]; script = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    bed_db = float(sys.argv[3]) if len(sys.argv) > 3 else -9.0
    work = Path("/scratch/work/rw"); work.mkdir(exist_ok=True)
    parts, marks, t = [], [], 0.0
    for i, row in enumerate(script):
        who = row.get("who", "narrator"); txt = row["text"]
        m, ls, pause = V.get(who, V["narrator"])
        p = work / f"l{i:02d}.wav"
        w = wave.open(str(p), "wb")
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        voice(m).synthesize_wav(txt, w, syn_config=SynthesisConfig(length_scale=ls, noise_scale=0.62, noise_w_scale=0.75))
        w.close()
        y = trim(load(p)); parts.append(y)
        marks.append({"who": who, "text": txt, "start": round(t, 2), "dur": round(len(y) / SR, 2)})
        g = np.zeros(int(pause * SR), dtype=np.float32); parts.append(g); t += (len(y) + len(g)) / SR
    voice_track = np.concatenate(parts)
    bed = river_bed(len(voice_track))
    vr = float(np.sqrt((voice_track ** 2).mean())) + 1e-9
    br = float(np.sqrt((bed ** 2).mean())) + 1e-9
    bed *= (vr * 10 ** (bed_db / 20)) / br
    L = voice_track * 0.95 + bed * 1.05
    R = voice_track * 0.95 + bed * 0.95
    pk = max(np.abs(L).max(), np.abs(R).max()); L *= 0.92 / pk; R *= 0.92 / pk
    tmp = work / "pre.wav"
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(np.stack([L, R], 1), -1, 1) * 32767).astype("<i2").tobytes())
    subprocess.run([FF, "-v", "error", "-y", "-i", str(tmp), "-af",
                    "equalizer=f=3500:width_type=q:w=1.3:g=-2.2,loudnorm=I=-16:TP=-2:LRA=11,alimiter=limit=0.88",
                    "-c:a", "libmp3lame", "-b:a", "160k", out], check=True)
    (work / "marks.json").write_text(json.dumps({"dur": round(len(voice_track) / SR, 2), "marks": marks}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"out": out, "dur": round(len(voice_track) / SR, 2), "bed_db": bed_db}))

if __name__ == "__main__":
    main()
