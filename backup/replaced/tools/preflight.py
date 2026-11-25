#!/usr/bin/env python3
"""Truthful ASTRA runtime preflight. Installed != model downloaded != inference verified."""
from __future__ import annotations
import importlib.util, os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def _has(mod: str) -> bool:
    try: return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError): return False

def report() -> dict:
    checks={}
    for m in ("numpy","soundfile","torch","torchaudio","safetensors","vocos","f5_tts","TTS"):
        checks[m]=_has(m)
    checks["ffmpeg"]=bool(shutil.which("ffmpeg"))
    checks["hf_token"]=bool((os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip())
    indic_deps=all(checks[x] for x in ("torch","torchaudio","safetensors","vocos","f5_tts","soundfile"))
    xtts_deps=checks["TTS"] and checks["soundfile"]
    return {"checks":checks,
      "backends":{
        "indicf5":{"dependencies_present":indic_deps,"token_present":checks["hf_token"],"inference_verified":False,
                   "status":"preflight_pass_model_access_unverified" if indic_deps and checks["hf_token"] else "not_ready"},
        "xtts":{"dependencies_present":xtts_deps,"model_downloaded":False,"hindi_support_verified":False,
                "inference_verified":False,"status":"dependencies_present_model_and_hindi_unverified" if xtts_deps else "not_ready"}},
      "warning":"Preflight is not an inference test. Run a consented test render and listen/score it before production."}

def main() -> int:
    import json
    r=report(); print(json.dumps(r,ensure_ascii=False,indent=2))
    return 0 if any(x["dependencies_present"] for x in r["backends"].values()) else 1
if __name__=="__main__": raise SystemExit(main())
