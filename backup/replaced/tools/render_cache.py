#!/usr/bin/env python3
"""Render Cache — ek hi line dobara banane par paisa aur time bachao.

Kaam: text + voice + params ka hash banao; wahi file pehle bani ho to seedha wahi do.
Faayda:
  - Sarvam ka paisa nahi katta dobara
  - piper/edge ka time nahi lagta
  - "kya ban chuka hai" ka hisaab cache.json me rehta hai

CLI:
  python tools/render_cache.py stats
  python tools/render_cache.py clear --older-than 30
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(os.environ.get("ASTRA_CACHE_DIR", ROOT / "cache" / "tts"))
INDEX = CACHE / "cache.json"


def key_for(text: str, voice: str, engine: str, params: dict | None = None) -> str:
    """Ek hi input par hamesha ek hi key."""
    payload = json.dumps({"t": (text or "").strip(), "v": voice, "e": engine,
                          "p": params or {}}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


import threading as _th
_CACHE_LOCK = _th.Lock()


def _load() -> dict:
    if INDEX.exists():
        try:
            return json.loads(INDEX.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(idx: dict) -> None:
    """Index likhna thread-safe (do render ek saath khatam ho to JSON na toote)."""
    with _CACHE_LOCK:
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = INDEX.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, INDEX)


def _usable(path: Path) -> bool:
    """Cache ki file asli kaam ki hai? (khamosh ya 0.25s se chhoti = bekaar)."""
    try:
        import subprocess
        from imageio_ffmpeg import get_ffmpeg_exe
        raw = subprocess.run([get_ffmpeg_exe(), "-v", "quiet", "-i", str(path),
                              "-f", "s16le", "-ac", "1", "-ar", "8000", "-"],
                             capture_output=True, timeout=20).stdout
        if len(raw) < 8000 * 0.25 * 2:        # 0.25 s se chhoti
            return False
        import numpy as np
        x = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
        return float(np.sqrt((x ** 2).mean())) > 0.005
    except Exception:
        return True          # naap fail ho to file par bharosa rakho


def get(key: str) -> Path | None:
    idx = _load()
    row = idx.get(key)
    if not row:
        return None
    p = Path(row["file"])
    if p.exists() and p.stat().st_size > 1000 and _usable(p):
        row["hits"] = row.get("hits", 0) + 1
        row["last_used"] = time.strftime("%Y-%m-%d %H:%M")
        idx[key] = row
        _save(idx)
        return p
    idx.pop(key, None)          # file gayab/kharab ho gayi to entry hatao
    _save(idx)
    return None


def put(key: str, src: str, meta: dict | None = None) -> Path:
    """Bani hui file cache me daalo (copy), index update."""
    CACHE.mkdir(parents=True, exist_ok=True)
    src_p = Path(src)
    dst = CACHE / f"{key}{src_p.suffix or '.wav'}"
    shutil.copy2(src_p, dst)
    idx = _load()
    idx[key] = {"file": str(dst), "bytes": dst.stat().st_size,
                "created": time.strftime("%Y-%m-%d %H:%M"), "hits": 0,
                "meta": meta or {}}
    _save(idx)
    return dst


def stats() -> dict:
    idx = _load()
    total = sum(r.get("bytes", 0) for r in idx.values())
    hits = sum(r.get("hits", 0) for r in idx.values())
    return {"entries": len(idx), "size_mb": round(total / 1048576, 2), "total_hits": hits}


def clear(older_than_days: int | None = None) -> dict:
    idx = _load()
    removed = 0
    now = time.time()
    for k, row in list(idx.items()):
        p = Path(row.get("file", ""))
        drop = False
        if older_than_days is None:
            drop = True
        else:
            try:
                drop = (now - p.stat().st_mtime) > older_than_days * 86400
            except Exception:
                drop = True
        if drop:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
            idx.pop(k, None)
            removed += 1
    _save(idx)
    return {"removed": removed, "left": len(idx)}


def main() -> int:
    ap = argparse.ArgumentParser(description="TTS render cache")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    c = sub.add_parser("clear"); c.add_argument("--older-than", type=int, default=None)
    a = ap.parse_args()
    if a.cmd == "stats":
        print(json.dumps(stats(), ensure_ascii=False, indent=2)); return 0
    print(json.dumps(clear(a.older_than), ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
