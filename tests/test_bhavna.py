import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.bhavna as b


def test_detect_dukh():
    r = b.detect("मुझे बहुत तकलीफ़ हो रही है।")
    assert r["emotion"] == "dukh" and r["confidence"] >= 0.6


def test_detect_gussa_with_marks():
    r = b.detect("चुप रहो!! कुछ मत बोलो!")
    assert r["emotion"] == "gussa"


def test_detect_pyaar():
    r = b.detect("बेटा, आ जा पास।")
    assert r["emotion"] == "pyaar"


def test_neutral_when_nothing_matches():
    r = b.detect("कल सुबह दस बजे निकलेंगे।")
    assert r["emotion"] == "neutral"


def test_prosody_changes_with_emotion():
    d = b.prosody("dukh"); g = b.prosody("gussa")
    assert d["raftaar"] < 1.0 < g["raftaar"]      # dukh dheema, gussa tez
    assert g["zor"] > d["zor"]


def test_every_emotion_has_hindi_name_and_example():
    for row in b.list_all():
        assert row["hindi"] and row["misaal"] and row["arth"]


def test_show_unknown_raises():
    try:
        b.show("khushii")
        assert False
    except KeyError as exc:
        assert "aisa bhaav nahi" in str(exc)
