import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.free_api as fa


def test_chunks_respect_limit():
    text = "यह एक लंबा वाक्य है। " * 40
    parts = fa._chunks(text, 190)
    assert parts and all(len(p) <= 190 for p in parts)
    assert "".join(parts).replace(" ", "") in text.replace(" ", "")[:len("".join(parts)) + 10]


def test_style_defaults_without_key():
    st = fa._style("dukh")
    assert 0.6 <= st["pace"] <= 1.6


def test_provider_registry_has_google():
    assert "google" in fa.PROVIDERS


def test_no_words_fails_honestly():
    assert fa._has_words("नमस्ते") is True
    assert fa._has_words("।।।") is False
    assert fa._has_words("") is False
    assert fa._has_words("123 ...") is False


def test_learned_style_ignores_dry_run(tmp_path, monkeypatch):
    """Apne engine ka dry-run naap ko 'seekha hua' mat maano — sirf asli (elevenlabs)."""
    import json
    import tools.voice_provider as vp
    f = tmp_path / "learned_style.json"
    f.write_text(json.dumps({"source": "piper dry-run",
                             "style": {"dukh": {"pitch": 0.5, "pace": 2.0}}}), encoding="utf-8")
    monkeypatch.setattr(vp, "_LEARNED_CACHE", {})
    monkeypatch.setattr(vp, "_learned_style", lambda: {})
    st = vp._bhaav_style("dukh")
    assert st.get("source") == "default" and st["pace"] < 1.0
