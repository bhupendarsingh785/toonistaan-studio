#!/usr/bin/env python3
"""
ASTRA — Auto Score: poori kahani ke liye background music khud banata hai.

Kaise:
  1. Har scene ka mahaul (env) aur bhaav (music) dekhta hai
  2. Library se 1-2 track chunta hai (music + halka ambience)
  3. Har track ka **sabse accha hissa** kaatta hai (shuru ka khaali hissa nahi)
  4. Scene ki lambai ke hisaab se **loop + crossfade** karta hai
  5. Scene badalne par **3s crossfade** (achanak badlav nahi)
  6. Awaaz ke waqt **duck** (music dheema) — cues.json ke time se
  7. Master: −18 LUFS, limiter, stereo-safe

Chalao:
  python3 astra/score.py studio/series/user/story_demo.json -o score.mp3
  python3 astra/score.py story.json -o score.mp3 --cues kahani.cues.json
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library")
SR = 44100
ISR = 22050   # beech ke file ke liye (jagah bachao)

# mahaul -> (music, ambience) — dono library ke variant naam
SCENE_MUSIC = {
    "village":   ("village", "birds"),
    "room":      ("calm", "clock"),
    "street":    ("happy", "crowd"),
    "station":   ("mystery", "crowd"),
    "night":     ("night", "wind"),
    "jungle":    ("forest", "leaves"),
    "hall":      ("mystery", "clock"),
    "cave":      ("horror", "water"),
    "neutral":   ("calm", None),
}

# bhaav (story ka "music" field) -> library variant
MOOD_MUSIC = {
    "calm": "calm", "happy": "happy", "sad": "sad", "emotional": "sad",
    "romantic": "romantic", "suspense": "tension", "tension": "tension",
    "horror": "horror", "action": "action", "epic": "epic",
    "devotional": "devotional", "funny": "fun", "comedy": "fun",
    "mystery": "mystery", "lullaby": "lullaby",
}


def ff():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or b"").decode("utf-8", "ignore")[-300:])
    return r


def load(path, seconds=60.0):
    cmd = [ff(), "-loglevel", "error", "-i", path, "-t", str(seconds), "-ac", "1",
           "-ar", str(ISR), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or len(r.stdout) < 8000:
        return None
    return np.frombuffer(r.stdout, dtype=np.float32)


def dur(path):
    r = subprocess.run([ff(), "-i", path], capture_output=True)
    for line in (r.stderr or b"").decode("utf-8", "ignore").splitlines():
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def best_window(path, need):
    """Sabse 'bhara hua' hissa chuno — shuru ka khaali part nahi."""
    x = load(path, max(need * 3, 45))
    if x is None:
        return 0.0
    win = int(ISR * 1.0)
    if len(x) < win * 2:
        return 0.0
    rms = np.array([float(np.sqrt((x[i:i + win] ** 2).mean())) for i in range(0, len(x) - win, win)])
    if len(rms) == 0:
        return 0.0
    # pehla hissa jahan awaaz theek ho (median se upar), warna sabse zor wala
    thr = np.median(rms) * 0.9
    idx = next((i for i, v in enumerate(rms) if v >= thr), int(np.argmax(rms)))
    start = max(0.0, idx * 1.0 - 0.5)
    total = len(x) / SR
    return min(start, max(0.0, total - need))


def make_bed(path, need, out, gain=1.0, fade=2.5):
    """Ek track se need-second ka bed banao (loop + crossfade + fade out)."""
    d = dur(path)
    if d <= 0.5:
        raise RuntimeError("khaali file: " + path)
    start = best_window(path, min(need, d))
    if d >= need:
        af = (f"atrim={start:.2f}:{start + need:.2f},asetpts=N/SR/TB,volume={gain},"
              f"afade=t=in:st=0:d={fade},afade=t=out:st={max(0, need - fade):.2f}:d={fade}")
        run([ff(), "-loglevel", "error", "-y", "-i", path, "-filter:a", af,
             "-ac", "1", "-ar", str(SR), out])
        return out
    # chhota hai -> loop karo
    loops = int(np.ceil(need / max(0.5, d - 0.4))) + 1
    af = (f"atrim={start:.2f},asetpts=N/SR/TB,volume={gain},"
          f"afade=t=in:st=0:d={fade},afade=t=out:st={max(0, d - start - fade):.2f}:d={fade},"
          f"aloop=loop={loops}:size={int(SR * max(0.5, d - start))},"
          f"atrim=0:{need:.2f},afade=t=out:st={max(0, need - fade):.2f}:d={fade}")
    run([ff(), "-loglevel", "error", "-y", "-i", path, "-filter:a", af,
         "-ac", "1", "-ar", str(SR), out])
    return out


def pick(variant):
    """Library se variant ka file dhundo."""
    try:
        sys.path.insert(0, HERE)
        import library as L
        p = L.fetch(variant)
        return p
    except Exception:
        return None


def build_score(ep, out_path, cues=None, verbose=True):
    tmp = os.path.join(os.path.dirname(os.path.abspath(out_path)) or ".", "_score_tmp")
    os.makedirs(tmp, exist_ok=True)

    scenes = ep.get("scenes", [])
    if not scenes:
        raise SystemExit("kahani me scene nahi hain")

    # har scene ki lambai: cues se (agar hai) warna lines ke hisaab se
    timings = []
    if cues:
        for sc in cues.get("scenes", []):
            timings.append(max(4.0, float(sc.get("end", 0)) - float(sc.get("start", 0))))
    if len(timings) != len(scenes):
        timings = [max(6.0, 2.6 * len(sc.get("lines", []))) for sc in scenes]

    parts = []
    report = []
    for i, sc in enumerate(scenes):
        need = timings[i] + 3.0            # crossfade ke liye thoda extra
        env = sc.get("env", "neutral")
        mood = (sc.get("music") or "").strip()
        variant, amb = SCENE_MUSIC.get(env, ("calm", None))
        if mood in MOOD_MUSIC:
            variant = MOOD_MUSIC[mood]
        mpath = pick(variant) or pick("calm")
        if not mpath:
            continue
        seg = os.path.join(tmp, f"sc{i}_music.wav")
        make_bed(mpath, need, seg, gain=1.0)
        layers = [seg]
        if amb:
            apath = pick(amb)
            if apath:
                aseg = os.path.join(tmp, f"sc{i}_amb.wav")
                try:
                    make_bed(apath, need, aseg, gain=0.22, fade=3.0)
                    layers.append(aseg)
                except Exception:
                    pass
        report.append({"scene": i, "env": env, "mood": mood or "-",
                       "music": variant, "ambience": amb or "-",
                       "seconds": round(need, 1)})

    if not parts and not report:
        raise SystemExit("koi music file nahi mili")

    # music + ambience ko per-scene mix karo
    mixed = []
    for r in report:
        i = r["scene"]
        m = os.path.join(tmp, f"sc{i}_music.wav")
        a = os.path.join(tmp, f"sc{i}_amb.wav")
        out = os.path.join(tmp, f"sc{i}_mix.wav")
        if os.path.exists(a):
            fc = "[0:a][1:a]amix=inputs=2:normalize=0[m]"
            run([ff(), "-loglevel", "error", "-y", "-i", m, "-i", a, "-filter_complex", fc,
                 "-map", "[m]", "-ac", "1", "-ar", str(SR), out])
        else:
            shutil.copy(m, out)
        mixed.append(out)

    # crossfade chain
    cur = mixed[0]
    for n, nxt in enumerate(mixed[1:], 1):
        out = os.path.join(tmp, f"chain{n}.wav")
        fc = "[0:a][1:a]acrossfade=d=3:c1=tri:c2=tri[o]"
        run([ff(), "-loglevel", "error", "-y", "-i", cur, "-i", nxt,
             "-filter_complex", fc, "-map", "[o]", "-ac", "1", "-ar", str(ISR), out])
        try:
            if cur != mixed[0]:
                os.remove(cur)
        except Exception:
            pass
        cur = out

    # ducking (agar cues me lines ka time hai)
    duck_af = ""
    if cues:
        try:
            times = []
            for sc in cues.get("scenes", []):
                for c in sc.get("cues", []):
                    if c.get("type") == "line":
                        times.append((float(c.get("start", 0)), float(c.get("end", 0))))
            if times:
                total = dur(cur)
                env = np.ones(int(total * 200), dtype=np.float32)   # 200 Hz envelope
                for a, b in times:
                    i0, i1 = int(max(0, a) * 200), int(min(total, b) * 200)
                    env[i0:i1] = 0.45
                # smooth
                k = np.ones(40) / 40
                env = np.convolve(env, k, "same")
                # volume expression (ffmpeg): 0.45..1.0
                expr = "0.45+0.55*(" + "+".join(
                    f"between(t,{a:.2f},{b:.2f})" for a, b in times[:40]) + "==0)"
                duck_af = f",volume='if(gt({expr},0),0.45,1)':eval=frame"
        except Exception:
            duck_af = ""

    af = ("afade=t=in:st=0:d=2" + duck_af +
          ",alimiter=limit=0.95,loudnorm=I=-18:TP=-2:LRA=9")
    run([ff(), "-loglevel", "error", "-y", "-i", cur, "-filter:a", af,
         "-ac", "2", "-ar", str(SR), "-b:a", "160k", out_path])

    try:
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass

    if verbose:
        print("SCORE TAIYAR", out_path, round(dur(out_path), 1), "s", flush=True)
        for r in report:
            print(f"  scene {r['scene']}: {r['env']:9s} mood={r['mood']:10s} "
                  f"music={r['music']:28s} amb={r['ambience']}", flush=True)
    return {"output": out_path, "seconds": round(dur(out_path), 1), "scenes": report}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("-o", "--out", default="score.mp3")
    ap.add_argument("--cues", default="")
    a = ap.parse_args()
    ep = json.load(open(a.story, encoding="utf-8"))
    cues = json.load(open(a.cues, encoding="utf-8")) if a.cues and os.path.exists(a.cues) else None
    r = build_score(ep, a.out, cues)
    print(json.dumps({"output": r["output"], "seconds": r["seconds"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
