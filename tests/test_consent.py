import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.consent import record_consent, revoke_consent, assert_consent_active

def test_consent_record_and_revoke_blocks_use(tmp_path):
    record_consent(tmp_path, "speaker")
    assert_consent_active(tmp_path)
    revoke_consent(tmp_path)
    try:
        assert_consent_active(tmp_path)
        assert False
    except PermissionError:
        pass

def test_missing_consent_fails_closed(tmp_path):
    try:
        assert_consent_active(tmp_path)
        assert False, 'missing record must block'
    except PermissionError:
        pass

def test_corrupt_consent_fails_closed(tmp_path):
    (tmp_path / 'consent_record.json').write_text('{broken', encoding='utf-8')
    try:
        assert_consent_active(tmp_path)
        assert False, 'corrupt record must block'
    except PermissionError:
        pass

def test_wrong_scope_fails_closed(tmp_path):
    record_consent(tmp_path, 'speaker', consent_scope='demo_only')
    try:
        assert_consent_active(tmp_path)
        assert False, 'wrong scope must block'
    except PermissionError:
        pass
