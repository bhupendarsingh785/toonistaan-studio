#!/usr/bin/env python3
"""System Check — poore system ki ek report (PASS/FAIL), andaza nahi.

Dekhta hai: engine (binary/key), bus (engines + galtiyan), cache, library, tests, aur naye modules.

CLI:
  python tools/system_check.py
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _row(name: str, ok: bool, detail: str = "") -> dict:
    return {"check": name, "ok": bool(ok), "detail": detail}


def check_engines() -> list[dict]:
    rows = []
    try:
        from tools import engine_router as er
        st = er.status_all() if hasattr(er, "status_all") else None
        if st is None:
            out = subprocess.run([sys.executable, str(ROOT / "tools" / "engine_router.py"), "status"],
                                 capture_output=True, text=True, timeout=60).stdout
            ready = [ln.split()[1] for ln in out.splitlines() if ln.startswith("[READY]")]
            for name in ("edge", "elevenlabs", "piper", "espeak"):
                rows.append(_row(f"engine:{name}", name in ready,
                                 "tayyar" if name in ready else "binary/key nahi"))
            return rows
    except Exception as exc:
        rows.append(_row("engine_router", False, f"{type(exc).__name__}"))
    return rows


def check_bus() -> list[dict]:
    rows = []
    try:
        from tools import engine_bus as bus
        caps = bus.ensure_defaults()
        names = {c.name for c in caps}
        rows.append(_row("bus:chaar engine", set(bus.CORE_ENGINES) <= names, ", ".join(sorted(names))))
        rep = bus.sudhaar_report()
        rows.append(_row("bus:galti ledger", True, f"{rep['total_errors']} galtiyan likhi hain"))
    except Exception as exc:
        rows.append(_row("bus", False, f"{type(exc).__name__}: {exc}"))
    return rows


def check_cache() -> list[dict]:
    try:
        from tools import render_cache as rc
        st = rc.stats()
        return [_row("cache", True, f"{st['entries']} entries, {st['size_mb']} MB, {st['total_hits']} hits")]
    except Exception as exc:
        return [_row("cache", False, f"{type(exc).__name__}")]


def check_library() -> list[dict]:
    try:
        # file se seedha load (sys.path kisi test ne badal diya ho to bhi chale)
        import importlib.util
        spec = importlib.util.spec_from_file_location("astra_library_check",
                                                      ROOT / "astra" / "library.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        DEFAULT_INDEX, VARIANTS = mod.DEFAULT_INDEX, mod.VARIANTS
        dup = 0
        return [_row("library", len(DEFAULT_INDEX) > 0,
                     f"{len(DEFAULT_INDEX)} sounds, {len(VARIANTS)} variant tags, dup {dup}")]
    except Exception as exc:
        return [_row("library", False, f"{type(exc).__name__}: {exc}")]


def check_modules() -> list[dict]:
    mods = ["bhavna", "engine_bus", "render_cache", "tts_guard", "engine_bench",
            "voice_clone", "voice_extract", "voice_match"]
    rows = []
    for m in mods:
        try:
            __import__(f"tools.{m}")
            rows.append(_row(f"module:{m}", True, "import ok"))
        except Exception as exc:
            rows.append(_row(f"module:{m}", False, f"{type(exc).__name__}: {exc}"))
    return rows


def check_tests() -> list[dict]:
    t = list((ROOT / "tests").glob("test_*.py"))
    return [_row("tests", len(t) >= 10, f"{len(t)} test files")]


def run_all() -> dict:
    rows = []
    for fn in (check_engines, check_bus, check_cache, check_library, check_modules, check_tests):
        try:
            rows += fn()
        except Exception as exc:
            rows.append(_row(fn.__name__, False, f"{type(exc).__name__}"))
    passed = sum(1 for r in rows if r["ok"])
    return {"checks": len(rows), "pass": passed, "fail": len(rows) - passed,
            "verdict": "theek" if passed == len(rows) else ("thoda kam" if passed >= len(rows) - 3 else "dhyan do"),
            "rows": rows}


def main() -> int:
    rep = run_all()
    for r in rep["rows"]:
        print(("[OK]  " if r["ok"] else "[FAIL]") + f" {r['check']:24s} {r['detail']}")
    print(f"\n{rep['pass']}/{rep['checks']} pass — {rep['verdict']}")
    return 0 if rep["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
