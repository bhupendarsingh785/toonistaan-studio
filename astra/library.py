#!/usr/bin/env python3
"""
ASTRA LOCAL LIBRARY — asli recordings jo hum khud rakhte hain (best quality, sabse pehle).

Kaise kaam karta hai:
  library.fetch("scream")  -> astra/library/... ka wav path (44.1k mono) ya None

Naya sound jodna:
  1. mp3/wav ko astra/library/<category>/<naam>.mp3 me rakho
  2. library.json me entry likho: {"naam": {"file": "...", "tags": [...], "license": "..."}}
  3. Bas — system usko sabse pehle use karega (Freesound/Mixkit se bhi pehle).
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library")
CACHE = os.path.join(HERE, "cache", "lib")
INDEX = os.path.join(LIB, "library.json")
os.makedirs(CACHE, exist_ok=True)

# naam -> tags (Hindi + English) — isse match hota hai
DEFAULT_INDEX = {
    "horror_intro":      {"file": "horror/horror_intro.mp3", "tags": ["horror", "intro", "drone", "डरावना", "शुरुआत"], "license": "Pixabay"},
    "horror_pad_crowd":  {"file": "horror/horror_pad_crowd.mp3", "tags": ["horror", "pad", "crowd", "भीड़", "डर"], "license": "Pixabay"},
    "monster_lurk":      {"file": "horror/monster_lurk.mp3", "tags": ["monster", "rakshas", "राक्षस", "भूत", "darr"], "license": "Pixabay"},
    "scary_sting":       {"file": "horror/scary_sting.mp3", "tags": ["scary", "sting", "jump", "डर", "चौंक"], "license": "Pixabay"},
    "horror_hit":        {"file": "horror/horror_hit.mp3", "tags": ["hit", "impact", "dhamaka", "धमाका", "टकराव"], "license": "Pixabay"},
    "horror_ambience":   {"file": "horror/horror_ambience.mp3", "tags": ["ambience", "horror", "mahaul", "माहौल", "डर"], "license": "Pixabay"},
    "ghost":             {"file": "horror/ghost.mp3", "tags": ["ghost", "bhoot", "भूत", "आत्मा", "spirit"], "license": "Pixabay"},
    "scream_woman":      {"file": "horror/scream_woman.mp3", "tags": ["scream", "cheekh", "चीख", "chillana", "aurat"], "license": "Pixabay"},
    "crowd_applause":    {"file": "crowd/crowd_applause.mp3", "tags": ["crowd", "applause", "tali", "ताली", "khushi", "भीड़"], "license": "Pixabay"},
    "crowd_panic":       {"file": "crowd/crowd_panic.mp3", "tags": ["crowd", "panic", "bhagdad", "भगदड़", "scream", "भीड़"], "license": "Pixabay"},
}

# hamare SFX naam -> library naam (seedha match)
ALIAS = {
    "scream": "scream_woman",
    "monster": "monster_lurk",
    "crowd": "crowd_applause",
    "panic": "crowd_panic",
    "ghost": "ghost",
    "horror": "horror_ambience",
    "hit": "horror_hit",
    "sting": "scary_sting",
    "thunder": "horror_hit",
}


def _index():
    if os.path.exists(INDEX):
        try:
            data = json.load(open(INDEX, encoding="utf-8"))
            if data:
                return data
        except Exception:
            pass
    return DEFAULT_INDEX


def _ff():
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def entries():
    return _index()


def find(name):
    """Naam ya tag se best entry ka key."""
    idx = _index()
    if name in idx:
        return name
    alias = ALIAS.get(name)
    if alias and alias in idx:
        return alias
    low = str(name or "").lower()
    for key, meta in idx.items():
        tags = [t.lower() for t in meta.get("tags", [])]
        if low in key.lower() or low in tags or any(low and low in t for t in tags):
            return key
    return None


def fetch(name):
    """Asli library file ka wav (44.1k mono) — na mile to None."""
    key = find(name)
    if not key:
        return None
    meta = _index()[key]
    src = os.path.join(LIB, meta["file"])
    if not os.path.exists(src):
        return None
    out = os.path.join(CACHE, f"{key}.wav")
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        return out
    r = subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", src, "-ac", "1", "-ar", "44100", out],
                       capture_output=True)
    if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 5000:
        print("LIB_OK", key, meta.get("license", ""), flush=True)
        return out
    return None


def info(name):
    key = find(name)
    if not key:
        return None
    m = dict(_index()[key])
    m["key"] = key
    return m


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("library me:", len(_index()), "sounds")
        for k, v in _index().items():
            print(f"  {k:18s} {v['file']}")
        sys.exit(0)
    for n in sys.argv[1:]:
        print(n, "->", fetch(n))
