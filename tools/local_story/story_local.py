#!/usr/bin/env python3
"""Local Story — sirf apne system se audio (Sarvam nahi): Piper + apni ambience + apna mix."""
from __future__ import annotations
import os
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
SR = int(os.environ.get('SEETAL_SR', '22050'))   # 2 GB RAM me 16000 chalao

VOICES = {"m": HERE.parent/"voices/hi_IN-pratham-medium.onnx",
          "m2": HERE.parent/"voices/hi_IN-rohan-medium.onnx",     # narrator (naap me behtar)
          "f": HERE.parent/"voices/hi_IN-priyamvada-medium.onnx"}

# kirdaar: voice, length_scale (slow>1), pitch_shift (semitones), pause
CAST = {
 "narrator": {"v": "m2", "ls": 1.00, "ratio": 1.00, "formant": 0.97, "pause": 0.44},   # rohan + h-spell
 "dadi":     {"v": "f", "ls": 1.08, "ratio": 1.00, "formant": 0.94, "pause": 0.42},   # dadi: formant neecha = badi umar, ASR safe
 "maa":      {"v": "f", "ls": 1.00, "ratio": 1.00, "formant": 0.94, "pause": 0.42},
 "sonu":     {"v": "f", "ls": 0.98, "ratio": 1.02, "formant": 1.05, "pause": 0.40},   # bachcha: halka ooncha/patla
 "bhediya":  {"v": "m", "ls": 1.06, "ratio": 1.00, "formant": 0.90, "pause": 0.46},   # bhediya→insaan: gehri, dheemi
 "stree":    {"v": "f", "ls": 1.02, "ratio": 1.00, "formant": 1.00, "pause": 0.42},   # premika: garam, saaf
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
 "हवा": "wind", "ठंड": "wind", "झोंका": "wind",
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

def breath(dur=0.50, level=0.030, band=(300, 2000), seed=5):
    """halki saans (inhale) — gap me daalne ke liye. High-mid band, dheema envelope."""
    import numpy as np
    n = int(SR * dur); t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    nz = rng.normal(0, 1, n)
    X = np.fft.rfft(nz); f = np.fft.rfftfreq(n, 1 / SR)
    lo, hi = band
    bandm = 1 / (1 + (lo / (f + 1e-9)) ** 4) * 1 / (1 + (hi / (f + 1e-9)) ** 4)
    nz = np.fft.irfft(X * bandm, n)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.6
    return (nz / (np.max(np.abs(nz)) + 1e-9) * env * level).astype("float32")


def _hp(x, fc=110.0):
    """low-cut — bhaaripan (mud) kam karne ke liye."""
    import numpy as np
    n = len(x); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    return np.fft.irfft(X / (1 + (fc / (f + 1e-9)) ** 4), n)


def _stereo(voice, bed, width=0.10, delay_ms=4):
    """mono se stereo — awaaz beech me, duniya baayein-daayein (duniya engine ka asar)."""
    import numpy as np
    d = int(SR * delay_ms / 1000)
    bl = np.concatenate([bed, np.zeros(d)])[:len(bed)]
    br = np.concatenate([np.zeros(d), bed])[:len(bed)]
    L = voice + bl * (1 + width)
    R = voice + br * (1 - width * 0.2)
    st = np.stack([L, R], axis=1)
    return st


# --- saans ka model (research se): speech me inhale ~0.5s, exhale lamba
# arousal zyada (dar/gussa) = tez + chhoti + shallow; sadness = dheemi + gehri (sigh)
BREATH_MODEL = {
    #             rate/min  dur_s      level   band(Hz)
    "neutral": (11, 0.50, 0.030, (300, 2000)),
    "calm":    (9,  0.55, 0.028, (280, 1800)),
    "sad":     (8,  0.75, 0.050, (260, 1600)),
    "happy":   (17, 0.38, 0.034, (320, 2400)),
    "anger":   (21, 0.40, 0.060, (350, 3200)),
    "fear":    (26, 0.27, 0.048, (400, 4200)),
}
EMO_WORDS = {
    "fear":  ["डर", "भागो", "चिल्ला", "बचाओ", "काँप", "सहम", "खतरा"],
    "anger": ["गुस्सा", "अरे", "चुप", "बेवकूफ", "मार"],
    "sad":   ["दुख", "रो", "आँसू", "मर", "अकेल", "याद"],
    "happy": ["खुश", "हँस", "मज़ा", "मजा", "आनंद"],
}


def line_emotion(text: str) -> str:
    for emo, words in EMO_WORDS.items():
        if any(w in text for w in words):
            return emo
    return "neutral"


def breath_plan(text: str, t_since_breath: float):
    """Kab saans leni chahiye — line index se nahi, TIME aur BHAV se (insaan jaisa)."""
    emo = line_emotion(text)
    rate, dur, level, band = BREATH_MODEL[emo]
    need_after = 60.0 / rate          # itne second me ek saans
    if t_since_breath >= need_after:
        return emo, dur, level, band
    return None


def _presence(x):
    """master presence EQ — smooth reference ke target (bright ~2086, mid ~57, high ~27)."""
    import numpy as np
    n = len(x); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    g -= 0.55 * np.exp(-((f - 550) ** 2) / (2 * 500 ** 2))     # mid ka bhaaripan kam
    g += 1.00 * np.exp(-((f - 3100) ** 2) / (2 * 1200 ** 2))   # presence
    g += 0.35 * np.exp((0) * -1) * np.exp(-((f - 6200) ** 2) / (2 * 1600 ** 2))   # air
    g -= 0.15 * np.exp(-((f - 7600) ** 2) / (2 * 1100 ** 2))   # halka de-ess
    return np.fft.irfft(X * g, n)


def room_tone(n, level_db=-52, seed=3):
    """hamesha chalu room tone — asli duniya kabhi poori chup nahi hoti (holes band)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, n)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    x = np.fft.irfft(X / (1 + (120 / (f + 1e-9)) ** 2), n)      # pink-ish
    x = x / (np.max(np.abs(x)) + 1e-9)
    return (x * (10 ** (level_db / 20))).astype("float32")


# bhaav → prosody (realtime/bhaav.py ka target use hota hai)
BHAV_PROFILE = {   # sur (semi), raftaar (ls guna), zor (dB)
    "khushi":  (+1.0, 0.96, +1.0),
    "gussa":   (+0.7, 0.94, +2.0),
    "dar":     (+1.2, 1.02, +0.5),
    "dukh":    (-0.8, 1.08, -1.0),
    "pyaar":   (-0.4, 1.05, +0.2),
    "hairani": (+0.9, 1.00, +0.8),
    "neutral": (0.0, 1.00, 0.0),
}


def bhaav_prosody(text, who, cfg_who=None):
    """line ka bhaav → (semi, ls_guna, gain_db). Na ho to neutral."""
    try:
        import sys as _s
        _s.path.insert(0, str(HERE.parent / "realtime"))
        import bhaav as B
        r = B.target({"text": text, "who": who})
        emo, inten = r.get("emotion", "neutral"), float(r.get("intensity", 0) or 0)
        semi, lsm, db = BHAV_PROFILE.get(emo, BHAV_PROFILE["neutral"])
        k = min(1.0, max(0.0, inten))
        _semi = max(-1.6, min(1.6, semi * k))    # ±1.6 st; dadi par cap try kiya (0.6) — ASR aur kharab hua
        _lsm = 1 + (lsm - 1) * k * 1.6                   # raftaar ka asar 1.6 guna
        return _semi, _lsm, db * k, emo, inten
    except Exception:
        return 0.0, 1.0, 0.0, "neutral", 0.0


MOODS = {"bed": [("rain", 0.5), ("river", 0.35), ("wind", 0.25), ("crickets", 0.04)],
         "pad": (130.8, 164.8, 196.0)}


_VCACHE = {}


def _voice(key):
    """PiperVoice ek hi baar load — har line par load karna hi speed ka asli bug tha."""
    if key not in _VCACHE:
        from piper import PiperVoice
        _VCACHE[key] = PiperVoice.load(str(VOICES[key]), config_path=str(VOICES[key]) + ".json")
    return _VCACHE[key]


_LINE_GATES = []


def line_check(y, sr, who, text):
    """Line-level jaanch — halka (numpy only, 2 GB RAM me bhi chalta hai).
    gates.py/nirantarta.py ka kaam yahin inline: clipping, RMS, brightness, echo, gap."""
    import numpy as np
    rec = {"who": who, "text": text[:40]}
    try:
        peak = float(np.max(np.abs(y)))
        rms = float(np.sqrt((y ** 2).mean()))
        n = min(len(y), sr * 4)
        S = np.abs(np.fft.rfft(y[:n] * np.hanning(n)))
        f = np.fft.rfftfreq(n, 1 / sr)
        bright = float((S * f).sum() / (S.sum() + 1e-9))
        k = 16
        env = np.array([np.abs(y[i:i + k]).mean() for i in range(0, max(1, len(y) - k), k)])
        a = np.correlate(env - env.mean(), env - env.mean(), "full")[len(env) - 1:]
        a = a / (a[0] + 1e-12)
        step = k / sr
        lo, hi = int(0.017 / step), int(0.031 / step)
        echo = float(np.max(np.abs(a[lo:hi + 1]))) if hi < len(a) else 0.0
        rec["gates"] = {"clip": round(peak, 3), "rms_db": round(20 * float(np.log10(max(1e-9, rms))), 1),
                        "bright": round(bright), "echo": round(echo, 3),
                        "clip_ok": peak < 0.99, "echo_ok": echo < 0.78}
    except Exception as e:
        rec["gates"] = {"error": type(e).__name__}
    _LINE_GATES.append(rec)
    return rec


def synth_line(text, cfg, out: Path):
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    v = _voice(cfg["v"])
    raw = out.with_suffix(".raw.wav")
    # prosody jitter — insaan har line ek jaisi nahi bolta (sur ±1.5%, raftaar ±4%)
    import random as _rnd
    _seed = abs(hash(text)) % (2 ** 31)
    _r = _rnd.Random(_seed)
    _semi_b, _ls_b, _db_b, _emo, _inten = bhaav_prosody(text, cfg.get("who", ""))
    _ls = float(cfg["ls"]) * _r.uniform(0.96, 1.04) * _ls_b
    _ratio = float(cfg.get("ratio", 1.0)) * _r.uniform(0.985, 1.015)
    sc = SynthesisConfig(length_scale=_ls, noise_scale=0.62 + _r.uniform(-0.04, 0.04),
                         noise_w_scale=0.75)
    import respell as RS
    _txt = RS.respell(text)          # mahapraan giraane wali galti ka ilaaj (sirf TTS ke liye)
    with wave.open(str(raw), "wb") as w:
        v.synthesize_wav(_txt, w, syn_config=sc)
    # formant-safe pitch shift + humanize + warm EQ + room + breath (apna FX)
    import voice_fx as fx
    src = load(raw)
    y = fx.pitch_resample(src, _ratio)
    if abs(_semi_b) > 0.15:
        y = fx.pitch_shift_formant(y, _semi_b)
    if abs(_db_b) > 0.2:
        y = y * (10 ** (_db_b / 20.0))
    if cfg.get("formant"):
        y = fx.formant_shift(y, float(cfg["formant"]))     # umar/chehra: F0 nahi, formant badlo (ASR safe)
    y = fx.prosody_contour(y, SR, depth_st=float(cfg.get("contour", 0.6)), seed=abs(hash(text)) % 9999)
    y = fx.trim_silence(y)
    y = fx.compress_silences(y, SR, min_gap=0.10, max_gap=0.35)   # duniya niyam: saans bachi rahe
    y = fx.smooth_chain(y, semitones=0.0, human=True, br=True, warm_eq=True, rv=False)
    y = fx.de_buzz(y, SR)
    y = fx.trim_silence(y, keep_ms=40)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("int16").tobytes())
    raw.unlink(missing_ok=True)
    try:
        line_check(y, SR, cfg.get("who", ""), text)      # realtime/gates + nirantarta — har line par
    except Exception as _e:
        print(f'[chhoti dikkat] {type(_e).__name__}: {_e}', file=__import__('sys').stderr)
    return out


def load(p: Path):
    r = subprocess.run([FF, "-v", "quiet", "-i", str(p), "-f", "s16le", "-ac", "1",
                        "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768


def group_script(script):
    """Lagatar ek hi kirdaar ki lines jodo — beech me rukna band (ruk-ruk ka ilaaj)."""
    out = []
    for row in script:
        who, text = row[0], row[1]
        if out and out[-1][0] == who:
            out[-1] = (who, out[-1][1] + " " + text)
        else:
            out.append((who, text))
    return out


def build(out_mp3: Path):
    import ambience as amb
    work = HERE / "work"; work.mkdir(exist_ok=True)
    clips = []
    _last_breath_s = 0.0
    _breath_log = []
    _script = group_script(SCRIPT)
    for i, (who, text) in enumerate(_script):
        p = synth_line(text, {**CAST[who], "who": who}, work / f"line{i:02d}.wav")
        clips.append((who, p, load(p)))
    # scene break: har 4th line ke baad lamba ruk (duniya ubharne ke liye) — duniya niyam 1.4–2.6s
    scene_gap = {i: 1.2 for i in range(3, len(clips), 4)}
    total = (sum(len(c[2]) for c in clips)
             + int(SR * sum(CAST[c[0]]["pause"] for c in clips))
             + int(SR * sum(scene_gap.values())) + SR)
    voice = np.zeros(total)
    _join = True
    t = 0
    marks = []
    prev_end = 0
    for _idx, (who, p, sig) in enumerate(clips):
        if t > 0 and t == prev_end:
            n = int(0.02 * SR)
            if n < len(sig):
                sig = sig.copy()
                sig[:n] *= np.linspace(0, 1, n)
        voice[t:t+len(sig)] += sig
        # saans: time + bhaav ke hisaab se (line number se nahi)
        _since = (t / SR) - _last_breath_s
        _gap_before = (t / SR) - prev_end / SR if prev_end else 0
        _plan = breath_plan(_script[_idx][1], _since) if _gap_before >= 0.9 else None
        if _plan:
            _emo, _dur, _lvl, _band = _plan
            br = breath(_dur, level=_lvl, band=_band, seed=100 + _idx)
            b_start = max(prev_end, t - len(br) - int(SR * 0.06))   # BUG: saans speech par chadh rahi thi (pehla shabd kha jaati thi)
            voice[b_start:b_start + len(br)] += br
            _last_breath_s = t / SR
            _breath_log.append({"at_s": round(t / SR, 2), "emotion": _emo, "dur_s": _dur})
        _semi_i, _ls_i, _db_i, _emo_i, _inten_i = bhaav_prosody(_script[_idx][1], who)
        marks.append({"who": who, "start": round(t/SR, 2), "dur": round(len(sig)/SR, 2),
                      "text": _script[_idx][1], "bhaav": _emo_i, "intensity": round(_inten_i, 2)})
        prev_end = t + len(sig)
        idx_now = len(marks) - 1
        t += len(sig) + int(SR * CAST[who]["pause"]) + int(SR * scene_gap.get(idx_now, 0))
    dur = len(voice) / SR
    # ---- duniya ki awaaz: har line ke shabd se sound, line-wise automation
    bed = np.zeros(total)
    _real_used = []
    try:
        import real_bed as RB
        _env = os.environ.get("SEETAL_BED", "").strip()
        _kinds = [(x.split(":")[0], float(x.split(":")[1])) for x in _env.split(",")] if _env else [(k, w) for k, w in MOODS["bed"]]
        _rb, _real_used = RB.make_bed(_kinds, total, SR, level_db=-24)
        if _rb is not None:
            bed += _rb.astype(np.float32)      # ASLI recordings (synthetic nahi)
    except Exception as _e:
        _real_used = [{"error": type(_e).__name__}]
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
    if _os.environ.get("SEETAL_HP", "1") == "1":
        voice = _hp(voice, 130); bed = _hp(bed, 220)
    # bed ka level APNE AAP calibrate: gaps me awaaz se 12 dB neeche (naap se, andaaze se nahi)
    _vr = float(np.sqrt((voice ** 2).mean())) + 1e-9
    _br = float(np.sqrt((bed ** 2).mean())) + 1e-9
    _bg = min(1.0, (_vr * (10 ** (-12 / 20))) / _br) if (_real_used and 'error' not in _real_used[0]) else 0.16
    mix = voice * 0.95 + bed * _bg
    mix = _presence(np.tanh(mix * 1.05))
    mix[:len(room_tone(len(mix)))] += room_tone(len(mix))   # holes band
    mix_st = None
    if _os.environ.get("SEETAL_STEREO", "1") == "1":
        mix_st = _stereo(voice * 0.95, np.tanh(bed * _bg * 1.05) * 0.55, width=0.12, delay_ms=5)
        _rt = room_tone(len(mix_st), level_db=-48)
        mix_st[:, 0] += _rt; mix_st[:, 1] += _rt * 0.96     # dono channel me halka room tone
    rms = float(np.sqrt((mix**2).mean())) + 1e-9
    mix *= (10 ** (-16.9/20)) / rms
    mix = mix / max(1.0, float(np.max(np.abs(mix)))/0.95)
    wav = out_mp3.with_suffix(".wav")
    if mix_st is not None:
        mix_st = np.stack([_presence(mix_st[:, 0]), _presence(mix_st[:, 1])], axis=1)
        # soft limiter (peak 0.98) phir RMS -16.9 dBFS — LUFS target -16 ke liye
        mix_st = mix_st / max(1e-9, float(np.max(np.abs(mix_st)))) * 0.98
        mix_st = np.tanh(mix_st * 1.05)
        _r = float(np.sqrt((mix_st ** 2).mean())) + 1e-9
        mix_st = mix_st * (10 ** (-16.9 / 20)) / _r
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
            "line_checks": _LINE_GATES, "real_bed": _real_used, "breaths": _breath_log, "breaths_per_min": round(len(_breath_log) / max(1e-6, (len(mix)/SR/60)), 2),
            "marks": marks, "bed": MOODS["bed"], "peak": round(float(np.max(np.abs(mix))), 2),
            "rms_dbfs": round(20*float(np.log10(max(1e-9, float(np.sqrt((mix**2).mean()))))), 1)}
    (HERE / "story_local.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    # world_qa ke liye voice-stem gaps (sidecar) — mix me bed gaps chhupa deta hai
    try:
        _all = [round(g/1000, 3) for g in _gaps]
        Path(str(out_mp3).rsplit(".", 1)[0] + ".pauses.json").write_text(
            json.dumps({"voice_gaps_s": _all}, ensure_ascii=False), encoding="utf-8")
    except Exception as _e:
        print(f'[chhoti dikkat] {type(_e).__name__}: {_e}', file=__import__('sys').stderr)
    return info


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "local-story.mp3"
    SCRIPT_JSON = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if SCRIPT_JSON and SCRIPT_JSON.exists():
        import json as _json
        _new = [(r["who"], r["text"], r.get("bhaav", "")) for r in _json.loads(SCRIPT_JSON.read_text(encoding="utf-8"))]
        globals()["SCRIPT"] = _new
    print(json.dumps(build(out), ensure_ascii=False))
