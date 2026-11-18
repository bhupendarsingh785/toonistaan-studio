#!/usr/bin/env python3
"""
ASTRA — Music Probe: naam nahi, awaaz sun kar bhaav pehchano.

Har music file ko naap-ta hai:
  - tempo (BPM), energy (RMS), brightness (spectral centroid),
    low-end (bass), onset density (kitni harkat), chuppi
  - in sabse ek "bhaav" (mood) nikalta hai:
      calm, sad, romantic, happy, epic, tension, horror, mystery, action, lullaby

Sach: ye **acoustic naap** hai (asli sunna nahi). Isliye report me
"confidence" aur "evidence" dono likhe jaate hain — jhooth nahi.

Chalao:
  python3 astra/music_probe.py                 # poore music folder ka report
  python3 astra/music_probe.py <file.mp3>      # ek file
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library")
SR = 22050


def ff():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def load(path, seconds=60):
    cmd = [ff(), "-loglevel", "error", "-i", path, "-t", str(seconds),
           "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or len(r.stdout) < 8000:
        return None
    return np.frombuffer(r.stdout, dtype=np.float32)


def analyse(path):
    x = load(path)
    if x is None or len(x) < SR:
        return None
    x = x / (np.abs(x).max() + 1e-9)

    # --- energy
    rms = float(np.sqrt((x ** 2).mean()))

    # --- spectrum (average)
    win = 2048
    hop = 1024
    frames = 1 + (len(x) - win) // hop
    frames = min(frames, 900)
    if frames < 4:
        return None
    spec = np.zeros(win // 2 + 1)
    flux = []
    prev = None
    for i in range(frames):
        seg = x[i * hop:i * hop + win]
        if len(seg) < win:
            break
        mag = np.abs(np.fft.rfft(seg * np.hanning(win)))
        spec += mag
        if prev is not None:
            flux.append(float(np.maximum(mag - prev, 0).sum()))
        prev = mag
    spec /= max(1, frames)
    freqs = np.fft.rfftfreq(win, 1 / SR)
    centroid = float((spec * freqs).sum() / (spec.sum() + 1e-9))
    bass = float(spec[freqs < 200].sum() / (spec.sum() + 1e-9))
    high = float(spec[freqs > 4000].sum() / (spec.sum() + 1e-9))
    # flatness: 1 = shor/ambient, 0 = saaf sur
    band = spec[(freqs > 100) & (freqs < 6000)] + 1e-12
    flatness = float(np.exp(np.log(band).mean()) / band.mean()) if len(band) else 0.0
    # percussive: onsets ka utar-chadhav (dhol/tabla zyada)
    perc = float(np.std(flux) / (np.mean(flux) + 1e-9)) if flux else 0.0

    # --- tempo (onset envelope autocorrelation)
    bpm = 0.0
    if len(flux) > 20:
        env = np.array(flux, dtype=np.float32)
        env = env - env.mean()
        ac = np.correlate(env, env, "full")[len(env) - 1:]
        lo, hi = int(SR / hop * 60 / 200), int(SR / hop * 60 / 40)
        hi = min(hi, len(ac) - 1)
        if hi > lo + 2:
            lag = lo + int(np.argmax(ac[lo:hi]))
            if lag > 0:
                bpm = 60.0 * SR / (hop * lag)
    # octave fold: 40-200 ke bahar wala tempo asli nahi hota
    while bpm > 180:
        bpm /= 2.0
    while 0 < bpm < 50:
        bpm *= 2.0

    onset = float(np.mean(flux)) if flux else 0.0
    onset_n = onset / (spec.sum() / max(1, frames) + 1e-9)

    # --- mood (naap se, naam se nahi) — do axis: bhaav + tarah
    mood, conf, why = "neutral", 0.30, []
    calm = rms < 0.09 and onset_n < 0.45 and perc < 2.2
    slow = 0 < bpm <= 85
    mid = 85 < bpm <= 125
    fast = bpm > 125
    dark = bass > 0.35 and centroid < 1400
    bright = centroid > 2200

    if flatness > 0.12 and calm:
        mood, conf = "ambient", 0.6
        why.append("shor-jaisa patla sound, dheema")
    elif dark and flatness > 0.06 and rms < 0.14:
        mood, conf = "horror", 0.55
        why.append("gehra bass + dhundhla sound")
    elif calm and slow and centroid < 1500:
        mood, conf = "lullaby", 0.55
        why.append("bahut dheema, narm, kam awaaz")
    elif calm and slow:
        mood, conf = "calm", 0.6
        why.append("dheema + shaant")
    elif slow and dark:
        mood, conf = "sad", 0.55
        why.append("dheema + gehra/bhaari")
    elif slow and not dark:
        mood, conf = "romantic", 0.5
        why.append("dheema + garam/narm sur")
    elif mid and perc > 2.5:
        mood, conf = "devotional", 0.5
        why.append("tabla/dhol jaisa taal + madhyam tempo")
    elif mid and bright:
        mood, conf = "happy", 0.55
        why.append("madhyam tempo + khula/chamakdar")
    elif fast and rms > 0.15 and perc > 2.0:
        mood, conf = "epic", 0.55
        why.append("tez + zor + taal")
    elif fast and bright:
        mood, conf = "action", 0.5
        why.append("tez + bahut chamakdar")
    elif mid and flatness > 0.05:
        mood, conf = "mystery", 0.45
        why.append("madhyam tempo, dhundhla sound")
    else:
        why.append("saaf pehchan nahi — neutral rakha")

    return {
        "file": os.path.relpath(path, LIB),
        "bpm": round(bpm, 1),
        "rms": round(rms, 3),
        "centroid_hz": round(centroid),
        "bass_share": round(bass, 2),
        "high_share": round(high, 2),
        "onset_density": round(onset_n, 2),
        "flatness": round(flatness, 3),
        "percussive": round(perc, 2),
        # ye sirf ANDAZA hai (naam nahi, sunna bhi nahi) — faisla isse nahi hota
        "guess": mood,
        "guess_confidence": round(conf, 2),
        # ye naap bharosemand hain — mix (gain/fade/ducking) me inhi ka use hota hai
        "mix_facts": {"loudness_rms": round(rms, 3), "brightness_hz": round(centroid),
                      "bass_share": round(bass, 2), "activity": round(onset_n, 2)},
        "evidence": why,
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        for p in args:
            r = analyse(p)
            print(json.dumps(r or {"file": p, "error": "padha nahi ja saka"}, ensure_ascii=False, indent=2))
        return 0

    files = []
    for r, _, fs in os.walk(os.path.join(LIB, "music")):
        for f in fs:
            if f.endswith(".mp3"):
                files.append(os.path.join(r, f))
    files.sort()
    print(f"music files: {len(files)}", flush=True)
    out = []
    for p in files:
        r = analyse(p)
        if r:
            out.append(r)
            print(f"{r['guess']:9s} {r['guess_confidence']:.2f} | {r['bpm']:5.0f} BPM | "
                  f"rms {r['rms']:.3f} | cen {r['centroid_hz']:5d} | {r['file']}", flush=True)
    json.dump(out, open(os.path.join(HERE, "music_probe_report.json"), "w"), ensure_ascii=False, indent=1)
    print("report: astra/music_probe_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
