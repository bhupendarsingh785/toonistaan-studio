import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.engine_stress as st
import tools.voice_provider as vp
import tools.engine_router as er


def test_text_guard_blocks_nonsense():
    assert vp.has_words("नमस्ते") and not vp.has_words("।।।") and not vp.has_words("")


def test_router_rejects_before_cache(tmp_path):
    ok, log = er.render_line("।।।", "dadi", tmp_path / "x.wav", engine="piper")
    assert ok is False and "asli shabd" in log[0]["note"]


def test_cache_rejects_silent_file(tmp_path):
    import tools.render_cache as rc
    f = tmp_path / "quiet.wav"
    import wave
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 800)          # 0.05 s khamosh
    assert rc._usable(f) is False


def test_stress_result_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "_render", lambda e, t, o, b="": False)
    r = st.stress_engine("fake", tmp_path)
    assert set(r) >= {"engine", "passed", "total", "score", "tests"}
    assert r["score"] < 60                        # khaali/punct hi pass honge
    assert r["tests"]["normal"]["ok"] is False
