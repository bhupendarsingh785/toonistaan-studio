from pathlib import Path
import numpy as np
import soundfile as sf
import pytest
from astra_audio.real_library import index_audio_library, build_production_spec
from astra_audio.story_intelligence import analyze_script_text

def _write(path: Path, seconds=0.5, sr=16000, freq=440):
    t = np.arange(int(seconds*sr), dtype=np.float32)/sr
    sf.write(path, (0.1*np.sin(2*np.pi*freq*t)).astype(np.float32), sr)

def test_real_library_indexes_actual_audio_and_preserves_source(tmp_path):
    src = tmp_path/"conch_test.wav"
    _write(src)
    before = src.read_bytes()
    result = index_audio_library(tmp_path, tmp_path/"index.json")
    assert result["asset_count"] == 1
    asset = result["assets"][0]
    assert asset["duration_seconds"] == pytest.approx(0.5, abs=0.002)
    assert asset["sha256"]
    assert asset["filename_category_hints"] == ["conch"]
    assert asset["license_status"] == "unknown_requires_verification"
    assert src.read_bytes() == before
    assert result["policy"]["semantic_audio_recognition_performed"] is False

def test_production_spec_requires_explicit_approval_and_timestamp(tmp_path):
    narration = tmp_path/"narration.wav"
    sfx = tmp_path/"conch.wav"
    _write(narration, seconds=2)
    _write(sfx, seconds=0.3, freq=700)
    library = index_audio_library(tmp_path)
    analysis = analyze_script_text("दृश्य 1: मंदिर\nSFX: शंख की आवाज़\n")
    cue = next(c for c in analysis["scenes"][0]["sound_cues"] if c["cue_type"]=="sound_event")
    asset = next(a for a in library["assets"] if a["asset_name"]=="conch.wav")
    approvals = {cue["cue_id"]: {"asset_id":asset["asset_id"],"start_seconds":0.7,"approved":True}}
    with pytest.raises(PermissionError):
        build_production_spec(analysis,library,narration,approvals)
    spec = build_production_spec(analysis,library,narration,approvals,
                                 allow_unlicensed_personal_preview=True)
    assert len(spec["tracks"]) == 2
    assert spec["tracks"][1]["start_seconds"] == pytest.approx(0.7)
    assert spec["production_manifest"]["private_preview_only"] is True
    assert spec["production_manifest"]["commercial_release_cleared"] is False

def test_production_spec_blocks_unapproved_and_missing_timestamps(tmp_path):
    narration=tmp_path/"narration.wav"; sfx=tmp_path/"conch.wav"
    _write(narration,seconds=2); _write(sfx,seconds=0.3)
    library=index_audio_library(tmp_path)
    analysis=analyze_script_text("दृश्य 1: मंदिर\nSFX: शंख की आवाज़\n")
    cue=next(c for c in analysis["scenes"][0]["sound_cues"] if c["cue_type"]=="sound_event")
    asset=next(a for a in library["assets"] if a["asset_name"]=="conch.wav")
    with pytest.raises(ValueError,match="unresolved/unapproved"):
        build_production_spec(analysis,library,narration,{})
    approvals={cue["cue_id"]:{"asset_id":asset["asset_id"],"approved":True}}
    with pytest.raises(ValueError,match="start_seconds"):
        build_production_spec(analysis,library,narration,approvals,allow_unlicensed_personal_preview=True)


def test_production_spec_requires_reason_for_explicit_omission(tmp_path):
    narration=tmp_path/"narration.wav"; _write(narration,seconds=2)
    analysis=analyze_script_text("दृश्य 1: जंगल\nSFX: पत्तों की सरसराहट\n")
    cue=next(c for c in analysis["scenes"][0]["sound_cues"] if c["cue_type"]=="sound_event")
    with pytest.raises(ValueError,match="requires a reason"):
        build_production_spec(analysis,{"schema":"astra-real-audio-library-index/v1","assets":[]},
                              narration,{cue["cue_id"]:{"approved":True,"omit":True}})


def test_one_call_production_pipeline_runs_index_to_qa(tmp_path):
    from astra_audio.real_library import produce_story_audio
    libroot=tmp_path/"library"; libroot.mkdir()
    narration=tmp_path/"narration.wav"
    sfx=libroot/"conch.wav"
    _write(narration,seconds=1.5)
    _write(sfx,seconds=0.25,freq=800)
    script=tmp_path/"story.txt"
    script.write_text("दृश्य 1: मंदिर\\nSFX: शंख की आवाज़\\n",encoding="utf-8")
    # Deterministic asset ID comes from the same SHA-256 rule as the scanner.
    import hashlib
    asset_id=hashlib.sha256(sfx.read_bytes()).hexdigest()[:20]
    analysis=analyze_script_text(script.read_text(encoding="utf-8"))
    cue=next(c for c in analysis["scenes"][0]["sound_cues"] if c["cue_type"]=="sound_event")
    approvals={cue["cue_id"]:{"approved":True,"asset_name":"conch.wav",
                               "start_seconds":0.4}}
    out=tmp_path/"rendered"
    summary=produce_story_audio(script,libroot,approvals,narration,out,
                                allow_unlicensed_personal_preview=True)
    assert summary["status"] in {"technical_qa_pass","technical_qa_review"}
    assert summary["inserted_sfx_count"] == 1
    assert summary["human_listening_certified"] is False
    assert Path(summary["outputs"]["production-mix.wav"]).is_file()
    assert Path(summary["outputs"]["qa-report.json"]).is_file()
    assert summary["commercial_release_cleared"] is False
