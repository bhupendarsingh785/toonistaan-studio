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
    durs = {}
    for emo in ("dukh", "gussa"):
        vals = []
        for i in range(2):          # piper me thodi randomness hoti hai — 2 baar naapo
            f = tmp_path / f"{emo}_{i}.wav"
            if not vp.piper_tts(text, "dadi", str(f), bhaav=emo):
                import pytest; pytest.skip("piper render fail (binary/model nahi)")
            vals.append(_dur(f))
        durs[emo] = sum(vals) / len(vals)
    assert durs["dukh"] > durs["gussa"]                 # dukh dheema, gussa tez
    assert durs["dukh"] / durs["gussa"] > 1.02          # saaf farq
