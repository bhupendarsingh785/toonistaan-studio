import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.engine_setup as es


def test_engines_registry_has_four():
    assert set(es.ENGINES) == {"piper", "espeak", "edge", "elevenlabs"}


def test_report_shape(monkeypatch):
    monkeypatch.setattr(es, "test_piper", lambda: {"ok": True})
    monkeypatch.setattr(es, "test_espeak", lambda: {"ok": True})
    monkeypatch.setattr(es, "test_edge", lambda: {"ok": False, "why": "internet band"})
    monkeypatch.setattr(es, "test_elevenlabs", lambda: {"ok": False, "why": "key nahi"})
    rep = es.setup(install=False)
    assert rep["ok_count"] == 2 and rep["total"] == 4
    assert rep["verdict"] == "kaam chalau"


def test_elevenlabs_without_key_is_honest(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    r = es.test_elevenlabs()
    assert r["ok"] is False and "key" in r["why"]
