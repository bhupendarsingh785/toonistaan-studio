#!/usr/bin/env python3
"""Bhaav — Hindi bhaavon ki samajh (pehchan + asar + misaal).

Kaam:
  1) Line padh kar bhaav pehchano (dukh, gussa, dar, khushi, pyaar, hasai, rona, hairan, sharam, thakan)
  2) Batаo kis bhaav me awaaz kaisi honi chahiye (sur, raftaar, zor, rukna)
  3) Har bhaav ke Hindi shabd, cues aur misaal — taaki engine "samajh" sake

CLI:
  python tools/bhavna.py detect --text "बेटा, आ जा पास।"
  python tools/bhavna.py list
  python tools/bhavna.py show --name dukh
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

# ---------------------------------------------------------------- knowledge
BHAV = {
 "neutral": {
   "hindi": "सामान्य", "arth": "bina khaas bhaav ke, seedhi baat",
   "sur": 1.00, "raftaar": 1.00, "zor": 1.00, "rukna": "normal",
   "cues": [], "misaal": "शाम ढल रही थी।",
 },
 "khushi": {
   "hindi": "खुशी", "arth": "khushi, utsaah, hansi-mazaak",
   "sur": 1.08, "raftaar": 1.08, "zor": 1.05, "rukna": "kam",
   "cues": ["खुश", "खुशी", "बहुत अच्छा", "वाह", "शाबाश", "हुर्रे", "मज़ा", "मजा", "आनंद", "सुंदर", "!",
            "हँस", "हंस"],
   "misaal": "वाह! आज तो मज़ा आ गया।",
 },
 "dukh": {
   "hindi": "दुख", "arth": "dukh, takleef, udaasi, khed",
   "sur": 0.94, "raftaar": 0.88, "zor": 0.90, "rukna": "zyada",
   "cues": ["दुख", "तकलीफ", "उदास", "रो", "अफसोस", "माफ", "खो दिया", "चला गया", "अकेला", "दर्द", "मुश्किल"],
   "misaal": "मुझे आज बहुत तकलीफ़ हो रही है।",
 },
 "gussa": {
   "hindi": "गुस्सा", "arth": "gussa, chidh, dhamki",
   "sur": 1.06, "raftaar": 1.10, "zor": 1.15, "rukna": "kam",
   "cues": ["गुस्सा", "चुप", "बंद करो", "बकवास", "क्यों", "नहीं सुनूँगा", "हट", "धिक्कार", "!!"],
   "misaal": "चुप रहो! कुछ मत बोलो।",
 },
 "dar": {
   "hindi": "डर", "arth": "dar, ghabrahat, sahamna",
   "sur": 1.04, "raftaar": 1.12, "zor": 0.85, "rukna": "beech me",
   "cues": ["डर", "कौन है", "बचाओ", "भागो", "भूत", "अंधेरा", "साया", "आहट", "काँप", "कांप"],
   "misaal": "कौन है वहाँ? कोई है क्या?",
 },
 "pyaar": {
   "hindi": "प्यार", "arth": "pyaar, apnapan, lagaav",
   "sur": 1.02, "raftaar": 0.94, "zor": 0.95, "rukna": "thoda",
   "cues": ["प्यार", "बेटा", "बेटी", "माँ", "जान", "दिल", "अपना", "गले", "मेरा बच्चा", "साथ"],
   "misaal": "बेटा, आ जा पास।",
 },
 "hasai": {
   "hindi": "हँसी", "arth": "hansi, mazaak, halka-pan",
   "sur": 1.10, "raftaar": 1.06, "zor": 1.02, "rukna": "kam",
   "cues": ["हा हा", "ही ही", "मज़ाक", "मजाक", "मज़ेदार", "मजेदार", "बेवकूफ", "हँसी", "हंसी"],
   "misaal": "हा हा, ये तो कमाल हो गया!",
 },
 "rona": {
   "hindi": "रोना", "arth": "rone jaisi haalat, bhaari gala",
   "sur": 0.92, "raftaar": 0.82, "zor": 0.88, "rukna": "bahut zyada",
   "cues": ["रो", "रुला", "आँसू", "आंसू", "सिसक", "छोड़ गए", "अब क्या होगा"],
   "misaal": "अब मैं क्या करूँ... सब छोड़ के चले गए।",
 },
 "hairan": {
   "hindi": "हैरानी", "arth": "achanak, hairat, shak",
   "sur": 1.05, "raftaar": 1.02, "zor": 1.00, "rukna": "thoda",
   "cues": ["क्या", "अरे", "ओह", "सच", "हैरान", "अचानक", "ये कैसे", "अजीब"],
   "misaal": "अरे! ये कैसे हो गया?",
 },
 "sharam": {
   "hindi": "शरम", "arth": "sharm, jhijhak, dheemi awaaz",
   "sur": 1.00, "raftaar": 0.90, "zor": 0.82, "rukna": "thoda",
   "cues": ["शरम", "झिझक", "माफ़ कीजिए", "माफ कीजिए", "क्या कहूँ", "मुझे नहीं पता"],
   "misaal": "वो... मुझे ठीक से नहीं पता।",
 },
 "thakan": {
   "hindi": "थकान", "arth": "thakaan, sustee, saans bhaari",
   "sur": 0.96, "raftaar": 0.84, "zor": 0.85, "rukna": "zyada",
   "cues": ["थक", "थका", "नींद", "आराम", "बहुत दिन", "अब नहीं होगा", "सुस्त"],
   "misaal": "आज बहुत थक गया हूँ, अब सो जाऊँ।",
 },
}

EMOTIONS = tuple(BHAV.keys())


def detect(text: str) -> dict:
    """Line se bhaav pehchano — cues + vakya ke nishaan."""
    t = (text or "").strip()
    if not t:
        return {"emotion": "neutral", "confidence": 0.0, "hits": [], "why": "khaali line"}
    scores: dict[str, float] = {}
    hits: dict[str, list] = {}
    for name, row in BHAV.items():
        if name == "neutral":
            continue
        found = [c for c in row["cues"] if c and c in t]
        if found:
            scores[name] = len(found) * 1.0
            hits[name] = found
    # vakya ke nishaan (punctuation) ka asar
    if "!!" in t or t.count("!") >= 2:
        scores["gussa"] = scores.get("gussa", 0) + 0.8
        hits.setdefault("gussa", []).append("!!")
    if t.count("?") >= 2 or t.startswith("क्या"):
        scores["hairan"] = scores.get("hairan", 0) + 0.5
        hits.setdefault("hairan", []).append("?")
    if "..." in t or "…" in t:
        scores["dukh"] = scores.get("dukh", 0) + 0.4
        scores["rona"] = scores.get("rona", 0) + 0.3
        hits.setdefault("dukh", []).append("...")
    if not scores:
        return {"emotion": "neutral", "confidence": 0.35, "hits": [], "why": "koi cue nahi mila"}
    best = max(scores, key=lambda k: scores[k])
    total = sum(scores.values()) or 1.0
    return {"emotion": best, "confidence": round(min(0.99, 0.45 + 0.35 * scores[best] / total + 0.1 * min(1, scores[best] / 3)), 2),
            "hits": hits.get(best, []), "also": [k for k in scores if k != best],
            "why": f"cue mile: {', '.join(hits.get(best, [])[:3])}"}


def prosody(emotion: str) -> dict:
    """Us bhaav me awaaz kaisi honi chahiye."""
    row = BHAV.get(emotion, BHAV["neutral"])
    return {"emotion": emotion, "sur": row["sur"], "raftaar": row["raftaar"],
            "zor": row["zor"], "rukna": row["rukna"]}


def style(emotion: str, character: str = "") -> dict:
    """Ek jagah se bhaav ka style: sur (pitch), raftaar (pace), zor (energy), rukna (pause ms)."""
    row = BHAV.get(emotion, BHAV["neutral"])
    gap_ms = {"kam": 120, "normal": 220, "thoda": 320, "zyada": 450,
              "bahut zyada": 600, "beech me": 380}.get(row.get("rukna", "normal"), 220)
    return {"emotion": emotion if emotion in BHAV else "neutral",
            "pitch": round(row["sur"], 3), "pace": round(row["raftaar"], 3),
            "energy": round(row["zor"], 3), "gap_ms": gap_ms}


def list_all() -> list[dict]:
    return [{"emotion": k, **{kk: vv for kk, vv in v.items() if kk != "cues"},
             "cues": len(v["cues"])} for k, v in BHAV.items()]


def show(name: str) -> dict:
    row = BHAV.get(name)
    if not row:
        raise KeyError(f"aisa bhaav nahi: {name} (hai: {', '.join(EMOTIONS)})")
    return {"emotion": name, **row}


def main() -> int:
    ap = argparse.ArgumentParser(description="Hindi bhaav samajh")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect"); d.add_argument("--text", required=True)
    sub.add_parser("list")
    s = sub.add_parser("show"); s.add_argument("--name", required=True)
    a = ap.parse_args()
    try:
        if a.cmd == "detect":
            print(json.dumps(detect(a.text), ensure_ascii=False, indent=2)); return 0
        if a.cmd == "list":
            print(json.dumps(list_all(), ensure_ascii=False, indent=1)); return 0
        print(json.dumps(show(a.name), ensure_ascii=False, indent=2)); return 0
    except Exception as exc:
        print(f"[x] {type(exc).__name__}: {exc}"); return 1


if __name__ == "__main__":
    sys.exit(main())
