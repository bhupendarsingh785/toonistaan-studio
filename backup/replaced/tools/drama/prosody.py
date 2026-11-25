#!/usr/bin/env python3
"""prosody.py — layer 3: bhaav + kirdaar -> performance instructions (bina LLM, bina API)."""
from __future__ import annotations
import re

# (pitch_scale, pace, energy, pause_extra) — intensity se guna hota hai
EMO = {
    "pyaar":   (1.20, 0.96, 1.02, 0.06), "dukh": (0.88, 0.92, 0.94, 0.12),
    "dar":     (1.26, 1.08, 1.04, -0.02), "gussa": (0.94, 1.12, 1.12, -0.04),
    "khushi":  (1.28, 1.05, 1.08, 0.00), "hairani": (1.24, 1.04, 1.06, 0.02),
    "rahasya": (0.94, 0.92, 0.96, 0.14), "neutral": (1.00, 1.00, 1.00, 0.00),
}
STRESS = {"नहीं","बहुत","सबसे","अकेला","पहले","कभी","फिर","अब","क्यों","क्या","रुको","ज़रूर","कभी"}
Q_WORDS = ("क्या","क्यों","कहाँ","कब","कौन","कैसे","कितना")


def plan(line: dict, profile: dict | None = None) -> dict:
    prof = profile or {}
    txt = line["text"].strip()
    emo = (line.get("emotion") or "neutral").lower()
    inten = max(0.0, min(1.0, float(line.get("intensity", 0.7))))
    ps, pace, energy, pextra = EMO.get(emo, EMO["neutral"])
    k = 0.5 + 0.5 * inten                     # intensity ka asar (0.5..1.0)
    pitch_scale = 1 + (ps - 1) * k
    pace = prof.get("pace", 1.0) * (1 + (pace - 1) * k)
    energy = 1 + (energy - 1) * k
    words = [w for w in re.split(r"\s+", txt) if w]
    is_q = "?" in txt or any(txt.startswith(w) or f" {w}" in txt for w in Q_WORDS)
    p_start = 0.7 * (pitch_scale - 1) * 12 + 0.4        # semitone
    p_mid = 0.25 * (pitch_scale - 1) * 12
    p_end = ((2.6 if is_q else -1.8) * pitch_scale)
    stress = [w for w in words if w.strip("।,?!…") in STRESS or len(w.strip("।,?!…")) >= 6][:4]
    pause = float(line.get("pause_after", 0.42)) + pextra * k + (0.05 if is_q else 0)
    return {"who": line["who"], "text": txt, "emotion": emo, "intensity": round(inten, 2),
            "pace": round(max(0.85, min(1.18, pace)), 3), "energy": round(energy, 3),
            "curve": [(0.0, round(p_start, 2)), (0.45, round(p_mid, 2)),
                      (0.8, round(-1.2 * pitch_scale, 2)), (1.0, round(p_end, 2))],
            "stress": stress, "pause_after": round(max(0.2, min(0.9, pause)), 2)}


def plan_all(lines: list[dict], chars: dict) -> list[dict]:
    return [plan(l, chars.get(l["who"])) for l in lines]
