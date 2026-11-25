import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.system_check as sc


def test_rows_have_shape():
    rep = sc.run_all()
    assert rep["checks"] == len(rep["rows"]) > 5
    for r in rep["rows"]:
        assert set(r) == {"check", "ok", "detail"} and isinstance(r["ok"], bool)


def test_verdict_is_honest():
    rep = sc.run_all()
    if rep["fail"] == 0:
        assert rep["verdict"] == "theek"
    else:
        assert rep["verdict"] in ("thoda kam", "dhyan do")


def test_library_check_reports_counts():
    rows = sc.check_library()
    assert rows[0]["ok"] and "sounds" in rows[0]["detail"], rows


def test_modules_all_import():
    rows = sc.check_modules()
    assert all(r["ok"] for r in rows), [r for r in rows if not r["ok"]]
