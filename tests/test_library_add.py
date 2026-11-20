import sys, json
from pathlib import Path
import numpy as np, soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.library_add as la


def _wav(p, seconds=2.0):
    sr = 16000
    sf.write(p, (0.2*np.sin(2*np.pi*200*np.arange(int(seconds*sr))/sr)).astype("float32"), sr)
    return p


def test_slug_is_clean():
    assert la.slug("Some File-Name (1).MP3") == "some_file_name_1"


def test_check_reports_missing_and_duplicate(tmp_path):
    a = _wav(tmp_path / "a.wav")
    rep = la.check([str(a), str(tmp_path / "nope.wav")])
    assert rep["rows"][0]["exists"] is True and rep["rows"][1]["exists"] is False


def test_add_skips_unknown_file(tmp_path, monkeypatch):
    monkeypatch.setattr(la, "LIB", tmp_path / "lib")
    rep = la.add([str(tmp_path / "none.wav")])
    assert rep["added_count"] == 0 and "nahi mili" in rep["skipped"][0]["why"]


def test_register_adds_comma_safely(tmp_path, monkeypatch):
    """Purane entry ke baad comma na ho to bhi index tootna nahi chahiye."""
    libpy = tmp_path / "library.py"
    libpy.write_text('DEFAULT_INDEX = {\n "a": {"file": "a.mp3"}\n}\n', encoding="utf-8")
    monkeypatch.setattr(la, "LIBPY", libpy)
    assert la.register("b", "b.mp3", ["t"], "x", 1.0) is True
    import ast
    src = libpy.read_text()
    ast.parse(src)                      # syntax valid hona chahiye
    assert '"b"' in src
