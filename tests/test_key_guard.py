import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.key_guard as kg


def test_patterns_catch_elevenlabs_style():
    txt = 'xi-api-key: abcdef1234567890abcdef1234567890'
    assert kg.PATTERNS["elevenlabs"].search(txt)


def test_patterns_ignore_placeholder():
    assert not kg.PATTERNS["generic"].search('api_key = "YOUR_KEY_HERE"')


def test_scan_shape():
    rep = kg.scan()
    assert set(rep) >= {"leaks", "secret_files", "ok", "checked"}


def test_repo_is_clean():
    rep = kg.scan()
    assert rep["ok"], f"key leak: {rep['leaks'][:2]} / secret files: {rep['secret_files'][:2]}"
