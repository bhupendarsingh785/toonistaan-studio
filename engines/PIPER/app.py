
import argparse, json, os, sys, time
from pathlib import Path
from hindi_core import scan_file
from model_registry import scan_model_directories
from character_voice import save_profiles
from browser_research import browser_collect
from browser_agent_v08 import research as run_browser_agent, agent_status
from open_source_learning import learning_status
from system_watchdog import health_report
from error_memory import ErrorLedger
from quality_lab import blank_report, save_report
from tts_engine import render_segment
from dialogue_renderer import render_story
from audio_perception import inspect_audio
from intelligence_agent import run_cycle as intelligence_cycle, autopilot as intelligence_autopilot, IntelligenceMemory
from agent_benchmark import evaluate as benchmark_evaluate, fixture_self_test as benchmark_self_test
from agent_cognition import analyze_sources, load_sources, backend_status
from open_source_learning import load_open_source_records
from hindi_understanding import analyze_story as deep_analyze_story
from hindi_phonology import inspect_text as inspect_hindi_phonology
from prosody_intelligence import analyze_script as analyze_prosody


from cinematic_audio.tools import prepare_story as cinematic_prepare_story, plan_soundscape as cinematic_plan_soundscape, plan_actions as cinematic_plan_actions, audio_qa as cinematic_audio_qa, vocal_backends as cinematic_vocal_backends, vocal_audit as cinematic_vocal_audit, mix_story as cinematic_mix_story, index_library as cinematic_index_library, produce_story as cinematic_produce_story

BASE=Path(__file__).resolve().parent
CFG=json.loads((BASE/"config.json").read_text(encoding="utf-8"))
LEDGER=ErrorLedger(BASE/"memory"/"error_ledger.json")
def dump(path,obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
def scan(path):
    result=scan_file(path); dump(BASE/"reports"/"script_scan.json",result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
def models(paths):
    result=scan_model_directories(paths or CFG.get("model_paths",[]))
    dump(BASE/"reports"/"model_inventory.json",result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
def collect(url):
    result=browser_collect(url,CFG.get("allowed_domains") or None)
    name=str(abs(hash(url)))+".json"; dump(BASE/"research"/name,result)
    print("Saved source record:",BASE/"research"/name)
def profiles(path,overrides):
    result=scan_file(path)
    ov=json.loads(Path(overrides).read_text(encoding="utf-8")) if overrides else {}
    made=save_profiles(result,BASE/"profiles"/"characters.json",ov)
    print(f"Created {len(made)} planned profiles. Voice match remains UNVERIFIED until real audio review.")
def render(path):
    result=scan_file(path); dump(BASE/"reports"/"render_scan.json",result)
    for i,seg in enumerate(result["segments"],1):
        try:
            out=render_segment(seg["text"],BASE/"output"/f"segment_{i:04d}.wav",CFG)
            print("AUDIO_OK",out)
        except Exception as e:
            fp=LEDGER.add("TTS render failure",str(e),"Backend/model/dependency/configuration unavailable or failed",
                "Install/configure a supported backend and rerun the regression case",
                "Preflight backend, model file, credentials and output validation before batch render",
                "python app.py preflight")
            print("AUDIO_FAILED",i,str(e),"error_id",fp)
def render_story_command(path, profile_file):
    text=Path(path).read_text(encoding="utf-8")
    result=render_story(text,CFG,BASE/"output"/"story",profile_file or (BASE/"profiles"/"characters.json"))
    dump(BASE/"reports"/"story_quality_manifest.json",result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
def show_errors():
    rows=json.loads((BASE/"memory"/"error_ledger.json").read_text(encoding="utf-8"))
    print(json.dumps(rows,ensure_ascii=False,indent=2))
def resolve_error(fingerprint,evidence):
    LEDGER.close(fingerprint,evidence)
    print("Error marked FIXED_TESTED only with supplied evidence. Verify that evidence is a real regression test.")
def inspect(path):
    result=inspect_audio(path)
    dump(BASE/"reports"/"audio_inspection.json",result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
def preflight():
    issues=[]
    a=CFG["adapter"]
    if a=="piper" and (not CFG.get("piper_model") or not Path(CFG["piper_model"]).exists()):
        issues.append("Piper model path missing or file absent")
    if a=="elevenlabs" and not os.getenv("ELEVENLABS_API_KEY"):
        issues.append("ElevenLabs API key absent (paid cloud use disabled)")
    if a=="espeak" and not (CFG.get("espeak_executable") or __import__("shutil").which("espeak-ng") or __import__("shutil").which("espeak")):
        issues.append("eSpeak executable not found")
    if a=="edge":
        try: import edge_tts
        except ImportError: issues.append("edge-tts package missing")
    print(json.dumps({"engine":CFG["title"],"adapter":a,"issues":issues,
                      "ready":not issues},ensure_ascii=False,indent=2))
def new_report(run_id):
    rep=blank_report(CFG["title"],run_id)
    blockers=LEDGER.release_blockers()
    save_report(rep,BASE/"reports"/f"quality_{run_id}.json",blockers)
    print("Report created:",BASE/"reports"/f"quality_{run_id}.json","; open error blockers:",len(blockers))
def deep_analysis_command(path):
    result=deep_analyze_story(Path(path).read_text(encoding="utf-8"))
    dump(BASE/"reports"/"deep_story_analysis.json",result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
def phonology_command(path):
    result=inspect_hindi_phonology(Path(path).read_text(encoding="utf-8")); dump(BASE/"reports"/"phonology_report.json",result); print(json.dumps(result,ensure_ascii=False,indent=2))
def prosody_command(path):
    result=analyze_prosody(Path(path).read_text(encoding="utf-8")); dump(BASE/"reports"/"prosody_report.json",result); print(json.dumps(result,ensure_ascii=False,indent=2))
def intelligence_status():
    mem=IntelligenceMemory(BASE)
    print(json.dumps(mem.status(),ensure_ascii=False,indent=2))
def report_feedback(category, issue, severity):
    mem=IntelligenceMemory(BASE); mem.feedback(category,issue,severity)
    print("Feedback saved to this engine's private learning memory.")
def run_intelligence(cycles,interval,max_pages,topics):
    engine=BASE.name
    result=intelligence_autopilot(BASE,engine,cycles,interval,max_pages,topics)
    print(json.dumps(result,ensure_ascii=False,indent=2))

def _print_json(obj): print(json.dumps(obj,ensure_ascii=False,indent=2))
def cinematic_plan_cmd(path, report, catalog=None):
    _print_json(cinematic_prepare_story(path,report,catalog))
def soundscape_cmd(path, report): _print_json(cinematic_plan_soundscape(path,report))
def actions_cmd(path, report): _print_json(cinematic_plan_actions(path,report))
def audio_qa_cmd(path, report): _print_json(cinematic_audio_qa(path,report))
def vocal_backends_cmd(): _print_json(cinematic_vocal_backends())
def vocal_audit_cmd(path, report, asr, diar, token, emotion): _print_json(cinematic_vocal_audit(path,report,asr,diar,token,emotion))
def mix_story_cmd(spec, out, report, overwrite): _print_json(cinematic_mix_story(spec,out,report,overwrite))
def index_library_cmd(folder, report): _print_json(cinematic_index_library(folder,report))
def produce_story_cmd(script, library, approvals, narration, outdir, music, private_preview): _print_json(cinematic_produce_story(script,library,approvals,narration,outdir,music,private_preview))

def run_deep_research(query,max_pages,counter_rounds=2):
    """Run primary research, fetch counter-evidence in separate rounds, then re-review."""
    result=run_browser_agent(query,BASE,max_pages)
    path=result.get("research_file")
    primary_sources=load_sources(path) if path and Path(path).exists() else []
    open_sources=load_open_source_records(BASE)
    seen={x.get("sha256") for x in primary_sources}
    primary_sources.extend(x for x in open_sources if x.get("sha256") not in seen)
    first_review=analyze_sources(query,BASE.name,primary_sources,BASE/"reports"/"cognition") if primary_sources else None
    counter_runs=[]; combined=list(primary_sources)
    # The counter-round is intentionally bounded. It does not recursively spawn more research.
    followups=(first_review or {}).get("follow_up_queries",[])
    for counter_query in followups[:max(0,min(int(counter_rounds),3))]:
        try:
            counter=run_browser_agent(counter_query,BASE,max_pages=max(2,min(4,int(max_pages))))
            counter_path=counter.get("research_file")
            rows=load_sources(counter_path) if counter_path and Path(counter_path).exists() else []
            before=len(combined); known={x.get("sha256") for x in combined}
            combined.extend(x for x in rows if x.get("sha256") and x.get("sha256") not in known)
            counter_runs.append({"query":counter_query,"status":"completed" if rows else "no_evidence",
                                 "sources_collected":len(rows),"new_unique_sources":len(combined)-before,
                                 "research_file":counter_path})
        except Exception as exc:
            counter_runs.append({"query":counter_query,"status":"failed","error":f"{type(exc).__name__}: {exc}"})
    # Reconcile after counter-evidence has been gathered; no source is auto-approved.
    cognitive=analyze_sources(query,BASE.name,combined,BASE/"reports"/"cognition") if combined else first_review
    combined_file=BASE/"research"/"combined_deep_research.json"
    dump(combined_file,{"schema":"combined-counter-research/v1.2","engine":BASE.name,"query":query,
        "primary_research_file":path,"counter_research":counter_runs,"sources":combined,
        "limits":["Counter-search results are leads, not proof.","Offline debate is structured evidence triage, not semantic model reasoning.","No automatic code execution, training or production mutation."]})
    benchmark=None
    if path and Path(path).exists():
        # Benchmark the combined evidence view and final review report.
        benchmark=benchmark_evaluate(combined_file,cognitive.get("report_file") if cognitive else None)
    print(json.dumps({"browser":result,"counter_research":counter_runs,"combined_source_count":len(combined),
        "combined_research_file":str(combined_file),"cognition":cognitive,"benchmark":benchmark,
        "backend":backend_status()},ensure_ascii=False,indent=2))

def show_agent_backend():
    print(json.dumps(backend_status(),ensure_ascii=False,indent=2))

def run_agent_benchmark(research_file, cognition_file=None):
    if research_file == "__self_test__":
        print(json.dumps(benchmark_self_test(), ensure_ascii=False, indent=2)); return
    result=benchmark_evaluate(research_file, cognition_file)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def indicf5_cmd(text, profile, character, emotion, out):
    """IndicF5 (optional neural) se ek line banao.

    Model gated hai aur torch chahiye — na ho to saaf message, crash nahi.
    """
    try:
        from piper_indicf5_backend import IndicF5Backend, VoiceProfileError
    except Exception as exc:
        print(json.dumps({"ok": False, "reason": f"adapter load nahi hua: {exc}"}, ensure_ascii=False))
        return
    try:
        backend = IndicF5Backend()
        result = backend.render(text=text, profile_path=profile, character=character,
                                emotion=emotion, output_path=out)
        print(json.dumps({"ok": True, "result": str(result), "out": out}, ensure_ascii=False))
    except VoiceProfileError as exc:
        print(json.dumps({"ok": False, "stage": "profile", "reason": str(exc)}, ensure_ascii=False))
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "stage": "model", "reason": str(exc),
                          "next": "pip install -r requirements-indicf5.txt; HF par ai4bharat/IndicF5 ki terms accept karo"}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "stage": "unknown", "reason": str(exc)}, ensure_ascii=False))


def main():
    p=argparse.ArgumentParser(description=CFG["title"])
    s=p.add_subparsers(dest="cmd",required=True)
    x=s.add_parser("scan"); x.add_argument("file")
    x=s.add_parser("models"); x.add_argument("paths",nargs="*")
    x=s.add_parser("collect"); x.add_argument("url")
    x=s.add_parser("research"); x.add_argument("query"); x.add_argument("--max-pages",type=int,default=20); x.add_argument("--counter-rounds",type=int,default=2)
    x=s.add_parser("agent-benchmark"); x.add_argument("research_file",nargs="?",default="__self_test__"); x.add_argument("--cognition",default=None)
    s.add_parser("agent-status")
    s.add_parser("agent-backend")
    s.add_parser("open-source-status")
    s.add_parser("health-check")
    x=s.add_parser("profiles"); x.add_argument("file"); x.add_argument("--overrides",default="")
    x=s.add_parser("render"); x.add_argument("file")
    x=s.add_parser("new-report"); x.add_argument("--run-id",default="run-001")
    s.add_parser("preflight")
    s.add_parser("errors")
    x=s.add_parser("resolve-error"); x.add_argument("fingerprint"); x.add_argument("--evidence",required=True)
    x=s.add_parser("audio-inspect"); x.add_argument("file")
    x=s.add_parser("render-story"); x.add_argument("file"); x.add_argument("--profiles",default="")
    x=s.add_parser("deep-analyze"); x.add_argument("file")
    x=s.add_parser("intelligence-cycle"); x.add_argument("--max-pages",type=int,default=12); x.add_argument("--topics",type=int,default=3)
    x=s.add_parser("autopilot"); x.add_argument("--cycles",type=int,default=1); x.add_argument("--continuous",action="store_true"); x.add_argument("--interval",type=int,default=3600); x.add_argument("--max-pages",type=int,default=16); x.add_argument("--topics",type=int,default=4)
    x=s.add_parser("feedback"); x.add_argument("category"); x.add_argument("issue"); x.add_argument("--severity",default="medium")
    x=s.add_parser("phonology"); x.add_argument("file")
    x=s.add_parser("prosody-analyze"); x.add_argument("file")
    s.add_parser("intelligence-status")

    x=s.add_parser("story-audio-plan"); x.add_argument("file"); x.add_argument("--report",default="reports/story_audio_review_pack.json"); x.add_argument("--catalog",default=None)
    x=s.add_parser("soundscape-plan"); x.add_argument("file"); x.add_argument("--report",default="reports/soundscape_plan.json")
    x=s.add_parser("action-foley-plan"); x.add_argument("file"); x.add_argument("--report",default="reports/action_foley_plan.json")
    x=s.add_parser("audio-qa"); x.add_argument("file"); x.add_argument("--report",default="reports/audio_quality_report.json")
    s.add_parser("vocal-backends")
    x=s.add_parser("vocal-audit"); x.add_argument("file"); x.add_argument("--report",default="reports/vocal_audit.json"); x.add_argument("--asr-model",default="small"); x.add_argument("--diarization",action="store_true"); x.add_argument("--hf-token",default=None); x.add_argument("--emotion-model",default=None)
    x=s.add_parser("mix-story"); x.add_argument("--spec",required=True); x.add_argument("--out",default="output/story_mix.wav"); x.add_argument("--report",default="reports/story_mix_report.json"); x.add_argument("--overwrite",action="store_true")
    x=s.add_parser("index-audio-library"); x.add_argument("folder"); x.add_argument("--report",default="reports/audio_library_index.json")
    x=s.add_parser("produce-story"); x.add_argument("script"); x.add_argument("library"); x.add_argument("approvals"); x.add_argument("--narration",required=True); x.add_argument("--out-dir",required=True); x.add_argument("--music",default=None); x.add_argument("--private-preview",action="store_true")

    x=s.add_parser("indicf5-render"); x.add_argument("text"); x.add_argument("--profile",default="profiles/indicf5_characters.json"); x.add_argument("--character",required=True); x.add_argument("--emotion",default="neutral"); x.add_argument("--out",default="output/indicf5_out.wav")

    a=p.parse_args()
    {"scan":lambda:scan(a.file),"models":lambda:models(a.paths),"collect":lambda:collect(a.url),
     "research":lambda:run_deep_research(a.query,a.max_pages,a.counter_rounds),
     "agent-backend":show_agent_backend,"agent-benchmark":lambda:run_agent_benchmark(a.research_file,a.cognition),
     "agent-status":lambda:print(json.dumps(agent_status(BASE),ensure_ascii=False,indent=2)),
     "open-source-status":lambda:print(json.dumps(learning_status(BASE),ensure_ascii=False,indent=2)),
     "health-check":lambda:print(json.dumps(health_report(BASE,CFG),ensure_ascii=False,indent=2)),
     "profiles":lambda:profiles(a.file,a.overrides),"render":lambda:render(a.file),
     "new-report":lambda:new_report(a.run_id),"preflight":preflight,
     "errors":show_errors,"resolve-error":lambda:resolve_error(a.fingerprint,a.evidence),
     "audio-inspect":lambda:inspect(a.file),
     "render-story":lambda:render_story_command(a.file,a.profiles),
     "deep-analyze":lambda:deep_analysis_command(a.file),
     "intelligence-cycle":lambda:print(json.dumps(intelligence_cycle(BASE,BASE.name,a.max_pages,a.topics),ensure_ascii=False,indent=2)),
     "autopilot":lambda:run_intelligence(None if a.continuous else a.cycles,a.interval,a.max_pages,a.topics),
     "feedback":lambda:report_feedback(a.category,a.issue,a.severity),
     "intelligence-status":intelligence_status,"phonology":lambda:phonology_command(a.file),"prosody-analyze":lambda:prosody_command(a.file),
     "story-audio-plan":lambda:cinematic_plan_cmd(a.file,a.report,a.catalog),"soundscape-plan":lambda:soundscape_cmd(a.file,a.report),"action-foley-plan":lambda:actions_cmd(a.file,a.report),"audio-qa":lambda:audio_qa_cmd(a.file,a.report),"vocal-backends":vocal_backends_cmd,"vocal-audit":lambda:vocal_audit_cmd(a.file,a.report,a.asr_model,a.diarization,a.hf_token,a.emotion_model),"mix-story":lambda:mix_story_cmd(a.spec,a.out,a.report,a.overwrite),"index-audio-library":lambda:index_library_cmd(a.folder,a.report),"produce-story":lambda:produce_story_cmd(a.script,a.library,a.approvals,a.narration,a.out_dir,a.music,a.private_preview),
     "indicf5-render":lambda:indicf5_cmd(a.text,a.profile,a.character,a.emotion,a.out),}[a.cmd]()
if __name__=="__main__": main()
