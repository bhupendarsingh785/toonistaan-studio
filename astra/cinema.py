#!/usr/bin/env python3
"""
ASTRA CINEMA — kahani se "audio drama" (Pocket FM jaisa), ek hi command me.

Kahani likho (scene ke saath) -> ye khud:
  1. har scene ka mahaul chunta hai (gaon/kamra/jungle/sadak/mandir) + reverb
  2. dialogue ko kirdaar ki awaaz + bhaav se bolwata hai (tools/awaaz.py)
  3. har line ke shabdon se SFX nikalta hai (ASTRA generators) — doori/pan ke saath
  4. scene ka music (mood) lagata hai
  5. sab ko mix karta hai (ducking), master karta hai (-16 LUFS)
  6. cue-sheet JSON bhi deta hai (kaunsi awaaz kab)

Chalao:
  python3 astra/cinema.py banao story.json -o kahani.mp3

story.json:
{
 "title": "दो दीये",
 "scenes": [
   {"env": "village", "music": "calm", "lines": [
      ["madhur", "गाँव के छोटे से घर में दादी चूल्हा जला रही थीं।", "calm"],
      ["swara_bachcha", "दादी! देखो, मेरी गुल्लक में सौ रुपये हो गए!", "excited"],
      ["swara_dadi", "अरे वाह बेटा... इतने पैसे कहाँ से आए?", "surprised"]
   ]}
 ]
}
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "studio"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

SR = 44100
ENV_REVERB = {"room": 0.18, "village": 0.30, "jungle": 0.38, "street": 0.25,
              "temple": 0.55, "cave": 0.62, "hall": 0.45, "neutral": 0.20}


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def read_wav(p):
    import wave
    with wave.open(p) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    return x


def write_wav(p, x):
    import wave
    x = np.clip(x, -1, 1)
    with wave.open(p, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def norm(x, pk=0.9):
    m = float(np.abs(x).max()) if len(x) else 0.0
    return (x / m * pk).astype(np.float32) if m > 0 else x.astype(np.float32)


def place(canvas, x, at_sec, gain=1.0):
    k = int(SR * max(0.0, at_sec))
    if k >= len(canvas):
        return
    m = min(len(x), len(canvas) - k)
    canvas[k:k + m] += x[:m] * gain


def tts(text, kirdaar, bhaav, out_mp3):
    cmd = [sys.executable, os.path.join(ROOT, "tools", "awaaz.py"), "bolo", text, "--kirdaar", kirdaar, "-o", out_mp3, "--natural"]
    if bhaav:
        cmd += ["--bhaav", bhaav]
    r = sh(cmd)
    for line in (r.stdout or "").splitlines():
        if line.startswith(("ELEVEN_OK", "ELEVEN_FAIL", "ban gaya")):
            print("VOICE:", line.strip()[:110], flush=True)
    return r.returncode == 0 and os.path.exists(out_mp3)


def build(story_path, out_path, verbose=True):
    import astra as A  # same folder
    import sfx as S

    data = json.load(open(story_path, encoding="utf-8"))
    scenes = data.get("scenes") or []
    if not scenes:
        sys.exit("story me 'scenes' nahi mila")

    tmp = tempfile.mkdtemp(prefix="cinema_")
    cue = {"title": data.get("title", ""), "scenes": []}

    # pehle poora timeline banao (lambai pata chale)
    plan = []      # (kind, payload, start)
    t = 0.4
    for si, sc in enumerate(scenes):
        env = sc.get("env", "neutral")
        music = sc.get("music", "calm")
        sc_start = t
        cues = []
        # mahaul ka ambience (scene bhar)
        amb = A.ambience(env if env in ("rain", "wind", "night", "village", "room") else "room", 1.0)
        plan.append(("amb", {"env": env, "dur": 0.0, "start": sc_start}, sc_start))

        for li, item in enumerate(sc.get("lines", [])):
            if isinstance(item, str):
                kirdaar, text, bhaav = "madhur", item, None
            else:
                kirdaar = item[0] if len(item) > 0 else "madhur"
                text = item[1] if len(item) > 1 else ""
                bhaav = item[2] if len(item) > 2 else None
            if not str(text).strip():
                continue

            mp3 = os.path.join(tmp, f"s{si}_l{li}.mp3")
            ok = tts(text, kirdaar, bhaav, mp3)
            wav = os.path.join(tmp, f"s{si}_l{li}.wav")
            dur = 2.0
            if ok:
                sh(["ffmpeg", "-loglevel", "error", "-y", "-i", mp3, "-ac", "1", "-ar", str(SR), wav])
                if os.path.exists(wav):
                    a = read_wav(wav)
                    dur = len(a) / SR
                    plan.append(("line", {"wav": wav, "kirdaar": kirdaar, "bhaav": bhaav,
                                          "text": text, "start": t, "dur": dur}, t))
                    cues.append({"type": "dialogue", "who": kirdaar, "emotion": bhaav or "auto",
                                 "text": text, "start": round(t, 2), "dur": round(dur, 2)})
            else:
                if verbose:
                    print("TTS_FAIL", si, li, flush=True)
            t += dur + 0.35

            # line ke shabdon se SFX (max 2), thodi doori/pan ke saath
            for name in A.detect(text) if hasattr(A, "detect") else []:
                pass
            try:
                import sfx_extra
                for name in sfx_extra.detect(text)[:2]:
                    plan.append(("sfx", {"name": name, "start": t - 0.15, "text": text}, t - 0.15))
                    cues.append({"type": "sfx", "name": name, "start": round(t - 0.15, 2)})
            except Exception:
                pass
        # scene ka music
        plan.append(("music", {"mood": music, "start": sc_start, "end": t + 0.6}, sc_start))
        cue["scenes"].append({"env": env, "music": music, "start": round(sc_start, 2),
                              "end": round(t + 0.6, 2), "cues": cues})
        t += 0.6

    total = t + 0.8
    n = int(SR * total)
    voice = np.zeros(n, np.float32)
    fx = np.zeros(n, np.float32)
    amb_bus = np.zeros(n, np.float32)
    mus_bus = np.zeros(n, np.float32)

    for kind, p, start in plan:
        if kind == "line":
            a = read_wav(p["wav"])
            place(voice, a, p["start"], 1.0)
        elif kind == "sfx":
            done = False
            # 1) pehle ASLI recording (Freesound) — key ho to
            try:
                import real_audio
                rp = real_audio.fetch(p["name"], context=p.get("text", ""))
                if rp:
                    rw = read_wav(rp)
                    rw = norm(rw, 0.85)
                    rw = A.reverb(rw, 0.10)
                    place(fx, rw, p["start"], 0.95)
                    done = True
                    if verbose:
                        print("SFX_REAL", p["name"], flush=True)
            except Exception:
                pass
            # 2) na mile to procedural
            if not done:
                try:
                    import sfx_extra
                    snd = sfx_extra.ALL[p["name"]]()
                    snd = norm(snd, 0.85)
                    snd = A.reverb(snd, 0.25)
                    place(fx, snd, p["start"], 0.8)
                except Exception:
                    pass
        elif kind == "amb":
            env = p["env"]
            kind_amb = env if env in ("rain", "wind", "night", "village", "street", "jungle", "temple", "room") else "room"
            need = max(1.0, t - p["start"])
            seg = None
            # 1) asli recording (Freesound)
            try:
                import real_audio
                rp = real_audio.fetch(kind_amb)
                if rp:
                    rw = read_wav(rp)
                    if len(rw) > SR * 0.5:
                        reps = int(np.ceil((SR * need) / len(rw)))
                        seg = np.tile(rw, max(1, reps))[: int(SR * need)]
                        seg = norm(seg, 0.30)   # dheema, peeche
                        if verbose:
                            print("AMB_REAL", kind_amb, flush=True)
            except Exception:
                pass
            # 2) na mile to synth
            if seg is None:
                seg = A.ambience(kind_amb, need)
            seg = np.pad(seg, (0, max(0, n - int(SR * p["start"]) - len(seg))))[: max(0, n - int(SR * p["start"]))]
            amb_bus[int(SR * p["start"]):int(SR * p["start"]) + len(seg)] += seg * 0.9
        elif kind == "music":
            dur = max(2.0, p["end"] - p["start"])
            m = None
            try:
                import music_engine as ME
                import wave as _w
                path, _meta = ME.generate_music(p["mood"], max(8.0, dur + 1.0))
                with _w.open(str(path)) as wf:
                    raw = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float32) / 32768
                    ch = wf.getnchannels(); sr = wf.getframerate()
                if ch == 2:
                    raw = raw.reshape(-1, 2).mean(1)
                if sr != SR:
                    raw = np.interp(np.linspace(0, len(raw) - 1, int(len(raw) * SR / sr)),
                                    np.arange(len(raw)), raw).astype(np.float32)
                m = raw[: int(SR * dur)]
                if verbose:
                    print("MUSIC_ENGINE", p["mood"], len(m) / SR, "s", flush=True)
            except Exception as e:
                if verbose:
                    print("MUSIC_FALLBACK", str(e)[:60], flush=True)
                m = S.music(p["mood"], dur + 1.0)[: int(SR * dur)]
            m = norm(m, 0.9)
            f = min(int(SR * 0.6), len(m) // 3)
            if f > 1:
                m[:f] *= np.linspace(0, 1, f)
                m[-f:] *= np.linspace(1, 0, f)
            place(mus_bus, m, p["start"], 0.55)

    # ducking
    win = int(SR * 0.25)
    envl = np.convolve(np.abs(voice), np.ones(win) / win, "same")
    thr = max(0.01, float(np.percentile(envl, 55)))
    duck = np.where(envl > thr, 0.32, 1.0)
    duck = np.convolve(duck, np.ones(int(SR * 0.30)) / int(SR * 0.30), "same")

    mix = voice + fx + amb_bus * (0.55 + 0.45 * duck) + mus_bus * duck
    mix = norm(mix, 0.95)

    premix = os.path.join(tmp, "premix.wav")
    write_wav(premix, mix)

    af = ("highpass=f=65,"
          "equalizer=f=180:t=q:w=1.0:g=-1.5,"
          "equalizer=f=3200:t=q:w=1.2:g=2.5,"
          "equalizer=f=9000:t=q:w=1.0:g=1.0,"
          "deesser=i=0.3,"
          "acompressor=threshold=0.10:ratio=2.6:attack=6:release=180:makeup=1.5,"
          "alimiter=limit=0.95,"
          "loudnorm=I=-16:TP=-1.5:LRA=11")
    codec = ["-c:a", "libmp3lame", "-b:a", "192k"] if out_path.lower().endswith(".mp3") else []
    r = sh(["ffmpeg", "-loglevel", "error", "-y", "-i", premix, "-af", af, "-ar", "44100", "-ac", "1", *codec, out_path])
    if r.returncode != 0:
        sys.exit("master fail: " + r.stderr[-300:])

    cues_path = os.path.splitext(out_path)[0] + ".cues.json"
    json.dump(cue, open(cues_path, "w"), ensure_ascii=False, indent=1)
    print(f"TAIYAR {out_path} | {round(total,1)}s | {len(plan)} events | cues: {cues_path}")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="ASTRA Cinema — kahani se audio drama")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("banao")
    b.add_argument("story")
    b.add_argument("-o", "--out", default="kahani.mp3")
    a = ap.parse_args()
    build(a.story, a.out)


if __name__ == "__main__":
    main()
