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
