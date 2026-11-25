#!/usr/bin/env python3
"""Story Sound Map — kahani ki HAR cheez ki awaaz, deep level.

Kaam:
  1) Script ki har line padho, usme maujood cheezon ko pehchano (bhediya, nadi,
     patte, darwaza, khidki, baarish, gaadi, train, ghoda...)
  2) Har cheez ke liye library me asli file dhoondo (na mile to "MISSING" batao)
  3) Line ke shuru me us cheez ki awaaz ka event banao (gain ke saath)
  4) Report: kitni cheezein mili, kaunsi missing (naam ke saath)

CLI: python tools/story_soundmap.py --script stories/x.json [--write]
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "astra" / "library"

# cheez -> (library me dhoondhne ke patterns, gain_db, kya bed hai?)
SOUNDS: dict[str, dict] = {
    "bhediya":   {"pat": ["animals/dingo_howl.mp3", "animals/dogs_howl.mp3"], "gain": -15},
    "bhediya_pair": {"pat": ["footsteps/feet_leaves.mp3", "footsteps/leaves_dry.mp3"], "gain": -20},
    "gurrana":   {"pat": ["horror/monster_lurk.mp3", "animals/dragon_growl.mp3"], "gain": -14},
    "patte":     {"pat": ["footsteps/feet_leaves.mp3", "footsteps/leaves_dry.mp3", "nature/bush_rustling.mp3"], "gain": -17},
    "kadam":     {"pat": ["footsteps/steps_soil.mp3", "footsteps/bvk_footsteps_1.mp3"], "gain": -15},
    "nadi":      {"pat": ["water/flowing_river.mp3", "ambience/forest_river_bed.mp3"], "gain": -24, "bed": True},
    "baarish":   {"pat": ["ambience/rain_gentle_1.mp3", "ambience/rain_window.mp3"], "gain": -22, "bed": True},
    "garaj":     {"pat": ["ambience/weather_rain_thunder_storm.mp3"], "gain": -17},
    "darwaza":   {"pat": ["door/bvk_door_1.mp3", "door/bvk_door_2.mp3"], "gain": -15},
    "khidki":    {"pat": ["ambience/wind_howl_window.mp3", "door/bvk_door_3.mp3"], "gain": -19},
    "train":     {"pat": ["transport/steam_train_passing_1.mp3", "transport/indian_train_arriving_announcement.mp3"], "gain": -16},
    "station":   {"pat": ["transport/train_platform_ambience_1.mp3", "crowd/crowd_applause.mp3"], "gain": -23, "bed": True},
    "chai":      {"pat": ["water/kettle_cup.mp3", "kitchen/boil_2.mp3"], "gain": -19},
    "pakshi":    {"pat": ["ambience/bird_chirp_3.mp3", "ambience/birds_forest_1.mp3"], "gain": -20, "bed": True},
    "jhingur":   {"pat": ["nature/city_night_crickets.mp3", "nature/cicada_insects.mp3"], "gain": -22, "bed": True},
    "hawa":      {"pat": ["ambience/wind_blowing.mp3", "ambience/wind_cold.mp3"], "gain": -23, "bed": True},
    "ghoda":     {"pat": ["animals/horse_walk.mp3", "animals/horse_neigh.mp3"], "gain": -16},
    "bheed":     {"pat": ["crowd/cheering_crowd_2.mp3", "crowd/crowd_applause.mp3"], "gain": -24, "bed": True},
}
# text me kaunse shabd kis cheez ko darshate hain
TRIGGERS: dict[str, list[str]] = {
    "bhediya": ["भेड़िया", "भेड़िये", "शेरू"],
    "gurrana": ["गुर्रा", "गुर्र", "दहाड़"],
    "patte":   ["पत्ते", "पत्तों", "सूखे पत्ते", "झाड़ियों", "घास"],
    "kadam":   ["चलने लगे", "चल पड़ी", "पैर", "रास्ते", "भागी", "दौड़"],
    "nadi":    ["नदी", "पानी", "पुल"],
    "baarish": ["बारिश", "बरसात"],
    "garaj":   ["बिजली", "गर्जना", "बादल"],
    "darwaza": ["दरवाज़ा", "दरवाजा", "फाटक"],
    "khidki":  ["खिड़की", "पर्दा"],
    "train":   ["ट्रेन", "सीटी", "रेलवे", "पटरियां", "डिब्बे"],
    "station": ["स्टेशन", "प्लेटफॉर्म"],
    "chai":    ["चाय", "दूध", "रोटियां", "खाना"],
    "pakshi":  ["चिड़ियां", "पक्षी", "तोते", "मुर्गे"],
    "jhingur": ["रात", "जंगल में कहीं"],
    "hawa":    ["हवा", "शाखाएं", "झूमने"],
    "bheed":   ["भीड़", "लोग"],
}


def find(pat_list: list[str]) -> str | None:
    for rel in pat_list:
        if (LIB / rel).exists():
            return rel
    # exact fail -> same folder me pehla match
    for rel in pat_list:
        folder = (LIB / rel).parent
        if folder.exists():
            anyf = sorted(p for p in folder.glob("*.mp3"))
            if anyf:
                return str(anyf[0].relative_to(LIB))
    return None


def analyse(script: dict) -> dict:
    t = 0.0
    found, missing = [], []
    events = list(script.get("events", []))
    for line in script["lines"]:
        text = line["text"]
        hits = [k for k, words in TRIGGERS.items() if any(w in text for w in words)]
        for key in hits:
            rel = find(SOUNDS[key]["pat"])
            if not rel:
                missing.append({"line": text[:40], "cheez": key})
                continue
            found.append({"at": round(t + 0.05, 2), "cheez": key, "file": rel})
            if key == "bhediya":       # bhediya ke pairon ki awaaz (patton par)
                rel2 = find(SOUNDS["bhediya_pair"]["pat"])
                if rel2:
                    events.append({"at": round(t + 0.9, 2), "file": rel2,
                                   "gain": SOUNDS["bhediya_pair"]["gain"]})
            events.append({"at": round(t + 0.05, 2), "file": rel, "gain": SOUNDS[key]["gain"]})
        t += 4.0      # andaazan (asli timing render ke baad cues se milta hai)
    return {"found": found, "missing": missing, "events": events}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--write", action="store_true", help="script me events jod do")
    a = ap.parse_args()
    path = Path(a.script)
    script = json.loads(path.read_text(encoding="utf-8"))
    rep = analyse(script)
    print(json.dumps({"mili": len(rep["found"]), "missing": len(rep["missing"]),
                      "missing_list": rep["missing"][:10]}, ensure_ascii=False, indent=1))
    if a.write:
        script["events"] = rep["events"]
        path.write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
        print("events likh diye:", len(rep["events"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
