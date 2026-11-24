#!/usr/bin/env python3
"""ffbin.py — poore system ke liye EK jagah se ffmpeg/ffprobe.

Kai module `subprocess.run(["ffmpeg", ...])` likhte hain aur maan lete hain ki
ffmpeg PATH par hai. Har machine par nahi hota. Ye module:
  1. imageio_ffmpeg ka bundled binary dhoondta hai (ya PATH wala),
  2. /scratch/work/bin me shim bana deta hai,
  3. us folder ko PATH me sabse aage daal deta hai.

Isliye purane 80+ call sites bina chhue chalne lagte hain.
"""
from __future__ import annotations
import os
import shutil
import stat
import sys
from pathlib import Path

SHIM_DIR = Path(os.environ.get("ASTRA_BIN_DIR") or "/scratch/work/bin")
_done = False


def _bundled() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _make_shim(name: str, target: str) -> Path | None:
    try:
        SHIM_DIR.mkdir(parents=True, exist_ok=True)
        p = SHIM_DIR / name
        if p.exists() or p.is_symlink():
            try:
                if p.resolve() == Path(target).resolve():
                    return p
            except Exception:
                pass
            p.unlink()
        p.symlink_to(target)
        return p
    except Exception:
        # symlink na bane to chhoti wrapper script
        try:
            p = SHIM_DIR / name
            p.write_text('#!/bin/sh\nexec "%s" "$@"\n' % target, encoding="utf-8")
            p.chmod(p.stat().st_mode | stat.S_IEXEC)
            return p
        except Exception:
            return None


def ensure(verbose: bool = False) -> str | None:
    """ffmpeg ka raasta taiyar karo aur PATH me daal do. Ek hi baar chalta hai."""
    global _done
    if _done:
        return shutil.which("ffmpeg")
    _done = True
    ff = shutil.which("ffmpeg") or _bundled()
    if ff and not shutil.which("ffmpeg"):
        _make_shim("ffmpeg", ff)
    if SHIM_DIR.is_dir():
        paths = os.environ.get("PATH", "").split(os.pathsep)
        if str(SHIM_DIR) not in paths:
            os.environ["PATH"] = str(SHIM_DIR) + os.pathsep + os.environ.get("PATH", "")
    # ffprobe (agar mil jaye to)
    if not shutil.which("ffprobe"):
        cand = Path(str(ff)).with_name("ffprobe") if ff else None
        if cand and cand.exists():
            _make_shim("ffprobe", str(cand))
    got = shutil.which("ffmpeg")
    if verbose:
        print("ffmpeg:", got or "NAHI MILA", file=sys.stderr)
    return got


if __name__ == "__main__":
    print(ensure(verbose=True))
