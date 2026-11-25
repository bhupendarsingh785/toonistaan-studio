#!/usr/bin/env python3
"""
ASTRA — duplicate (do baar bheji gayi) recordings hatao.

Kaam: har mp3 ka "fingerprint" banata hai (8 kHz mono PCM ka md5).
Do file ka fingerprint same = wahi recording do baar = ek hata do.

Kaise chalta hai:
  python3 astra/dedupe_library.py            # sirf report (kuch delete nahi)
  python3 astra/dedupe_library.py --apply    # duplicate delete + index saaf

Niyam:
  - ek hi content ki kai files: naam ke hisaab se pehli rakhi jati hai
  - chhoti file (<3 KB) ko chhod deta hai
  - index (DEFAULT_INDEX) se hataayi gayi file ki entry bhi nikal jati hai
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library")
INDEX_PY = os.path.join(HERE, "library.py")


def ff():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def fingerprint(path, seconds=30):
    """8 kHz mono PCM ka md5 — same recording = same hash."""
    cmd = [ff(), "-loglevel", "error", "-i", path, "-t", str(seconds),
           "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or len(r.stdout) < 4000:
        return None
    return hashlib.md5(r.stdout).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="duplicate delete karo")
    a = ap.parse_args()

    files = []
    for root, _, fs in os.walk(LIB):
        for x in fs:
            if x.lower().endswith(".mp3"):
                files.append(os.path.join(root, x))
    files.sort()
    print(f"files: {len(files)}", flush=True)

    seen = {}
    dups = []
    for p in files:
        if os.path.getsize(p) < 3000:
            continue
        h = fingerprint(p)
        if not h:
            continue
        if h in seen:
            dups.append((p, seen[h]))
        else:
            seen[h] = p

    print(f"unique: {len(seen)} | duplicate: {len(dups)}", flush=True)
    for d, orig in dups:
        print("  DUP", os.path.relpath(d, LIB), "==", os.path.relpath(orig, LIB), flush=True)

    if not dups:
        print("koi duplicate nahi — sab saaf", flush=True)
        return 0

    if not a.apply:
        print("\n(report only — delete karne ke liye --apply)", flush=True)
        return 0

    removed = []
    for d, _orig in dups:
        try:
            os.remove(d)
            removed.append(os.path.relpath(d, LIB))
        except Exception as e:
            print("  FAIL remove", d, str(e)[:50], flush=True)

    # index se entry hatao
    try:
        src = open(INDEX_PY, encoding="utf-8").read()
        m = re.search(r"DEFAULT_INDEX = (\{.*?\n\})\n", src, re.S)
        import ast
        idx = ast.literal_eval(m.group(1))
        before = len(idx)
        idx = {k: v for k, v in idx.items() if v["file"] not in removed}
        body = json.dumps(idx, ensure_ascii=False, indent=1)
        src = re.sub(r"DEFAULT_INDEX = \{.*?\n\}\n", "DEFAULT_INDEX = " + body + "\n", src, count=1, flags=re.S)
        open(INDEX_PY, "w", encoding="utf-8").write(src)
        print(f"index: {before} -> {len(idx)}", flush=True)
    except Exception as e:
        print("index update fail:", str(e)[:80], flush=True)

    print(f"TAIYAR: {len(removed)} duplicate hataye", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
