#!/usr/bin/env python3
"""Deep Audit — jo tarike abhi tak try nahi kiye (fuzz, idempotency, race, injection).

7 tarike:
  1. FUZZ        — ajeeb text (emoji, HTML, JSON, control chars, mixed script, 5000 akshar)
  2. IDEMPOTENT  — ek hi text do baar → bilkul same file (hash barabar)
  3. RACE        — 8 thread ek saath, cache/state file tootey na
  4. INJECTION   — text me shell/JSON/HTML daal kar dekho — kuch na phate
  5. IMPORT      — circular import, import time
  6. LEAK        — temp files ka dher bade to nahi ho rahe
  7. DISK        — jagah bachi hai ya nahi

CLI: python tools/deep_audit.py [--engine espeak]
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FUZZ = [
    "नमस्ते 🎉🙏 दादी",
    "<script>alert(1)</script> बेटा आ जा",
    '{"text": "hack", "drop": "table"}',
    "Line1\nLine2\r\nLine3\tTabbed",
    "हिन्दी and English mixed 123 ४५६ ₹99",
    "\x00\x01\x02 control chars",
    "।।।।।।।।",
    "   ",
    "a" * 5000,
    "😀" * 200,
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else ""


def t_fuzz(engine: str, tmp: Path) -> list[str]:
    from tools import engine_router as er
    bad = []
    for i, text in enumerate(FUZZ):
        out = tmp / f"fuzz_{i}.wav"
        try:
            ok, log = er.render_line(text, "dadi", out, engine=engine)
            note = log[-1]["note"][:60] if log else ""
        except Exception as exc:
            bad.append(f"#{i} EXC {type(exc).__name__}: {str(exc)[:50]}")
            continue
        # jahan shabd nahi, wahan False hona chahiye; jahan shabd hai wahan True
        has_word = any(c.isalpha() for c in text)
        if has_word and not ok:
            bad.append(f"#{i} shabd hai par render fail ({note})")
        if not has_word and ok:
            bad.append(f"#{i} shabd nahi par render pass")
    return bad


def t_idempotent(engine: str, tmp: Path) -> list[str]:
    from tools import engine_router as er
    a, b = tmp / "idem_a.wav", tmp / "idem_b.wav"
    text = "एक ही वाक्य, दो बार।"
    er.render_line(text, "dadi", a, engine=engine)
    for f in (a, b):
        f.unlink(missing_ok=True)
    er.render_line(text, "dadi", a, engine=engine)
    er.render_line(text, "dadi", b, engine=engine)
    if not (a.exists() and b.exists()):
        return ["cache/engine ne file hi nahi di"]
    # cache se aayi file bilkul same honi chahiye (bytes)
    if _sha(a) != _sha(b):
        return [f"same text, alag file ({_sha(a)} vs {_sha(b)}) — cache kaam nahi kar raha"]
    return []


def t_race(engine: str, tmp: Path) -> list[str]:
    from tools import engine_router as er
    import tools.sarvam_keys as sk
    bad = []

    def one(i):
        try:
            ok, _ = er.render_line("बेटा आ जा पास।", "dadi", tmp / f"race_{i}.wav", engine=engine)
            return ok
        except Exception as exc:
            return f"{type(exc).__name__}: {str(exc)[:40]}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        res = list(pool.map(one, range(8)))
    fails = [r for r in res if r is not True]
    if fails:
        bad.append(f"8 thread me {len(fails)} fail: {fails[0]}")
    # state file: ek saath likho, JSON toote na
    for i in range(10):
        sk.mark_ok(f"dummy_key_{i}")
    try:
        json.loads(sk.STATE.read_text(encoding="utf-8"))
    except Exception as exc:
        bad.append(f"state file toot gaya: {type(exc).__name__}")
    return bad


def t_injection(engine: str, tmp: Path) -> list[str]:
    from tools import engine_router as er
    bad = []
    payloads = ["$(rm -rf /)", "; ls -la", "`whoami`", "../../etc/passwd",
                "\"; drop table x; --", "%s%s%s%n"]
    for i, p in enumerate(payloads):
        try:
            out = tmp / f"inj_{i}.wav"
            er.render_line(f"बेटा {p} आ जा", "dadi", out, engine=engine)
            if not (ROOT / "astra" / "library.py").exists():
                bad.append("library.py gayab!")
        except Exception as exc:
            bad.append(f"payload {i} par crash: {type(exc).__name__}")
    return bad


def t_import() -> list[str]:
    bad = []
    mods = ["tools.voice_provider", "tools.engine_router", "tools.bhavna",
            "tools.world_scape", "tools.free_api", "tools.sarvam_keys",
            "tools.render_cache", "tools.tts_guard", "tools.teacher_student",
            "tools.research_connect", "astra.library", "astra.real_audio"]
    for m in mods:
        t0 = time.time()
        try:
            __import__(m)
        except Exception as exc:
            bad.append(f"{m}: {type(exc).__name__}: {str(exc)[:60]}")
            continue
        dt = time.time() - t0
        if dt > 3:
            bad.append(f"{m} import {dt:.1f}s (dheema)")
    return bad


def t_leak() -> list[str]:
    from tools import worktmp as wt
    bad = []
    for name in ("engine_stress", "engine_load", "piper_parts", "setup", "free"):
        d = wt.BASE / name
        if not d.exists():
            continue
        files = list(d.rglob("*"))
        size_mb = sum(f.stat().st_size for f in files if f.is_file()) / (1024 * 1024)
        if size_mb > 200:
            bad.append(f"{name}: {size_mb:.0f} MB pada hai (saaf karo)")
    return bad


def t_disk() -> list[str]:
    from tools import worktmp as wt
    free = wt.free_mb()
    return [f"jagah kam: {free} MB"] if free < 500 else []


def main() -> int:
    ap = argparse.ArgumentParser(description="deep audit — naye tarike")
    ap.add_argument("--engine", default="espeak")
    a = ap.parse_args()
    from tools import worktmp as wt
    tmp = wt.work_tmp("deep_audit")
    tests = {
        "fuzz": lambda: t_fuzz(a.engine, tmp),
        "idempotent": lambda: t_idempotent(a.engine, tmp),
        "race": lambda: t_race(a.engine, tmp),
        "injection": lambda: t_injection(a.engine, tmp),
        "import": t_import,
        "leak": t_leak,
        "disk": t_disk,
    }
    report, total_bad = {}, 0
    for name, fn in tests.items():
        t0 = time.time()
        try:
            bad = fn()
        except Exception as exc:
            bad = [f"test khud crash: {type(exc).__name__}: {str(exc)[:70]}"]
        report[name] = {"ok": not bad, "problems": bad, "seconds": round(time.time() - t0, 1)}
        total_bad += len(bad)
        print(f"{name:11s} {'OK' if not bad else 'FAIL'}  {round(time.time()-t0,1)}s")
        for b in bad:
            print(f"            - {b}")
    print(json.dumps({"problems": total_bad, "engine": a.engine}, ensure_ascii=False))
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
