"""Read-only health monitor for this engine only."""
from pathlib import Path
import importlib.util, json, os, shutil, time

def health_report(root, config):
    root=Path(root); checks=[]
    required=["app.py","browser_agent.py","hindi_core.py","tts_engine.py","dialogue_renderer.py","error_memory.py"]
    for name in required:
        ok=(root/name).is_file(); checks.append({"check":f"file:{name}","ok":ok,"detail":"present" if ok else "missing"})
    for name in ["research","knowledge_inbox","reports","memory","output"]:
        p=root/name
        try: p.mkdir(parents=True,exist_ok=True); probe=p/".health_probe"; probe.write_text("ok",encoding="utf-8"); probe.unlink(); ok=True; detail="writable"
        except Exception as e: ok=False; detail=str(e)
        checks.append({"check":f"storage:{name}","ok":ok,"detail":detail})
    adapter=config.get("adapter","unknown")
    deps={"edge":"edge_tts","piper":"piper","elevenlabs":"requests","espeak":None}
    dep=deps.get(adapter)
    if dep:
        ok=importlib.util.find_spec(dep) is not None; checks.append({"check":f"dependency:{dep}","ok":ok,"detail":"installed" if ok else "not installed"})
    if adapter=="espeak":
        exe=config.get("espeak_executable") or shutil.which("espeak-ng") or shutil.which("espeak"); checks.append({"check":"executable:espeak","ok":bool(exe),"detail":exe or "not found"})
    if adapter=="piper":
        model=config.get("piper_model",""); ok=bool(model and Path(model).is_file()); checks.append({"check":"model:piper","ok":ok,"detail":model or "model path not configured"})
    if adapter=="elevenlabs":
        key=bool(os.getenv("ELEVENLABS_API_KEY")); checks.append({"check":"credential:elevenlabs","ok":key,"detail":"available" if key else "not configured (optional paid engine)"})
    status=root/"reports"/"browser_agent_status.json"
    checks.append({"check":"browser-agent-status","ok":status.exists(),"detail":"has run" if status.exists() else "not run yet"})
    inbox=list((root/"knowledge_inbox").glob("inbox_*.json")) if (root/"knowledge_inbox").exists() else []
    checks.append({"check":"knowledge-handoff","ok":True,"detail":f"{len(inbox)} research handoff file(s) pending review"})
    result={"engine":root.name,"checked_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"checks":checks,"passed":sum(x["ok"] for x in checks),"failed":sum(not x["ok"] for x in checks),"mode":"read-only; no auto-fix or model training"}
    (root/"reports"/"system_health.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result
