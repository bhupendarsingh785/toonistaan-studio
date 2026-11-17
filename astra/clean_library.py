#!/usr/bin/env python3
"""
ASTRA — library saaf karne wala tool (khud chal jata hai).

Har mp3 par safai:
  1. afftdn      — hiss/pankha/AC ka shor hatao
  2. highpass 70 — gungunahat/bijli ki hum kaato
  3. agate       — chup ke waqt bacha shor dabao
  4. loudnorm    — sab sounds ek barabar star par (-19 LUFS)
  5. 2-pass      — pehle naapo, phir lagao (saaf aur stable)

Kaise chalta hai:
  python3 astra/clean_library.py                # poora library
  python3 astra/clean_library.py --force        # sab dobara (marker ignore)
  python3 astra/clean_library.py --dir footsteps

Marker: astra/library/.cleaned.json — jo file saaf ho chuki, dobara nahi hoti.
GitHub Action `clean-library.yml` isko har push par apne aap chalata hai.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library")
MARK = os.path.join(LIB, ".cleaned.json")

AF = ("afftdn=nr=12:nf=-45:tn=1,"
      "highpass=f=70,"
      "agate=threshold=0.02:ratio=3:range=0.10:attack=5:release=150,"
      "loudnorm=I=-19:TP=-2:LRA=9")


def ff():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def load_mark():
    if os.path.exists(MARK):
        try:
            return json.load(open(MARK))
        except Exception:
            return {}
    return {}


def save_mark(m):
    json.dump(m, open(MARK, "w"), indent=1, sort_keys=True)


def clean_one(path, bitrate="64k"):
    """Ek file saaf karo (in place). True = cleaned."""
    tmp = tempfile.mktemp(suffix=".mp3")
    cmd = [ff(), "-loglevel", "error", "-y", "-i", path,
           "-af", AF, "-ac", "1", "-ar", "44100", "-b:a", bitrate, tmp]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 2000:
        if os.path.exists(tmp):
            os.remove(tmp)
        print("FAIL", os.path.relpath(path, LIB), (r.stderr or b"")[-90:], flush=True)
        return False
    os.replace(tmp, path)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="marker ignore, sab dobara")
    ap.add_argument("--dir", default="", help="sirf ek folder (jaise footsteps)")
    ap.add_argument("--limit", type=int, default=0, help="itni files ke baad ruk jao")
    a = ap.parse_args()

    mark = {} if a.force else load_mark()
    root = os.path.join(LIB, a.dir) if a.dir else LIB
    files = []
    for r, _, fs in os.walk(root):
        for x in fs:
            if x.lower().endswith(".mp3"):
                files.append(os.path.join(r, x))
    files.sort()
    todo = [f for f in files if a.force or f not in mark]
    print(f"total {len(files)} | saaf karna hai {len(todo)}", flush=True)

    done = fail = 0
    for p in todo:
        if a.limit and done >= a.limit:
            print("limit reached — agli baar baaki", flush=True)
            break
        if clean_one(p):
            mark[p] = True
            done += 1
            if done % 20 == 0:
                save_mark(mark)
                print(f"  ... {done} saaf", flush=True)
        else:
            fail += 1
    save_mark(mark)
    print(f"TAIYAR: {done} saaf, {fail} fail, kul marker {len(mark)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
