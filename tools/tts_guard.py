#!/usr/bin/env python3
"""TTS Guard — cache + retry + quality check, ek hi jagah.

Har engine call isi se guzre to:
  - dobara bani line cache se aati hai (paisa/time bachta hai)
  - Sarvam 429/5xx par apne aap retry (backoff ke saath)
  - bani file kharab ho (khaali/NaN/bahut chhoti) to fail saaf dikhe, chup-chaap nahi

CLI:
  python tools/tts_guard.py check --file out.wav
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import render_cache as rc


class BadAudio(RuntimeError):
    pass


def audio_ok(path: str | Path, min_sec: float = 0.08, max_silence: float = 0.95) -> tuple[bool, str]:
    """Bani awaaz ki jaanch: lambai, khaali pan, NaN."""
    p = Path(path)
    if not p.exists():
        return False, "file nahi bani"
    if p.stat().st_size < 1000:
        return False, f"file bahut chhoti ({p.stat().st_size} bytes)"
    try:
        import numpy as np
        import subprocess
        from imageio_ffmpeg import get_ffmpeg_exe
        r = subprocess.run([get_ffmpeg_exe(), "-v", "quiet", "-i", str(p), "-f", "s16le",
                            "-ac", "1", "-ar", "16000", "-"], capture_output=True)
        x = np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768.0
    except Exception as exc:
        return True, f"check skip: {type(exc).__name__}"   # check na ho to render rokna nahi
    if len(x) == 0:
        return False, "audio khali hai"
    sec = len(x) / 16000
    if sec < min_sec:
        return False, f"bahut chhoti ({sec:.2f}s)"
    if not np.isfinite(x).all():
        return False, "audio me NaN/Inf hai"
    if float(np.max(np.abs(x))) < 0.005:
        return False, "awaaz hi nahi (silence)"
    w = 1600
    rms = np.array([np.sqrt((x[i:i + w] ** 2).mean()) for i in range(0, max(1, len(x) - w), w)])
    if len(rms) and float((rms < 0.005).mean()) > max_silence:
        return False, "bahut zyada khamoshi"
    return True, "theek"


def render(engine: str, voice: str, text: str, params: dict, fn,
           want: str | None = None) -> tuple[Path, dict]:
    """fn(out_path) -> None. Cache → retry → quality check.

    `want` = jahan file chahiye. Cache hit par wahan **copy** hoti hai (warna
    caller ko file milti hi nahi).
    """
    # purana tareeka: params me "out" ho to wahi manzil maano
    want = want or params.get("out")
    key_params = {k: v for k, v in (params or {}).items() if k != "out"}
    key = rc.key_for(text, voice, engine, key_params)
    hit = rc.get(key)
    if hit:
        dest = Path(want) if want else hit
        if str(dest) != str(hit):
            dest.parent.mkdir(parents=True, exist_ok=True)
            import shutil as _sh
            try:
                _sh.copy2(hit, dest)
            except _sh.SameFileError:
                pass          # ek hi file hai — kuch karne ki zaroorat nahi
        return dest, {"cached": True, "engine": engine}
    tries = 0
    last = None
    out = Path(want) if want else (rc.CACHE / f"{key}.wav")
    out.parent.mkdir(parents=True, exist_ok=True)
    while tries < 3:
        tries += 1
        try:
            fn(str(out))
            ok, why = audio_ok(out)
            if ok:
                rc.put(key, str(out), {"engine": engine, "voice": voice})
                return out, {"cached": False, "engine": engine, "tries": tries}
            last = why
        except Exception as exc:
            last = f"{type(exc).__name__}: {str(exc)[:120]}"
        time.sleep(1.2 * tries)          # backoff (429/5xx ke liye)
    raise BadAudio(f"{engine} 3 koshish ke baad bhi theek nahi: {last}")


def main() -> int:
    ap = argparse.ArgumentParser(description="TTS guard")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("--file", required=True)
    sub.add_parser("cache-stats")
    a = ap.parse_args()
    if a.cmd == "cache-stats":
        print(json.dumps(rc.stats(), ensure_ascii=False, indent=2)); return 0
    ok, why = audio_ok(a.file)
    print(json.dumps({"ok": ok, "why": why}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
