#!/usr/bin/env python3
"""agent_intel.py — chaar agent/browser ko system ka haal de kar KAAM karwao.

Kaam:
  1) agent_brief se system ki asli kamzoriyan lo (pace, background, patli library...)
  2) har agent ko uski zimmedari ke sawaal do (browser_mesh se asli internet)
  3) jawab ko PROPOSAL banao — knowledge/agent-proposals.jsonl
     (koi proposal khud lagu NAHI hota; insaan/Seetal dekhe, phir lage)

  python tools/agent_intel.py --per 2
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import agent_brief as AB           # noqa: E402
import browser_mesh as BM          # noqa: E402

OUT = ROOT / "knowledge" / "agent-proposals.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=2, help="har query par kitne source")
    ap.add_argument("--agents", default="")
    a = ap.parse_args()

    brief = AB.build()
    qs = AB.queries(brief)
    agents = [x.strip() for x in a.agents.split(",") if x.strip()] or list(qs)

    rows = []
    for agent in agents:
        queries = qs.get(agent, [])
        if not queries:
            continue
        topic = queries[0]
        try:
            res = BM.mesh(topic, agents=[agent], per=a.per)
        except Exception as e:
            rows.append({"agent": agent, "topic": topic, "status": "FAIL", "why": repr(e)[:200]})
            continue
        srcs = []
        ev = res.get("evidence") or res.get("pool") or []
        for s in ev[: a.per * 2]:
            srcs.append({"title": (s.get("title") or "")[:120], "url": s.get("url"),
                         "domain": s.get("domain"), "chars": len(s.get("text") or "")})
        rows.append({
            "agent": agent,
            "topic": topic,
            "queries": queries,
            "status": "ok" if srcs else "khali",
            "sources": srcs,
            "internal": list((res.get("agents") or {}).keys()),
            "suggest": "sources padho -> ek chhota badlav propose karo; lagu karne se pehle naap se saabit karo",
            "applied": False,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        for r in rows:
            r["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    for r in rows:
        print("%-11s %-6s %-45s sources=%d" % (r["agent"], r["status"], r["topic"][:45], len(r.get("sources", []))))
    print("\nproposals:", OUT, "| koi khud lagu nahi hua (applied=false)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
