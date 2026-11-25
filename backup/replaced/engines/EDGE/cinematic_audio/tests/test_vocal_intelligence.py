import json
import numpy as np
import soundfile as sf
import pytest
from pathlib import Path

from astra_audio.vocal_intelligence import (
    _attach_speakers, analyze_vocal_file, backend_status, save_vocal_report,
)
from astra_audio.vocal_dataset import build_voice_dataset_manifest


def test_attach_speakers_by_maximum_overlap():
    transcript = [{"start": 1.0, "end": 2.0, "text": "hello"}]
    turns = [
        {"start": 0.0, "end": 1.3, "speaker_id": "S0"},
        {"start": 1.3, "end": 2.5, "speaker_id": "S1"},
    ]
    _attach_speakers(transcript, turns)
    assert transcript[0]["speaker_id"] == "S1"
    assert transcript[0]["speaker_overlap_seconds"] == pytest.approx(0.7)


def test_report_never_overwrites_audio(tmp_path):
    audio = tmp_path / "a.wav"
    sf.write(audio, np.zeros(8000, dtype=np.float32), 8000)
    report = {"input": str(audio)}
    with pytest.raises(ValueError):
        save_vocal_report(report, audio)


def test_missing_audio_rejected():
    with pytest.raises(FileNotFoundError):
        analyze_vocal_file("/not/a/real/file.wav")


def test_backend_status_is_non_downloading():
    result = backend_status()
    assert result["models_downloaded_by_check"] is False
    assert "faster_whisper" in result["backends"]


def test_dataset_manifest_requires_explicit_consent(tmp_path):
    root = tmp_path / "voices"
    speaker = root / "SPEAKER_A"
    speaker.mkdir(parents=True)
    sf.write(speaker / "clip.wav", np.zeros(16000, dtype=np.float32), 16000)
    consent = tmp_path / "consent.json"
    consent.write_text(json.dumps({"SPEAKER_A": {"voice_training_consent": False}}))
    with pytest.raises(ValueError, match="No eligible audio clips"):
        build_voice_dataset_manifest(root, tmp_path / "manifest.json", consent_file=consent)


def test_dataset_manifest_indexes_consented_clips(tmp_path):
    root = tmp_path / "voices"
    speaker = root / "SPEAKER_A"
    speaker.mkdir(parents=True)
    sf.write(speaker / "clip.wav", np.zeros(32000, dtype=np.float32), 16000)
    consent = tmp_path / "consent.json"
    consent.write_text(json.dumps({"SPEAKER_A": {"voice_training_consent": True,
                                                    "consent_reference": "signed-1"}}))
    out = tmp_path / "manifest.json"
    result = build_voice_dataset_manifest(root, out, consent_file=consent)
    assert result["clip_count"] == 1
    assert result["training_executed"] is False
    assert json.loads(out.read_text())["speaker_count"] == 1
