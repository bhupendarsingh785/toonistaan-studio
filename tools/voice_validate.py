#!/usr/bin/env python3
"""Voice Validate — voices.json ke Sarvam speakers sahi hain ya nahi.

Kyun: Sarvam ne bulbul:v2 hata diya; v3 me sirf kuch speaker hain. Galat speaker par
API 400 deta hai (ya default awaaz de deta hai) — chup-chaap kharab output.

CLI:
  python tools/voice_validate.py            # check karo
  python tools/voice_validate.py --json
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICES = ROOT / "astra" / "voices.json"

# bulbul:v3 ke valid speakers (Sarvam API error message se liye — 20 Nov 2026)
V3_SPEAKERS = {"aditya", "ritu", "ashutosh", "priya", "neha", "rahul", "pooja",
               "rohan", "simran", "kavya", "amit", "dev"}


def check(path: Path | None = None, allowed: set[str] | None = None) -> dict:
    allowed = allowed or V3_SPEAKERS
    p = path or VOICES
    if not p.exists():
        return {"ok": False, "error": f"voices.json nahi mila: {p}", "bad": [], "speakers": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    chars = data.get("characters", {})
    bad = []
    used = set()
    for name, row in chars.items():
        sp = (row.get("sarvam") or "").strip()
        used.add(sp)
        if sp and sp not in allowed:
            bad.append({"character": name, "speaker": sp})
    return {"ok": not bad, "characters": len(chars), "speakers": sorted(used),
            "bad": bad, "allowed_count": len(allowed)}


def main() -> int:
    ap = argparse.ArgumentParser(description="voices.json ke speaker check karo")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rep = check()
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        if rep.get("error"):
            print("[x]", rep["error"]); return 1
        print(f"kirdaar: {rep['characters']} | speakers: {len(rep['speakers'])} | valid: {rep['allowed_count']}")
        if rep["ok"]:
            print("[OK] sab speaker valid hain")
        else:
            print(f"[FAIL] {len(rep['bad'])} kirdaar ka speaker galat:")
            for b in rep["bad"][:20]:
                print(f"   {b['character']:12s} -> {b['speaker']}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
