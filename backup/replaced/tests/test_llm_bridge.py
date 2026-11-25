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
    """v2: fallback provider apna hi model use karta hai (cross-provider model ID nahi)."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-1")
    monkeypatch.setenv("GROQ_API_KEY", "test-key-2")
    calls = []

    def fake_post(url, payload, key, timeout=90):
        calls.append((url, payload.get("model")))
        if url.startswith("https://api.openai.com"):
            raise RuntimeError("quota")
        return {"choices": [{"message": {"content": "namaste"}}]}

    monkeypatch.setattr(b, "_post", fake_post)
    text, meta = b.chat([{"role": "user", "content": "hi"}])
    assert text == "namaste"
    assert meta["provider"] == "groq"
    # groq ke liye uska apna model gaya, openai ka nahi
    groq_model = b.PROVIDERS["groq"]["model"]
    assert any(m == groq_model for _, m in calls)


def test_chat_raises_when_all_fail(monkeypatch):
    monkeypatch.setattr(b, "ready_providers", lambda: ["openai"])
    monkeypatch.setattr(b, "_post", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("band")))
    try:
        b.chat([{"role": "user", "content": "hi"}])
        assert False, "raise hona chahiye tha"
    except RuntimeError as exc:
        assert "providers failed" in str(exc)


def test_no_provider_ready(monkeypatch):
    """Koi key nahi -> chat saaf error deta hai (jhootha jawab nahi)."""
    for env in ("OPENAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "TOGETHER_API_KEY", "LLM_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "")
    try:
        b.chat([{"role": "user", "content": "hi"}])
        assert False, "error aana chahiye tha"
    except RuntimeError as exc:
        assert "providers failed" in str(exc) or "koi provider" in str(exc)


def test_groq_default_model_is_not_retired():
    """Groq ne llama-3.3-70b-versatile 16 Aug 2026 ko band kar diya tha — dobara na aaye."""
    assert b.PROVIDERS["groq"]["model"] != "llama-3.3-70b-versatile"
    assert b.PROVIDERS["groq"]["model"] == "openai/gpt-oss-120b"


def test_remember_writes_knowledge(monkeypatch, tmp_path):
    monkeypatch.setattr(b, "KNOWLEDGE", tmp_path)
    p = b.remember("sawaal", "jawab", "groq")
    assert p.exists() and "jawab" in p.read_text(encoding="utf-8")
