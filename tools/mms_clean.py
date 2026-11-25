#!/usr/bin/env python3
"""mms_clean.py — bina background, bina artefact: sirf saaf awaaz.

Bhrrr/buzz ki jad: 20-120 Hz rumble + 2-5k metallic + hiss. Yahan:
  • 100 Hz high-pass (rumble)   • halka de-ess 6-8.5k   • loudness -16 LUFS
"""
import sys, subprocess, numpy as np, soundfile as sf
from pathlib import Path
sys.path.insert(0,"tools"); sys.path.insert(0,".")
from scipy import signal as ss
import ffbin, pyloudnorm as ln
SR=24000
CFG={"गौरी":205,"कमला":186,"मोहन":275}
lines=[]
for l in Path("/tmp/nai-kahani.txt").read_text(encoding="utf-8").splitlines():
    if ":" in l:
        w,t=l.split(":",1)
        if t.strip(): lines.append((w.strip(), t.strip()))
tmp=Path("/tmp/clean_parts"); tmp.mkdir(exist_ok=True)
pieces=[]
for i,(who,text) in enumerate(lines):
    f=tmp/f"{i}.wav"
    if not f.exists():
        pitch=float(np.clip(CFG.get(who,150)/190.0,0.8,1.35))
        subprocess.run([sys.executable,"tools/mms_worker.py","--text",text,"--out",str(f),"--pitch",f"{pitch:.3f}"],capture_output=True)
    y,sr=sf.read(str(f)); y=y.mean(1) if y.ndim>1 else y
    # rumble hatao (bhrrr) — 100 Hz high-pass
    sos=ss.butter(4, 100/(SR/2), btype="high", output="sos")
    y=ss.sosfilt(sos, y.astype(np.float64))
    # halka de-ess: 6-8k ki chamak niyantran
    sos2=ss.butter(2,[6000/(SR/2), min(0.95, 8500/(SR/2))],btype="band",output="sos")
    y=y-0.15*ss.sosfilt(sos2,y)
    pieces.append(y); pieces.append(np.zeros(int(0.28*SR)))
voice=np.concatenate(pieces)
voice=voice/(np.max(np.abs(voice))+1e-9)*0.9
meter=ln.Meter(SR); voice=ln.normalize.loudness(voice, meter.integrated_loudness(voice), -16.0)
pk=float(np.max(np.abs(voice)))
if pk>0.95: voice=voice*(0.95/pk)
sf.write("/scratch/output/kahani-voice-clean.wav", voice.astype("float32"), SR)
subprocess.run([ffbin.ensure(),"-v","error","-y","-i","/scratch/output/kahani-voice-clean.wav","-b:a","160k","/scratch/output/kahani-voice-clean.mp3"],check=True)
print("dur", round(len(voice)/SR,1), "peak", round(float(np.max(np.abs(voice))),3))
