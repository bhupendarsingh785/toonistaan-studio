#!/usr/bin/env python3
"""
ASTRA — QA gate (v0.11.0 ka technical quality check, safe wrapper).

Kya karta hai:
  - banayi hui mp3/wav ko naap-ta hai: sample peak, true peak (4x), RMS,
    DC offset, chuppi, full-scale samples, stereo balance.
  - report likhta hai: <audio>.qa.json
  - PASS / REVIEW / FAIL batata hai.

Niyam: ye KABHI audio ko badalta nahi (non-destructive) aur fail ho jaye to
render nahi rukta (fail-open).

Chalao:
  python3 astra/qa_gate.py kahani.mp3
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _ensure_ffmpeg():
    """astra_audio ko 'ffmpeg' naam ki binary chahiye — imageio wali ka naam alag hota hai."""
    if shutil.which("ffmpeg"):
        return True
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return False
    bindir = os.path.join(ROOT, ".bin")
    try:
        os.makedirs(bindir, exist_ok=True)
        link = os.path.join(bindir, "ffmpeg")
        if not os.path.exists(link):
            os.symlink(exe, link)
        os.environ["PATH"] = bindir + os.pathsep + os.environ.get("PATH", "")
        return True
    except Exception:
        return False


def run_qa(audio_path, report_path=None, peak_limit=-1.0, true_peak_limit=-1.0, max_dc=-50.0):
    """Return dict with status + report path. Never raises."""
    out = {"ok": False, "status": "SKIPPED", "report": None, "reason": ""}
    try:
        if not os.path.exists(audio_path):
            out["reason"] = "file nahi mili"
            return out
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        _ensure_ffmpeg()
        from astra_audio.quality_check import quality_check
        rep = report_path or (audio_path + ".qa.json")
        result = quality_check(audio_path, rep, peak_limit, true_peak_limit, max_dc)
        out.update({
            "ok": True,
            "status": result.get("status", "REVIEW"),
            "report": rep,
            "sample_peak_dbfs": result.get("sample_peak_dbfs"),
            "true_peak_dbtp": result.get("estimated_true_peak_dbtp"),
            "warnings": result.get("warnings", []),
        })
    except Exception as e:
        out["reason"] = str(e)[:160]
    return out


def main():
    if len(sys.argv) < 2:
        print("usage: qa_gate.py <audio file>")
        return 1
    r = run_qa(sys.argv[1])
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
