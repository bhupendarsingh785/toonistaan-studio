import sys
from pathlib import Path
import numpy as np, soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.tts_guard as g
import tools.render_cache as rc


def _wav(path, seconds=1.0, amp=0.3):
    sr = 16000
    t = np.arange(int(seconds * sr)) / sr
    sf.write(path, (amp * np.sin(2 * np.pi * 180 * t)).astype("float32"), sr)
    return path


def test_audio_ok_accepts_normal(tmp_path):
    ok, why = g.audio_ok(_wav(tmp_path / "a.wav"))
    assert ok and why == "theek"


def test_audio_ok_rejects_silence(tmp_path):
    p = tmp_path / "s.wav"
    sf.write(p, np.zeros(16000, dtype="float32"), 16000)
    ok, why = g.audio_ok(p)
    assert not ok and "awaaz" in why or "khamoshi" in why


def test_audio_ok_rejects_tiny(tmp_path):
    p = tmp_path / "t.wav"
    sf.write(p, np.zeros(800, dtype="float32"), 16000)
    ok, why = g.audio_ok(p)
    assert not ok


def test_render_uses_cache_second_time(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "CACHE", tmp_path / "c")
    monkeypatch.setattr(rc, "INDEX", tmp_path / "c" / "cache.json")
    calls = []

    def fn(out):
        calls.append(out); _wav(out, 0.8)

    out, meta = g.render("piper", "dadi", "नमस्ते", {"out": str(tmp_path / "o.wav")}, fn)
    assert meta["cached"] is False and len(calls) == 1
    out2, meta2 = g.render("piper", "dadi", "नमस्ते", {"out": str(tmp_path / "o.wav")}, fn)
    assert meta2["cached"] is True and len(calls) == 1


def test_render_retries_then_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "CACHE", tmp_path / "c")
    monkeypatch.setattr(rc, "INDEX", tmp_path / "c" / "cache.json")
    monkeypatch.setattr(g.time, "sleep", lambda *_: None)
    def fn(out):
        Path(out).write_bytes(b"x" * 2000)      # kharab audio
    try:
        g.render("sarvam", "dadi", "line", {"out": str(tmp_path / "bad.wav")}, fn)
        assert False
    except g.BadAudio as exc:
        assert "3 koshish" in str(exc)
