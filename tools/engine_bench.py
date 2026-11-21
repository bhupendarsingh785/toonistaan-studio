#!/usr/bin/env python3
"""Engine Bench — kaun engine kitna tez hai (asli naap, andaza nahi).

Har engine par ek hi line chalata hai aur batata hai:
  - kitna second laga (pehli baar = model load + render)
  - kitna second laga dobara (cache ke saath)
  - kitne words per second bane

CLI:
  python tools/engine_bench.py --line "नमस्ते, मैं दादी हूँ।" --engines piper,edge,sarvam
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import worktmp as wt
from tools import engine_router as er


def bench(line: str, engines: list[str], character: str = "dadi") -> list[dict]:
    out = []
    for eng in engines:
        t0 = time.time()
        ok1, log1 = er.render_line(line, character, wt.work_tmp("bench") / f"{eng}_1.wav", eng, [])
        first = round(time.time() - t0, 2)
        t0 = time.time()
        ok2, log2 = er.render_line(line, character, wt.work_tmp("bench") / f"{eng}_2.wav", eng, [])
        second = round(time.time() - t0, 2)
        words = max(1, len(line.split()))
        out.append({"engine": eng, "ok": ok1 and ok2, "first_sec": first, "second_sec": second,
                    "words_per_sec": round(words / second, 2) if second > 0 else None,
                    "note": (log1[-1]["note"] if log1 else ""),
                    "tries": (log1[-1].get("engine") if log1 else "")})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="engine speed bench")
    ap.add_argument("--line", default="नमस्ते, मैं दादी हूँ। तुम आ जाओ, खाना ठंडा हो रहा है।")
    ap.add_argument("--engines", default="piper,edge,espeak,sarvam,elevenlabs")
    ap.add_argument("--character", default="dadi")
    a = ap.parse_args()
    rows = bench(a.line, [e.strip() for e in a.engines.split(",") if e.strip()], a.character)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    ready = [r for r in rows if r["ok"]]
    if ready:
        best = min(ready, key=lambda r: r["second_sec"])
        print(f"\nSabse tez: {best['engine']} ({best['second_sec']}s, cache ke baad)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
