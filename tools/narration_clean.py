#!/usr/bin/env python3
"""narration_clean.py — vachak (narrator) awaaz ka shabd nahi likhega.

Swag ka niyam: "नदी कल-कल बह रही थी" nahi — bas "नदी बह रही थी".
Awaaz ka kaam awaaz karegi (bed/event layer), vachak usse nakal kar ke nahi bolega.

  python tools/narration_clean.py "नदी कल-कल बह रही थी"
"""
from __future__ import annotations
import re
import sys

# awaaz ki nakal (onomatopoeia) — ye vachak ki line me nahi aani chahiye
SOUND_WORDS = [
    "कल-कल", "कलकल", "छन-छन", "छनछन", "टप-टप", "टपटप", "सर-सर", "सरसर",
    "गड़-गड़", "गड़गड़", "झर-झर", "झरझर", "खड़-खड़", "खड़खड़", "टर्र-टर्र",
    "चूं-चूं", "कू-कू", "भिनभिन", "भिन-भिन", "टन-टन", "धड़-धड़", "धड़धड़",
    "फड़फड़", "फड़-फड़", "सनसन", "सन-सन", "गूंज-गूंज",
]
# nakal hatane ke baad jo shabd bachte hain unhe theek karo
TIDY = [
    (r"\s+", " "),
    (r"\s+([,।])", r"\1"),
    (r"बह\s+रही\s+थी\s+।", "बह रही थी।"),
]


def strip_sounds(text: str) -> tuple[str, list[str]]:
    """Nakal ke shabd hatao; jo hataya wo wapas batao (taaki awaaz se bhara ja sake)."""
    found = []
    out = text
    for w in SOUND_WORDS:
        if w in out:
            found.append(w)
            out = out.replace(w, " ")
    for pat, rep in TIDY:
        out = re.sub(pat, rep, out)
    out = out.strip(" ,")
    if out and not out.endswith(("।", ".", "?", "!")):
        out += "।"
    return out, found


def clean_script(lines: list[dict], narrator_names=("vachak", "सूत्रधार", "narrator")) -> tuple[list[dict], list[dict]]:
    """Poori script: sirf vachak ki lines saaf; kirdaron ki dialogue ko chhedo mat."""
    notes = []
    for ln in lines:
        who = (ln.get("who") or ln.get("speaker") or "").strip().lower()
        if who in [n.lower() for n in narrator_names]:
            new, found = strip_sounds(ln.get("text") or "")
            if found:
                notes.append({"line": ln.get("text"), "saaf": new, "hataya": found,
                              "kaam": "ye awaaz background/event layer se aayegi"})
                ln["text"] = new
    return lines, notes


def main() -> int:
    t = " ".join(sys.argv[1:]) or "शाम ढल रही थी और नदी कल-कल बह रही थी।"
    new, found = strip_sounds(t)
    print("pehle:", t)
    print("ab   :", new)
    print("hataya:", found or "kuch nahi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
