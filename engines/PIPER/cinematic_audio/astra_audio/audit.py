from __future__ import annotations
from pathlib import Path
import hashlib, json
from .analyzer import analyze_audio
from .io import save_json_atomic

AUDIO_EXTS={".wav",".flac",".ogg",".aiff",".aif",".mp3",".m4a",".aac",".mp4"}

def sha256_file(path: str|Path) -> str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def audit_folder(folder: str|Path, report_path: str|Path|None=None) -> dict:
    folder=Path(folder)
    if not folder.exists() or not folder.is_dir():
        raise NotADirectoryError(folder)
    audio_paths = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS)
    if report_path is not None and Path(report_path).resolve() in {p.resolve() for p in audio_paths}:
        raise ValueError("Audit report path must not overwrite an audio asset")
    rows=[]
    for path in audio_paths:
        try:
            analysis=analyze_audio(path)
            rows.append({
                "file":str(path), "sha256":sha256_file(path),
                "status":"analyzed", "analysis":analysis,
                "production_readiness":"human_listening_and_license_review_required",
                "review_reasons":analysis.get("diagnostic_warnings",[])
            })
        except Exception as exc:
            rows.append({"file":str(path),"sha256":sha256_file(path),
                         "status":"error","error_type":type(exc).__name__,
                         "error":str(exc)[:500]})
    result={
        "schema":"astra-audio-batch-audit/v1",
        "folder":str(folder),
        "file_count":len(rows),
        "analyzed_count":sum(r["status"]=="analyzed" for r in rows),
        "error_count":sum(r["status"]=="error" for r in rows),
        "assets":rows,
        "policy":{
            "source_files_modified":False,
            "automatic_deletion":False,
            "semantic_classification":False,
            "recommendation":"Review warnings and listen to every asset before assigning production roles."
        }
    }
    if report_path:
        out=Path(report_path)
        save_json_atomic(out,result)
    return result
