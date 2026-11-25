#!/usr/bin/env python3
"""Voice Guru — teaching.json se har engine ka config banao aur audio ki jaanch karo.

CLI:
  python tools/voice_guru.py --teach            # Hindi me sabak (engine-wise)
  python tools/voice_guru.py --export DIR       # edge/espeak/piper/elevenlabs config files
  python tools/voice_guru.py --qa audio.mp3     # QA checklist ke hisaab se jaanch
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TEACH = ROOT / "voice" / "teaching.json"


def teach(show_engine: str = "") -> None:
    t = json.loads(TEACH.read_text(encoding="utf-8"))
    print(f"# Voice Guru — {t['source']}\n")
    for name, e in t["engines"].items():
        if show_engine and name != show_engine:
            continue
        print(f"## {name.upper()}")
        print("  params:", json.dumps(e["params"], ensure_ascii=False))
        for r in e["rules"]:
            print("  -", r)
        print("  post:", " → ".join(e["post"]))
        print()
    print("## 7 niyam")
    for i, r in enumerate(t["natural_rules"], 1):
        print(f"  {i}. {r}")


def export(dirpath: Path) -> None:
    t = json.loads(TEACH.read_text(encoding="utf-8"))
    dirpath.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, c in t["characters"].items():
        f0, pace, pause = c["f0"], c["pace"], c["pause_s"]
        out[name] = {
            "edge": {"pitch": f"{f0 - 120:+d}Hz", "rate": f"{int((pace / 4.0 - 1) * 100):+d}%"},
            "espeak": {"pitch": int(max(0, min(99, 50 * f0 / 120))), "speed": int(pace * 40),
                       "gap_ms": int(pause * 1000)},
            "piper": {"length_scale": round(4.0 / pace, 2), "sentence_silence": round(pause * 0.4, 2)},
            "elevenlabs": {"stability": 0.4, "similarity_boost": 0.75, "style": 0.38, "speaker_boost": True},
            "browser": {"pitch": round(min(2, f0 / 120), 2), "rate": round(min(1.6, pace / 4.0), 2)},
        }
    for eng in ("edge", "espeak", "piper", "elevenlabs", "browser"):
        cfg = {k: v[eng] for k, v in out.items()}
        cfg["_emotion_map"] = t["emotion_map"]
        cfg["_qa"] = t["qa_checklist"]
        p = dirpath / f"{eng}.json"
        p.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
        print("likha:", p)


def qa(audio: str) -> int:
    t = json.loads(TEACH.read_text(encoding="utf-8"))
    from tools import audio_read6 as ar
    rep = ar.read(audio)
    q = t["qa_checklist"]
    turns = [x for x in rep.get("turns", []) if x["f0"] > 0]
    if not turns:
        print(json.dumps({"ok": False, "why": "awaaz nahi mili"})); return 1
    import numpy as np
    bands = q["f0_bands_hz"]
    def band_of(hz):
        for k, (lo, hi) in bands.items():
            if lo <= hz <= hi:
                return k
        return None
    in_band = [band_of(x["f0"]) for x in turns]
    hit = sum(1 for b in in_band if b)
    pct = round(100 * hit / len(turns), 1)
    f0 = int(np.median([x["f0"] for x in turns]))
    std = round(float(np.median([x["f0_std"] for x in turns])), 1)
    pace = round(float(np.median([x["pace"] for x in turns])), 2)
    diff = rep["levels"]["farq_db"]
    checks = {
        "f0_band": {"median_hz": f0, "turns_in_band_pct": pct,
                    "ok": pct >= 80,
                    "detail": "har turn ka sur kisi kirdaar ke band me girna chahiye (>=80%)"},
        "f0_std": {"value": std, "min": q["min_f0_std"], "ok": std >= q["min_f0_std"]},
        "pace": {"value": pace, "range": q["pace_range"],
                 "ok": q["pace_range"][0] <= pace <= q["pace_range"][1]},
        "background": {"farq_db": diff, "range": q["background_below_db"],
                       "ok": q["background_below_db"][0] <= diff <= q["background_below_db"][1]},
    }
    passed = sum(1 for c in checks.values() if c["ok"])
    print(json.dumps({"file": Path(audio).name, "passed": f"{passed}/{len(checks)}",
                      "checks": checks}, ensure_ascii=False, indent=1))
    return 0 if passed == len(checks) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teach", action="store_true")
    ap.add_argument("--engine", default="")
    ap.add_argument("--export", default="")
    ap.add_argument("--qa", default="")
    a = ap.parse_args()
    if a.export:
        export(Path(a.export)); return 0
    if a.qa:
        return qa(a.qa)
    teach(a.engine); return 0


if __name__ == "__main__":
    raise SystemExit(main())
