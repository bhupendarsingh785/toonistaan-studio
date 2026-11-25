import argparse, json
from pathlib import Path
from dataclasses import asdict
from .analyzer import analyze_audio
from .processor import process_audio, ProcessingOptions
from .library import AssetWorkspace
from .audit import audit_folder
from .io import load_audio, save_json_atomic
from .acoustic_map import build_acoustic_map
from .story_mix import mix_story
from .quality_check import quality_check
from .story_intelligence import analyze_script_file, build_reviewable_mix_spec
from .asset_matching import match_assets
from .real_library import index_audio_library, build_production_spec, produce_story_audio
from .tts_sarvam import synthesize_script

def main():
    p=argparse.ArgumentParser(prog="astra-audio",description="ASTRA standalone audio intelligence/cleanup")
    sub=p.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("analyze"); a.add_argument("input"); a.add_argument("--out",default="./audio_workspace")
    q=sub.add_parser("process"); q.add_argument("input"); q.add_argument("--out",default="./audio_workspace")
    q.add_argument("--highpass",type=float); q.add_argument("--hum",type=float,choices=[50,60])
    q.add_argument("--noise-start",type=float); q.add_argument("--noise-end",type=float)
    q.add_argument("--denoise",type=float,default=0.0); q.add_argument("--normalize",type=float)
    q.add_argument("--tags",default="")
    q.add_argument("--profile",choices=["speech","music","chant","ambience","sfx","unknown"],default="unknown")
    q.add_argument("--allow-non-speech-denoise",action="store_true",
                   help="Explicitly override the safety guard after auditioning the noise-only profile")
    q.add_argument("--overwrite",action="store_true",help="Replace an existing processed output after backing it up")
    b=sub.add_parser("audit"); b.add_argument("folder"); b.add_argument("--report",default="./audio_batch_audit.json")
    m=sub.add_parser("map"); m.add_argument("input"); m.add_argument("--report",default="./acoustic_map.json")
    qa=sub.add_parser("qa",help="Non-destructive rendered-audio quality gate")
    qa.add_argument("input"); qa.add_argument("--report",default="./audio_quality_report.json")
    qa.add_argument("--peak-limit",type=float,default=-1.0)
    qa.add_argument("--true-peak-limit",type=float,default=-1.0)
    qa.add_argument("--max-dc",type=float,default=-50.0)
    si=sub.add_parser("analyze-script",help="Create a reviewable scene/character/sound-cue plan from a text script")
    si.add_argument("input"); si.add_argument("--report",default="./story_intelligence_report.json")
    bs=sub.add_parser("build-story-spec",help="Create a review-only mix spec after script analysis")
    bs.add_argument("analysis_json"); bs.add_argument("--out",default="./story_mix_review_spec.json")
    bs.add_argument("--track",action="append",default=[],help="ROLE=PATH; repeat for each audio stem")
    bs.add_argument("--sample-rate",type=int,default=48000); bs.add_argument("--creativity",type=float,default=0.35)
    ma=sub.add_parser("match-assets",help="Rank sound-library candidates for story cues; review only")
    ma.add_argument("analysis_json"); ma.add_argument("catalog_json")
    ma.add_argument("--report",default="./asset_match_report.json")
    ma.add_argument("--min-score",type=float,default=0.18)
    ma.add_argument("--max-candidates",type=int,default=5)
    ts=sub.add_parser("tts-sarvam",help="Generate Hindi dialogue/narration clips using Sarvam Bulbul REST")
    ts.add_argument("script"); ts.add_argument("voice_map_json")
    ts.add_argument("--out-dir",required=True)
    ix=sub.add_parser("index-library",help="Scan actual audio files and build a technical asset index")
    ix.add_argument("folder"); ix.add_argument("--out",default="./audio_library_index.json")
    ix.add_argument("--non-recursive",action="store_true")
    pr=sub.add_parser("produce",help="Run the complete local production pipeline from supplied narration and approved SFX")
    pr.add_argument("script"); pr.add_argument("library_folder"); pr.add_argument("approvals_json")
    pr.add_argument("--narration",required=True); pr.add_argument("--music")
    pr.add_argument("--out-dir",required=True)
    pr.add_argument("--sample-rate",type=int,default=48000)
    pr.add_argument("--creativity",type=float,default=0.25)
    pr.add_argument("--private-preview",action="store_true",
                    help="Allow unlicensed/un-auditioned assets for private preview only; never commercial clearance")
    ps=sub.add_parser("build-production-spec",help="Build a render-ready spec from explicitly approved/timestamped SFX")
    ps.add_argument("analysis_json"); ps.add_argument("library_json"); ps.add_argument("approvals_json")
    ps.add_argument("--narration",required=True); ps.add_argument("--music")
    ps.add_argument("--out",default="./production_mix_spec.json")
    ps.add_argument("--sample-rate",type=int,default=48000)
    ps.add_argument("--creativity",type=float,default=0.25)
    ps.add_argument("--private-preview",action="store_true",
                    help="Allow unlicensed/un-auditioned assets for private preview only; never commercial clearance")
    sm=sub.add_parser("mix-story"); sm.add_argument("--spec",required=True)
    sm.add_argument("--out",default="./story_mix.wav"); sm.add_argument("--report",default="./story_mix_report.json")
    sm.add_argument("--overwrite",action="store_true",help="Replace existing output/report files; back them up first")
    args=p.parse_args()
    if args.cmd=="analyze-script":
        result=analyze_script_file(args.input,args.report)
        print(json.dumps({"scenes":result["scene_count"],"characters":len(result["characters"]),
                          "sound_event_candidates":result["summary"]["sound_event_candidate_count"],
                          "report":args.report,"review_required":True},ensure_ascii=False,indent=2))
        return
    if args.cmd=="build-story-spec":
        analysis=json.loads(Path(args.analysis_json).read_text(encoding="utf-8"))
        track_paths={}
        for item in args.track:
            if "=" not in item:
                raise ValueError("--track must be ROLE=PATH")
            role,path=item.split("=",1)
            if role in track_paths:
                raise ValueError(f"Duplicate track role: {role}")
            track_paths[role]=path
        spec=build_reviewable_mix_spec(analysis,track_paths,args.sample_rate,args.creativity)
        out=Path(args.out).resolve()
        if out == Path(args.analysis_json).resolve():
            raise ValueError("Output path must not overwrite the story analysis JSON")
        save_json_atomic(out,spec)
        print(json.dumps({"output":str(out),"tracks":len(spec["tracks"]),
                          "review_required":True,"ready_for_render":False},ensure_ascii=False,indent=2))
        return
    if args.cmd=="tts-sarvam":
        voice_map=json.loads(Path(args.voice_map_json).read_text(encoding="utf-8"))
        manifest=synthesize_script(args.script,voice_map,args.out_dir)
        print(json.dumps({"clips":manifest["clip_count"],"segments":manifest["segment_count"],
                          "output_dir":args.out_dir,"provider":manifest["provider"],
                          "model":manifest["model"],"voice_continuity":manifest["voice_continuity"]},
                         ensure_ascii=False,indent=2))
        return
    if args.cmd=="produce":
        approvals=json.loads(Path(args.approvals_json).read_text(encoding="utf-8"))
        summary=produce_story_audio(args.script,args.library_folder,approvals,args.narration,
                                    args.out_dir,args.music,args.sample_rate,args.creativity,
                                    args.private_preview)
        print(json.dumps(summary,ensure_ascii=False,indent=2))
        return
    if args.cmd=="index-library":
        report=index_audio_library(args.folder,args.out,recursive=not args.non_recursive)
        print(json.dumps({"asset_count":report["asset_count"],"error_count":report["error_count"],
                          "output":args.out,"source_files_modified":False,
                          "semantic_audio_recognition":False},ensure_ascii=False,indent=2))
        return
    if args.cmd=="build-production-spec":
        analysis=json.loads(Path(args.analysis_json).read_text(encoding="utf-8"))
        library=json.loads(Path(args.library_json).read_text(encoding="utf-8"))
        approvals=json.loads(Path(args.approvals_json).read_text(encoding="utf-8"))
        spec=build_production_spec(analysis,library,args.narration,approvals,args.music,
                                   args.sample_rate,args.creativity,args.private_preview)
        out=Path(args.out).resolve()
        protected={Path(args.analysis_json).resolve(),Path(args.library_json).resolve(),
                   Path(args.approvals_json).resolve(),Path(args.narration).resolve()}
        if args.music: protected.add(Path(args.music).resolve())
        if out in protected:
            raise ValueError("Output path must not overwrite any source, catalog, approval, or narration file")
        save_json_atomic(out,spec)
        print(json.dumps({"output":str(out),"tracks":len(spec["tracks"]),
                          "sfx_count":spec["production_manifest"]["inserted_sfx_count"],
                          "commercial_release_cleared":spec["production_manifest"]["commercial_release_cleared"],
                          "private_preview_only":spec["production_manifest"]["private_preview_only"]},
                         ensure_ascii=False,indent=2))
        return
    if args.cmd=="match-assets":
        analysis=json.loads(Path(args.analysis_json).read_text(encoding="utf-8"))
        if not isinstance(analysis,dict) or not isinstance(analysis.get("scenes"),list):
            raise ValueError("analysis_json must contain a scenes list from analyze-script")
        events=[]
        for scene in analysis["scenes"]:
            if not isinstance(scene,dict):
                continue
            for cue in scene.get("sound_cues",[]):
                if isinstance(cue,dict) and cue.get("cue_type")=="sound_event":
                    events.append({"event_id":cue.get("cue_id"),"event_type":cue.get("event"),
                                   "text":cue.get("text_excerpt",""),"scene_id":scene.get("scene_id"),
                                   "evidence":cue.get("evidence",[]),"confidence":cue.get("confidence")})
        report=match_assets(events,args.catalog_json,args.min_score,args.max_candidates)
        out=Path(args.report).resolve()
        if out in {Path(args.analysis_json).resolve(),Path(args.catalog_json).resolve()}:
            raise ValueError("Report path must not overwrite story analysis or catalog")
        save_json_atomic(out,report)
        print(json.dumps({"events":report["event_count"],"matched_events":report["matched_event_count"],
                          "report":str(out),"auto_inserted":False,"review_required":True},
                         ensure_ascii=False,indent=2))
        return
    if args.cmd=="qa":
        result=quality_check(args.input,args.report,args.peak_limit,args.true_peak_limit,args.max_dc)
        print(json.dumps({"status":result["status"],"sample_peak_dbfs":result["sample_peak_dbfs"],
                          "estimated_true_peak_dbtp":result["estimated_true_peak_dbtp"],
                          "warnings":result["warnings"],"report":args.report},ensure_ascii=False,indent=2))
        return
    if args.cmd=="mix-story":
        result=mix_story(args.spec,args.out,args.report,overwrite=args.overwrite)
        print(json.dumps({"output":result["output"],"duration_seconds":result["duration_seconds"],
                          "tracks":result["track_count"],"peak_dbfs":result["output_peak_dbfs"],
                          "report":args.report},ensure_ascii=False,indent=2))
        return
    if args.cmd=="audit":
        result=audit_folder(args.folder,args.report)
        print(json.dumps({"file_count":result["file_count"],"analyzed_count":result["analyzed_count"],
                          "error_count":result["error_count"],"report":args.report},ensure_ascii=False,indent=2))
        return
    if args.cmd=="map":
        data,sr,decoder=load_audio(args.input)
        result=build_acoustic_map(data,sr)
        result["input"]=args.input; result["decoder"]=decoder
        save_json_atomic(args.report,result)
        print(json.dumps({"frames":len(result["frames"]),"report":args.report,
                          "semantic_labels_performed":False},ensure_ascii=False,indent=2))
        return
    workspace=AssetWorkspace(args.out)
    src=Path(args.input)
    if args.cmd=="analyze":
        report=analyze_audio(src)
        report_path=workspace.root/"reports"/(src.stem+"_analysis.json")
        save_json_atomic(report_path,report)
        workspace.register(src,report=report_path)
        print(json.dumps(report,ensure_ascii=False,indent=2))
    else:
        tags=tuple(t.strip() for t in args.tags.split(",") if t.strip())
        opts=ProcessingOptions(highpass_hz=args.highpass,hum_hz=args.hum,
            noise_start_seconds=args.noise_start,noise_end_seconds=args.noise_end,
            denoise_strength=args.denoise,normalize_peak_dbfs=args.normalize,tags=tags,
            asset_profile=args.profile,allow_non_speech_denoise=args.allow_non_speech_denoise)
        out=workspace.root/"processed"/(src.stem+"_clean.wav")
        report=process_audio(src,out,opts,overwrite=args.overwrite)
        report_path=workspace.root/"reports"/(src.stem+"_report.json")
        save_json_atomic(report_path,report)
        workspace.register(src,processed=out,report=report_path,tags=tags)
        print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
