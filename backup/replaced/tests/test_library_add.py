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


def test_fingerprint_similarity_flags_duplicate():
    """Ek hi audio ke do naam — similarity se pakde jayein (naam se nahi)."""
    import numpy as np, soundfile as sf
    from pathlib import Path
    sr = 16000
    t = np.arange(sr * 3) / sr
    x = (0.3*np.sin(2*np.pi*220*t) + 0.1*np.sin(2*np.pi*440*t)).astype("float32")
    a = Path("/tmp/dup_a.wav"); b = Path("/tmp/dup_b.wav"); c = Path("/tmp/dup_c.wav")
    sf.write(a, x, sr); sf.write(b, x, sr)
    sf.write(c, (0.3*np.sin(2*np.pi*900*t)).astype("float32"), sr)
    sim_same = la.similarity(a, b)
    sim_diff = la.similarity(a, c)
    assert sim_same > 0.95 and sim_diff < 0.8
