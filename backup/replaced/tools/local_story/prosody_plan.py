#!/usr/bin/env python3
"""prosody_plan.py — local prosody planner (layer 2). Bina LLM, bina API.

Har line ko padh kar "performance instructions" deta hai:
  {pace, pitch_start, pitch_mid, pitch_end, stress:[words], pause_after, energy}

Niyam (Hindi ke liye):
  - sawaal (?) -> ant me sur upar (+2.2 st)
  - statement (।) -> ant me sur neeche (-1.6 st)
  - comma (,) -> 0.18s ka rukav + halka upar
  - bhaav -> pitch/pace/energy ka guna
  - zor wale shabd: sambandhit/adjective (naam se pehchan), numbers, "nahi"
"""
from __future__ import annotations
import re

BHAV = {   # (pitch_mult, pace, energy)
    "pyaar":   (1.18, 0.96, 1.02), "dukh": (0.90, 0.93, 0.96), "dar": (1.15, 1.08, 1.04),
    "hairani": (1.22, 1.04, 1.06), "khushi": (1.25, 1.05, 1.08), "gussa": (1.15, 1.10, 1.10),
    "rahasya": (0.95, 0.92, 0.97), "neutral": (1.00, 1.00, 1.00),
}
STRESS_WORDS = {"नहीं", "बहुत", "सबसे", "अकेला", "पहले", "कभी", "फिर", "अब", "क्यों", "क्या", "रुको"}


def _is_content(w: str) -> bool:
    """naam/vishleshan jaise lambhe shabd par zor (Hindi endings se pehchan)."""
    w = w.strip("।,?!…")
    if len(w) < 3:
        return False
    return bool(re.search(r"(ता|त्व|ई|ाओं|ियों|पन|वाला|वाली|ेरा|ारा)$", w)) or len(w) >= 6


def plan_line(text: str, bhaav: str = "neutral", who: str = "narrator") -> dict:
    b = BHAV.get((bhaav or "neutral").lower(), BHAV["neutral"])
    pitch_mult, pace, energy = b
    t = text.strip()
    words = [w for w in re.split(r"\s+", t) if w]
    is_q = "?" in t or re.search(r"(क्या|क्यों|कहाँ|कब|कौन|कैसे)\b", t) is not None
    commas = t.count(",") + t.count("…")
    # sur ka curve (semitone me, base se)
    p_start = 0.6 * pitch_mult
    p_mid = 0.2 * pitch_mult
    p_end = (2.2 if is_q else -1.6) * pitch_mult
    # zor wale shabd
    stress = [w for w in words if w.strip("।,?!…") in STRESS_WORDS or _is_content(w)][:4]
    # rukav
    pause_after = 0.42 + 0.06 * commas
    if is_q:
        pause_after += 0.06
    if who == "bhediya":
        pace *= 0.96          # bhediya dheema bolta hai
    if who == "stree":
        pace *= 1.00
        energy *= 1.05        # ladki ki awaaz thodi upar
    return {"text": t, "who": who, "bhaav": bhaav, "is_question": is_q,
            "pace": round(min(1.15, max(0.85, pace)), 3),
            "energy": round(energy, 3),
            "pitch_start": round(p_start, 2), "pitch_mid": round(p_mid, 2), "pitch_end": round(p_end, 2),
            "stress": stress, "pause_after": round(pause_after, 2),
            "words": len(words)}


def plan_script(script: list[dict]) -> list[dict]:
    return [plan_line(r["text"], r.get("bhaav", "neutral"), r.get("who", "narrator")) for r in script]


if __name__ == "__main__":
    import json, sys
    from pathlib import Path
    sc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = plan_script(sc)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:1200])
