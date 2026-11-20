#!/usr/bin/env python3
"""Browser Mesh — chaar browser agent aapas me baat karke data laate hain.

Kaam:
  1) **Baat-cheet (negotiation):** har agent apne queries deta hai; mesh duplicate
     query hata kar kaam baant deta hai (kisi ka kaam dohra nahi hota)
  2) **Parallel:** chaar agent ek saath chalte hain (threads) — waqt bachta hai
  3) **Ek hi pool:** sab sources ek jagah, URL+sha256 se duplicate hataye
  4) **Score:** kaun kitna laaya, kaun fail hua, kaunse domain mile — sab asli
  5) **Report:** mesh_run_<ts>.json (evidence + agent report + timing)

CLI:
  python tools/browser_mesh.py --topic "india general election 2024 result" --per 3
  python tools/browser_mesh.py --topic "hindi tts quality" --agents EDGE,PIPER
"""
from __future__ import annotations
import argparse, json, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import research_connect as rc

# chaar agent + unka sochne ka tareeka (query ke saath angle)
AGENTS = {
    "EDGE":        {"agent": "VAJRA",  "browser": "DRISHTI", "research": "NETRA",
                    "angle": "official/primary source pehle"},
    "ELEVENLABS":  {"agent": "ASTRA",  "browser": "KRIYA",   "research": "KARMA",
                    "angle": "quality/benchmark comparison"},
    "ESPEAK":      {"agent": "VAYU",   "browser": "PARAKH",  "research": "SATYA",
                    "angle": "limitation/counter-view (skeptic)"},
    "PIPER":       {"agent": "AGNI",   "browser": "ANVESH",  "research": "KHOJ",
                    "angle": "practical use/implementation"},
}
# Is project ka asli kaam — research inhi par hoti hai (rajniti nahi)
PROJECT_TOPICS = {
    "hindi_tts_quality": "hindi tts natural prosody quality",
    "voice_clone": "voice cloning few shot hindi XTTS quality",
    "emotion_prosody": "emotion prosody control tts pitch pace",
    "engine_compare": "piper vs espeak vs edge tts comparison quality",
    "audio_world": "cinematic ambience layering ducking sound design",
    "hindi_text": "hindi text normalization tts number pronunciation",
}

ANGLES = {
    "EDGE": ["official site", "documentation"],
    "ELEVENLABS": ["comparison benchmark", "quality review"],
    "ESPEAK": ["criticism limitation", "problems"],
    "PIPER": ["tutorial implementation", "github example"],
}


def negotiate(topic: str, agents: list[str]) -> dict[str, list[str]]:
    """Baat-cheet: har agent apne angle se query deta hai; duplicate hata do."""
    plan, seen = {}, set()
    for a in agents:
        qs = [f"{topic} {suffix}" for suffix in ANGLES.get(a, [topic])]
        mine = []
        for q in qs:
            key = q.lower().strip()
            if key in seen:
                continue
            seen.add(key)
            mine.append(q)
        plan[a] = mine
    return plan


def _run_agent(agent: str, queries: list[str], per: int) -> dict:
    t0 = time.time()
    rows, err = [], ""
    for q in queries:
        try:
            rep = rc.research(q, max_sources=per)
            for s in rep["sources"]:
                s["agent"] = agent
                s["query"] = q
                rows.append(s)
        except Exception as exc:
            err = f"{type(exc).__name__}: {str(exc)[:90]}"
    got = [r for r in rows if r.get("status") == "collected" and r.get("text")]
    return {"agent": agent, **AGENTS[agent], "queries": queries,
            "tried": len(rows), "collected": len(got),
            "seconds": round(time.time() - t0, 1), "error": err, "sources": rows}


def mesh(topic: str, agents: list[str] | None = None, per: int = 3,
         workers: int = 4) -> dict:
    agents = agents or list(AGENTS)
    plan = negotiate(topic, agents)
    t0 = time.time()
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_run_agent, a, plan[a], per): a for a in agents}
        for f in as_completed(futs):
            r = f.result()
            results[r["agent"]] = r
    # ek pool + duplicate hatao (url aur sha256 dono se)
    pool_rows, seen_url, seen_sha = [], set(), set()
    for r in results.values():
        for s in r["sources"]:
            if s.get("status") != "collected" or not s.get("text"):
                continue
            u, h = s.get("url", ""), s.get("sha256", "")
            if u in seen_url or (h and h in seen_sha):
                continue
            seen_url.add(u)
            if h:
                seen_sha.add(h)
            pool_rows.append(s)
    domains = sorted({s.get("domain") or urlparse(s.get("url", "")).hostname
                      for s in pool_rows} - {None, ""})
    report = {
        "topic": topic,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds_total": round(time.time() - t0, 1),
        "agents": {a: {k: r[k] for k in ("agent", "browser", "research", "queries",
                                         "tried", "collected", "seconds", "error")}
                   for a, r in results.items()},
        "evidence_count": len(pool_rows),
        "unique_domains": domains,
        "domain_count": len(domains),
        "evidence": pool_rows,
    }
    out_dir = ROOT / "reports" / "mesh"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"mesh_run_{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    report["report_file"] = str(out)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="chaar browser agent ka mesh")
    ap.add_argument("--topic", default="")
    ap.add_argument("--project", action="store_true", help="project ke saare topic chalao")
    ap.add_argument("--pick", default="", help="project topic ke naam (comma se)")
    ap.add_argument("--agents", default="")
    ap.add_argument("--per", type=int, default=3)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    agents = [x.strip().upper() for x in a.agents.split(",") if x.strip()] or None
    if a.project or a.pick:
        names = ([x.strip() for x in a.pick.split(",") if x.strip()] or list(PROJECT_TOPICS))
        allrep = {}
        for n in names:
            topic = PROJECT_TOPICS.get(n, n)
            r = mesh(topic, agents, a.per, a.workers)
            allrep[n] = {"topic": topic, "evidence": r["evidence_count"],
                         "domains": r["domain_count"], "seconds": r["seconds_total"],
                         "report": r["report_file"]}
            print(f"{n:18s} {r['evidence_count']:2d} evidence | {r['domain_count']:2d} domain | {r['seconds_total']:5.1f}s")
        print(json.dumps(allrep, ensure_ascii=False))
        return 0
    if not a.topic:
        print("--topic ya --project do"); return 2
    rep = mesh(a.topic, agents, a.per, a.workers)
    print(json.dumps({k: rep[k] for k in ("topic", "seconds_total", "evidence_count",
                                          "domain_count", "report_file")}, ensure_ascii=False))
    for name, r in rep["agents"].items():
        print(f"  {name:11s} {r['browser']:8s} collected={r['collected']:2d} "
              f"{r['seconds']:5.1f}s {('ERR ' + r['error']) if r['error'] else ''}")
    print("  domains:", ", ".join(rep["unique_domains"][:8]))
    return 0 if rep["evidence_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
