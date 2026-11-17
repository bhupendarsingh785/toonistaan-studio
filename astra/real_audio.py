#!/usr/bin/env python3
"""
ASTRA REAL AUDIO — asli recording wali awaazein (Freesound), bina key bhi chalta hai.

Kaise:
  1. FREESOUND_API_KEY ho to Freesound se asli recording download hoti hai (preview mp3).
  2. Key na ho / internet na ho / kuch na mile -> None (caller apna procedural sound use kare).

Freesound key FREE milti hai: https://freesound.org/apiv2/apply
  (login -> "Apply for a new API credential" -> Client secret/Api key copy)
Key ko GitHub Secret me daalo: FREESOUND_API_KEY

Note: Freesound par licences alag hote hain (CC0, CC-BY...). Har sound ka licence
metadata ke saath save hota hai — CC-BY ho to credit dena zaroori hai.

Pixabay ke baare me sach: unka official API sirf images + videos deta hai.
Sound effects / music official API me nahi hain (isliye Pixabay se real SFX nahi aate).
"""
import json
import os
import subprocess
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "real")
os.makedirs(CACHE, exist_ok=True)

API = "https://freesound.org/apiv2/search/"
UA = "ASTRA-Cinematic-Audio/1.0"

# hamare SFX naam -> English search (Freesound me English tags hote hain)
SEARCH_TERMS = {
    "footsteps": "footsteps walking",
    "leaf_crush": "dry leaves crunch",
    "leaves": "leaves rustle",
    "rain": "rain ambience",
    "wind": "wind ambience",
    "water": "river water flow",
    "water_drop": "water drop",
    "fire": "fire crackling",
    "thunder": "thunder",
    "door": "wooden door open close house interior",
    "glass": "glass break",
    "metal": "metal hit clang",
    "wood": "wood knock",
    "paper": "paper rustle",
    "coins": "coins falling",
    "engine": "car engine",
    "train": "train pass",
    "helicopter": "helicopter",
    "machine": "machine hum",
    "dog": "dog bark",
    "cat": "cat meow",
    "bird": "birds chirping",
    "cricket": "crickets night",
    "monster": "monster growl",
    "magic": "magic sparkle",
    "laser": "laser",
    "explosion": "explosion",
    "laugh": "man laughing",
    "cry": "crying",
    "breath": "breathing",
    "scream": "scream",
    "gate_open": "wooden door creak opening",
    "gate_close": "wooden door close shut",
    "heartbeat": "heartbeat slow",
    "phone": "old telephone ring",
    "crowd": "crowd talking market ambience",
    "bell": "temple bell ring",
    "switch": "light switch click",
    "car": "car passing by street",
    "whoosh": "whoosh transition",
    "footsteps": "footsteps walking indoor slow",
    "rain": "rain heavy ambience",
    "wind": "wind blowing ambience",
    "fire": "fire crackling close",
}

AMBIENCE_TERMS = {
    "village": "indian village morning ambience birds",
    "night": "night crickets insects ambience",
    "rain": "rain ambience loop",
    "wind": "wind ambience loop",
    "room": "room tone quiet",
    "street": "street traffic crowd ambience",
    "jungle": "jungle forest birds ambience",
    "temple": "temple bells ambience india",
}


def _clean_key():
    """Key me chhupa space/newline/quotes hata do (secret copy karte waqt aata hai)."""
    import re
    k = os.environ.get("FREESOUND_API_KEY", "") or ""
    k = k.strip().strip('"').strip("'")
    return re.sub(r"[^A-Za-z0-9]", "", k)


def have_key():
    return bool(_clean_key())


BANNED_WORDS = ["horror", "scary", "jumpscare", "monster", "demonic", "gun", "storm",
                "slam", "explosion", "scream", "creepy", "zombie", "alien"]

TARGET_DUR = {
    "door": (0.7, 4.5), "gate_open": (0.7, 4.5), "gate_close": (0.4, 3.5),
    "footsteps": (1.5, 10.0), "heartbeat": (1.0, 8.0), "paper": (0.3, 3.0),
    "coins": (0.4, 4.0), "bell": (1.0, 8.0), "phone": (1.0, 8.0),
    "glass": (0.3, 3.5), "metal": (0.3, 4.0), "wood": (0.2, 2.5),
}


def _clean_name(name, target_name):
    """Boring/realistic naam chuno — horror/slam wale hata do (jab tak khud na maanga ho)."""
    n = str(name or "").lower()
    if target_name in ("door", "gate_open", "gate_close", "footsteps", "paper", "coins"):
        return not any(b in n for b in BANNED_WORDS)
    return True


def _dur_score(dur, target_name):
    """Target duration ke andar wale ko zyada point."""
    rng = TARGET_DUR.get(target_name)
    if not rng or not dur:
        return 0
    lo, hi = rng
    return 2 if lo <= float(dur) <= hi else 0


def _license_ok(lic):
    """NC (non-commercial) aur ND (no-derivs) hata do — warna monetized video illegal ho jayegi."""
    l = str(lic or "").lower()
    if "publicdomain" in l or "zero" in l:
        return True
    if "by-nc" in l or "/nc" in l or "noncommercial" in l:
        return False
    if "by-nd" in l or "/nd" in l or "noderiv" in l:
        return False
    return True


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def search(query, limit=8, min_seconds=0.3, max_seconds=60, name_hint=""):
    """Freesound par search. Key na ho to None."""
    key = _clean_key()
    if not key:
        return None
    params = {
        "query": str(query),
        "fields": "id,name,previews,duration,license,username",
        "page_size": str(int(limit)),
        "filter": f"duration:[{min_seconds} TO {max_seconds}]",
        "token": key,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    try:
        data = _get(url)
    except Exception as e:
        print("REAL_SEARCH_FAIL", str(e)[:80], flush=True)
        return None
    out = []
    for s in (data.get("results") or []):
        if not _clean_name(s.get("name"), name_hint):
            print("REAL_SKIP_NAME", str(s.get("name", ""))[:34], flush=True)
            continue
        pv = (s.get("previews") or {})
        link = pv.get("preview-hq-mp3") or pv.get("preview-lq-mp3") or pv.get("preview-hq-ogg")
        if not link:
            continue
        if not _license_ok(s.get("license")):
            print("REAL_SKIP_NC", s.get("name", "")[:30], s.get("license", "")[:40], flush=True)
            continue
        out.append({"id": s.get("id"), "name": s.get("name"), "url": link,
                    "duration": s.get("duration"), "license": s.get("license"),
                    "author": s.get("username"),
                    "score": _dur_score(s.get("duration"), name_hint)
                    + (2 if "zero" in str(s.get("license", "")).lower() else 0)})
    out.sort(key=lambda r: -r.get("score", 0))
    return out


def _download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
        f.write(r.read())
    return os.path.getsize(path) > 5000


def fetch(name, target_seconds=None, force=False):
    """
    Naam (jaise 'footsteps') -> asli recording ka wav path (44.1k mono).
    Key na ho, na mile, ya fail ho -> None.
    """
    term = SEARCH_TERMS.get(name) or AMBIENCE_TERMS.get(name) or name
    out_wav = os.path.join(CACHE, f"{name}.wav")
    meta_path = os.path.join(CACHE, f"{name}.json")
    if os.path.exists(out_wav) and os.path.getsize(out_wav) > 5000 and not force:
        return out_wav
    results = search(term, limit=8, name_hint=name)
    if not results:
        return None
    for r in results:
        tmp = os.path.join(CACHE, f"_tmp_{name}")
        try:
            if not _download(r["url"], tmp):
                continue
            cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, "-ac", "1", "-ar", "44100"]
            if target_seconds:
                cmd += ["-t", f"{float(target_seconds):.2f}"]
            cmd += [out_wav]
            subprocess.run(cmd, check=True, capture_output=True)
            if os.path.exists(out_wav) and os.path.getsize(out_wav) > 5000:
                json.dump({**r, "query": term, "local": out_wav},
                          open(meta_path, "w"), ensure_ascii=False, indent=1)
                print("REAL_OK", name, r["name"][:40], r["license"], flush=True)
                return out_wav
        except Exception as e:
            print("REAL_FAIL", name, str(e)[:60], flush=True)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    return None


def normalize_lufs(path, target=-16.0, out=None):
    """Kisi bhi audio ko target LUFS par lao (voice/music barabar)."""
    out = out or path
    tmp = path + ".n.wav"
    af = f"loudnorm=I={target}:TP=-1.5:LRA=11"
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-af", af,
                        "-ar", "44100", "-ac", "1", tmp], capture_output=True)
    if r.returncode == 0 and os.path.exists(tmp):
        os.replace(tmp, out)
        return True
    return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("use: python3 astra/real_audio.py <naam> [naam2 ...]")
        print("key hai:", have_key())
        sys.exit(0)
    for n in sys.argv[1:]:
        p = fetch(n)
        print(n, "->", p or "(nahi mila — procedural chalega)")
