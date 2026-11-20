"""Independent command-line runtime for one ASTRA learning engine.

Each engine owns its browser research, SQLite memory, inbox, reports and learning
worker under its own directory. This runtime does not import another engine.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence_agent import run_cycle, autopilot, IntelligenceMemory
from browser_agent_v08 import research as browser_research, agent_status
from agent_cognition import backend_status
from agent_evolution import AgentEvolution
from open_source_learning import learning_status
from youtube_research import research_youtube

ENGINE = ROOT.name.lower()

def status():
    memory = IntelligenceMemory(ROOT)
    return {
        "schema": "astra-independent-learning-agent/v1",
        "engine": ENGINE,
        "state": "ready",
        "ownership": {
            "browser": str(ROOT / "browser_agent_v08.py"),
            "memory_db": str(memory.db),
            "research": str(ROOT / "research"),
            "knowledge_inbox": str(ROOT / "knowledge_inbox"),
            "reports": str(ROOT / "reports"),
            "learning_worker_lock": str(ROOT / "memory" / "open_source_learning.lock"),
        },
        "browser_agent": agent_status(ROOT),
        "memory": memory.status(),
        "agent_evolution": AgentEvolution(ROOT).status(),
        "reasoning_backend": backend_status(),
        "open_source_learning": learning_status(ROOT),
        "independence": "No cross-engine memory, browser context, research files or SQLite database.",
        "learning_limit": "Evidence-based software learning; no neural weights are trained or changed.",
        "youtube_research": {"available": True, "mode": "public metadata/captions only; no video/audio download"}
    }

def main():
    ap=argparse.ArgumentParser(description=f"ASTRA {ENGINE.upper()} independent learning agent")
    sub=ap.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    rp=sub.add_parser("research"); rp.add_argument("query"); rp.add_argument("--pages",type=int,default=8)
    lp=sub.add_parser("learn"); lp.add_argument("--cycles",type=int,default=1); lp.add_argument("--interval",type=int,default=3600); lp.add_argument("--continuous",action="store_true"); lp.add_argument("--youtube",action="store_true")
    yp=sub.add_parser("youtube"); yp.add_argument("query"); yp.add_argument("--limit",type=int,default=5)
    fp=sub.add_parser("feedback"); fp.add_argument("--category",required=True); fp.add_argument("--issue",required=True); fp.add_argument("--severity",choices=["low","medium","high","critical"],default="medium")
    args=ap.parse_args()
    if args.command=="status":
        result=status()
    elif args.command=="research":
        result=browser_research(args.query,ROOT,max_pages=args.pages,engine=ENGINE)
    elif args.command=="youtube":
        result=research_youtube(args.query,ROOT,limit=args.limit)
    elif args.command=="feedback":
        memory=IntelligenceMemory(ROOT); memory.feedback(args.category,args.issue,args.severity)
        result={"engine":ENGINE,"feedback_saved":True,"agent_evolution":AgentEvolution(ROOT).status()}
    else:
        result=autopilot(ROOT,ENGINE,cycles=None if args.continuous else args.cycles,interval_seconds=args.interval,youtube=args.youtube)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
