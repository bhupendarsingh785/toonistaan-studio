import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.voice_validate as vv


def test_repo_voices_are_valid():
    rep = vv.check()
    assert rep["ok"], rep["bad"]
    assert rep["characters"] >= 20


def test_invalid_speaker_detected(tmp_path):
    p = tmp_path / "voices.json"
    p.write_text(json.dumps({"characters": {
        "dadi": {"sarvam": "anushka"},
        "maa": {"sarvam": "ritu"}}}), encoding="utf-8")
    rep = vv.check(p)
    assert not rep["ok"] and rep["bad"][0]["speaker"] == "anushka"


def test_missing_file_reports_error(tmp_path):
    rep = vv.check(tmp_path / "none.json")
    assert rep["ok"] is False and "nahi mila" in rep["error"]
