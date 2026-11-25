import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.worktmp as wt
import tools.voice_provider as vp


def test_work_tmp_is_big_disk_not_tmp():
    p = wt.work_tmp("test_worktmp")
    assert p.exists() and "/tmp" != str(p)[:4]
    assert wt.free_mb(p) > 100          # bade disk par hai


def test_espeak_render_counter_exists():
    assert isinstance(vp._ESPEAK_RENDERS, int)


def test_espeak_library_lock_is_rlock_safe():
    assert vp._ESPEAK_LOCK is not None and hasattr(vp._ESPEAK_LOCK, "acquire")


def test_piper_lock_exists():
    assert vp._PIPER_LOCK is not None
