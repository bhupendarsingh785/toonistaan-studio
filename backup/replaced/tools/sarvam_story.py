#!/usr/bin/env python3
"""sarvam_story.py — expressive Hindi kahani (Sarvam bulbul), har line bhaav ke saath.

  SARVAM_API_KEY=xxx python tools/sarvam_story.py out.mp3 script.json [--bed -7]

Kirdaar -> Sarvam speaker (SARVAM_SPEAKER_<NAME> env se badla ja sakta hai):
  narrator=shubh, bhediya=ratan, stree=ritu
Bhaav -> pace/pitch/loudness (voice_provider.EMOTION_STYLE + _bhaav_style)
Key na ho / fail ho to piper (local) par gir jaata hai — kahani kabhi khaali nahi.
"""
from __future__ import annotations
import json, os, subprocess, sys, wave
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))

SPEAKER = {"narrator": "shubh", "bhediya": "ratan", "stree": "ritu"}
FALLBACK_PIPER = {"narrator": "rohan", "bhediya": "pratham", "stree": "priyamvada"}
SR = 22050


def _ff():
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()


def load(p, t=None, sr=SR):
    cmd = [_ff(), "-v", "quiet"] + (["-t", str(t)] if t else []) + ["-i", str(p), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, dtype=np.float32).copy()


def trim(y):
    a = np.abs(y); i = np.where(a > a.max() * 0.02)[0]
    return y[max(0, i[0] - 800): i[-1] + 800] if len(i) else y


def piper_line(text, who, out):
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    m = FALLBACK_PIPER.get(who, "rohan")
    p = f"/scratch/work/voices/hi_IN-{m}-medium.onnx"
    if not Path(p).exists():
        return None
    v = PiperVoice.load(p, config_path=p + ".json")
    w = wave.open(out, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    v.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=1.02, noise_scale=0.62, noise_w_scale=0.75))
    w.close()
    return out


def sarvam_line(text, who, bhaav, out):
    """Sarvam se ek line — bhaav ke saath. Fail par None."""
    try:
        import voice_provider as vp
    except ModuleNotFoundError:
        from tools import voice_provider as vp
    os.environ.setdefault(f"SARVAM_SPEAKER_{who.upper()}", SPEAKER.get(who, "shubh"))
    ok = vp.sarvam_tts(text, who, out, bhaav=bhaav)
    return out if ok and Path(out).exists() and Path(out).stat().st_size > 2000 else None


def river_bed(n):
    src = [("/scratch/input/gugunxyz-flowing-water-02-464647.mp3", 0.55),
           ("/scratch/input/gugunxyz-flowing-water-03-464668-2.mp3", 0.30),
           ("/scratch/input/loswin23-flowing-river-623417.mp3", 0.35)]
    bed = np.zeros(n, dtype=np.float32)
    for p, w in src:
        if not Path(p).exists():
            continue
        x = load(p, 30)
        if len(x) < SR:
            continue
        y = np.tile(x, int(np.ceil(n / len(x))))[:n]
        bed += y / (np.max(np.abs(y)) + 1e-9) * w
    S = np.fft.rfft(bed); f = np.fft.rfftfreq(n, 1 / SR)
    return np.fft.irfft(S * (1 + 0.35 * np.exp(-((f - 1800) ** 2) / (2 * 900 ** 2))), n).astype(np.float32)


def main():
    out = sys.argv[1]; script = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    bed_db = -7.0
    if "--bed" in sys.argv:
        bed_db = float(sys.argv[sys.argv.index("--bed") + 1])
    work = Path("/scratch/work/sarvam"); work.mkdir(exist_ok=True)
    parts, marks, t, engines = [], [], 0.0, {}
    for i, row in enumerate(script):
        who = row.get("who", "narrator"); txt = row["text"]; bhaav = row.get("bhaav", "neutral")
        p = work / f"l{i:02d}.wav"
        src = sarvam_line(txt, who, bhaav, str(p))
        used = "sarvam"
        if src is None:
            src = piper_line(txt, who, str(p)); used = "piper"
        if src is None:
            raise SystemExit(f"line {i}: na Sarvam na piper")
        engines[used] = engines.get(used, 0) + 1
        y = trim(load(p)); parts.append(y)
        pause = float(row.get("pause", 0.42))
        marks.append({"who": who, "text": txt, "bhaav": bhaav, "start": round(t, 2), "dur": round(len(y) / SR, 2), "engine": used})
        g = np.zeros(int(pause * SR), dtype=np.float32); parts.append(g); t += (len(y) + len(g)) / SR
    voice = np.concatenate(parts)
    bed = river_bed(len(voice))
    vr = float(np.sqrt((voice ** 2).mean())) + 1e-9
    br = float(np.sqrt((bed ** 2).mean())) + 1e-9
    bed *= (vr * 10 ** (bed_db / 20)) / br
    L = voice * 0.95 + bed * 1.05; R = voice * 0.95 + bed * 0.95
    pk = max(np.abs(L).max(), np.abs(R).max()); L *= 0.90 / pk; R *= 0.90 / pk
    tmp = work / "pre.wav"
    w = wave.open(str(tmp), "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(np.stack([L, R], 1), -1, 1) * 32767).astype("<i2").tobytes()); w.close()
    subprocess.run([_ff(), "-v", "error", "-y", "-i", str(tmp), "-af",
                    "equalizer=f=3500:width_type=q:w=1.3:g=-1.5,loudnorm=I=-16:TP=-2.5:LRA=11,volume=0.88,alimiter=limit=0.82",
                    "-c:a", "libmp3lame", "-b:a", "160k", out], check=True)
    (work / "marks.json").write_text(json.dumps({"dur": round(len(voice) / SR, 2), "marks": marks, "engines": engines}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"out": out, "dur": round(len(voice) / SR, 2), "engines": engines}))


if __name__ == "__main__":
    main()
