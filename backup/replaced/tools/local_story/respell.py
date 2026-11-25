#!/usr/bin/env python3
"""Respell — piper ke Hindi G2P ki pakki galtiyon ka ilaaj.

Naap se mila (22 Nov): piper **mahapraan (aspirated) vyanjan gira deta hai** —
छ→च, थ→त, ध→द, ख→क (jaise "छह" → "चैहे", "थे" → "ते", "धुआँ" → "दूवान").
Ilaaj: unhe likhte waqt tod kar likho — "च्ह", "त्ह", "द्ह" (h-spell). Yehi trick espeak ke
galti-report me bhi kaam aayi thi (महाप्राण: h-spell 3/3).

Sirf TTS ko diya jaata hai — marks/script ka asli text waisa hi rehta hai.
"""
from __future__ import annotations

HSPELL = {"ख": "क्ह", "घ": "ग्ह", "छ": "च्ह", "झ": "ज्ह", "ठ": "ट्ह", "ढ": "ड्ह",
          "थ": "त्ह", "ध": "द्ह", "फ": "प्ह", "भ": "ब्ह"}

# chhote, safe badlav (naap se: गाँव→गांव se thoda sudhar hua)
SAFE = [("गाँव", "गांव"), ("गाँवों", "गांवों"), ("धुआँ", "धुआं"), ("आँख", "आंख"),
        ("आँसू", "आंसू"), ("हँस", "हंस"), ("ठंड", "ठंड"), ("चाँद", "चांद")]


def respell(text: str, hspell: bool = True, safe: bool = True) -> str:
    """Ab hindi_shabd.py ka poora niyam lagta hai (nasal + safe roop + h-spell)."""
    try:
        import hindi_shabd as HS
        return HS.respell(text, hspell=hspell, nasal=safe)
    except Exception:
        pass
    t = text
    if safe:
        for a, b in SAFE:
            t = t.replace(a, b)
    if hspell:
        for a, b in HSPELL.items():
            t = t.replace(a, b)
    return t
