#!/usr/bin/env python3
"""Ground demo — ek hi kahani me teen zameen: kachchi mitti, sookhe patte, pakka farash."""
import sys, wave, json, subprocess
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from piper import PiperVoice
from piper.config import SynthesisConfig
import ambience as amb
SR = 44100
V = PiperVoice.load(str(HERE.parent/"voices/hi_IN-pratham-medium.onnx"),
                    config_path=str(HERE.parent/"voices/hi_IN-pratham-medium.onnx.xml".replace(".xml",".json")))
LINES = [
 ("narrator", "वो कच्ची मिट्टी के रास्ते पर धीरे-धीरे चलने लगा।", "steps_dirt"),
 ("narrator", "फिर सूखे पत्तों पर उसके कदम चरमराने लगे।", "steps_leaves"),
 ("narrator", "पुरानी इमारत के पक्के फर्श पर कदम टकराए।", "steps_concrete"),
]
def ffmpeg():
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()
clips = []
for who, text, ground in LINES:
    p = HERE/f"work/demo_{ground}.wav"; p.parent.mkdir(exist_ok=True)
    with wave.open(str(p), "wb") as w:
        V.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=0.98, noise_scale=0.62, noise_w_scale=0.75))
    r = subprocess.run([ffmpeg(), "-v","quiet","-i",str(p),"-f","f32le","-ac","1","-ar",str(SR),"-"], capture_output=True)
    voice = np.frombuffer(r.stdout, dtype=np.float32).copy()
    n = len(voice)
    def fit(x):
        x = np.asarray(x, dtype=np.float32)[:n]
        return np.pad(x, (0, n - len(x))) if len(x) < n else x
    steps = fit(getattr(amb, ground)(n/SR + 0.5))
    bed = fit(amb.air(n/SR + 0.5)) * 0.5
    mix = voice*0.95 + steps*0.5 + bed*0.25
    clips.append((ground, mix))
gap = np.zeros(int(0.35*SR), dtype=np.float32)
full = np.concatenate([np.concatenate([c[1], gap]) for c in clips])
full = np.tanh(full*1.05)
full *= (10**(-16/20))/max(1e-9, float(np.sqrt((full**2).mean())))
out = HERE/"ground-demo.wav"
with wave.open(str(out), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(full,-1,1)*32767).astype("int16").tobytes())
mp3 = HERE/"ground-demo.mp3"
subprocess.run([ffmpeg(), "-v","quiet","-y","-i",str(out),"-codec:a","libmp3lame","-b:a","192k",str(mp3)], check=False)
print(json.dumps({"file": str(mp3), "dur": round(len(full)/SR,1), "grounds": [c[0] for c in clips]}, ensure_ascii=False))
