import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.llm_bridge as b


def test_status_covers_all_providers():
    names = [s.name for s in b.status()]
    assert names == b.ORDER


def test_custom_without_base_is_not_ready(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "")
    b.PROVIDERS["custom"]["base"] = ""
    states = {s.name: s for s in b.status()}
    assert states["custom"].ready is False


def test_chat_falls_back(monkeypatch):
    monkeypatch.setattr(b, "ready_providers", lambda: ["openai", "groq"])
    calls = []

    def fake_post(url, payload, key, timeout=90):
        calls.append(url)
        if url.startswith("https://api.openai.com"):   # groq ke URL me bhi "openai" aata hai
            raise RuntimeError("quota")
        return {"choices": [{"message": {"content": "namaste"}}]}

    monkeypatch.setattr(b, "_post", fake_post)
    b.PROVIDERS["openai"]["base"] = "https://api.openai.com/v1"
    b.PROVIDERS["groq"]["base"] = "https://api.groq.com/openai/v1"
    text, meta = b.chat([{"role": "user", "content": "hi"}])
    assert text == "namaste"
    assert meta["provider"] == "groq"
    assert meta["tries"][0]["ok"] is False


def test_chat_raises_when_all_fail(monkeypatch):
    monkeypatch.setattr(b, "ready_providers", lambda: ["openai"])
    monkeypatch.setattr(b, "_post", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("band")))
    try:
        b.chat([{"role": "user", "content": "hi"}])
        assert False, "raise hona chahiye tha"
    except RuntimeError as exc:
        assert "sab provider fail" in str(exc)


def test_no_provider_ready(monkeypatch):
    monkeypatch.setattr(b, "ready_providers", lambda: [])
    try:
        b.chat([{"role": "user", "content": "hi"}])
        assert False
    except RuntimeError as exc:
        assert "koi provider tayyar nahi" in str(exc)


def test_remember_writes_knowledge(monkeypatch, tmp_path):
    monkeypatch.setattr(b, "KNOWLEDGE", tmp_path)
    p = b.remember("sawaal", "jawab", "groq")
    assert p.exists() and "jawab" in p.read_text(encoding="utf-8")
