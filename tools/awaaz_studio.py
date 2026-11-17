#!/usr/bin/env python3
"""
Toonistaan AWAAZ STUDIO — Pocket FM jaisi "insan wali" awaaz.

Kya karta hai (kram se):
 1. Har line ko kirdaar + bhaav ke saath bolwata hai (tools/awaaz.py se)
 2. Line ke andar comma/danda par chhota saans (natural pause)
 3. Line ke beech halki **saans** (breath) — robot jaisa nahi lagta
 4. Lines ke beech chup-chaap chhota gap (jaisa insan bolta hai)
 5. Peeche **mahaul** (baaris, hawa, jhingur, kamre ki goonj) — bahut dheema
 6. Peeche **music bed** (mood ke hisaab se) — awaaz aate hi dab jata hai (ducking)
 7. Aakhir me Pocket FM master: EQ -> compressor -> limiter -> **-16 LUFS**

Chalane ka tareeka:
  python3 tools/awaaz_studio.py sunao script.json -o kahani.mp3
  python3 tools/awaaz_studio.py sunao script.json -o kahani.mp3 --mahaul rain --music calm

script.json (do tarah se likh sakte hain):
  {"mahaul": "rain", "music": "calm",
   "lines": [["swara_bachcha", "दादी! बचाओ!", "scared"],
             ["swara_dadi", "डरो मत बेटा।", "calm"]]}
ya seedha:
  {"lines": ["पहली लाइन", "दूसरी लाइन"]}     (narrator madhur, bhaav apne aap)

Zaroorat: ffmpeg, numpy, edge-tts
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.join(os.path.dirname(HERE), "studio")
sys.path.insert(0, HERE)
sys.path.insert(0, STUDIO)

SR = 44100


# ---------------------------------------------------------------- helpers
def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def dur_of(path):
    r = sh(["ffmpeg", "-hide_banner", "-i", path])
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def to_wav(src, dst, sr=SR):
    sh(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-ac", "1", "-ar", str(sr), dst])
    return dst


def read_wav(path):
    import wave
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return x


def write_wav(path, x):
    import wave
    x = np.clip(x, -1, 1)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def silence(sec):
    return np.zeros(int(SR * max(0.0, sec)), np.float32)


# ---------------------------------------------------------------- saans
def breath(level=0.06, length=0.28):
    """Halki saans — sunai de par khatke na."""
    n = int(SR * length)
    tt = np.linspace(0, length, n, False)
    noise = np.random.randn(n).astype(np.float32)
    # sirf "hawa" wali awaaz: halka band-pass
    k = max(1, int(SR * 0.002))
    noise = np.convolve(noise, np.ones(k) / k, "same")
    env = np.sin(np.pi * tt / length) ** 2
    return (noise * env * level).astype(np.float32)


# ---------------------------------------------------------------- mahaul
def ambience(kind="room", sec=10.0):
    """Peeche ka mahaul (bahut dheema). kind: room, rain, wind, night, village."""
    import sfx
    n = int(SR * sec)
    if kind == "rain":
        base = sfx.noise(sec) * 0.5
        base = sfx.lowpass(base, 6000) * 0.55 + sfx.noise(sec) * 0.10
    elif kind == "wind":
        base = sfx.wind(sec)
    elif kind == "night":
        base = sfx.noise(sec) * 0.12
        tt = sfx.t(sec)
        # jhingur: do tez tikh-tikh
        for f in (4200, 5100):
            gate = (np.sin(2 * np.pi * 6.5 * tt) > 0.93).astype(np.float32)
            base = base + np.sin(2 * np.pi * f * tt) * gate * 0.05
    elif kind == "village":
        base = sfx.noise(sec) * 0.15 + sfx.lowpass(sfx.noise(sec), 300) * 0.35
    else:  # room tone
        base = sfx.lowpass(sfx.noise(sec), 500) * 0.12
    if len(base) < n:
        base = np.pad(base, (0, n - len(base)))
    base = base[:n]
    pk = float(np.abs(base).max()) or 1.0
    return (base / pk * 0.10).astype(np.float32)


# ---------------------------------------------------------------- music
def music_bed(mood="calm", sec=10.0):
    import sfx
    m = sfx.music(mood, sec + 1.0)
    m = m[: int(SR * sec)]
    if len(m) < int(SR * sec):
        m = np.pad(m, (0, int(SR * sec) - len(m)))
    pk = float(np.abs(m).max()) or 1.0
    return (m / pk * 0.16).astype(np.float32)


# ---------------------------------------------------------------- main
def sunao(script_path, out, mahaul="room", music="calm", gap=0.45, rate_shift=True):
    data = json.load(open(script_path, encoding="utf-8"))
    lines = data.get("lines") or []
    if not lines:
        sys.exit("script me 'lines' nahi mila")
    mahaul = data.get("mahaul", mahaul)
    music = data.get("music", music)

    tmp = tempfile.mkdtemp(prefix="awaaz_")
    parts = []      # (audio, kind)
    total = 0.0

    for idx, item in enumerate(lines):
        if isinstance(item, str):
            kirdaar, text, bhaav = "madhur", item, None
        elif isinstance(item, (list, tuple)):
            kirdaar = item[0] if len(item) > 0 else "madhur"
            text = item[1] if len(item) > 1 else ""
            bhaav = item[2] if len(item) > 2 else None
        else:
            kirdaar = item.get("kirdaar", "madhur")
            text = item.get("text", "")
            bhaav = item.get("bhaav")

        if not str(text).strip():
            continue

        mp3 = os.path.join(tmp, f"l{idx}.mp3")
        cmd = [sys.executable, os.path.join(HERE, "awaaz.py"), "bolo", text, "--kirdaar", kirdaar, "-o", mp3]
        if bhaav:
            cmd += ["--bhaav", bhaav]
        r = sh(cmd)
        if r.returncode != 0 or not os.path.exists(mp3):
            print("LINE_FAIL", idx, r.stderr[-160:], flush=True)
            continue

        wav = to_wav(mp3, os.path.join(tmp, f"l{idx}.wav"))
        x = read_wav(wav)

        # 1) halki saans shuru me (har line par nahi — ghadi-ghadi ajeeb lagta hai)
        if idx % 2 == 0:
            x = np.concatenate([breath(0.05, 0.22), x])

        # 2) line ke baad chhota "saans" + gap
        x = np.concatenate([x, breath(0.035, 0.18), silence(gap)])

        parts.append(x)
        total += len(x) / SR
        print("LINE_OK", idx, kirdaar, round(len(x) / SR, 2), "s", flush=True)

    if not parts:
        sys.exit("koi line nahi bani")

    voice = np.concatenate(parts)
    n = len(voice)

    # mahaul + music ko awaaz ki lambai tak stretch karo
    amb = ambience(mahaul, n / SR + 1)
    mus = music_bed(music, n / SR + 1)
    amb = np.pad(amb, (0, max(0, n - len(amb))))[:n]
    mus = np.pad(mus, (0, max(0, n - len(mus))))[:n]

    # ducking: awaaz aate hi music neeche
    win = int(SR * 0.25)
    env = np.convolve(np.abs(voice), np.ones(win) / win, "same")
    thr = max(0.01, float(np.percentile(env, 55)))
    duck = np.where(env > thr, 0.35, 1.0)
    duck = np.convolve(duck, np.ones(int(SR * 0.30)) / int(SR * 0.30), "same")

    mix = voice + amb + mus * duck
    pk = float(np.abs(mix).max()) or 1.0
    mix = mix / pk * 0.95

    premix = os.path.join(tmp, "premix.wav")
    write_wav(premix, mix)

    # Pocket FM master: saaf + garam + -16 LUFS
    af = ("highpass=f=70,"
          "equalizer=f=180:t=q:w=1.0:g=-1.5,"
          "equalizer=f=3200:t=q:w=1.2:g=2.5,"
          "equalizer=f=9000:t=q:w=1.0:g=1.0,"
          "deesser=i=0.3,"
          "acompressor=threshold=0.10:ratio=2.6:attack=6:release=180:makeup=1.5,"
          "alimiter=limit=0.95,"
          "loudnorm=I=-16:TP=-1.5:LRA=11")
    codec = ["-c:a", "libmp3lame", "-b:a", "192k"] if out.lower().endswith(".mp3") else []
    r = sh(["ffmpeg", "-loglevel", "error", "-y", "-i", premix, "-af", af, "-ar", "44100", "-ac", "1", *codec, out])
    if r.returncode != 0:
        sys.exit("master fail: " + r.stderr[-300:])
    print(f"TAIYAR {out}  {round(dur_of(out), 1)}s  ({len(parts)} lines, mahaul={mahaul}, music={music})")


def main():
    ap = argparse.ArgumentParser(description="Toonistaan Awaaz Studio — Pocket FM jaisi awaaz")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sunao", help="script.json se poori audio banao")
    s.add_argument("script")
    s.add_argument("-o", "--out", default="kahani.mp3")
    s.add_argument("--mahaul", default="room", choices=["room", "rain", "wind", "night", "village"])
    s.add_argument("--music", default="calm", choices=["happy", "sad", "action", "mystery", "comedy",
                                                       "calm", "romance", "epic", "lofi", "suspense", "horror"])
    s.add_argument("--gap", type=float, default=0.45, help="lines ke beech chup (second)")
    a = ap.parse_args()
    sunao(a.script, a.out, a.mahaul, a.music, a.gap)


if __name__ == "__main__":
    main()
