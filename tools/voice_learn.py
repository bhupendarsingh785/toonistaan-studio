#!/usr/bin/env python3
"""Voice Learn — asli insaan ke naap se har engine ko tune karo (bina Sarvam).

Kaam:
  1) target: `voice/presets.json` (RISHTEY jaisi asli awaaz ke naap)
  2) har engine ke liye **parameter math**: browser TTS, espeak, piper, edge
  3) agar engine ka output mile to **naap kar** galti batao (F0 kitna door)
  4) `--check` se: target vs naapa hua (kisi bhi audio file par)

CLI:
  python tools/voice_learn.py --targets              # har engine ke settings
  python tools/voice_learn.py --check audio.mp3      # file se tulna
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PRESETS = ROOT / "voice" / "presets.json"


def engine_settings(p: dict) -> dict:
    out = {}
    for name, c in p["characters"].items():
        f0, pace = c["f0"], c["pace"]
        out[name] = {
            "target_f0": f0, "target_pace": pace,
            "browser": {"pitch": round(min(2, max(0.1, f0 / 120)), 2),
                        "rate": round(min(1.6, max(0.5, pace / 4.0)), 2),
                        "pause_s": c["pause_s"]},
            "espeak": {"pitch": int(max(0, min(99, 50 * f0 / 120))),
                       "speed": int(max(80, min(260, pace * 40))),
                       "gap_ms": int(c["pause_s"] * 1000)},
            "piper": {"length_scale": round(min(2.0, max(0.6, 4.0 / pace)), 2),
                      "sentence_silence": round(c["pause_s"] * 0.4, 2)},
            "edge": {"pitch_hz": f"{f0 - 120:+d}Hz",
                     "rate": f"{int((pace / 4.0 - 1) * 100):+d}%"},
        }
    return out


def check(audio: str, p: dict) -> dict:
    from tools import audio_read6 as ar
    rep = ar.read(audio)
    f0s = [t["f0"] for t in rep.get("turns", []) if t["f0"] > 0]
    if not f0s:
        return {"ok": False, "why": "koi awaaz nahi mili"}
    import numpy as np
    hz = int(np.median(f0s))
    bands = p["targets"]
    best = min(bands.items(), key=lambda kv: abs(kv[1]["f0_median"] - hz))
    return {"ok": True, "file": Path(audio).name, "naapa_f0": hz,
            "sabse_kareeb": best[0], "target_f0": best[1]["f0_median"],
            "farq_hz": hz - best[1]["f0_median"],
            "salah": ("sur theek" if abs(hz - best[1]["f0_median"]) <= 12 else
                      f"pitch {'ghatao' if hz > best[1]['f0_median'] else 'badhao'} "
                      f"{abs(hz - best[1]['f0_median'])} Hz")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", action="store_true")
    ap.add_argument("--check", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    p = json.loads(PRESETS.read_text(encoding="utf-8"))
    if a.check:
        res = check(a.check, p)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res.get("ok") else 1
    s = engine_settings(p)
    print(json.dumps(s, ensure_ascii=False, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
