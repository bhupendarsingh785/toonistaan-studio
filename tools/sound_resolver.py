#!/usr/bin/env python3
"""sound_resolver.py — EK darwaza: shabd se awaaz tak (pehchano → chuno → banao → laao).

Training ka maksad yahi hai. Kahani me jo shabd aaya, uske liye char raaste:
  1. **library** — pehle se maujood asli recording (content-index se, naam se nahi)
  2. **synth**   — nahi mili to KHUD banao (loop_maker / awaazein registry)
  3. **web**     — tab bhi na bane to internet se laao (Wikimedia), aur library me jod do
  4. **voice**   — insaan ki awaaz ho to TTS + umar/sur ka niyam (dadi ≠ ladki)

Har jawab ke saath "kaun sa raasta chala, kyun" likha jaata hai — jhooth nahi.

  python tools/sound_resolver.py "भेड़िया"
  python tools/sound_resolver.py --demo
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "world"))

K = ROOT / "knowledge"
INP = Path("/scratch/input")
LOG = K / "sound-resolver-log.jsonl"

# shabd -> (kism, library patterns, synth naam, web query)
WORDS = {
    "भेड़िया": ("jeev", ["wolf", "howl", "bhediya"], None, "wolf howling"),
    "कुत्ता": ("jeev", ["dog-bark", "barking", "dog-"], "dog_bark", "dog barking"),
    "बिल्ली": ("jeev", ["cat-meow", "meow"], None, "cat meowing"),
    "शेर": ("jeev", ["lion", "tiger", "roar"], None, "lion roar"),
    "मोर": ("jeev", ["peacock", "myna", "koel"], None, "peacock call"),
    "झींगुर": ("keeda", ["cricket", "cicada"], "crickets", "crickets at night"),
    "मेंढक": ("jeev", ["frog", "croak"], "frog", "frog croaking"),
    "घोड़ा": ("jeev", ["horse", "neigh", "hoof"], None, "horse neigh"),
    "हाथी": ("jeev", ["elephant"], None, "elephant trumpet"),
    "बंदर": ("jeev", ["monkey", "chimp"], None, "monkey calls"),
    "नदी": ("jagah", ["river", "stream", "flowing-water"], "river", "river flowing"),
    "बारिश": ("jagah", ["rain"], "rain", "rain sound"),
    "हवा": ("jagah", ["wind"], "wind", "wind blowing"),
    "पत्ते": ("jagah", ["leaves", "rustl"], "leaves", "leaves rustling"),
    "आग": ("jagah", ["fire", "crackle"], "fire", "campfire crackle"),
    "दरवाज़ा": ("cheez", ["door"], "door_creak", "door creak"),
    "कदम": ("cheez", ["footstep", "kadam", "walking"], "wood_steps", "footsteps"),
    "गुफा": ("jagah", ["cave"], "room", "cave ambience"),
    "गाय": ("jeev", ["cow", "cattle"], None, "cow moo"),
    "बकरी": ("jeev", ["goat", "sheep"], None, "goat bleat"),
    "सांप": ("jeev", ["snake", "python", "hiss"], None, "snake hiss"),
    "चिड़िया": ("jeev", ["bird", "chirp"], "birds", "bird chirping"),
}


def _index():
    p = K / "audio-content-index.json"
    return json.loads(p.read_text(encoding="utf-8")).get("tags", {}) if p.exists() else {}


def _tag_for(kind: str) -> list[str]:
    """Sirf SPECIFIC tag — 'animals' jaisa mota tag nahi (warna giraffe ke liye myna de dega)."""
    return {"jagah": ["water"], "cheez": ["door", "footsteps", "foley/impact"]}.get(kind, [])


def from_library(patterns: list[str], kind: str, k: int = 3):
    """Asli recording — pehle naam se, phir content tag se."""
    files = [p for p in INP.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".ogx")]
    hits = [p for p in files if any(x in p.name.lower() for x in patterns)]
    if hits:
        return hits[0], "naam se mili"
    # tag se sirf tab jab shabd hi paani/awaaz ka ho (warna galat cheez aa jaati hai)
    if any(x in " ".join(patterns) for x in ("water", "river", "rain", "stream")):
        idx = _index()
        for rec in idx.get("water", [])[:20]:
            p = INP / rec["file"]
            if p.exists() and rec.get("sec", 0) > 1.0:
                return p, "content tag 'water' se"
    return None, ""


def from_synth(synth: str, kind: str, sec: float = 3.0):
    """Nahi mili to banao — jagah ki awaaz loop_maker se, cheez/jeev awaazein se."""
    try:
        import loop_maker as LM
        if synth in LM.MAKERS:
            x, seed, why = LM.make_checked(synth, sec=sec)
            if x is not None:
                return x, f"loop_maker ({why})"
    except Exception:
        pass
    try:
        import awaazein as AW
        if synth and synth in AW.REGISTRY:
            rng = np.random.default_rng(7)
            x = AW.REGISTRY[synth](rng)
            x = x / (np.max(np.abs(x)) + 1e-9)
            return x, "awaazein registry"
    except Exception:
        pass
    return None, ""


def from_web(query: str, tag: str):
    """Internet se laao (Wikimedia), aur library me jod do."""
    try:
        import fetch_real_audio as F
        rows = F.fetch(query, 1, tag)
        if rows:
            return Path(rows[0]["file"]), rows[0].get("license", "?")
    except Exception as e:
        return None, f"web fail: {type(e).__name__}"
    return None, "web khali"


def resolve(word: str, allow_web: bool = True) -> dict:
    kind, patterns, synth, webq = WORDS.get(word, ("cheez", [word], None, word))
    out = {"word": word, "kind": kind, "routes": []}

    p, why = from_library(patterns, kind)
    if p:
        out.update(route="library", path=str(p), why=why)
        out["routes"].append("library")
        return out

    x, why = from_synth(synth, kind)
    if x is not None:
        out.update(route="synth", why=why, audio=x)
        out["routes"].append("synth")
        return out

    if allow_web:
        p, lic = from_web(webq, word[:6] or "web")
        if p:
            out.update(route="web", path=str(p), why=f"internet se, license {lic}")
            out["routes"].append("web")
            return out
        out["web_note"] = lic

    out.update(route="kuch_nahi", why="library + synth + web teeno khali")
    return out


def demo() -> int:
    words = ["भेड़िया", "मोर", "झींगुर", "मेंढक", "नदी", "बारिश", "दरवाज़ा", "कदम"]
    rows = []
    for w in words:
        r = resolve(w, allow_web=False)      # demo me web band (tez)
        rows.append(r)
        print(f"{w:8s} -> {r['route']:8s} | {r['why'][:52]}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if k != "audio"}, ensure_ascii=False) + "\n")
    ok = sum(1 for r in rows if r["route"] in ("library", "synth"))
    print(f"\n{ok}/{len(rows)} shabd ki awaaz mil gayi (library ya synth se)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("word", nargs="?", default="")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--web", action="store_true")
    a = ap.parse_args()
    if a.demo or not a.word:
        return demo()
    r = resolve(a.word, allow_web=a.web)
    print(json.dumps({k: v for k, v in r.items() if k != "audio"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
