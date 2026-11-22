#!/usr/bin/env python3
"""Local Story — sirf apne system se audio (Sarvam nahi): Piper + apni ambience + apna mix."""
from __future__ import annotations
import json, subprocess, sys, wave

def ffmpeg_bin():
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

FF = ffmpeg_bin()
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SR = 44100

VOICES = {"m": HERE.parent/"voices/hi_IN-pratham-medium.onnx",
          "f": HERE.parent/"voices/hi_IN-priyamvada-medium.onnx"}

# kirdaar: voice, length_scale (slow>1), pitch_shift (semitones), pause
CAST = {
 "narrator": {"v": "m", "ls": 1.254, "semi": -1.0, "pause": 1.7},
 "dadi":     {"v": "f", "ls": 1.411, "semi": -5.2, "pause": 1.5},
 "sonu":     {"v": "f", "ls": 1.03, "semi": +3.9, "pause": 1.0},
 "maa":      {"v": "f", "ls": 1.165, "semi": -3.8, "pause": 1.3},
}
SCRIPT = [
 ("narrator", "सुबह के छह बजे थे। गाँव की छतों से धुआँ उठ रहा था, और दूर नदी कलकल बह रही थी।"),
 ("sonu",     "दादी! दादी, आज बारिश होगी क्या?"),
 ("dadi",     "होगी बेटा। देख, हवा में ठंडक आ गई है।"),
 ("sonu",     "फिर आज हम नदी नहीं जाएँगे?"),
 ("dadi",     "जाएँगे। बारिश में नदी का किनारा सबसे सुंदर होता है।"),
 ("narrator", "दोपहर तक बादल घिर आए। पहली बूँद गिरी, और पूरा गाँव महक उठा।"),
 ("maa",      "अम्मा, छाता ले लो। बच्चा भीग जाएगा।"),
 ("dadi",     "भीगने दो। मिट्टी की खुशबू बच्चों को ज़िंदगी भर याद रहती है।"),
 ("sonu",     "दादी, देखो! नदी में कितनी लहरें आ रही हैं!"),
 ("narrator", "शाम को बारिश थम गई। नदी शांत बह रही थी, और आसमान में पहला तारा निकल आया।"),
]
MOODS = {"bed": [("rain", 0.5), ("river", 0.35), ("wind", 0.25), ("crickets", 0.04)],
         "pad": (130.8, 164.8, 196.0)}


def synth_line(text, cfg, out: Path):
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    v = PiperVoice.load(str(VOICES[cfg["v"]]), config_path=str(VOICES[cfg["v"]]) + ".json")
    raw = out.with_suffix(".raw.wav")
    sc = SynthesisConfig(length_scale=float(cfg["ls"]))
    with wave.open(str(raw), "wb") as w:
        v.synthesize_wav(text, w, syn_config=sc)
    # formant-safe pitch shift + humanize + warm EQ + room + breath (apna FX)
    import voice_fx as fx
    src = load(raw)
    y = fx.smooth_chain(src, semitones=cfg.get("semi", 0.0), human=True, br=True, warm_eq=True, rv=False)
    y = fx.formant_shift(y, cfg.get("formant", 1.0))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("int16").tobytes())
    raw.unlink(missing_ok=True)
    return out


def load(p: Path):
    r = subprocess.run([FF, "-v", "quiet", "-i", str(p), "-f", "s16le", "-ac", "1",
                        "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768


def build(out_mp3: Path):
    import ambience as amb
    work = HERE / "work"; work.mkdir(exist_ok=True)
    clips = []
    for i, (who, text) in enumerate(SCRIPT):
        p = synth_line(text, CAST[who], work / f"line{i:02d}.wav")
        clips.append((who, p, load(p)))
    total = sum(len(c[2]) for c in clips) + int(SR * sum(CAST[c[0]]["pause"] for c in clips)) + SR
    voice = np.zeros(total)
    t = 0
    marks = []
    for who, p, sig in clips:
        voice[t:t+len(sig)] += sig
        marks.append({"who": who, "start": round(t/SR, 2), "dur": round(len(sig)/SR, 2)})
        t += len(sig) + int(SR * CAST[who]["pause"])
    dur = len(voice) / SR
    # ambience beds
    bed = np.zeros(total)
    for name, lvl in MOODS["bed"]:
        sig = getattr(amb, name)(dur + 1)
        bed[:total] += sig[:total] * lvl * 0.5
    bed[:total] += amb.pad_chords(dur + 1, MOODS["pad"])[:total] * 0.35
    # ducking on speech
    duck = np.ones(total)
    for m in marks:
        a = int(m["start"]*SR); b = a + int(m["dur"]*SR)
        n = int(0.12*SR)
        duck[max(0,a-n):a] = np.linspace(1.0, 0.40, min(n, max(0, a-max(0,a-n))))[:max(0, min(n, a-max(0,a-n)))] if a > n else duck[max(0,a-n):a]
        duck[a:b] = np.minimum(duck[a:b], 0.40)
        duck[b:b+n] = np.linspace(0.40, 1.0, min(n, total-b))[:max(0, min(n, total-b))]
    bed *= duck
    mix = voice * 0.95 + bed * 0.13
    mix = np.tanh(mix * 1.05)
    rms = float(np.sqrt((mix**2).mean())) + 1e-9
    mix *= (10 ** (-16/20)) / rms
    mix = mix / max(1.0, float(np.max(np.abs(mix)))/0.95)
    wav = out_mp3.with_suffix(".wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1)*32767).astype("int16").tobytes())
    subprocess.run([FF, "-v", "quiet", "-y", "-i", str(wav), "-codec:a", "libmp3lame",
                    "-b:a", "192k", str(out_mp3)], check=False)
    wav.unlink(missing_ok=True)
    info = {"engine": "piper (local)", "dur": round(len(mix)/SR, 2), "lines": len(SCRIPT),
            "marks": marks, "bed": MOODS["bed"], "peak": round(float(np.max(np.abs(mix))), 2),
            "rms_dbfs": round(20*float(np.log10(max(1e-9, float(np.sqrt((mix**2).mean()))))), 1)}
    (HERE / "story_local.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "local-story.mp3"
    print(json.dumps(build(out), ensure_ascii=False))
