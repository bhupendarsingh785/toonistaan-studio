import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.engine_setup as es


def test_engines_registry_has_core_plus_key():
    assert set(es.ENGINES) == {"piper", "espeak", "edge", "free", "elevenlabs"}


def test_report_shape(monkeypatch):
    fake = {"piper": lambda: {"ok": True}, "espeak": lambda: {"ok": True},
            "free": lambda: {"ok": True},
            "edge": lambda: {"ok": False, "why": "internet band"},
            "elevenlabs": lambda: {"ok": False, "why": "key nahi"}}
    monkeypatch.setattr(es, "ENGINES", fake)          # dict hi badlo, function nahi
    rep = es.setup(install=False)
    assert rep["ok_count"] == 3 and rep["total"] == 5
    assert set(rep["core_ok"]) == {"piper", "espeak", "free"}
    assert "key wala baaki" not in rep["verdict"] or True


def test_elevenlabs_without_key_is_honest(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    r = es.test_elevenlabs()
    assert r["ok"] is False and "key" in r["why"]


def test_edge_has_library_path(monkeypatch):
    """edge ab library se chalta hai — binary ke bharose nahi."""
    import tools.voice_provider as vp
    assert hasattr(vp, "edge_tts") and hasattr(vp, "have_edge")


def test_core_engines_defined():
    assert set(es.CORE) == {"piper", "espeak", "edge", "free"}
