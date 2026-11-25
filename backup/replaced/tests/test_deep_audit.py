import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.deep_audit as da
import tools.voice_provider as vp
import tools.render_cache as rc
import tools.engine_router as er


def test_clean_text_strips_control_chars():
    assert vp.clean_text("\x00\x01abc\x02") == "abc"
    assert vp.clean_text("a   b") == "a b"
    assert "\n" in vp.clean_text("line1\nline2")


def test_cache_key_ignores_output_path():
    a = rc.key_for("नमस्ते", "dadi", "espeak", {"bhaav": "neutral"})
    b = rc.key_for("नमस्ते", "dadi", "espeak", {"bhaav": "neutral"})
    assert a == b


def test_cache_hit_copies_to_requested_path(tmp_path):
    import numpy as np, soundfile as sf
    sr = 16000
    tone = (0.3 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)).astype("float32")
    src = tmp_path / "tone.wav"
    sf.write(src, tone, sr)
    key = rc.key_for("text", "dadi", "espeak", {"bhaav": "neutral"})
    rc.put(key, str(src))
    want = tmp_path / "wanted.wav"
    from tools import tts_guard as tg
    got, meta = tg.render("espeak", "dadi", "text", {"bhaav": "neutral"},
                          lambda dst: None, want=str(want))
    assert want.exists() and meta.get("cached") is True


def test_audit_tests_registry():
    assert hasattr(da, "t_fuzz") and hasattr(da, "t_race") and hasattr(da, "t_injection")
