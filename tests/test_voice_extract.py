import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.voice_extract as ve


def test_best_window_picks_loud_part():
    sr = 24000
    quiet = np.zeros(int(3 * sr), dtype=np.float32)
    loud = 0.3 * np.sin(2 * np.pi * 180 * np.arange(int(4 * sr)) / sr).astype(np.float32)
    x = np.concatenate([quiet, loud, quiet])
    start, dur = ve.best_window(x, sr, seconds=4.0)
    assert 2.0 <= start <= 4.5 and dur == 4.0


def test_best_window_short_audio_returns_all():
    x = np.zeros(24000, dtype=np.float32)
    start, dur = ve.best_window(x, 24000, seconds=12.0)
    assert start == 0.0 and dur == 1.0


def test_transcribe_reports_reason_when_missing(monkeypatch):
    import builtins
    real = builtins.__import__
    def fake(name, *a, **k):
        if name == "faster_whisper":
            raise ImportError("no")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    text, why = ve.transcribe("x.wav")
    assert text == "" and "faster-whisper" in why
