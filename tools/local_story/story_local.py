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
 "narrator": {"v": "m", "ls": 0.98, "ratio": 1.00, "pause": 0.52},
 "dadi":     {"v": "f", "ls": 1.05, "ratio": 0.72, "pause": 0.50},
 "maa":      {"v": "f", "ls": 0.98, "ratio": 0.70, "pause": 0.48},
 "sonu":     {"v": "f", "ls": 0.92, "ratio": 1.02, "pause": 0.46},
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
# ---- duniya ki awaaz: shabd se sound (har cheez ka apna sound)
WORLD = {
 "नदी": "river", "पानी": "river", "लहर": "river", "बह": "river",
 "बारिश": "rain", "बूँद": "rain", "भीग": "rain", "बादल": "rain",
 "हवा": "wind", "ठंड": "wind", "हवा": "wind",
 "पेड़": "leaves", "पत्त": "leaves", "मिट्टी": "leaves",
 "चिड़िया": "birds", "पक्षी": "birds", "तारा": "crickets", "शाम": "crickets",
 "गाँव": "village", "छत": "village", "दादी": "village",
 "चल": "footsteps", "जाएँगे": "footsteps", "किनारा": "footsteps",
}
# zameen ka type (kadmon ki awaaz usi hisaab se)
GROUND = {
 "कच्ची": "steps_dirt", "मिट्टी": "steps_dirt", "रास्ता": "steps_dirt", "धूल": "steps_dirt",
 "पक्का": "steps_concrete", "फर्श": "steps_concrete", "पत्थर": "steps_concrete", "इमारत": "steps_concrete",
 "पत्ते": "steps_leaves", "सूखे": "steps_leaves", "पत्तों": "steps_leaves",
 "घास": "steps_grass", "मैदान": "steps_grass",
 "लकड़ी": "steps_wood", "सीढ़ी": "steps_wood", "लकड़ी की": "steps_wood",
 "कीचड़": "steps_mud", "दलदल": "steps_mud", "गीली": "steps_mud",
 "कंकड़": "steps_gravel", "बजरी": "steps_gravel", "पथरीला": "steps_gravel",
 "चल": "steps_dirt", "जंगल": "steps_leaves",
}
# jeev / duniya
CREATURES = {"भेड़िया": "wolf", "कुत्ता": "dog", "शेर": "lion", "चिड़िया": "birds",
             "पक्षी": "birds", "झींगुर": "crickets", "नदी": "river", "पानी": "river"}

def breath(dur=0.30, level=0.05, seed=5):
    """halki saans (inhale) — gap me daalne ke liye. High-mid band, dheema envelope."""
    import numpy as np
    n = int(SR * dur); t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    nz = rng.normal(0, 1, n)
    X = np.fft.rfft(nz); f = np.fft.rfftfreq(n, 1 / SR)
    band = 1 / (1 + (280 / (f + 1e-9)) ** 4) * 1 / (1 + (2600 / (f + 1e-9)) ** 4)
    nz = np.fft.irfft(X * band, n)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.6
    return (nz / (np.max(np.abs(nz)) + 1e-9) * env * level).astype("float32")


def _hp(x, fc=110.0):
    """low-cut — bhaaripan (mud) kam karne ke liye."""
    import numpy as np
    n = len(x); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    return np.fft.irfft(X / (1 + (fc / (f + 1e-9)) ** 4), n)


def _stereo(voice, bed, width=0.06, delay_ms=7):
    """mono se stereo — awaaz beech me, duniya baayein-daayein (duniya engine ka asar)."""
    import numpy as np
    d = int(SR * delay_ms / 1000)
    bl = np.concatenate([bed, np.zeros(d)])[:len(bed)]
    br = np.concatenate([np.zeros(d), bed])[:len(bed)]
    L = voice + bl * (1 + width)
    R = voice + br * (1 - width * 0.2)
    st = np.stack([L, R], axis=1)
    return st


MOODS = {"bed": [("rain", 0.5), ("river", 0.35), ("wind", 0.25), ("crickets", 0.04)],
         "pad": (130.8, 164.8, 196.0)}


def synth_line(text, cfg, out: Path):
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    v = PiperVoice.load(str(VOICES[cfg["v"]]), config_path=str(VOICES[cfg["v"]]) + ".json")
    raw = out.with_suffix(".raw.wav")
    sc = SynthesisConfig(length_scale=float(cfg["ls"]), noise_scale=0.62, noise_w_scale=0.75)
    with wave.open(str(raw), "wb") as w:
        v.synthesize_wav(text, w, syn_config=sc)
    # formant-safe pitch shift + humanize + warm EQ + room + breath (apna FX)
    import voice_fx as fx
    src = load(raw)
    y = fx.pitch_resample(src, cfg.get("ratio", 1.0))
    y = fx.trim_silence(y)
    y = fx.compress_silences(y, SR, min_gap=0.10, max_gap=0.35)   # duniya niyam: saans bachi rahe
    y = fx.smooth_chain(y, semitones=0.0, human=True, br=True, warm_eq=True, rv=False)
    y = fx.trim_silence(y, keep_ms=40)
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
    # scene break: har 4th line ke baad lamba ruk (duniya ubharne ke liye) — duniya niyam 1.4–2.6s
    scene_gap = {i: 1.7 for i in range(3, len(clips), 4)}
    total = (sum(len(c[2]) for c in clips)
             + int(SR * sum(CAST[c[0]]["pause"] for c in clips))
             + int(SR * sum(scene_gap.values())) + SR)
    voice = np.zeros(total)
    _join = True
    t = 0
    marks = []
    prev_end = 0
    for who, p, sig in clips:
        if t > 0 and t == prev_end:
            n = int(0.02 * SR)
            if n < len(sig):
                sig = sig.copy()
                sig[:n] *= np.linspace(0, 1, n)
        voice[t:t+len(sig)] += sig
        if i % 2 == 1:
            br = breath(0.30, level=0.045, seed=100 + i)
            b_start = max(0, t - int(SR * 0.30) - int(SR * 0.06))
            voice[b_start:b_start + len(br)] += br
        marks.append({"who": who, "start": round(t/SR, 2), "dur": round(len(sig)/SR, 2), "text": SCRIPT[i][1]})
        prev_end = t + len(sig)
        idx_now = len(marks) - 1
        t += len(sig) + int(SR * CAST[who]["pause"]) + int(SR * scene_gap.get(idx_now, 0))
    dur = len(voice) / SR
    # ---- duniya ki awaaz: har line ke shabd se sound, line-wise automation
    bed = np.zeros(total)
    base = {"rain": 0.30, "river": 0.22, "wind": 0.18, "crickets": 0.12, "leaves": 0.14,
            "birds": 0.16, "village": 0.08, "footsteps": 0.0, "air": 0.85}
    # har sound ka poora track banao, phir line-wise gain lagao
    # zameen ke kadam: script ke hisaab se material chuno
    ground_track = None
    ground_kind = None
    for m in marks:
        for word, fn in GROUND.items():
            if word in m.get("text", "") and hasattr(amb, fn):
                ground_kind = fn
                ground_track = getattr(amb, fn)(dur + 1)[:total]
                break
        if ground_track is not None:
            break
    tracks = {}
    if ground_track is not None:
        tracks[ground_kind] = ground_track
        base[ground_kind] = 0.22
    for name in base:
        if hasattr(amb, name):
            tracks[name] = getattr(amb, name)(dur + 1)[:total]
    gain = {k: np.full(total, base[k], dtype="float32") for k in tracks}
    for m in marks:
        a = int(m["start"] * SR); b = min(total, a + int(m["dur"] * SR))
        txt = m.get("text", "")
        for word, snd in WORLD.items():
            if word in txt and snd in gain:
                gain[snd][a:b] = np.maximum(gain[snd][a:b], base[snd] * 2.4)
        # jahan koi world sound nahi, wahan base
    # smooth automation (1.2 s fade) — bed chatka nahi lagta
    def smooth(g):
        k = int(1.2 * SR)
        ker = np.ones(k, dtype="float32") / k
        return np.convolve(g, ker, mode="same")
    for name, tr in tracks.items():
        bed[:total] += tr * smooth(gain[name])
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
    import os as _os
    if _os.environ.get("SEETAL_HP", "0") == "1":
        voice = _hp(voice, 140); bed = _hp(bed, 120)
    mix = voice * 0.95 + bed * 0.17
    mix = np.tanh(mix * 1.05)
    mix_st = None
    if _os.environ.get("SEETAL_STEREO", "0") == "1":
        mix_st = _stereo(voice * 0.95, np.tanh(bed * 0.17 * 1.05), width=0.06, delay_ms=7)
    rms = float(np.sqrt((mix**2).mean())) + 1e-9
    mix *= (10 ** (-18/20)) / rms
    mix = mix / max(1.0, float(np.max(np.abs(mix)))/0.95)
    wav = out_mp3.with_suffix(".wav")
    if mix_st is not None:
        st = np.clip(mix_st / max(1.0, float(np.max(np.abs(mix_st))) / 0.95), -1, 1)
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((st * 32767).astype("int16").tobytes())
    else:
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(mix, -1, 1) * 32767).astype("int16").tobytes())
    subprocess.run([FF, "-v", "quiet", "-y", "-i", str(wav), "-codec:a", "libmp3lame",
                    "-b:a", "192k", str(out_mp3)], check=False)
    wav.unlink(missing_ok=True)
    # voice-only gap naap (bed ke bina) — smoothness ka asli pata
    _w = 256
    _e = np.array([np.sqrt((voice[i:i+_w]**2).mean()) for i in range(0, max(1, len(voice)-_w), _w)])
    _thr = max(1e-4, float(np.percentile(_e, 75)) * 10 ** (-20/20))
    _q = _e <= _thr
    _gaps = []; _i = 0
    while _i < len(_q):
        if _q[_i]:
            _j = _i
            while _j < len(_q) and _q[_j]:
                _j += 1
            _ms = (_j - _i) * _w / SR * 1000
            if 40 <= _ms < 3000:
                _gaps.append(_ms)
            _i = _j
        else:
            _i += 1
    info = {"engine": "piper (local)",
            "voice_gaps": len(_gaps),
            "voice_gap_mean_ms": round(float(np.mean(_gaps)), 0) if _gaps else 0,
            "voice_gap_max_ms": round(max(_gaps)) if _gaps else 0,
            "voice_speech_pct": round(100 * (1 - _q.mean()), 1), "dur": round(len(mix)/SR, 2), "lines": len(SCRIPT),
            "marks": marks, "bed": MOODS["bed"], "peak": round(float(np.max(np.abs(mix))), 2),
            "rms_dbfs": round(20*float(np.log10(max(1e-9, float(np.sqrt((mix**2).mean()))))), 1)}
    (HERE / "story_local.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    # world_qa ke liye voice-stem gaps (sidecar) — mix me bed gaps chhupa deta hai
    try:
        _all = [round(g/1000, 3) for g in _gaps]
        Path(str(out_mp3).rsplit(".", 1)[0] + ".pauses.json").write_text(
            json.dumps({"voice_gaps_s": _all}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return info


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "local-story.mp3"
    print(json.dumps(build(out), ensure_ascii=False))
