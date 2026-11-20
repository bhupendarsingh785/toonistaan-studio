import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.script_pipeline import prepare_script

def test_long_line_split_keeps_order_and_emotion():
    text = "[dukh] " + ("यह एक लंबा वाक्य है। " * 45)
    rows = prepare_script(text, max_chars=100)
    assert len(rows) > 1
    assert all(r["emotion"] == "dukh" for r in rows)
    assert [r["sequence"] for r in rows] == list(range(1, len(rows)+1))
    assert all(len(r["text"]) <= 100 for r in rows)

def test_speaker_and_emotion_tags():
    rows = prepare_script("[gussa] दादी: तुम यहाँ क्यों आए?\n[whisper] धीरे बोलो।")
    assert rows[0]["speaker"] == "दादी"
    assert rows[0]["emotion"] == "gussa"
    assert rows[1]["emotion"] == "whisper"

def test_blank_and_comment_lines_ignored():
    assert prepare_script("# comment\n\n   ") == []

def test_minimum_chunk_size_guard():
    try:
        prepare_script("test", max_chars=10)
        assert False
    except ValueError:
        pass
