#!/usr/bin/env python3
"""Audio Learn — Swag ke bheje audio se seekho aur apne cast ko sudharo.

Kaam:
  1) audio ko padho (audio_profile)
  2) uske "andaaz" ke numbers nikalo (sur, raftaar, rukna, background)
  3) hamare cast presets se tulna karo
  4) sudhaar ke sifarish do: pitch/pace me kitna badlav (Hz aur % me)
  5) seekha hua `knowledge/audio-lessons.jsonl` me jodo (agle render me kaam aaye)

CLI:
  python tools/audio_learn.py --audio x.mp3            # report + sifarish
  python tools/audio_learn.py --audio x.mp3 --apply    # presets me lagao (backup ke saath)
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import audio_profile as ap_mod

PRESETS = ROOT / "voice-core" / "cast-presets.json"
LESSONS = ROOT / "knowledge" / "audio-lessons.jsonl"


def advice(rep: dict) -> dict:
    p = rep["pitch"]; cmp_ = rep["compare"]
    hz, lo_hi = p["median_hz"], ap_mod.CAST.get(cmp_["closest_cast"], (0, 0))
    out = {"closest": cmp_["closest_cast"], "target_band": lo_hi}
    if hz < lo_hi[0]:
        out["pitch_change_hz"] = lo_hi[0] - hz
        out["pitch_param_delta"] = round(-(lo_hi[0] - hz) / max(1, hz) / 0.7, 3)
        out["action"] = "awaaz neechi hai — pitch upar karo"
    elif hz > lo_hi[1]:
        out["pitch_change_hz"] = lo_hi[1] - hz
        out["pitch_param_delta"] = round(-(hz - lo_hi[1]) / max(1, hz) / 0.7, 3)
        out["action"] = "awaaz upar hai — pitch neeche karo"
    else:
        out["pitch_change_hz"] = 0; out["pitch_param_delta"] = 0.0
        out["action"] = "sur band me hai — jaisa hai waisa rakho"
    # expressiveness
    if p["std_hz"] < 20:
        out["expressiveness"] = "flat hai — temperature/emotion badhao (Sarvam temp +0.1)"
    elif p["std_hz"] > 70:
        out["expressiveness"] = "bahut utar-chadhav — temp thoda kam karo"
    else:
        out["expressiveness"] = "theek (insaan jaisa utar-chadhav)"
    # rukna
    pz = rep["pauses"]
    out["pause_style"] = ("bahut rukta hai — pace badhao" if pz["count"] > rep["dur"] / 3
                          else "natural rukavat")
    # background
    bg = rep["background"]
    out["background_note"] = ("background bed hai (spectral flatness zyada)" if bg["bed_likely"]
                              else "saaf recording, background halka")
    out["gain_note"] = ("awaaz dheemi hai — -6 dB se zyada boost karna padega" if rep["rms_dbfs"] < -24
                        else "level theek")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--apply", action="store_true", help="presets me pitch badlav lagao")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    rep = ap_mod.profile(a.audio)
    if not rep.get("ok"):
        print(json.dumps(rep)); return 1
    adv = advice(rep)
    rep["advice"] = adv
    print(json.dumps({"dur": rep["dur"], "pitch_hz": rep["pitch"]["median_hz"],
                      "closest": adv["closest"], "action": adv["action"],
                      "pitch_param_delta": adv["pitch_param_delta"],
                      "expressiveness": adv["expressiveness"],
                      "pause": adv["pause_style"], "background": adv["background_note"],
                      "gain": adv["gain_note"]}, ensure_ascii=False, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    LESSONS.parent.mkdir(parents=True, exist_ok=True)
    with LESSONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "audio": Path(a.audio).name, **{k: rep[k] for k in ("dur", "pitch", "voice", "background")},
                            "advice": adv}, ensure_ascii=False) + "\n")
    if a.apply and PRESETS.exists() and adv["pitch_param_delta"]:
        data = json.loads(PRESETS.read_text(encoding="utf-8"))
        who = adv["closest"]
        if who in data["cast"]:
            old = data["cast"][who]["pitch"]
            data["cast"][who]["pitch"] = round(max(-0.5, min(0.5, old + adv["pitch_param_delta"])), 3)
            PRESETS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            print(json.dumps({"applied": who, "pitch": f"{old} -> {data['cast'][who]['pitch']}"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
