#!/usr/bin/env python3
"""
Toonistaan AWAAZ STUDIO — Pocket FM jaisi "insan wali" awaaz, poore mahaul ke saath.

Har line:
  kirdaar ki awaaz (awaaz.py) + bhaav (darr/dukh/khushi) + halki saans
  + line ke shabdon se apne aap SFX (सिक्के, दरवाज़ा, कदम, फोन, मंदिर, गाड़ी...)
  + peeche mahaul (gaon/baaris/hawa/raat) + music (mood) + ducking
Aakhir me: Pocket FM master (-16 LUFS).

Chalao:
  python3 tools/awaaz_studio.py sunao script.json -o kahani.mp3 --mahaul village --music calm

script.json:
 {"mahaul":"village","music":"calm",
  "lines":[
    ["swara_bachcha","दादी! देखो, मेरी गुल्लक में सौ रुपये हैं!","excited"],
    ["swara_dadi","अरे वाह बेटा... इतने पैसे कहाँ से?","surprised"],
    ["madhur","दरवाज़ा खुला और कदमों की आहट आई।","calm"]
  ]}
SFX khud lagenge (गुल्लक->सिक्के, दरवाज़ा->gate, कदम->footsteps).
Apna SFX dena ho: ["madhur","...","calm",{"sfx":["bell","crowd"]}]
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


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def dur_of(p):
    r = sh(["ffmpeg", "-hide_banner", "-i", p])
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def read_wav(p):
    import wave
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def write_wav(p, x):
    import wave
    x = np.clip(x, -1, 1)
    with wave.open(p, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def breath(level=0.05, length=0.25):
    n = int(SR * length)
    tt = np.linspace(0, length, n, False)
    x = np.random.randn(n).astype(np.float32)
    k = max(1, int(SR * 0.002))
    x = np.convolve(x, np.ones(k) / k, "same")
    return (x * (np.sin(np.pi * tt / length) ** 2) * level).astype(np.float32)


def ambience(kind="room", sec=10.0):
    import sfx
    n = int(SR * sec)
    if kind == "rain":
        base = sfx.lowpass(sfx.noise(sec), 6000) * 0.55 + sfx.noise(sec) * 0.10
    elif kind == "wind":
        base = sfx.wind(sec)
    elif kind == "night":
        base = sfx.noise(sec) * 0.12
        tt = sfx.t(sec)
        for f in (4200, 5100):
            gate = (np.sin(2 * np.pi * 6.5 * tt) > 0.93).astype(np.float32)
            base = base + np.sin(2 * np.pi * f * tt) * gate * 0.05
    elif kind == "village":
        base = sfx.noise(sec) * 0.15 + sfx.lowpass(sfx.noise(sec), 300) * 0.35
    else:
        base = sfx.lowpass(sfx.noise(sec), 500) * 0.12
    base = np.pad(base, (0, max(0, n - len(base))))[:n]
    pk = float(np.abs(base).max()) or 1.0
    return (base / pk * 0.10).astype(np.float32)


def music_bed(mood="calm", sec=10.0):
    import sfx
    m = sfx.music(mood, sec + 1.0)[: int(SR * sec)]
    m = np.pad(m, (0, max(0, int(SR * sec) - len(m))))
    pk = float(np.abs(m).max()) or 1.0
    return (m / pk * 0.16).astype(np.float32)


def sunao(script_path, out, mahaul="room", music="calm", gap=0.45, sfx_level=0.55):
    import sfx_extra
    data = json.load(open(script_path, encoding="utf-8"))
    lines = data.get("lines") or []
    if not lines:
        sys.exit("script me 'lines' nahi mila")
    mahaul = data.get("mahaul", mahaul)
    music = data.get("music", music)
    tmp = tempfile.mkdtemp(prefix="awaaz_")
    parts = []

    for idx, item in enumerate(lines):
        sfx_list = []
        if isinstance(item, str):
            kirdaar, text, bhaav = "madhur", item, None
        elif isinstance(item, (list, tuple)):
            kirdaar = item[0] if len(item) > 0 else "madhur"
            text = item[1] if len(item) > 1 else ""
            bhaav = item[2] if len(item) > 2 else None
            if len(item) > 3 and isinstance(item[3], dict):
                sfx_list = item[3].get("sfx", []) or []
        else:
            kirdaar = item.get("kirdaar", "madhur")
            text = item.get("text", "")
            bhaav = item.get("bhaav")
            sfx_list = item.get("sfx", []) or []
        if not str(text).strip():
            continue

        # 1) SFX: pehle apne diye, warna shabdon se pehchan
        if not sfx_list:
            sfx_list = sfx_extra.detect(text)

        head = np.zeros(0, np.float32)
        tail = np.zeros(0, np.float32)
        for name in sfx_list[:2]:
            fn = sfx_extra.ALL.get(name)
            if not fn:
                continue
            s = fn()
            pk = float(np.abs(s).max()) or 1.0
            s = (s / pk * sfx_level * 0.5).astype(np.float32)
            # pehla SFX line se pehle, doosra line ke baad
            if len(head) == 0:
                head = np.concatenate([s, np.zeros(int(SR * 0.12), np.float32)])
            else:
                tail = np.concatenate([tail, s])
            print("SFX", name, "line", idx, flush=True)

        # 2) awaaz
        mp3 = os.path.join(tmp, f"l{idx}.mp3")
        cmd = [sys.executable, os.path.join(HERE, "awaaz.py"), "bolo", text, "--kirdaar", kirdaar, "-o", mp3, "--natural"]
        if bhaav:
            cmd += ["--bhaav", bhaav]
        r = sh(cmd)
        if r.returncode != 0 or not os.path.exists(mp3):
            print("LINE_FAIL", idx, r.stderr[-140:], flush=True)
            continue
        wav = os.path.join(tmp, f"l{idx}.wav")
        sh(["ffmpeg", "-loglevel", "error", "-y", "-i", mp3, "-ac", "1", "-ar", str(SR), wav])
        x = read_wav(wav)

        if idx % 2 == 0:
            x = np.concatenate([breath(0.05, 0.22), x])
        seg = np.concatenate([head, x, breath(0.035, 0.18), tail, np.zeros(int(SR * gap), np.float32)])
        parts.append(seg)
        print("LINE_OK", idx, kirdaar, bhaav or "auto", round(len(seg) / SR, 2), "s", flush=True)

    if not parts:
        sys.exit("koi line nahi bani")

    voice = np.concatenate(parts)
    n = len(voice)
    amb = np.pad(ambience(mahaul, n / SR + 1), (0, max(0, n - len(ambience(mahaul, n / SR + 1)))))[:n]
    mus = music_bed(music, n / SR + 1)
    mus = np.pad(mus, (0, max(0, n - len(mus))))[:n]

    win = int(SR * 0.25)
    envl = np.convolve(np.abs(voice), np.ones(win) / win, "same")
    thr = max(0.01, float(np.percentile(envl, 55)))
    duck = np.where(envl > thr, 0.35, 1.0)
    duck = np.convolve(duck, np.ones(int(SR * 0.30)) / int(SR * 0.30), "same")

    mix = voice + amb + mus * duck
    pk = float(np.abs(mix).max()) or 1.0
    mix = mix / pk * 0.95

    premix = os.path.join(tmp, "premix.wav")
    write_wav(premix, mix)

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
    print(f"TAIYAR {out} {round(dur_of(out), 1)}s ({len(parts)} lines, mahaul={mahaul}, music={music})")


def main():
    ap = argparse.ArgumentParser(description="Awaaz Studio — Pocket FM jaisi awaaz")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sunao")
    s.add_argument("script")
    s.add_argument("-o", "--out", default="kahani.mp3")
    s.add_argument("--mahaul", default="room", choices=["room", "rain", "wind", "night", "village"])
    s.add_argument("--music", default="calm", choices=["happy", "sad", "action", "mystery", "comedy", "calm",
                                                       "romance", "epic", "lofi", "suspense", "horror"])
    s.add_argument("--gap", type=float, default=0.45)
    s.add_argument("--sfx", type=float, default=0.55, help="SFX ki awaaz (0.2 halka ... 1.0 tez)")
    a = ap.parse_args()
    sunao(a.script, a.out, a.mahaul, a.music, a.gap, a.sfx)


if __name__ == "__main__":
    main()
