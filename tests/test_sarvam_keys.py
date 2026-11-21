import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.voice_provider as vp
import tools.sarvam_keys as sk


def _clean(monkeypatch, tmp_path):
    for i in range(1, 13):
        name = "SARVAM_API_KEY" if i == 1 else f"SARVAM_API_KEY_{i}"
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sk, "STATE", tmp_path / "state.json")


def test_twelve_keys_read(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    for i in range(1, 13):
        name = "SARVAM_API_KEY" if i == 1 else f"SARVAM_API_KEY_{i}"
        monkeypatch.setenv(name, f"key{i}_abcdef")
    ks = vp.sarvam_keys()
    assert len(ks) == 12 and ks[0] == "key1_abcdef"


def test_duplicate_not_repeated(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("SARVAM_API_KEY", "same")
    monkeypatch.setenv("SARVAM_API_KEY_2", "same")
    assert vp.sarvam_keys() == ["same"]


def test_quota_dead_key_goes_last(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("SARVAM_API_KEY", "aaa")
    monkeypatch.setenv("SARVAM_API_KEY_2", "bbb")
    sk.mark_quota_dead("aaa", 429)
    order = [k for _n, k in sk.order()]
    assert order[-1] == "aaa"          # cooldown wali aakhir me
    assert sk.status()["rotation_ready"] is True


def test_state_file_has_no_key_only_hash(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("SARVAM_API_KEY", "supersecretkey123")
    sk.mark_ok("supersecretkey123")
    raw = (tmp_path / "state.json").read_text(encoding="utf-8")
    assert "supersecretkey123" not in raw       # key kabhi file me nahi
    assert sk.status()["keys"][0]["uses"] == 1


def test_reset_clears(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("SARVAM_API_KEY", "x1")
    sk.mark_quota_dead("x1", 402)
    sk.reset()
    assert sk.status()["keys"][0]["status"] == "naya"
