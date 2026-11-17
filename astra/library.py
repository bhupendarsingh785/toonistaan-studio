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
    "footsteps_parquet": {"file": "footsteps/footsteps_parquet.mp3", "tags": ["footsteps", "kadam", "कदम", "parquet", "boots", "indoor", "ghar", "घर"], "license": "Pixabay"},
    "footsteps_hallway": {"file": "footsteps/footsteps_hallway.mp3", "tags": ["footsteps", "kadam", "कदम", "hallway", "corridor", "हवेली", "indoor"], "license": "Pixabay"},
    "footsteps_concrete": {"file": "footsteps/footsteps_concrete.mp3", "tags": ["footsteps", "kadam", "कदम", "concrete", "road", "सड़क", "bahar", "outdoor"], "license": "Pixabay"},
    "footsteps_walk":    {"file": "footsteps/footsteps_walk.mp3", "tags": ["footsteps", "walking", "kadam", "कदम", "chalna"], "license": "Pixabay"},
    "door_open_a":       {"file": "door/door_open_a.mp3", "tags": ["door", "open", "दरवाज़ा", "darwaza", "khulna"], "license": "Pixabay"},
    "door_open_b":       {"file": "door/door_open_b.mp3", "tags": ["door", "open", "दरवाज़ा", "darwaza", "khulna"], "license": "Pixabay"},
    "door_open_c":       {"file": "door/door_open_c.mp3", "tags": ["door", "open", "दरवाज़ा", "darwaza", "khulna"], "license": "Pixabay"},
    "door_close_a":      {"file": "door/door_close_a.mp3", "tags": ["door", "close", "दरवाज़ा", "darwaza", "band"], "license": "Pixabay"},
    "door_close_b":      {"file": "door/door_close_b.mp3", "tags": ["door", "close", "दरवाज़ा", "darwaza", "band"], "license": "Pixabay"},
    "door_close_c":      {"file": "door/door_close_c.mp3", "tags": ["door", "close", "दरवाज़ा", "darwaza", "band"], "license": "Pixabay"},
    "jungle_nature":     {"file": "nature/jungle_nature.mp3", "tags": ["jungle", "forest", "जंगल", "nature", "birds", "ambience"], "license": "Pixabay"},
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


def find(name, context=""):
    """Naam ya tag se best entry ka key (context se footsteps chunte hain)."""
    if name in ("footsteps", "kadam", "कदम"):
        return pick_footsteps(context)
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


VARIANTS = {
    "gate_open": ["door_open_a", "door_open_b", "door_open_c"],
    "door": ["door_open_a", "door_open_b", "door_open_c"],
    "gate_close": ["door_close_a", "door_close_b", "door_close_c"],
    "jungle": ["jungle_nature"],
    "footsteps_walk": ["footsteps_walk", "footsteps_parquet", "footsteps_concrete"],
}

FAST_WORDS = ["दौड़", "भाग", "तेज़", "तेज", "जल्दी", "fast", "run", "daud"]
SLOW_WORDS = ["धीरे", "आहिस्ता", "dheere", "slow"]
SCARY_WORDS = ["डरावन", "डर", "आहट", "scary", "horror", "धीमी"]

INDOOR_WORDS = ["घर", "कमरा", "हवेली", "अंदर", "सीढ़ी", "छत", "room", "indoor", "hall", "floor"]
OUTDOOR_WORDS = ["सड़क", "बाहर", "मिट्टी", "खेत", "बाज़ार", "गली", "road", "street", "outdoor", "concrete"]


def pick_footsteps(text=""):
    """Kahani ke vaakya se indoor/outdoor kadam chuno."""
    t = str(text or "")
    if any(w in t for w in INDOOR_WORDS):
        return "footsteps_hallway" if "सीढ़ी" in t or "हवेली" in t else "footsteps_parquet"
    if any(w in t for w in OUTDOOR_WORDS):
        return "footsteps_concrete"
    return "footsteps_parquet"


def speed_for(name, context=""):
    """Vaakya se raftaar: tez / dheema / daravana."""
    t = str(context or "")
    if any(w in t for w in FAST_WORDS):
        return 1.25
    if any(w in t for w in SCARY_WORDS):
        return 0.82
    if any(w in t for w in SLOW_WORDS):
        return 0.88
    return 1.0


_ROT = {}


def _variant(name, context=""):
    """Ek hi tarah ki kai awaazein — baari-baari chuno (har scene alag lage)."""
    if name in ("footsteps", "kadam", "कदम"):
        return pick_footsteps(context)
    if name in VARIANTS:
        lst = VARIANTS[name]
        i = _ROT.get(name, 0) % len(lst)
        _ROT[name] = i + 1
        return lst[i]
    return find(name, context)


def fetch(name, context=""):
    """Asli library file ka wav (44.1k mono) — na mile to None."""
    key = _variant(name, context)
    if not key:
        return None
    meta = _index()[key]
    src = os.path.join(LIB, meta["file"])
    if not os.path.exists(src):
        return None
    sp = speed_for(name, context)
    out = os.path.join(CACHE, f"{key}_{sp:.2f}.wav")
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        return out
    cmd = [_ff(), "-loglevel", "error", "-y", "-i", src, "-ac", "1", "-ar", "44100"]
    if abs(sp - 1.0) > 0.02:
        cmd += ["-filter:a", f"atempo={sp:.3f}"]
    cmd += [out]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 5000:
        print("LIB_OK", key, "speed", sp, meta.get("license", ""), flush=True)
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
