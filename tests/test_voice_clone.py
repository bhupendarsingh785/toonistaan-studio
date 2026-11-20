import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.voice_clone as vc


def test_enroll_needs_consent(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = tmp_path / "a.wav"; audio.write_bytes(b"x" * 5000)
    try:
        vc.enroll("dadi", str(audio), "नमस्ते", consent=False)
        assert False, "ConsentMissing aana chahiye tha"
    except vc.ConsentMissing as exc:
        assert "Ijazat" in str(exc)


def test_enroll_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = tmp_path / "a.wav"; audio.write_bytes(b"x" * 5000)
    v = vc.enroll("dadi", str(audio), " नमस्ते, मैं दादी हूँ। ", consent=True, backend="indicf5")
    assert v.consent and v.transcript == "नमस्ते, मैं दादी हूँ।"
    vs = vc.list_voices()
    assert len(vs) == 1 and vs[0].name == "dadi"
    assert (tmp_path / "voices" / "dadi" / "reference.wav").exists()


def test_enroll_rejects_empty_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = tmp_path / "a.wav"; audio.write_bytes(b"x")
    try:
        vc.enroll("x", str(audio), "   ", consent=True)
        assert False
    except ValueError as exc:
        assert "transcript" in str(exc)


def test_speak_reports_backend_and_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = tmp_path / "a.wav"; audio.write_bytes(b"x" * 5000)
    vc.enroll("dadi", str(audio), "नमस्ते", consent=True, backend="indicf5")
    script = tmp_path / "s.txt"; script.write_text("पहली लाइन\nदूसरी लाइन\n", encoding="utf-8")
    monkeypatch.setattr(vc, "backend_status", lambda: [{"name": "indicf5", "ready": True, "why": ""}])
    calls = []

    def fake_render(backend, voice, text, out):
        calls.append(text); Path(out).write_bytes(b"y" * 4000); return True

    monkeypatch.setattr(vc, "_render_line", fake_render)
    rep = vc.speak("dadi", str(script), str(tmp_path / "out"))
    assert rep["ok"] == 2 and rep["failed"] == 0
    assert rep["backend"] == "indicf5"
    assert calls == ["पहली लाइन", "दूसरी लाइन"]


def test_no_backend_means_failure_not_fake_success(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = tmp_path / "a.wav"; audio.write_bytes(b"x" * 5000)
    vc.enroll("dadi", str(audio), "नमस्ते", consent=True, backend="indicf5")
    script = tmp_path / "s.txt"; script.write_text("लाइन\n", encoding="utf-8")
    monkeypatch.setattr(vc, "backend_status", lambda: [{"name": "indicf5", "ready": False, "why": ""}])
    monkeypatch.setattr(vc, "pick_backend", lambda: None)
    rep = vc.speak("dadi", str(script), str(tmp_path / "out"))
    assert rep["ok"] == 0 and rep["failed"] == 1
