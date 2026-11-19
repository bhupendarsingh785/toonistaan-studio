"""Per-engine cinematic story audio and deep vocal QA adapters."""
from pathlib import Path
import json

def prepare_story(script_path, out_path, catalog=None):
 from .astra_audio.story_production import prepare_story_audio_file
 return prepare_story_audio_file(script_path,out_path,catalog)

def plan_soundscape(script_path,out_path):
 from .astra_audio.soundscape_planner import plan_soundscape_file
 return plan_soundscape_file(script_path,out_path)

def plan_actions(script_path,out_path):
 from .astra_audio.action_foley import analyze_action_chains
 from .astra_audio.io import save_json_atomic
 p=Path(script_path); result=analyze_action_chains(p.read_text(encoding='utf-8-sig'),p.name); save_json_atomic(out_path,result); return result

def audio_qa(audio_path,out_path):
 from .astra_audio.quality_check import quality_check
 return quality_check(audio_path,out_path)

def vocal_backends():
 from .astra_audio.vocal_intelligence import backend_status
 return backend_status()

def vocal_audit(audio_path,out_path,asr_model='small',diarization=False,hf_token=None,emotion_model=None):
 from .astra_audio.vocal_intelligence import analyze_vocal_file,save_vocal_report
 report=analyze_vocal_file(audio_path,asr_model=asr_model,language='hi',device='cpu',compute_type='int8',diarization=diarization,hf_token=hf_token,emotion_model=emotion_model)
 save_vocal_report(report,out_path);return report

def mix_story(spec_path,out_path,report_path=None,overwrite=False):
 from .astra_audio.story_mix import mix_story as _mix
 return _mix(spec_path,out_path,report_path,overwrite)

def index_library(folder,out_path):
 from .astra_audio.real_library import index_audio_library
 return index_audio_library(folder,out_path)

def produce_story(script_path,library_root,approvals_path,narration_path,out_dir,music=None,private_preview=False):
 from .astra_audio.real_library import produce_story_audio
 approvals=json.loads(Path(approvals_path).read_text(encoding='utf-8'))
 return produce_story_audio(script_path,library_root,approvals,narration_path,out_dir,music,48000,0.25,private_preview)
