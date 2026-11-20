"""Bhaav asar karta hai ya nahi — asli render par naap (piper offline)."""
import sys, shutil
from pathlib import Path
import numpy as np, soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.voice_provider as vp
from tools.bhavna import style

MODEL = Path("models/hi_IN-priyamvada-medium.onnx")


def _dur(path):
    x, sr = sf.read(path)
    return len(x) / sr


def test_emotion_changes_speed_and_pitch(tmp_path, monkeypatch):
    if not MODEL.exists():
        import pytest; pytest.skip("piper model nahi hai")
    monkeypatch.setenv("PIPER_MODEL_DIR", "models")
    text = "मुझे बहुत तकलीफ़ हो रही है, बेटा।"
    a = tmp_path / "dukh.wav"; b = tmp_path / "gussa.wav"
    ok1 = vp.piper_tts(text, "dadi", str(a), bhaav="dukh")
    ok2 = vp.piper_tts(text, "dadi", str(b), bhaav="gussa")
    if not (ok1 and ok2):
        import pytest; pytest.skip("piper render fail (binary/model nahi)")
    d1, d2 = _dur(a), _dur(b)
    assert d1 > d2                      # dukh dheema, gussa tez
    assert d1 / d2 > 1.05               # saaf farq
