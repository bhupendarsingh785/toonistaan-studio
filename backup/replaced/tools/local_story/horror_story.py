#!/usr/bin/env python3
"""Horror story demo — sab apna: piper awaaz + apni synth awaazein (jeev, zameen, mahaul).

CLI: python horror_story.py out.mp3
"""
from __future__ import annotations
import json, subprocess, sys, wave
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE.parent / "src" / "tools"))
SR = 44100
VOICES = {"m": HERE.parent/"voices/hi_IN-pratham-medium.onnx", "f": HERE.parent/"voices/hi_IN-priyamvada-medium.onnx"}

def ffmpeg():
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()

# kirdaar: voice, length_scale, pitch ratio, formant-ish (resample se hi)
CAST = {
 "narrator": {"v": "m", "ls": 0.98, "ratio": 1.00},
 "dadi":     {"v": "f", "ls": 1.10, "ratio": 0.74},
 "bachcha":  {"v": "f", "ls": 0.92, "ratio": 1.04},
 "aadmi":    {"v": "m", "ls": 0.96, "ratio": 0.92},
}
EMO = {  # (pitch ratio ×, rate ls ×)
 "neutral": (1.00, 1.00), "dar": (1.04, 1.10), "dukh": (0.96, 0.92),
 "khushi": (1.05, 1.05), "gussa": (1.02, 1.08), "hairan": (1.06, 0.95),
}
SCRIPT = [
 ("narrator", "गाँव के पीछे एक पुरानी हवेली थी, जिसके दरवाज़े चालीस साल से बंद थे।", "neutral"),
 ("bachcha",  "दादी, उस हवेली में रोशनी क्यों जलती है रात को?", "hairan"),
 ("dadi",     "बेटा, उस तरफ़ मत देख। वहाँ सिर्फ़ पेड़ हैं… और पेड़ों के पीछे कुछ और भी।", "dar"),
 ("narrator", "उस रात बारिश शुरू हुई। जंगल से झींगुरों की आवाज़ आ रही थी, और दूर नदी बह रही थी।", "neutral"),
 ("aadmi",    "अरे! इतनी रात को तुम लोग यहाँ क्यों खड़े हो? हवेली की तरफ़ मत जाओ।", "gussa"),
 ("bachcha",  "अंकल, वहाँ कोई रो रहा है… सुनिए ना।", "dar"),
 ("narrator", "झाड़ियों में हलचल हुई। सूखे पत्तों पर किसी के कदम चरमराए।", "dar"),
 ("dadi",     "भागो! भेड़िया है! भागो बेटा, भागो!", "dar"),
 ("narrator", "भेड़िया गुर्राया। उसकी आँखें बारिश में चमकीं, और वह पीछे मुड़कर जंगल में खो गया।", "dar"),
 ("bachcha",  "दादी… वो हमें कुछ नहीं करेगा ना?", "dukh"),
 ("dadi",     "नहीं बेटा। वो हमारा ही है — हमारे पुरखों का रखवाला।", "dukh"),
 ("narrator", "सुबह होते ही हवेली के दरवाज़े अपने आप खुल गए। अंदर से ठंडी हवा निकली, जैसे कोई साँस ले रहा हो।", "dar"),
 ("aadmi",    "चलो यहाँ से। यह जगह बोलती है, और जो बोलती है, वो भूलती नहीं।", "dar"),
 ("narrator", "आज भी गाँव के बच्चे कहते हैं — हवेली में रोशनी अब भी जलती है। और जंगल में भेड़िया आज भी पहरा देता है।", "neutral"),
]
WORLD = {"हवेली": "wind", "दरवाज़े": "wind", "पेड़": "leaves", "जंगल": "leaves", "झाड़ियों": "leaves",
         "बारिश": "rain", "नदी": "river", "झींगुरों": "crickets", "पत्तों": "leaves", "कदम": "steps_dirt",
         "भेड़िया": "wolf", "रोशनी": "wind", "आँखें": "wolf"}


def synth_line(text, who, emo):
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    cfg = CAST[who]; p_ratio, r_ls = EMO[emo]
    v = PiperVoice.load(str(VOICES[cfg["v"]]), config_path=str(VOICES[cfg["v"]]) + ".json")
    tmp = HERE/"work"; tmp.mkdir(exist_ok=True)
    raw = tmp/"line.wav"
    with wave.open(str(raw), "wb") as w:
        v.synthesize_wav(text, w, syn_config=SynthesisConfig(
            length_scale=cfg["ls"]*r_ls, noise_scale=0.62, noise_w_scale=0.75))
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", str(raw), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                       capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.float32).copy()
    # pitch: resample (deterministic, koi artifact nahi)
    ratio = cfg["ratio"] * p_ratio
    if abs(ratio - 1) > 0.005:
        n_out = max(2, int(len(x) / ratio))
        x = np.interp(np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x)
    return x


def trim(x, keep=0.03):
    w = 256
    e = np.array([np.sqrt((x[i:i+w]**2).mean()) for i in range(0, max(1, len(x)-w), w)])
    idx = np.where(e > 10**(-42/20))[0]
    if not len(idx): return x
    a = max(0, idx[0]*w - int(keep*SR)); b = min(len(x), idx[-1]*w + w + int(keep*SR))
    return x[a:b]


def compress_gaps(x, rel_db=-20, max_gap=0.028, min_gap=0.045):
    w = 128
    e = np.array([np.sqrt((x[i:i+w]**2).mean()) for i in range(0, max(1, len(x)-w), w)])
    if not len(e): return x
    thr = max(10**(-45/20), float(np.percentile(e, 75)) * 10**(rel_db/20))
    q = e <= thr
    out = []; prev = 0; i = 0
    while i < len(q):
        if q[i]:
            j = i
            while j < len(q) and q[j]: j += 1
            if (j-i)*w/SR >= min_gap:
                sa, sb = i*w, min(len(x), j*w)
                out.append(x[prev:sa]); out.append(x[sa:sa+int(max_gap*SR)])
                prev = sb
            i = j
        else:
            i += 1
    out.append(x[prev:])
    return np.concatenate(out) if out else x


def eq_warm(x):
    n = len(x); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1/SR)
    c = np.ones_like(f)
    c *= 1/(1+(95/(f+1e-9))**4)
    c += 0.05*np.exp(-((f-600)**2)/(2*380**2))
    c += 2.30*np.exp(-((f-3200)**2)/(2*1400**2))
    c += 1.45*np.exp(-((f-6200)**2)/(2*1900**2))
    c -= 0.38*np.exp(-((f-7500)**2)/(2*1300**2))
    return np.fft.irfft(X*c, n)


def build(out_mp3: Path):
    import sound_synth as ss
    clips, marks = [], []
    t = 0.0
    for who, text, emo in SCRIPT:
        x = trim(compress_gaps(trim(synth_line(text, who, emo))))
        x = eq_warm(x)
        clips.append(x); marks.append({"who": who, "start": round(t, 2), "dur": round(len(x)/SR, 2),
                                       "text": text, "emo": emo})
        t += len(x)/SR + 0.35
    total = int((t + 1.0) * SR)
    voice = np.zeros(total)
    pos = 0
    for x in clips:
        voice[pos:pos+len(x)] += x
        pos += len(x) + int(0.35*SR)
    dur = total / SR
    # ---- duniya: har line ke shabd se bed + jeev
    def fit(y):
        y = np.asarray(y, dtype=np.float32)[:total]
        return np.pad(y, (0, total-len(y))) if len(y) < total else y
    beds = {"rain": 0.18, "river": 0.14, "wind": 0.20, "leaves": 0.12, "crickets": 0.10, "air": 0.7}
    from ambience import wind as amb_wind, leaves as amb_leaves, air as amb_air
    tracks = {"rain": fit(ss.rain(dur+1)), "river": fit(ss.river(dur+1)),
              "wind": fit(amb_wind(dur+1)), "leaves": fit(amb_leaves(dur+1)),
              "crickets": fit(ss.cricket(dur+1)), "air": fit(amb_air(dur+1))}
    gain = {k: np.full(total, beds[k], dtype="float32") for k in tracks}
    # jeev cues: bhediya line par growl, kadmon par steps
    wolf = fit(ss.wolf_growl(2.5)); dog = fit(ss.dog_bark(1.6))
    for m in marks:
        a = int(m["start"]*SR); b = min(total, a + int(m["dur"]*SR))
        for word, snd in WORLD.items():
            if word in m["text"] and snd in gain:
                gain[snd][a:b] = np.maximum(gain[snd][a:b], beds[snd]*2.6)
        if "भेड़िया" in m["text"]:
            seg = wolf[:max(1, min(len(wolf), total - a))]
            voice[a:a+len(seg)] += seg * 0.35
        if "कदम" in m["text"] or "भागो" in m["text"]:
            steps = fit(ss.leaves_steps(min(3.0, max(0.5, m["dur"]))))
            end = min(total, a + len(steps))
            voice[a:end] += steps[:end-a] * 0.28
        if "दरवाज़े" in m["text"] or "हवेली" in m["text"]:
            gain["wind"][a:b] = np.maximum(gain["wind"][a:b], beds["wind"]*2.2)
    k = int(1.2*SR); ker = np.ones(k, dtype="float32")/k
    bed = np.zeros(total)
    for name, tr in tracks.items():
        bed += tr * np.convolve(gain[name], ker, mode="same")
    duck = np.ones(total)
    for m in marks:
        a = int(m["start"]*SR); b = min(total, a+int(m["dur"]*SR))
        duck[a:b] = np.minimum(duck[a:b], 0.45)
    mix = voice*0.95 + bed*0.30*duck
    mix = np.tanh(mix*1.03)
    mix *= (10**(-17/20)) / max(1e-9, float(np.sqrt((mix**2).mean())))
    mix = mix / max(1.0, float(np.max(np.abs(mix)))/0.95)
    wav = HERE/"horror-story.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1)*32767).astype("int16").tobytes())
    subprocess.run([ffmpeg(), "-v", "quiet", "-y", "-i", str(wav), "-codec:a", "libmp3lame",
                    "-b:a", "192k", str(out_mp3)], check=False)
    info = {"file": str(out_mp3), "dur": round(len(mix)/SR, 1), "lines": len(SCRIPT),
            "marks": marks, "world": list(WORLD.values()), "peak": round(float(np.max(np.abs(mix))), 2)}
    (HERE/"horror_story.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE/"horror_lines.json").write_text(json.dumps([{"who": w, "text": t} for w, t, _ in SCRIPT],
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    return info


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE/"horror-story.mp3"
    print(json.dumps(build(out), ensure_ascii=False)[:400])
