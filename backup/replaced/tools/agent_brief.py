#!/usr/bin/env python3
"""agent_brief.py — chaar agent/browser ko system ka ASLI haal do.

Problem: agents ko pata hi nahi hota system me kya toota hai, kya kamzor hai.
Hal: audit + QA + gaps se ek chhota brief banao, aur usse AGENT ke sawaal banao.

  python tools/agent_brief.py            # brief banao + dikhao
  python tools/agent_brief.py --json     # sirf json

Likhta hai: knowledge/agent-brief.json
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
K = ROOT / "knowledge"
OUT = K / "agent-brief.json"


def _run(cmd, timeout=180):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return "FAIL %r" % (e,)


def _last_manifest():
    best = None
    for p in sorted(Path("/scratch/work").glob("out-*/manifest.json")):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if best is None or m.get("audio", {}).get("bytes", 0) > best[1]:
            best = (p, m.get("audio", {}).get("bytes", 0), m)
    return best[2] if best else None


def build() -> dict:
    kram = _run([sys.executable, "tools/kram.py", "jaanch"], 240)
    wire = _run([sys.executable, "tools/sutradhar.py", "wire"], 240)
    m = _last_manifest() or {}
    qa = m.get("qa", {})
    fails = m.get("failed_checks", [])

    # kamzoriyan: jo QA me fail hai + jo library me hi nahi
    gaps = []
    for name in fails:
        q = qa.get(name, {})
        gaps.append({"kaam": name, "naap": q.get("value"), "chahiye": q.get("range") or q.get("min"),
                     "kaise": "engine me theek karo, chhupao mat"})
    idx = {}
    ci = K / "audio-content-index.json"
    if ci.exists():
        idx = json.loads(ci.read_text(encoding="utf-8")).get("tags", {})
    thin = [t for t, v in idx.items() if len(v) < 6]
    if thin:
        gaps.append({"kaam": "library patli", "naap": thin, "chahiye": ">=6 clip har tag me",
                     "kaise": "loop_maker se banao ya asli recording maango"})

    brief = {
        "system": {
            "kram_theek": "SAB THEEK" in kram,
            "wire_theek": "SAB JUDA HAI" in wire,
            "modules": len(list((ROOT / "tools").rglob("*.py"))),
            "last_qa": qa,
            "qa_fail": fails,
        },
        "gaps": gaps,
        "rules": ["kuch delete nahi", "kuch bahar nahi — sab kram ke andar",
                  "naap ke bina 'behtar hua' nahi kehna", "jhoothi awaaz scene me nahi"],
    }
    OUT.write_text(json.dumps(brief, ensure_ascii=False, indent=1), encoding="utf-8")
    return brief


AGENT_TOPICS = {
    "EDGE": ["hindi tts natural prosody pace syllables per second", "natural sounding ambience synthesis"],
    "ELEVENLABS": ["speech rate natural hindi narration words per minute", "loudness background music dialogue ratio film"],
    "ESPEAK": ["piper length_scale prosody control quality", "open source tts hindi prosody improvement"],
    "PIPER": ["procedural audio synthesis realism rain river wind", "game audio ambience layering distance attenuation"],
}


def queries(brief: dict) -> dict:
    """Har agent ko uski zimmedari ka sawaal — system ki asli kamzori se juda."""
    out = {}
    for agent, topics in AGENT_TOPICS.items():
        out[agent] = list(topics)
        for g in brief.get("gaps", []):
            k = g.get("kaam", "")
            if k == "pace" and agent in ("EDGE", "ELEVENLABS"):
                out[agent].append("fix speech pace %s to natural range" % g.get("naap"))
            if k == "background" and agent in ("ELEVENLABS", "PIPER"):
                out[agent].append("dialogue to background loudness ratio %s dB standard" % g.get("naap"))
            if k == "library patli" and agent == "PIPER":
                out[agent].append("free realistic ambience sound libraries india")
    return out


def main() -> int:
    b = build()
    q = queries(b)
    if "--json" in sys.argv:
        print(json.dumps({"brief": b, "queries": q}, ensure_ascii=False, indent=1))
        return 0
    print("SYSTEM: kram=%s wire=%s | QA fail=%s" % (b["system"]["kram_theek"], b["system"]["wire_theek"], b["system"]["qa_fail"]))
    for g in b["gaps"]:
        print("  GAP:", g["kaam"], "|", g["naap"], "->", g["chahiye"])
    for a, qs in q.items():
        print("%-11s" % a, qs[:3])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
