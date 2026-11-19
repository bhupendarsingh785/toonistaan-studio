\
"""Transparent, evidence-based evaluation of one browser research run.

This is a rubric/coverage evaluator, not an intelligence score or proof of
semantic understanding. It never marks a source as true merely because it was fetched.
"""
from __future__ import annotations
import json, re, time
from pathlib import Path
from urllib.parse import urlparse

def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def evaluate(research_path, cognition_path=None):
    started=time.perf_counter()
    research=_read(research_path)
    cognition=_read(cognition_path) if cognition_path else {}
    sources=research.get("sources",[])
    collected=[s for s in sources if s.get("status")=="collected" or s.get("text")]
    domains={s.get("domain") or urlparse(s.get("url"," ")).hostname for s in collected}
    domains.discard(None)
    primary=[s for s in collected if s.get("quality") in ("primary_or_project_source","primary","official")]
    urls=[s.get("url") for s in collected if s.get("url")]
    unique_urls=len(set(urls))
    inventory=cognition.get("evidence_inventory",[])
    source_ids={row.get("source_id") for row in inventory if row.get("source_id")}
    debate=cognition.get("debate") or {}
    skeptic=debate.get("skeptic") or {}
    judge=debate.get("decision_judge") or {}
    proposals=judge.get("proposals") or cognition.get("decisions") or []
    followups=cognition.get("follow_up_queries",[])
    # combined file me query_plan nahi hota — asli research file me hota hai.
    # Isliye pehle combined ke andar wali primary file padho.
    _src = research
    _pf = research.get("primary_research_file")
    if _pf:
        try:
            import os as _os, json as _json
            _cand = _pf if _os.path.isabs(_pf) else _os.path.join(str(root), _pf)
            if _os.path.exists(_cand):
                _src = _json.load(open(_cand, encoding="utf-8"))
        except Exception:
            _src = research
    query_plan=_src.get("query_plan") or _src.get("search_queries") or research.get("query_plan") or research.get("search_queries") or []
    blob=json.dumps(research,ensure_ascii=False)+" "+json.dumps(cognition,ensure_ascii=False)
    tests=[]
    def check(name, passed, observed, target, weight=1):
        tests.append({"id":name,"passed":bool(passed),"observed":observed,"target":target,"weight":weight})
    check("source_provenance", all(s.get("url") and s.get("sha256") for s in collected), sum(bool(s.get("url") and s.get("sha256")) for s in collected), f"all {len(collected)} collected sources have URL+SHA256",2)
    check("domain_diversity", len(domains)>=2, len(domains), ">=2 independent domains",2)
    check("primary_source_coverage", len(primary)>=1, len(primary), ">=1 primary/official source",2)
    check("duplicate_control", unique_urls==len(urls), f"{unique_urls}/{len(urls)} unique URLs", "no duplicate URLs",1)
    check("query_diversity", len(set(query_plan))>=3, len(set(query_plan)), ">=3 distinct research queries",1)
    check("counter_research", len(followups)>=2, len(followups), ">=2 explicit counter/falsification follow-ups",2)
    check("skeptic_role", bool(skeptic), bool(skeptic), "adversarial reviewer output",2)
    check("decision_gate", bool(judge.get("promotion_policy") or cognition.get("promotion_policy")), bool(judge.get("promotion_policy") or cognition.get("promotion_policy")), "explicit no-auto-promotion gate",1)
    check("actionable_acceptance", any(isinstance(x,dict) and x.get("acceptance_criteria") for x in proposals), sum(bool(x.get("acceptance_criteria")) for x in proposals if isinstance(x,dict)), ">=1 proposal with testable acceptance criteria",2)
    check("source_id_traceability", bool(source_ids) or not collected, len(source_ids), "evidence inventory has source IDs",2)
    check("limitations_disclosed", bool(research.get("limits") or research.get("quality_note") or cognition.get("warning")), bool(research.get("limits") or research.get("quality_note") or cognition.get("warning")), "limitations stated",1)
    measurable=bool(re.search(r"benchmark|WER|CER|MOS|latency|throughput|regression|evaluation",blob,re.I))
    check("benchmark_or_metric_awareness", measurable, "mentioned" if measurable else "not mentioned", "at least one measurable evaluation concept",1)
    total=sum(t["weight"] for t in tests); earned=sum(t["weight"] for t in tests if t["passed"])
    report={"schema":"browser-agent-benchmark/v1.2","evaluation_type":"transparent_rubric_not_semantic_intelligence_score",
      "research_file":str(Path(research_path)),"cognition_file":str(Path(cognition_path)) if cognition_path else None,
      "engine":research.get("engine"),"query":research.get("query"),
      "metrics":{"sources_collected":len(collected),"unique_domains":len(domains),"primary_sources":len(primary),"unique_urls":unique_urls,"query_count":len(set(query_plan)),"follow_up_query_count":len(followups)},
      "weighted_coverage":{"earned":earned,"possible":total,"percent":round(100*earned/max(1,total),1)},
      "checks":tests,"failed_checks":[t["id"] for t in tests if not t["passed"]],
      "warning":"A high score means research-process coverage only. It does not prove source truth, deep semantic reasoning, natural speech, or human-level intelligence.",
      "evaluation_seconds":round(time.perf_counter()-started,4)}
    out=Path(research_path).parent/"browser_benchmark_report.json"
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    report["report_file"]=str(out)
    return report

def fixture_self_test():
    """Offline deterministic checks of the benchmark evaluator itself."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        research={"engine":"fixture","query":"Hindi TTS","query_plan":["Hindi TTS","Hindi TTS failure","Hindi TTS benchmark"],"sources":[
          {"status":"collected","url":"https://docs.example.org/a","domain":"docs.example.org","sha256":"a"*64,"quality":"primary_or_project_source","text":"official benchmark evaluation"},
          {"status":"collected","url":"https://paper.example.net/b","domain":"paper.example.net","sha256":"b"*64,"quality":"research_index","text":"independent benchmark evaluation"}],"limits":["lexical score is not truth"]}
        cognition={"evidence_inventory":[{"source_id":"S1"},{"source_id":"S2"}],"follow_up_queries":["Hindi TTS counter evidence","Hindi TTS failure cases"],
          "debate":{"skeptic":{"challenges":["test contradiction"]},"decision_judge":{"promotion_policy":"PROPOSAL_ONLY","proposals":[{"acceptance_criteria":["run held-out tests"]}]}},"warning":"structured evidence triage"}
        rp=root/"research.json"; cp=root/"cognition.json"
        rp.write_text(json.dumps(research),encoding="utf-8"); cp.write_text(json.dumps(cognition),encoding="utf-8")
        result=evaluate(rp,cp)
        assert result["metrics"]["sources_collected"]==2
        assert result["weighted_coverage"]["percent"]==100.0
        assert not result["failed_checks"]
        return {"passed":True,"checks":len(result["checks"]),"score":result["weighted_coverage"]["percent"]}
