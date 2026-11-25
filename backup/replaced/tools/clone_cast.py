#!/usr/bin/env python3
"""clone_cast.py — har kirdaar ke liye ASLI insaan ki awaaz chuno (cloning ke liye).

Kaam: library/harvest ki asli recordings me se, kirdaar ke sur (hz) ke sabse kareeb
recording chuno -> uska profile banao -> knowledge/voice-profiles/<kirdaar>.json

Isse TTS ki robotic awaaz ki jagah asli recording ka "rang" aata hai
(naap: jitter 3.9 -> 1.9, shimmer 14.1 -> 8.1, HNR 8.9 -> 15.6 dB).

  python tools/clone_cast.py --build
  python tools/clone_cast.py --show
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
K = ROOT / "knowledge"
PROF = K / "voice-profiles"
SRC_DIRS = [Path("/scratch/work/voice_harvest"), Path("/scratch/input")]

# kirdaar -> (target hz, gender)
CAST = {
    "गौरी": (205, "f"), "कमला": (186, "f"), "माई": (168, "f"),
    "मोहन": (275, "m"), "हरिदास": (104, "m"), "ऋषि": (96, "m"),
    "भेड़िया": (88, "m"), "सरपंच": (118, "m"), "वाचक": (112, "m"),
}


def _files(limit=60):
    out = []
    for d in SRC_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.glob("*")):
            if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".ogx", ".oga"):
                out.append(p)
        if len(out) >= limit:
            break
    return out[:limit]


def build():
    """Pehle sab ke profile (tez), phir har kirdaar ke top-3 par ASR (dheema sirf wahan)."""
    import voice_clone_lite as VL
    PROF.mkdir(parents=True, exist_ok=True)
    pool = []
    for p in _files():
        x = VL.load(str(p), sec=10.0)
        if x is None:
            continue
        pr = VL.profile_of(x)
        ok, _why = VL.profile_quality(pr)
        if ok:
            pool.append({"file": str(p), "f0": pr["f0_median"], "prof": pr})
    print("profile pool:", len(pool), flush=True)
    try:
        import auto_label as AL
    except Exception:
        AL = None
    made = {}
    for name, (hz, g) in CAST.items():
        if not pool:
            break
        cands = sorted(pool, key=lambda r: abs(r["f0"] - hz))[:3]
        chosen = None
        for c in cands:
            if AL is None:
                chosen = c; break
            x = VL.load(c["file"], sec=10.0)
            has_words, _t = AL.asr_has_words(x) if x is not None else (False, "")
            print(f"  check {name}: {Path(c['file']).name[:34]} f0 {c['f0']:.0f} words={has_words}", flush=True)
            if has_words:
                chosen = c; break
        if not chosen:
            print(f"  !! {name}: insaan ki awaaz nahi mili (chhoda)", flush=True)
            continue
        pr = dict(chosen["prof"])
        pr.update({"name": name, "source": Path(chosen["file"]).name, "target_hz": hz})
        (PROF / f"{name}.json").write_text(json.dumps(pr, ensure_ascii=False, indent=1), encoding="utf-8")
        made[name] = {"ref": Path(chosen["file"]).name[:44], "ref_f0": round(chosen["f0"], 1), "target": hz}
        print(f"  OK {name:8s} ref {chosen['f0']:6.1f} -> {hz} | {Path(chosen['file']).name[:38]}", flush=True)
    (K / "clone-cast.json").write_text(json.dumps(made, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def show():
    p = K / "clone-cast.json"
    print(p.read_text(encoding="utf-8") if p.exists() else "pehle --build chalao")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if a.show:
        show(); return 0
    return build()


if __name__ == "__main__":
    raise SystemExit(main())
