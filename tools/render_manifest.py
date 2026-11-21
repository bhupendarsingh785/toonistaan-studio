#!/usr/bin/env python3
"""Render Manifest — har render ka pura record (provenance), tri-state QA ke saath.

Nava engine ke discipline se seekha:
  • har render ka **manifest** (input ka hash, settings, output ka hash, QA)
  • QA ke teen nateeje: **PASS / FAIL / SKIPPED** (skip ka karan likha ho)
  • bina manifest ke render "complete" nahi maana jata

CLI:
  python tools/render_manifest.py --script stories/x.json --audio out.mp3 --out manifest.json
  python tools/render_manifest.py --check manifest.json
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def sha(path: str | Path, limit: int = 0) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def qa_audio(path: str) -> dict:
    """tri-state QA — PASS / FAIL / SKIPPED (karan ke saath)."""
    from tools import audio_read6 as ar
    try:
        rep = ar.read(path)
    except Exception as e:
        return {"decode": {"status": "FAIL", "why": str(e)[:80]}}
    if not rep.get("ok"):
        return {"decode": {"status": "FAIL", "why": rep.get("why", "decode fail")}}
    turns = [t for t in rep.get("turns", []) if t["f0"] > 0]
    if not turns:
        return {"decode": {"status": "PASS"},
                "speech": {"status": "SKIPPED", "why": "koi awaaz nahi mili (music/sfx only)"}}
    import numpy as np
    f0 = int(np.median([t["f0"] for t in turns]))
    std = round(float(np.median([t["f0_std"] for t in turns])), 1)
    pace = round(float(np.median([t["pace"] for t in turns])), 2)
    farq = rep["levels"]["farq_db"]
    out = {"decode": {"status": "PASS"}}
    out["f0_std"] = {"status": "PASS" if std >= 12 else "FAIL", "value": std, "min": 12}
    out["pace"] = {"status": "PASS" if 3.0 <= pace <= 4.5 else "FAIL", "value": pace, "range": [3.0, 4.5]}
    out["background"] = {"status": "PASS" if 8 <= farq <= 16 else "FAIL", "value": farq, "range": [8, 16]}
    if 88 <= f0 <= 330:
        out["f0_band"] = {"status": "PASS", "value": f0}
    else:
        out["f0_band"] = {"status": "FAIL", "value": f0, "why": "kisi bhi kirdaar ke band me nahi"}
    return out


def build(script: str, audio: str, out: str, settings: dict | None = None) -> dict:
    man = {
        "version": "1.0",
        "script": {"path": script, "sha256": sha(script)},
        "audio": {"path": audio, "sha256": sha(audio),
                  "bytes": Path(audio).stat().st_size},
        "settings": settings or {},
        "qa": qa_audio(audio),
    }
    qa = man["qa"]
    fails = [k for k, v in qa.items() if v.get("status") == "FAIL"]
    skips = [k for k, v in qa.items() if v.get("status") == "SKIPPED"]
    man["verdict"] = "FAIL" if fails else ("PASS_WITH_SKIPS" if skips else "PASS")
    man["failed_checks"] = fails
    man["skipped_checks"] = skips
    Path(out).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def check(manifest: str) -> int:
    m = json.loads(Path(manifest).read_text(encoding="utf-8"))
    ok = True
    for k in ("script", "audio"):
        p = m[k]["path"]
        if not Path(p).exists():
            print(f"MISSING {k}: {p}"); ok = False; continue
        if sha(p) != m[k]["sha256"]:
            print(f"CHANGED {k}: {p}"); ok = False
    print(json.dumps({"verdict": m.get("verdict"), "integrity": "OK" if ok else "BAD",
                      "failed": m.get("failed_checks"), "skipped": m.get("skipped_checks")},
                     ensure_ascii=False))
    return 0 if ok and m.get("verdict") != "FAIL" else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="")
    ap.add_argument("--audio", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--check", default="")
    a = ap.parse_args()
    if a.check:
        return check(a.check)
    if not (a.script and a.audio and a.out):
        ap.error("--script --audio --out chahiye (ya --check)")
    m = build(a.script, a.audio, a.out)
    print(json.dumps({"verdict": m["verdict"], "failed": m["failed_checks"],
                      "skipped": m["skipped_checks"], "manifest": a.out}, ensure_ascii=False))
    return 0 if m["verdict"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
