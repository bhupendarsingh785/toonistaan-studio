import sys, json, importlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.render_cache as rc


def test_key_is_stable_and_sensitive(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "CACHE", tmp_path / "c")
    monkeypatch.setattr(rc, "INDEX", tmp_path / "c" / "cache.json")
    a = rc.key_for("नमस्ते", "dadi", "sarvam", {"pace": 0.9})
    b = rc.key_for("  नमस्ते ", "dadi", "sarvam", {"pace": 0.9})
    c = rc.key_for("नमस्ते", "maa", "sarvam", {"pace": 0.9})
    assert a == b and a != c


def test_put_then_get_returns_file(tmp_path, monkeypatch):
    """Asli (khamosh nahi) file cache me jaati hai aur wapas milti hai."""
    import numpy as np, soundfile as sf
    rc = importlib.reload(importlib.import_module("tools.render_cache"))
    monkeypatch.setattr(rc, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(rc, "INDEX", tmp_path / "cache" / "index.json")
    sr = 16000
    tone = (0.3 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)).astype("float32")
    src = tmp_path / "tone.wav"
    sf.write(src, tone, sr)
    p = rc.put("key1", str(src))
    assert p.exists()
    got = rc.get("key1")
    assert got is not None and got.exists()


def test_get_missing_file_drops_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "CACHE", tmp_path / "c")
    monkeypatch.setattr(rc, "INDEX", tmp_path / "c" / "cache.json")
    src = tmp_path / "x.wav"; src.write_bytes(b"a" * 5000)
    k = rc.key_for("line", "dadi", "piper")
    p = rc.put(k, str(src))
    p.unlink()
    assert rc.get(k) is None
    assert rc.stats()["entries"] == 0


def test_clear_removes_everything(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "CACHE", tmp_path / "c")
    monkeypatch.setattr(rc, "INDEX", tmp_path / "c" / "cache.json")
    src = tmp_path / "x.wav"; src.write_bytes(b"a" * 5000)
    rc.put(rc.key_for("l1", "dadi", "piper"), str(src))
    out = rc.clear(None)
    assert out["removed"] == 1 and out["left"] == 0
