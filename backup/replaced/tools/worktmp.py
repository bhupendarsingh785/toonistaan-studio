#!/usr/bin/env python3
"""Work Tmp — /tmp (chhota, 64 MB) ki jagah /scratch ka bada temp.

Kyun: sandbox ka /tmp sirf 64 MB ka hai — lambi audio files bhar deti hain
(`OSError: [Errno 28] No space left on device`). Yahan /scratch par 262 GB hai.
"""
from __future__ import annotations
import os, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = Path(os.environ.get("ASTRA_TMP", ROOT / "tmp"))


def work_tmp(name: str = "work") -> Path:
    """Bada temp folder (ban jata hai agar na ho)."""
    p = BASE / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def clean(name: str = "") -> None:
    """Temp saaf karo (disk bharne se bachne ke liye)."""
    target = BASE / name if name else BASE
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)


def free_mb(path: Path | None = None) -> int:
    """Kitni jagah bachi hai (MB)."""
    t = shutil.disk_usage(str(path or BASE))
    return t.free // (1024 * 1024)
