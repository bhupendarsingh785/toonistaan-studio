#!/usr/bin/env python3
"""scene_env.py — kahani ki JAGAH/TIME/MOSAM/KHATRA samajh kar vatavaran chuno.

Asli dikkat jo user ne batayi: "jungle ka matlab ye nahi ki 20 minute bhediye chillate rahein".
Yahan niyam saaf hain:

  jagah   : jungle, nadi, pahad, gaon, ghar, kamra, society, station, bazaar, gufa, khet
  samay   : subah, din, shaam, raat
  mosam   : saaf, barish, tufan, dhoop
  khatra  : 0 (shaant) .. 1 (jaan ka khatra)
  kaam    : chalna, daudna, baat, khaana, sona

Inse tay hota hai: kaun si bed chalegi, kaun si BAND, kitni door se, aur kahan CHUP rehna hai.

  python tools/scene_env.py --report /scratch/work/ch1-clean.txt
  python tools/scene_env.py --line "गौरी सोसायटी के कमरे में बैठी थी, रात हो चुकी थी।"
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
K = ROOT / "knowledge"

LOC = {
    "jungle": ["जंगल", "वन", "पेड़ों", "झाड़ी", "घने पेड़", "forest", "कीट"],
    "nadi": ["नदी", "धारा", "घाट", "पानी बह", "झरना", "river", "stream"],
    "pahad": ["पहाड़", "चोटी", "ढलान", "घाटी", "mountain"],
    "gaon": ["गाँव", "गांव", "खेत", "आँगन", "कुआँ", "गाय", "ग्वाला"],
    "ghar": ["घर", "दरवाज़ा", "दरवाजा", "आँगन", "चूल्हा", "रसोई", "छत"],
    "kamra": ["कमरा", "कमरे", "चारपाई", "खिड़की", "दीया", "बिस्तर", "room"],
    "society": ["सोसायटी", "कॉलोनी", "कालोनी", "फ्लैट", "लिफ्ट", "अपार्टमेंट", "बिल्डिंग"],
    "station": ["स्टेशन", "रेल", "ट्रेन", "प्लेटफॉर्म", "गाड़ी", "पटरी"],
    "bazaar": ["बाज़ार", "बाजार", "दुकान", "भीड़", "मेला"],
    "gufa": ["गुफा", "गुफाएँ", "कंदरा"],
    "khet": ["खेत", "हल", "फसल", "धान", "गेहूँ"],
}
TIME = {
    "subah": ["सुबह", "भोर", "तड़के", "सूरज उग"],
    "din": ["दिन", "दोपहर", "धूप"],
    "shaam": ["शाम", "ढल", "संध्या", "साँझ", "सांझ"],
    "raat": ["रात", "अंधेरा", "अंधेरे", "चाँद", "चांद", "चाँदनी", "आधी रात"],
}
WEATHER = {
    "barish": ["बारिश", "बरसात", "बूँद", "बूंद"],
    "tufan": ["तूफान", "आंधी", "आँधी", "बिजली"],
    "dhoop": ["धूप", "गर्मी", "तपन"],
}
DANGER = ["खतरा", "डर", "भागो", "चीख", "खून", "हमला", "भेड़िया", "श्राप", "मौत", "मर", "जख्म", "घायल"]
CALM = ["शांत", "चुप", "सो", "आराम", "मुस्कुरा", "हँस"]

# jagah -> {layer: (gain, "kab")}   "kab": always / din / raat / kabhi (kahani me zikr ho)
BEDS = {
    "jungle":  {"leaves": (0.9, "always"), "wind": (0.6, "always"), "crickets": (0.8, "raat"),
                "birds": (0.7, "din"), "koel": (0.5, "subah"), "wolf": (0.0, "nahi"), "owl": (0.5, "raat")},
    "nadi":    {"river": (1.0, "always"), "wind": (0.4, "always"), "birds": (0.5, "din"), "crickets": (0.5, "raat")},
    "pahad":   {"wind": (1.0, "always"), "birds": (0.4, "din"), "crickets": (0.3, "raat")},
    "gaon":    {"wind": (0.5, "always"), "birds": (0.7, "subah"), "crickets": (0.4, "raat"),
                "leaves": (0.3, "always"), "river": (0.3, "always")},
    "ghar":    {"wind": (0.25, "always"), "rain": (0.5, "barish"), "fire": (0.4, "always"), "crickets": (0.15, "raat")},
    "kamra":   {"wind": (0.1, "always"), "rain": (0.35, "barish"), "fire": (0.2, "always")},
    "society": {"wind": (0.15, "always"), "birds": (0.3, "subah"), "rain": (0.5, "barish")},
    "station": {"wind": (0.1, "always"), "rain": (0.4, "barish")},
    "bazaar":  {"wind": (0.15, "always")},
    "gufa":    {"wind": (0.2, "always"), "drip": (0.5, "always")},
    "khet":    {"wind": (0.6, "always"), "birds": (0.5, "subah"), "crickets": (0.4, "raat")},
}
# jin jagahon par jungle ki awaaz bilkul nahi (asli duniya ka niyam)
BAN_IN = {
    "society": {"crickets", "wolf", "owl", "leaves", "river", "koel"},
    "kamra":   {"wolf", "owl", "river", "koel", "birds"},
    "station": {"wolf", "owl", "crickets", "leaves"},
    "ghar":    {"wolf", "owl", "river"},
}


def _hits(text, table):
    for k, words in table.items():
        if any(w in text for w in words):
            return k
    return None


def analyse(text: str) -> dict:
    loc = _hits(text, LOC) or "jungle"
    tod = _hits(text, TIME) or "din"
    wx = _hits(text, WEATHER) or "saaf"
    dgr = min(1.0, sum(1 for w in DANGER if w in text) * 0.34)
    calm = any(w in text for w in CALM)
    return {"loc": loc, "time": tod, "weather": wx, "danger": round(dgr, 2), "calm": calm}


def beds_for(st: dict) -> dict:
    """Is scene me kaun si bed, kitne gain par (0 = band)."""
    table = BEDS.get(st["loc"], BEDS["jungle"])
    banned = BAN_IN.get(st["loc"], set())
    out = {}
    for layer, (gain, when) in table.items():
        if layer in banned:
            out[layer] = 0.0
            continue
        if when == "nahi":
            out[layer] = 0.0
        elif when == "always":
            out[layer] = gain
        elif when == st["time"]:
            out[layer] = gain
        else:
            out[layer] = gain * 0.25        # galat waqt par bahut halka
    # mosam
    if st["weather"] == "barish":
        out["rain"] = max(out.get("rain", 0), 0.7)
    elif st["weather"] == "tufan":
        out["rain"] = max(out.get("rain", 0), 0.8)
        out["thunder"] = 0.6
    # khatra: sab dheema, sirf zaroori
    if st["danger"] >= 0.6:
        out = {k: v * 0.55 for k, v in out.items()}
    # shaant scene: kuch layer band (natural silence)
    if st["calm"]:
        out = {k: (v * 0.6 if k in ("wind", "leaves") else v) for k, v in out.items()}
    return {k: round(v, 2) for k, v in out.items() if v > 0}


def plan(lines):
    """Har line ka vatavaran; badalne par crossfade ka waqt."""
    rows, prev = [], None
    for ln in lines:
        st = analyse(ln["text"])
        st["who"], st["text"] = ln.get("who", ""), ln["text"][:60]
        st["beds"] = beds_for(st)
        st["change"] = (prev is not None and (st["loc"] != prev["loc"] or st["time"] != prev["time"]))
        rows.append(st)
        prev = st
    return rows


def schedule(rows, min_gap: float = 8.0, max_layers: int = 4):
    """Scheduler ke niyam: ek awaaz baar-baar nahi, ek saath bahut saari nahi.

    rows: [{loc,time,beds,start,end,who,text}] (plan() se)
    """
    last_used, out = {}, []
    for r in rows:
        beds = dict(r["beds"])
        t0 = float(r.get("start", 0.0))
        # 1) jo abhi-abhi baja, use hata do (dohraav nahi)
        for k in list(beds):
            if k in last_used and t0 - last_used[k] < min_gap:
                beds[k] *= 0.35
        # 2) ek saath bahut saari layer nahi
        if len(beds) > max_layers:
            beds = dict(sorted(beds.items(), key=lambda kv: -kv[1])[:max_layers])
        # 3) samvaad ke waqt background dheema (baat pehle)
        if r.get("who") and r.get("who") != "" and r.get("text"):
            beds = {k: round(v * 0.75, 2) for k, v in beds.items()}
        for k in beds:
            last_used[k] = t0
        out.append({**r, "beds": beds})
    return out


def report(path: Path):
    lines = []
    for l in path.read_text(encoding="utf-8").splitlines():
        if ":" in l:
            who, t = l.split(":", 1)
            lines.append({"who": who.strip(), "text": t.strip()})
    rows = plan(lines)
    from collections import Counter
    print("scene badle:", sum(1 for r in rows if r["change"]), "| kul line:", len(rows))
    print("jagah:", dict(Counter(r["loc"] for r in rows)))
    print("samay:", dict(Counter(r["time"] for r in rows)))
    for r in rows[:12]:
        print(f"  {r['loc']:8s} {r['time']:5s} khatra {r['danger']:.2f} | beds: {list(r['beds'])[:6]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default="")
    ap.add_argument("--line", default="")
    a = ap.parse_args()
    if a.line:
        st = analyse(a.line); st["beds"] = beds_for(st)
        print(json.dumps(st, ensure_ascii=False, indent=1)); return 0
    if a.report:
        report(Path(a.report)); return 0
    print("kuch do: --line ya --report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
