#!/usr/bin/env python3
"""Sound Pick — script ke shabd se best background file chuno (catalog se).

CLI: python tools/sound_pick.py --catalog catalog.json --text "सूखे पत्तों पर चलना" 
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

KW = {
 "kadam": ["footsteps"], "चल": ["footsteps"], "कदम": ["footsteps"], "पैर": ["footsteps"],
 "पत्ते": ["footsteps"], "मिट्टी": ["footsteps"], "फर्श": ["footsteps"], "घास": ["footsteps"],
 "नदी": ["water"], "पानी": ["water"], "बारिश": ["rain"], "हवा": ["wind"],
 "भेड़िया": ["creatures"], "कुत्ता": ["creatures"], "शेर": ["creatures"], "घोड़ा": ["creatures"],
 "हाथी": ["creatures"], "बंदर": ["creatures"], "सांप": ["creatures"], "सुअर": ["creatures"],
 "चिड़िया": ["birds"], "कौआ": ["birds"], "झींगुर": ["insects"], "कीड़े": ["insects"], "मच्छर": ["insects"],
 "डर": ["horror"], "भूत": ["horror"], "चीख": ["human"], "हंसी": ["human"], "रोना": ["human"],
 "दरवाज़ा": ["doors"], "गाँव": ["city"], "बाज़ार": ["city"],
}

# jeev ka naam → file me dhoondhne wala token (species-aware)
SPECIES = {"भेड़िया": "wolf", "कुत्ता": "dog", "शेर": "lion", "बाघ": "tiger", "घोड़ा": "horse",
           "हाथी": "elephant", "बंदर": "monkey", "सांप": "snake", "सुअर": "boar", "ऊंट": "camel",
           "चिड़िया": "bird", "कौआ": "crow", "झींगुर": "cricket", "मच्छर": "mosquito", "मेंढक": "frog",
           "भालू": "bear", "ज़ेबरा": "zebra", "कंगारू": "kangaroo"}


def pick(catalog: dict, text: str, min_q: float = 0.7) -> list[dict]:
    want = set()
    for k, cats in KW.items():
        if k in text:
            want.update(cats)
    if not want:
        return []
    items = [r for r in catalog["items"] if r["cat"] in want and r.get("quality", 0) >= min_q]
    # species match ko sabse upar rakho
    tokens = [t for k, t in SPECIES.items() if k in text]
    def rank(r):
        hit = any(t in r["file"].lower() for t in tokens)
        return (0 if hit else 1, -r.get("quality", 0), abs(r.get("centroid_hz", 0) - 2000))
    items.sort(key=rank)
    return items[:3]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True); ap.add_argument("--text", required=True)
    a = ap.parse_args()
    cat = json.loads(Path(a.catalog).read_text(encoding="utf-8"))
    for r in pick(cat, a.text):
        print(f"{r['cat']:10s} q={r['quality']} {r['centroid_hz']:5d} Hz  {r['file'][:60]}")
