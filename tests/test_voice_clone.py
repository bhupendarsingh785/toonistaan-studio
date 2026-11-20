import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.voice_clone as vc


def _make_wav(path, seconds=4.0, f0=180, sr=16000):
    """Asli wav banao (quality gate audio decode karta hai)."""
    import soundfile as sf
    t = np.arange(int(seconds * sr)) / sr
    x = (0.3 * np.sin(2 * np.pi * f0 * t)).astype(np.float32)
    sf.write(path, x, sr)
    return path


def test_enroll_needs_consent(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = _make_wav(tmp_path / "a.wav")
    try:
        vc.enroll("dadi", str(audio), "नमस्ते", consent=False)
        assert False, "ConsentMissing aana chahiye tha"
    except vc.ConsentMissing as exc:
        assert "Ijazat" in str(exc)


def test_enroll_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = _make_wav(tmp_path / "a.wav")
    v = vc.enroll("dadi", str(audio), " नमस्ते, मैं दादी हूँ। ", consent=True, backend="indicf5")
    assert v.consent and v.transcript == "नमस्ते, मैं दादी हूँ।"
    vs = vc.list_voices()
    assert len(vs) == 1 and vs[0].name == "dadi"
    assert (tmp_path / "voices" / "dadi" / "reference.wav").exists()


def test_enroll_rejects_empty_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = _make_wav(tmp_path / "a.wav")
    try:
        vc.enroll("x", str(audio), "   ", consent=True)
        assert False
    except ValueError as exc:
        assert "transcript" in str(exc)


def test_speak_reports_backend_and_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = _make_wav(tmp_path / "a.wav")
    vc.enroll("dadi", str(audio), "नमस्ते", consent=True, backend="indicf5")
    script = tmp_path / "s.txt"; script.write_text("पहली लाइन\nदूसरी लाइन\n", encoding="utf-8")
    monkeypatch.setattr(vc, "backend_status", lambda: [{"name": "indicf5", "ready": True, "why": ""}])
    calls = []

    def fake_render(backend, voice, text, out, emotion="neutral"):
        calls.append(text); Path(out).write_bytes(b"y" * 4000); return True

    monkeypatch.setattr(vc, "_render_line", fake_render)
    rep = vc.speak("dadi", str(script), str(tmp_path / "out"))
    assert rep["ok"] == 2 and rep["failed"] == 0
    assert rep["backend"] == "indicf5"
    assert calls == ["पहली लाइन", "दूसरी लाइन"]


def test_no_backend_means_failure_not_fake_success(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = _make_wav(tmp_path / "a.wav")
    vc.enroll("dadi", str(audio), "नमस्ते", consent=True, backend="indicf5")
    script = tmp_path / "s.txt"; script.write_text("लाइन\n", encoding="utf-8")
    monkeypatch.setattr(vc, "backend_status", lambda: [{"name": "indicf5", "ready": False, "why": ""}])
    monkeypatch.setattr(vc, "pick_backend", lambda: None)
    rep = vc.speak("dadi", str(script), str(tmp_path / "out"))
    assert rep["ok"] == 0 and rep["failed"] == 1


def test_parse_line_emotion_tag_forms():
    assert vc.parse_line("[dukh] बेटा, आ जा पास।") == ("dukh", "बेटा, आ जा पास।")
    assert vc.parse_line("दादी [gussa]: चुप रहो!") == ("gussa", "चुप रहो!")
    assert vc.parse_line("बिना भाव") == ("neutral", "बिना भाव")


def test_enroll_from_media_uses_extract(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    media = tmp_path / "clip.mp4"; media.write_bytes(b"x" * 100)
    ref = tmp_path / "voices" / "dadi" / "reference.wav"

    def fake_run(src, out_dir, seconds=12.0, do_clean=True):
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        _make_wav(ref, seconds=6.0)
        return {"reference": str(ref), "duration_sec": 6.0, "transcript": "नमस्ते मैं दादी हूँ"}

    monkeypatch.setattr("tools.voice_extract.run", fake_run)
    v = vc.enroll_from_media("dadi", str(media), consent=True, backend="indicf5")
    assert v.transcript == "नमस्ते मैं दादी हूँ"
    assert "media se nikaala" in v.note
    assert ref.exists()


def test_enroll_from_media_needs_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    media = tmp_path / "clip.mp4"; media.write_bytes(b"x")
    monkeypatch.setattr("tools.voice_extract.run",
                        lambda *a, **k: {"reference": str(tmp_path / "r.wav"), "duration_sec": 5, "transcript": ""})
    try:
        vc.enroll_from_media("x", str(media), consent=True)
        assert False
    except ValueError as exc:
        assert "transcript" in str(exc)


def test_add_reference_and_pick_by_emotion(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    a = _make_wav(tmp_path / "a.wav", f0=180)
    vc.enroll("dadi", str(a), "नमस्ते", consent=True, backend="indicf5")
    b = _make_wav(tmp_path / "b.wav", f0=190)
    v = vc.add_reference("dadi", str(b), "मैं दुखी हूँ", emotion="dukh")
    assert len(v.references) == 2
    ref_a, txt = vc.pick_reference(v, "dukh")
    assert txt == "मैं दुखी हूँ" and "ref_dukh" in ref_a
    ref_n, txt_n = vc.pick_reference(v, "gussa")     # na ho to neutral
    assert txt_n == "नमस्ते"


def test_chunk_text_splits_long_line():
    long_line = "यह एक वाक्य है। " * 20
    parts = vc.chunk_text(long_line, max_chars=100)
    assert len(parts) > 1 and all(len(p) <= 130 for p in parts)


def test_quality_gate_rejects_short_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    a = _make_wav(tmp_path / "short.wav", seconds=1.0)
    try:
        vc.enroll("x", str(a), "नमस्ते", consent=True)
        assert False
    except ValueError as exc:
        assert "chhoti" in str(exc)
