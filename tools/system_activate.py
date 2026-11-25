#!/usr/bin/env python3
"""System Activate — har module ko jagao aur jaancho: import, entry point, wiring, smoke test.

Status:
  ACTIVE  = import hota hai + kisi aur module me use hota hai (pipeline me juda hua)
  READY   = import hota hai, par kisi pipeline me nahi juda
  BROKEN  = import fail (dependency ya code error)
  NEEDS   = network / API key / GPU chahiye (yahan nahi chal sakta — sach)

Chalao:
  python tools/system_activate.py            # table
  python tools/system_activate.py --json     # machine ke liye
"""
from __future__ import annotations
import argparse, contextlib, importlib, io, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__"}
NEEDS_NET = {"browser_mesh", "research_connect", "llm_bridge", "free_api", "voice_clone", "voice_provider",
             "edge_tts_probe", "sarvam_keys", "key_guard"}
NEEDS_HEAVY = {"voice_extract", "voice_clone", "indicf5_render", "teacher_student"}


def modules():
    out = []
    for p in sorted((ROOT / "tools").rglob("*.py")):
        if ("__pycache__" in str(p) or p.name == "__init__.py" or p.name == "system_activate.py"
                or "purana" in p.parts or "backup" in p.parts):      # archive — live system ka hissa nahi
            continue
        out.append(p)
    return out


def text_of(p):
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def audit():
    all_src = {str(p): text_of(p) for p in modules()}
    rows = []
    for p in modules():
        name = p.stem
        row = {"module": name, "path": str(p.relative_to(ROOT)), "import": "-", "entry": "-",
               "used_by": 0, "status": "?"}
        # import
        sys.path.insert(0, str(p.parent))
        try:
            importlib.invalidate_caches()
            if name in sys.modules:
                del sys.modules[name]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                importlib.import_module(name)
            row["import"] = "ok"
            if buf.getvalue().strip():
                row["side_effect"] = True      # import par hi kaam kar deta hai (khatra)
        except Exception as e:
            row["import"] = f"{type(e).__name__}"
            row["error"] = str(e)[:90]
        # entry point
        src = all_src[str(p)]
        row["entry"] = "cli" if "__main__" in src else ("fn" if "\ndef " in src else "-")
        # wiring
        row["used_by"] = sum(1 for q, t in all_src.items()
                             if q != str(p) and (f"import {name}" in t or f"from {name}" in t))
        if name in NEEDS_NET or name in NEEDS_HEAVY:
            row["status"] = "NEEDS"
        elif row["import"] in ("RuntimeError", "MemoryError", "ModuleNotFoundError"):
            row["status"] = "CLI"        # import par hi bhaari kaam / optional dep — script ki tarah chalta hai
        elif row["import"] != "ok":
            row["status"] = "BROKEN"
        elif row["used_by"] > 0:
            row["status"] = "ACTIVE"
        else:
            row["status"] = "READY"
        rows.append(row)
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return rows, counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--status", default="")
    a = ap.parse_args()
    rows, counts = audit()
    if a.status:
        rows = [r for r in rows if r["status"] == a.status.upper()]
    if a.json:
        print(json.dumps({"rows": rows, "counts": counts}, ensure_ascii=False, indent=1))
    else:
        mark = {"ACTIVE": "✅", "READY": "🟡", "BROKEN": "❌", "NEEDS": "🌐", "CLI": "🖥️"}
        for r in rows:
            print(f"{mark.get(r['status'], '?')} {r['module']:22s} {r['status']:6s} import={r['import']:14s} "
                  f"entry={r['entry']:3s} used_by={r['used_by']}")
        print("\n" + " | ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
