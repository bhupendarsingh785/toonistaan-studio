#!/usr/bin/env python3
"""nat_story.py — seedha, saaf, insaan jaisi awaaz wali kahani (koi formant/robot FX nahi).

  python nat_story.py out.mp3 script.json
"""
from __future__ import annotations
import json, os, subprocess, sys, wave
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
VOICES = {"rohan": HERE.parent / "voices/hi_IN-rohan-medium.onnx",
          "pratham": HERE.parent / "voices/hi_IN-pratham-medium.onnx",
          "priyamvada": HERE.parent / "voices/hi_IN-priyamvada-medium.onnx"}
SR = 22050
WHO = {  # kirdaar -> (model, length_scale, pause_after)
    "narrator": ("rohan", 1.00, 0.42),
    "bhediya": ("pratham", 1.05, 0.46),
    "stree": ("priyamvada", 1.02, 0.40),
}
_CACHE = {}


def voice(name):
    if name not in _CACHE:
        from piper import PiperVoice
        p = VOICES[name]
        _CACHE[name] = PiperVoice.load(str(p), config_path=str(p) + ".json")
    return _CACHE[name]


def say(text, model, ls, out: Path):
    from piper.config import SynthesisConfig
    v = voice(model)
    with wave.open(str(out), "wb") as w:
        v.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=ls, noise_scale=0.62, noise_w_scale=0.75))
    return out


def load(path, sr=SR):
    from imageio_ffmpeg import get_ffmpeg_exe
    raw = subprocess.run([get_ffmpeg_exe(), "-v", "quiet", "-i", str(path), "-f", "f32le",
                          "-ac", "1", "-ar", str(sr), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def trim(y, keep=0.05, sr=SR):
    a = np.abs(y); th = a.max() * 0.02
    idx = np.where(a > th)[0]
    if not len(idx): return y
    return y[max(0, idx[0] - int(keep * sr)): idx[-1] + int(keep * sr)]


def bed(total, sr=SR):
    """asli recordings: jungle + nadi + jheengur (insaan ki awaaz wali file nahi)."""
    sys.path.insert(0, str(HERE))
    import real_bed as RB
    kinds = [("jungle", 0.55), ("river", 0.35), ("crickets", 0.12)]
    b, used = RB.make_bed(kinds, total, sr, level_db=-22)
    return b, used


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "nat-story.mp3")
    script = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    work = Path("/scratch/work/nat"); work.mkdir(exist_ok=True)
    parts, marks, t = [], [], 0.0
    for i, row in enumerate(script):
        who = row.get("who", "narrator"); text = row["text"]
        model, ls, pause = WHO.get(who, WHO["narrator"])
        p = work / f"l{i:02d}.wav"
        say(text, model, ls, p)
        y = trim(load(p))
        parts.append(y)
        marks.append({"who": who, "text": text, "start": round(t, 2), "dur": round(len(y) / SR, 2)})
        gap = np.zeros(int(pause * SR), dtype=np.float32)
        parts.append(gap); t += (len(y) + len(gap)) / SR
    voice_track = np.concatenate(parts) if parts else np.zeros(SR, dtype=np.float32)
    # duniya
    bg, used = bed(len(voice_track) + SR)
    if bg is not None:
        bg = np.pad(bg, (0, max(0, len(voice_track) - len(bg))))[: len(voice_track)]
        vr = float(np.sqrt((voice_track ** 2).mean())) + 1e-9
        br = float(np.sqrt((bg ** 2).mean())) + 1e-9
        bg *= min(1.0, (vr * 10 ** (-18 / 20)) / br)      # bed awaaz se 18 dB neeche
        mix = voice_track * 0.95 + bg
    else:
        mix = voice_track; used = []
    # stereo halka (awaaz beech me, duniya kinaron par)
    L = mix.copy(); R = mix.copy()
    if bg is not None:
        L = voice_track * 0.95 + bg * 1.06
        R = voice_track * 0.95 + bg * 0.94
    peak = float(max(np.abs(L).max(), np.abs(R).max()))
    if peak > 0: L *= 0.92 / peak; R *= 0.92 / peak
    pcm = np.stack([L, R], axis=1)
    tmp = work / "pre.wav"
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
    from imageio_ffmpeg import get_ffmpeg_exe
    FF = get_ffmpeg_exe()
    subprocess.run([FF, "-v", "error", "-y", "-i", str(tmp),
                    "-af", "loudnorm=I=-16:TP=-2:LRA=11,alimiter=limit=0.90",
                    "-c:a", "libmp3lame", "-b:a", "160k", str(out)], check=True)
    (work / "marks.json").write_text(json.dumps({"dur": round(len(mix) / SR, 2), "marks": marks,
                                                 "bed": used}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"out": str(out), "dur": round(len(mix) / SR, 2), "lines": len(marks),
                      "bed": [u["file"][:40] for u in used]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
