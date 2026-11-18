#!/usr/bin/env python3
"""
ASTRA — Beat Mix: asli mixing (beat se beat milakar), sirf crossfade nahi.

Kaise:
  1. Har track ka **beat grid** nikalta hai (librosa — asli beat detection)
  2. Kaat **beat par** hota hai, lambai **poore bar** (4 beat) me
  3. Tempo **match** hota hai (dheema/tez), aur doosra track apne beat par shuru hota hai
  4. Crossfade **1 beat** ka (sur nahi takrata)
  5. **Key** (sur) bhi batata hai — E minor + E minor = saaf, alag key = takraav

Chalao:
  python3 astra/beat_mix.py info music/forest_lofi_piano.mp3
  python3 astra/beat_mix.py mix music/a.mp3 music/b.mp3 --bars 8 --out naya
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library")
OUT = os.path.join(LIB, "music")
WORK = os.path.join(HERE, "_beatwork")      # /tmp chhota hai — yahan kaam
SR = 22050
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def ff():
    e = shutil.which("ffmpeg")
    if e:
        return e
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or b"").decode("utf-8", "ignore")[-250:])
    return r


def decode(path, seconds=90.0):
    os.makedirs(WORK, exist_ok=True)
    wav = os.path.join(WORK, "in.wav")
    run([ff(), "-loglevel", "error", "-y", "-i", path, "-t", str(seconds),
         "-ac", "1", "-ar", str(SR), wav])
    import librosa
    y, sr = librosa.load(wav, sr=SR)
    return y, sr


def info(path):
    """Beat grid + tempo + key (sur)."""
    import librosa
    y, sr = decode(path)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    prof = chroma.mean(axis=1)
    root = int(np.argmax(prof))
    # major/minor ka andaza: teesra note (minor third) kitna zor
    minor3 = prof[(root + 3) % 12]
    major3 = prof[(root + 4) % 12]
    mode = "minor" if minor3 >= major3 else "major"
    return {
        "file": os.path.relpath(path, LIB),
        "bpm": round(tempo, 1),
        "beats": [round(float(b), 3) for b in beats[:400]],
        "beat_count": int(len(beats)),
        "key": f"{NOTES[root]} {mode}",
        "root_pc": root,
        "mode": mode,
        "seconds": round(len(y) / sr, 1),
    }


def key_distance(a, b):
    """0 = ek hi sur; 1-5 = kitna takraav (chhota = behtar)."""
    if not a or not b:
        return 99
    d = min((a["root_pc"] - b["root_pc"]) % 12, (b["root_pc"] - a["root_pc"]) % 12)
    if a["mode"] == b["mode"]:
        return d
    return d + 2


def cut_on_beat(path, start_beat, bars=8, out=None, tempo_factor=1.0, fade_beats=1.0):
    """Beat par shuru, poore bar ki lambai, beat-par fade."""
    inf = info(path)
    if not inf["beats"]:
        raise RuntimeError("beat nahi mile: " + path)
    beats = inf["beats"]
    bpm = inf["bpm"] or 100.0
    beat_len = 60.0 / bpm
    i0 = min(start_beat, max(0, len(beats) - 1))
    start = beats[i0]
    length = bars * 4 * beat_len
    total = inf["seconds"]
    if start + length > total:
        start = max(0.0, total - length)
    fade = max(0.05, fade_beats * beat_len)
    af = (f"atrim={start:.3f}:{start + length:.3f},asetpts=N/SR/TB,"
          + (f"atempo={tempo_factor:.4f}," if abs(tempo_factor - 1.0) > 0.01 else "")
          + f"afade=t=in:st=0:d={fade:.3f},afade=t=out:st={max(0, length - fade):.3f}:d={fade:.3f}")
    out = out or os.path.join(WORK, "cut.wav")
    run([ff(), "-loglevel", "error", "-y", "-i", path, "-filter:a", af,
         "-ac", "1", "-ar", "44100", out])
    return out, {"start": round(start, 2), "length": round(length, 2), "bpm": bpm,
                 "fade": round(fade, 2), "key": inf["key"]}


def mix(files, bars=8, out="beat_mix", verbose=True):
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    procs = [f if os.path.isabs(f) else os.path.join(LIB, f) for f in files]
    infos = [info(p) for p in procs]
    base_bpm = infos[0]["bpm"] or 100.0

    parts, meta = [], []
    for i, (p, inf) in enumerate(zip(procs, infos)):
        factor = 1.0
        if inf["bpm"]:
            factor = max(0.85, min(1.18, base_bpm / inf["bpm"]))
        # beech ka beat chuno (shuru ka khaali hissa nahi)
        start_beat = max(0, len(inf["beats"]) // 6)
        seg, m = cut_on_beat(p, start_beat, bars=bars, out=os.path.join(WORK, f"p{i}.wav"),
                             tempo_factor=factor)
        m.update({"file": os.path.relpath(p, LIB), "stretch": round(factor, 3),
                  "key_distance_from_first": key_distance(infos[0], inf)})
        meta.append(m)
        parts.append(seg)

    # jod: har jod par 1 beat ka crossfade (grid par)
    cur = parts[0]
    for n, nxt in enumerate(parts[1:], 1):
        beat_len = 60.0 / (base_bpm or 100.0)
        fade = max(0.12, beat_len)
        o = os.path.join(WORK, f"j{n}.wav")
        run([ff(), "-loglevel", "error", "-y", "-i", cur, "-i", nxt, "-filter_complex",
             f"[0:a][1:a]acrossfade=d={fade:.3f}:c1=tri:c2=tri[o]", "-map", "[o]",
             "-ac", "1", "-ar", "44100", o])
        meta[n]["join_fade_s"] = round(fade, 2)
        cur = o

    dst = os.path.join(OUT, out if out.endswith(".mp3") else out + ".mp3")
    run([ff(), "-loglevel", "error", "-y", "-i", cur, "-filter:a",
         "alimiter=limit=0.95,loudnorm=I=-18:TP=-2:LRA=9", "-ac", "1", "-ar", "44100", "-b:a", "64k", dst])

    if verbose:
        print("BEAT_MIX", os.path.basename(dst), flush=True)
        for m in meta:
            print(f"  {m['file']:32s} {m['bpm']:6.1f} BPM  key={m['key']:9s} "
                  f"stretch={m['stretch']} keydist={m['key_distance_from_first']} "
                  f"fade={m.get('join_fade_s', '-')}", flush=True)
    shutil.rmtree(WORK, ignore_errors=True)
    return {"output": dst, "parts": meta}


def main():
    if len(sys.argv) < 3:
        print("usage: beat_mix.py info <file> | mix <a> <b> [--bars 8] [--out name]")
        return 1
    cmd = sys.argv[1]
    argv = sys.argv[2:]
    out, bars = "beat_mix", 8
    if "--out" in argv:
        i = argv.index("--out")
        out = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if "--bars" in argv:
        i = argv.index("--bars")
        bars = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    files = [a for a in argv if not a.startswith("--")]

    if cmd == "info":
        for f in files:
            print(json.dumps(info(f if os.path.isabs(f) else os.path.join(LIB, f)),
                             ensure_ascii=False)[:600])
        return 0
    if cmd == "mix":
        r = mix(files, bars=bars, out=out)
        print(json.dumps({"output": r["output"]}, ensure_ascii=False))
        return 0
    print("pata nahi:", cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
