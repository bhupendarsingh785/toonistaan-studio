import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.voice_provider as vp


def test_multiple_keys_rotation(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "key_one_123")
    monkeypatch.setenv("SARVAM_API_KEY_2", "key_two_456")
    ks = vp.sarvam_keys()
    assert ks == ["key_one_123", "key_two_456"]
    assert vp.sarvam_key() == "key_one_123"


def test_duplicate_keys_are_not_repeated(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "same_key")
    monkeypatch.setenv("SARVAM_API_KEY_2", "same_key")
    assert vp.sarvam_keys() == ["same_key"]


def test_no_keys_returns_empty(monkeypatch):
    for n in ("SARVAM_API_KEY", "SARVAM_API_KEY_2", "SARVAM_API_KEY_3", "SARVAM_API_KEY_4"):
        monkeypatch.delenv(n, raising=False)
    assert vp.sarvam_keys() == [] and vp.sarvam_key() == ""
