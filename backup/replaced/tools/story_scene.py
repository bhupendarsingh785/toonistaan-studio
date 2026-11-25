#!/usr/bin/env python3
"""Story Scene Planner — kahani ki **jagah** aur **duri** samajh kar awaaz lagana.

Problem jo Swag ne bataya: pairon/bhediya/train ki awaaz galat waqt par, galat jagah.
Hal: pehle scene samjho (kahan hai? kaun hai? kitna door?), phir hi sound lagao.

Niyam (practical):
  • TRAIN  — sirf station/train wale scene me. Gaon/ghar me sirf **door ki halki** awaaz (-30 dB), ek baar.
  • NADI   — sirf nadi/jungle scene me (bed).
  • KADAM  — sirf jab koi **chal raha** ho (chal/daud/bhaag/ja rahi) — line se **0.35 s pehle**, 1.4 s tak.
  • BHEDIYA— sirf bhediya/gurrana wali line par; "paas/samne" = -15 dB, warna door -24 dB. Pair 0.8 s baad.
  • BAARISH— sirf बारिश/बादल/बिजली wali line ke baad se (bed).
  • JHINGUR— sirf raat wale scene me.
  • PAKSHI — sirf subah/jungle/gaon wale scene me, din me.
  • Ek hi awaaz 2.5 s ke andar dobara nahi.

CLI: python tools/story_scene.py --script stories/x.json [--write]
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "astra" / "library"

PLACE_WORDS = {
    "ghar":    ["घर", "आंगन", "रसोई", "चाय", "चारपाई", "बेंच", "अखबार", "कमरा", "दरवाज़ा"],
    "rasta":   ["रास्ते", "पगडंडी", "सड़क", "तालाब", "खेत", "पुल"],
    "jungle":  ["जंगल", "पेड़", "झाड़ियों", "पत्ते", "हिरण", "भेड़िया"],
    "nadi":    ["नदी", "पानी", "बह रही"],
    "station": ["स्टेशन", "प्लेटफॉर्म", "ट्रेन", "पटरियां", "सीटी", "डिब्बे"],
    "shahar":  ["शहर", "मौसी", "गाड़ियों", "बाजार"],
}
TIME_WORDS = {"subah": ["सुबह", "धूप", "मुर्गे", "चिड़ियां"],
              "raat":  ["रात", "अंधेरा", "लालटेन", "सो गया"]}
# sirf asli chalne wale shabd (pehle "गई" jaise aam shabd se galat kadam baj rahe the)
WALK_WORDS = ["चलने लगे", "चल पड़ी", "चल पड़े", "भागी", "भाग", "दौड़", "रवाना",
              "निकल पड़े", "बढ़ने लगे", "पैदल", "चले", "चलती रही", "उतर आई", "चढ़ने लगी"]

ASSETS = {
    "train":    ("transport/steam_train_passing_1.mp3", -14),
    "train_far":("transport/indian_train_arriving_announcement.mp3", -30),
    "station":  ("transport/train_platform_ambience_1.mp3", -24),
    "nadi":     ("water/flowing_river.mp3", -25),
    "kadam":    ("footsteps/steps_soil.mp3", -16),
    "kadam_far":("footsteps/feet_leaves.mp3", -23),
    "bhediya":  ("animals/dingo_howl.mp3", -15),
    "bhediya_far": ("animals/dogs_howl.mp3", -24),
    "pair":     ("footsteps/feet_leaves.mp3", -20),
    "gurrana":  ("horror/monster_lurk.mp3", -14),
    "baarish":  ("ambience/rain_gentle_1.mp3", -22),
    "garaj":    ("ambience/weather_rain_thunder_storm.mp3", -17),
    "jhingur":  ("nature/city_night_crickets.mp3", -22),
    "pakshi":   ("ambience/bird_chirp_3.mp3", -20),
    "darwaza":  ("door/bvk_door_1.mp3", -15),
    "chai":     ("water/kettle_cup.mp3", -19),
    "bheed":    ("crowd/cheering_crowd_2.mp3", -25),
}
MAXLEN = {"kadam": 1.4, "kadam_far": 1.6, "pair": 1.0, "bhediya": 3.5, "bhediya_far": 3.0,
          "gurrana": 2.5, "garaj": 3.0, "darwaza": 1.2, "chai": 2.0, "pakshi": 2.5,
          "train": 4.0, "train_far": 4.0, "bheed": 3.0}


def _has(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def plan(lines: list[dict], bed_extra: list[tuple[str, float]] | None = None) -> dict:
    """lines: [{text, start, dur, who}] → {'events': [(at, file, gain, dur)], 'beds': [(file, gain)]}"""
    events: list[tuple[float, str, float, float]] = []
    beds: list[tuple[str, float]] = []
    last_used: dict[str, float] = {}
    train_done_places: set[str] = set()
    rain_started = False

    def add(kind: str, at: float, *, far: bool = False, force: bool = False) -> None:
        key = kind if not far else f"{kind}_far"
        if key not in ASSETS and far:
            key = kind
        if key not in ASSETS:
            return
        cool = {"pakshi": 12.0, "jhingur": 15.0, "train": 15.0, "train_far": 40.0,
                "bheed": 8.0, "kadam": 3.0, "kadam_far": 4.0, "pair": 5.0}.get(key, 2.5)
        if not force and at - last_used.get(key, -99) < cool:
            return
        rel, gain = ASSETS[key]
        if not (LIB / rel).exists():
            return
        events.append((max(0.0, round(at, 2)), rel, gain, MAXLEN.get(key, 2.0)))
        last_used[key] = at

    for i, l in enumerate(lines):
        text = l["text"]; st = float(l["start"])
        place = next((p for p, ws in PLACE_WORDS.items() if _has(text, ws)), None)
        time_of_day = "raat" if _has(text, TIME_WORDS["raat"]) else ("subah" if _has(text, TIME_WORDS["subah"]) else "")

        # TRAIN — sirf station/train scene me; gaon me door ki halki (ek hi baar)
        if _has(text, ["ट्रेन", "सीटी", "पटरियां", "डिब्बे", "रेलवे"]):
            if place in ("station", "shahar"):
                add("train", st - 0.4)          # station par asli train
            elif place not in train_done_places:
                add("train_far", st - 0.4, force=True)   # gaon/ghar: bas door se halki
                train_done_places.add(str(place))
        if place == "station":
            add("station", st + 0.2)

        # NADI — bed (scene ke hisaab se)
        if _has(text, ["नदी", "बह रही", "पुल"]) and ("water/flowing_river.mp3", -25) not in beds:
            beds.append(("water/flowing_river.mp3", -25))

        # KADAM — sirf chalne par, line se 0.35s pehle
        if _has(text, WALK_WORDS):
            far = _has(text, ["दूर", "पीछे", "कुछ दूरी"])
            add("kadam", st - 0.35, far=far)

        # BHEDIYA / GURRANA
        if _has(text, ["भेड़िया", "भेड़िये", "शेरू"]):
            near = _has(text, ["सामने", "पास", "बाहर निकला", "खड़ा"])
            add("bhediya", st - 0.2, far=not near)
            add("pair", st + 0.8)
        if _has(text, ["गुर्रा", "गुर्र"]):
            add("gurrana", st - 0.1)

        # BAARISH / GARAJ — shuru hone ke baad bed
        if _has(text, ["बारिश", "बरसात", "बादल"]) and not rain_started:
            beds.append(("ambience/rain_gentle_1.mp3", -23)); rain_started = True
        if _has(text, ["बिजली", "गर्जना", "गरज"]):
            add("garaj", st + 0.1)

        # RAAT / SUBAH
        if time_of_day == "raat":
            add("jhingur", st + 0.3)
        if time_of_day == "subah":
            add("pakshi", st + 0.2)

        # GHAR ki cheezein
        if _has(text, ["दरवाज़ा", "दरवाजा", "फाटक"]):
            add("darwaza", st - 0.1)
        if _has(text, ["चाय", "दूध", "रोटियां"]):
            add("chai", st + 0.1)
        if _has(text, ["भीड़", "प्लेटफॉर्म", "लोग"]):
            add("bheed", st + 0.2)

    for b in (bed_extra or []):
        beds.append(b)
    return {"events": events, "beds": beds}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    p = Path(a.script); d = json.loads(p.read_text(encoding="utf-8"))
    lines = d.get("lines", [])
    t = 0.25
    timed = []
    for l in lines:
        timed.append({**l, "start": t, "dur": 4.0})
        t += 4.35
    rep = plan(timed)
    print(json.dumps({"events": len(rep["events"]), "beds": len(rep["beds"]),
                      "sample": rep["events"][:6]}, ensure_ascii=False, indent=1))
    if a.write:
        d["bed"] = [{"file": f, "gain": g} for f, g in rep["beds"]]
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print("bed likh diya")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
