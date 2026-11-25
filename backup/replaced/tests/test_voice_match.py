import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.voice_match as vm


def _tone(f0, dur=1.0, sr=16000, noise=0.0):
    t = np.arange(int(dur * sr)) / sr
    x = 0.3 * np.sin(2 * np.pi * f0 * t)
    if noise:
        x = x + noise * np.random.default_rng(0).normal(size=x.size)
    return x.astype(np.float32)


def test_same_pitch_high_cosine():
    a, b = _tone(200), _tone(200)
    assert abs(vm.f0_median(a) - 200) < 25
    assert vm.mfcc_cosine(a, b) > 0.95


def test_different_pitch_detected():
    a, b = _tone(120), _tone(240)
    assert vm.f0_median(a) < vm.f0_median(b)


def test_speech_ratio_between_0_and_1():
    x = np.concatenate([_tone(180, 0.5), np.zeros(8000, dtype=np.float32)])
    r = vm.speech_ratio(x)
    assert 0.0 < r < 1.0


def test_check_verdict_is_honest():
    import tempfile, soundfile as sf
    with tempfile.TemporaryDirectory() as d:
        p1, p2 = Path(d) / "a.wav", Path(d) / "b.wav"
        sf.write(p1, _tone(200), 16000)
        sf.write(p2, _tone(202), 16000)
        r = vm.check(str(p1), str(p2))
    assert r["f0_diff_percent"] < 5
    assert "warning" in r and "saboot nahi" in r["warning"]
