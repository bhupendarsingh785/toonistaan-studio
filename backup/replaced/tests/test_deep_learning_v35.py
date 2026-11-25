import json
from pathlib import Path
import numpy as np
import soundfile as sf
import pytest

from tools import voice_clone as vc


def _make_ref(path: Path, seconds=3.0, amp=0.1):
    sr = 24000
    t = np.arange(int(sr * seconds), dtype=np.float32) / sr
    sf.write(path, amp * np.sin(2 * np.pi * 180 * t), sr)
    return path


def test_emotion_reference_requires_both_consent_and_same_speaker(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    base = _make_ref(tmp_path / "base.wav")
    vc.enroll("narrator", str(base), "यह आधार नमूना है।", consent=True, backend="indicf5")
    emotion = _make_ref(tmp_path / "sad.wav", amp=0.08)
    with pytest.raises(vc.ConsentMissing):
        vc.add_emotion_reference("narrator", "sad", str(emotion), "मैं दुखी हूँ।", False, True)
    with pytest.raises(ValueError, match="same speaker"):
        vc.add_emotion_reference("narrator", "sad", str(emotion), "मैं दुखी हूँ।", True, False)


def test_emotion_reference_saved_and_loaded(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    base = _make_ref(tmp_path / "base.wav")
    vc.enroll("narrator", str(base), "यह आधार नमूना है।", consent=True, backend="indicf5")
    emotion = _make_ref(tmp_path / "sad.wav", amp=0.08)
    result = vc.add_emotion_reference("narrator", "dukh", str(emotion), "आज मन उदास है।", True, True)
    loaded = vc.load_voice("narrator")
    assert result["emotion"] == "sad"
    assert Path(loaded.emotion_refs["sad"]["audio"]).is_file()
    assert loaded.emotion_refs["sad"]["transcript"] == "आज मन उदास है।"


def test_indicf5_uses_matching_emotion_prompt_only_when_registered(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    base = _make_ref(tmp_path / "base.wav")
    sad = _make_ref(tmp_path / "sad.wav")
    vc.enroll("narrator", str(base), "आधार transcript", consent=True, backend="indicf5")
    vc.add_emotion_reference("narrator", "sad", str(sad), "दुख वाला transcript", True, True)
    voice = vc.load_voice("narrator")
    voice.render_emotion = "dukh"
    captured = {}
    class Result:
        returncode = 0; stderr = ""; stdout = ""
    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        out = Path(cmd[cmd.index("--out") + 1])
        sf.write(out, np.ones(3000, dtype=np.float32) * 0.05, 24000)
        return Result()
    monkeypatch.setattr(vc.subprocess, "run", fake_run)
    assert vc._render_line("indicf5", voice, "मैं दुखी हूँ।", tmp_path / "out.wav")
    cmd = captured["cmd"]
    assert cmd[cmd.index("--ref-audio") + 1] == voice.emotion_refs["sad"]["audio"]
    assert cmd[cmd.index("--ref-text") + 1] == "दुख वाला transcript"


def test_xtts_does_not_claim_emotion_conditioning(monkeypatch, tmp_path):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    base = _make_ref(tmp_path / "base.wav")
    sad = _make_ref(tmp_path / "sad.wav")
    vc.enroll("narrator", str(base), "आधार", consent=True, backend="xtts")
    vc.add_emotion_reference("narrator", "sad", str(sad), "दुख", True, True)
    voice = vc.load_voice("narrator")
    voice.render_emotion = "sad"
    class FakeModel:
        def tts_to_file(self, **kwargs):
            assert kwargs["speaker_wav"] == voice.audio
            sf.write(kwargs["file_path"], np.ones(3000, dtype=np.float32)*.05, 24000)
    monkeypatch.setattr(vc, "_get_xtts_model", lambda device: FakeModel())
    assert vc._render_line("xtts", voice, "मैं दुखी हूँ।", tmp_path / "xtts.wav")


def test_ecapa_module_exposes_unavailable_without_speechbrain():
    from tools.speaker_verification import MODEL_ID
    assert MODEL_ID == "speechbrain/spkrec-ecapa-voxceleb"


def test_speaker_similarity_has_no_default_identity_decision(tmp_path, monkeypatch):
    import pytest
    torch = pytest.importorskip("torch")   # torch na ho to test skip (fail nahi)
    from tools import speaker_verification as sv
    ref = _make_ref(tmp_path / "ref.wav")
    cand = _make_ref(tmp_path / "cand.wav", amp=0.08)
    class FakeModel:
        def encode_batch(self, x):
            return torch.tensor([[[1.0, 0.0, 0.0]]], dtype=torch.float32)
    monkeypatch.setattr(sv, "_load_model", lambda **kwargs: FakeModel())
    result = sv.cosine_similarity(ref, cand)
    assert result["cosine_similarity"] == 1.0
    assert result["decision"] is None
    assert "not calibrated" in result["model_domain"]


def test_emotion_reference_change_invalidates_voice_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    base = _make_ref(tmp_path / "base.wav")
    vc.enroll("narrator", str(base), "आधार नमूना", consent=True, backend="indicf5")
    voice = vc.load_voice("narrator")
    before = vc._voice_fingerprint(voice)
    emotion = _make_ref(tmp_path / "sad.wav", amp=0.07)
    vc.add_emotion_reference("narrator", "sad", str(emotion), "दुख का नमूना", True, True)
    after = vc._voice_fingerprint(vc.load_voice("narrator"))
    assert before != after


def test_emotion_reference_path_escape_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    base = _make_ref(tmp_path / "base.wav")
    vc.enroll("narrator", str(base), "आधार नमूना", consent=True, backend="indicf5")
    voice = vc.load_voice("narrator")
    voice.emotion_refs = {"sad": {"audio": str(base), "transcript": "गलत"}}
    with pytest.raises(ValueError, match="escapes"):
        vc._voice_fingerprint(voice)


def test_base_voice_reference_path_escape_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    base = _make_ref(tmp_path / "base.wav")
    vc.enroll("narrator", str(base), "आधार नमूना", consent=True, backend="indicf5")
    voice = vc.load_voice("narrator")
    voice.audio = str(base)
    with pytest.raises(ValueError, match="Base voice reference"):
        vc._voice_fingerprint(voice)
