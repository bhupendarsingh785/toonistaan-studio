#!/usr/bin/env python3
"""Hindi Shabd-Mala — shabd ki jaanch + TTS-safe likhai (piper/koi bhi engine).

Do kaam:
  1. check(text)  -> shabd-mala ki galtiyan (chandrabindu/anunasvar ki jagah, halant, nukta,
                     purane roop, dvitva) — naap ke saath, kism ke saath
  2. respell(text)-> TTS ko dene ke liye surakshit likhai (h-spell + nasal niyam + safe roop)

Niyam (Hindi shabd-mala):
  * चंद्रबिंदु (ँ) un hi jagah jahan svar अ/आ/ए/ओ/औ ho — jaise गाँव, आँख, धुआँ, हँस
  * अनुस्वार (ं) baaki jagah — jaise हिंदी, गंगा, संत, चंपा
  * 'हिन्दी' galat roop hai -> 'हिंदी' (standard)
  * 'क्ष/त्र/ज्ञ' sanyukt — TTS unhe tod kar bolta hai (naap: क्ष -> छ)
"""
from __future__ import annotations
import re

CHANDRA = "ँ"
ANUSVARA = "ं"

# jin svar ke saath chandrabindu aata hai
CHANDRA_VOWELS = set("अआएओऔ" + "ाेैोौ")

WRONG_FORMS = {
    "हिन्दी": "हिंदी", "हिन्दु": "हिंदू", "विशेषतः": "विशेषत:", "केवल": "केवल",
    "गद्य": "गद्य", "उर्दू": "उर्दू", "ज़रूर": "ज़रूर",
}

# TTS ke liye naap kar chune gaye roop (22 Nov: ASR se A/B)
TTS_FIX = {
    "धुआँ": "धुआं",          # piper 'धुआँ' ko 'दूमान' jaisa bolta tha
    "गाँव": "गांव",
    "आँख": "आंख",
    "आँसू": "आंसू",
    "हँस": "हंस",
    "चाँद": "चांद",
    "छह": "छः",              # mahapraan bachane ke liye (h-spell ke saath)
}
HSPELL = {"ख": "क्ह", "घ": "ग्ह", "छ": "च्ह", "झ": "ज्ह", "ठ": "ट्ह", "ढ": "ड्ह",
          "थ": "त्ह", "ध": "द्ह", "फ": "प्ह", "भ": "ब्ह"}


def _syllables(text):
    """aksahr ki moti-toti: vyanjan + matra + anusvar/chandrabindu."""
    return re.findall(r"[\u0915-\u0939\u0958-\u095F]?[\u093E-\u094C\u0962\u0963]?[\u0902\u0901]?[\u094D]?", text)


def check(text: str) -> list[dict]:
    """Shabd-mala ki galtiyan — har ek kism + surakshit roop ke saath."""
    out = []
    for wrong, right in WRONG_FORMS.items():
        if wrong in text:
            out.append({"kind": "purana-roop", "word": wrong, "fix": right,
                        "why": f"'{wrong}' standard nahi hai — '{right}' likho"})
    for syl in _syllables(text):
        vowel = "".join(c for c in syl if c in "ािीुूृेैोौ")
        # chandrabindu sirf khule अ / आ par: गाँव, आँख, धुआँ, हँस
        if CHANDRA in syl and vowel not in ("", "ा"):
            out.append({"kind": "chandrabindu", "word": syl, "fix": syl.replace(CHANDRA, ANUSVARA),
                        "why": "is svar ke saath अनुस्वार (ं) chahiye (jaise छतों, हिंदी), chandrabindu nahi"})
        # anusvara khule अ / आ par = galat: गांव -> गाँव
        if ANUSVARA in syl and vowel in ("", "ा"):
            out.append({"kind": "anusvar", "word": syl, "fix": syl.replace(ANUSVARA, CHANDRA),
                        "why": "khule अ/आ par चंद्रबिंदु (ँ) chahiye (jaise गाँव, आँख, धुआँ)"})
        if "्" in syl and len(syl) > 2 and syl[-1] == "्":
            out.append({"kind": "halant", "word": syl, "fix": syl.rstrip("्"),
                        "why": "shabd ke ant me halant nahi chahiye"})
    return out


def respell(text: str, hspell: bool = True, nasal: bool = True) -> str:
    t = text
    if nasal:
        for a, b in TTS_FIX.items():
            t = t.replace(a, b)
    if hspell:
        # sirf shabd ke BEECH ka mahapraan tod (shuru me 'ब्हेटा' jaisa garbage banta hai — naap se)
        out = []
        for word in t.split(" "):
            if len(word) <= 1:
                out.append(word); continue
            head, tail = word[0], word[1:]
            for a, b in HSPELL.items():
                tail = tail.replace(a, b)
            out.append(head + tail)
        t = " ".join(out)
    return t


def report(text: str) -> dict:
    issues = check(text)
    return {"text": text, "issues": issues, "count": len(issues),
            "tts_text": respell(text), "verdict": "PASS" if not issues else "WARN"}
