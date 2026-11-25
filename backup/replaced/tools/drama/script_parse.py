#!/usr/bin/env python3
"""script_parse.py — scene JSON ko lines me todo (layer 1).

Input (naya format):
  {"scene":"nadi_kinare","time":"raat","characters":["bhediya","stree"],
   "lines":[{"who":"stree","text":"...","emotion":"dar","intensity":0.8,"pause_after":0.35}]}

Purana simple format bhi chalta hai: [{"who","text","bhaav"}]
"""
from __future__ import annotations
import json
from pathlib import Path


def parse(data) -> dict:
    if isinstance(data, list):
        return {"scene": "adhyaay", "time": "day", "characters": sorted({r.get("who", "narrator") for r in data}),
                "lines": [{"who": r.get("who", "narrator"), "text": r["text"],
                           "emotion": r.get("bhaav", r.get("emotion", "neutral")),
                           "intensity": float(r.get("intensity", 0.7)),
                           "pause_after": float(r.get("pause", r.get("pause_after", 0.42)))} for r in data]}
    lines = []
    for r in data.get("lines", []):
        lines.append({"who": r.get("who", "narrator"), "text": r["text"],
                      "emotion": r.get("emotion", r.get("bhaav", "neutral")),
                      "intensity": float(r.get("intensity", 0.7)),
                      "pause_after": float(r.get("pause_after", 0.42))})
    return {"scene": data.get("scene", "adhyaay"), "time": data.get("time", "day"),
            "characters": data.get("characters", sorted({l["who"] for l in lines})), "lines": lines}


def load(path: str | Path) -> dict:
    return parse(json.loads(Path(path).read_text(encoding="utf-8")))
