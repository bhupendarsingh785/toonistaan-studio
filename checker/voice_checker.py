#!/usr/bin/env python3
"""voice_checker.py — awaaz ko insaan ke paimane par naapne wala tool (ALAG, system se bahar).

Ye audio_gate ke wahi naap use karta hai (jitter, shimmer, HNR, sur ka failaav,
buzz, rukna, rukne ki variety, raftaar, jhatke, clipping, background) aur seedha
report deta hai — bina kuch badle.

  python checker/voice_checker.py --file out.mp3
  python checker/voice_checker.py --audit-dir /scratch/output
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "tools"))

import audio_gate as G   # noqa: E402


def check(path: str, script: str | None = None) -> dict:
    m = G.scan(path, script)
    j = G.judge(m, script)
    return {"file": Path(path).name, "metrics": m, "verdict": j["verdict"],
            "robot_score": j["robot_score"], "rows": j["rows"]}


def show(r: dict) -> None:
    print(f"\n=== {r['file']} — {r['verdict']} (robot {r['robot_score']})")
    for row in r["rows"]:
        mark = "OK " if row["ok"] else "XX "
        print(f"  {mark} {row['naam']:<14} {row['value']}  ({row['note']})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--audit-dir", default="")
    ap.add_argument("--script", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    files = []
    if a.file:
        files = [a.file]
    elif a.audit_dir:
        d = Path(a.audit_dir)
        files = [str(p) for p in sorted(list(d.glob("*.mp3")) + list(d.glob("*.wav")))]
    else:
        print("--file ya --audit-dir do"); return 0
    out = []
    missing = [f for f in files if not Path(f).exists()]
    if missing:
        print(f"File nahi mili: {', '.join(missing)}  (pehle cast_build chalao)"); return 3
    for f in files:
        r = check(f, a.script or None)
        show(r); out.append(r)
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [r for r in out if r["verdict"] != "PASS"]
    print(f"\n{len(out)} file jaanchi | PASS {len(out)-len(bad)} | baaki {len(bad)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
