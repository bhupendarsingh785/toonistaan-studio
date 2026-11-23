#!/usr/bin/env python3
"""system_audit.py — poora system ek saath chalta hai ya nahi, aur koi hissa door to nahi.

Chaar jaanch:
  1. ORPHAN   : kaunsa module kisi bhi entry point se pahunch me nahi (door pada hai)
  2. COLLIDE  : do module me ek hi class/func naam (galat import ka khatra)
  3. WIRE     : sutradhar ke stage, doctor ke check, kram ke level — sab resolve hote hain?
  4. SMOKE    : ek chhoti chain chalao (kram jaanch + doctor + selftests)

  python tools/system_audit.py            # table
  python tools/system_audit.py --json     # machine ke liye
"""
from __future__ import annotations
import argparse, ast, json, subprocess, sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
ENTRIES = ["tools/sutradhar.py", "tools/system_doctor.py", "tools/kram.py",
           "tools/drama/drama.py", "tools/browser_mesh.py", "tools/self_improve.py",
           "tools/system_activate.py"]
SKIP = ("tools/purana/", "tools/backup/")


def mods():
    out = []
    for p in TOOLS.rglob("*.py"):
        rel = str(p.relative_to(ROOT))
        if "__pycache__" in rel or rel.startswith(SKIP):
            continue
        out.append(rel)
    return sorted(out)


def _name(rel):
    return Path(rel).stem


def parse(rel):
    try:
        return ast.parse((ROOT / rel).read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def imports_of(rel):
    t = parse(rel)
    if t is None:
        return set()
    names = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            for a in n.names:
                names.add(a.name.split(".")[-1])
        elif isinstance(n, ast.ImportFrom):
            if n.module:
                names.add(n.module.split(".")[-1])
            for a in n.names:
                names.add(a.name)
    return names


def graph():
    g = defaultdict(set)
    for rel in mods():
        for dep in imports_of(rel):
            g[rel].add(dep)
    return g


def referenced():
    """Kaunse module ka naam kisi doosri file me likha hai (subprocess/CLI/docs) — matlab wo 'use' hota hai."""
    texts = {}
    for rel in mods():
        try:
            texts[rel] = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            texts[rel] = ""
    refs = set()
    for rel, txt in texts.items():
        for other in mods():
            if other == rel: continue
            stem = _name(other)
            if len(stem) < 4: continue
            if f"{stem}.py" in txt or f"import {stem}" in txt or f"from {stem}" in txt:
                refs.add(other)
    return refs


def reachable():
    g = graph()
    by_name = {_name(r): r for r in mods()}
    seen, q = set(), deque([e for e in ENTRIES if (ROOT / e).exists()])
    while q:
        cur = q.popleft()
        if cur in seen: continue
        seen.add(cur)
        for dep in g.get(cur, ()):
            tgt = by_name.get(dep)
            if tgt and tgt not in seen:
                q.append(tgt)
    return seen


def collisions():
    """Ek hi naam ki class/func do jagah — galat import ka khatra."""
    seen = defaultdict(list)
    for rel in mods():
        t = parse(rel)
        if t is None: continue
        for n in t.body:
            if isinstance(n, (ast.ClassDef,)):
                seen[n.name].append(rel)
    return {k: v for k, v in seen.items() if len(v) > 1}


def wires():
    """sutradhar stage / doctor check / kram level — sab milte hain?"""
    out = {}
    try:
        sys.path.insert(0, str(TOOLS))
        import importlib
        S = importlib.import_module("sutradhar")
        stages = [(s[0], s[1], s[2]) for s in S.STAGES]
        bad = []
        for name, mod, fn in stages:
            try:
                m = importlib.import_module(mod)
                if not hasattr(m, fn): bad.append(f"{name}: {mod}.{fn} gayab")
            except Exception as e:
                bad.append(f"{name}: {mod} import fail ({type(e).__name__})")
        out["sutradhar"] = {"stages": len(stages), "problem": bad}
    except Exception as e:
        out["sutradhar"] = {"error": type(e).__name__}
    try:
        sys.path.insert(0, str(ROOT))
        D = importlib.import_module("tools.system_doctor")
        out["doctor"] = {"checks": len(D.CHECKS)}
    except Exception as e:
        out["doctor"] = {"error": type(e).__name__}
    try:
        K = importlib.import_module("kram")
        t = ast.parse((TOOLS / "kram.py").read_text(encoding="utf-8"))
        lv = None
        for n in t.body:
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "LEVELS":
                lv = ast.literal_eval(n.value)
        mapped = {m for v in lv.values() for m in v.get("modules", {})}
        disk = {str(Path(r).relative_to("tools")) for r in mods()}
        out["kram"] = {"levels": len(lv), "mapped": len(mapped),
                       "bina_level": sorted(disk - mapped)[:8]}
    except Exception as e:
        out["kram"] = {"error": type(e).__name__}
    return out


def smoke():
    """Chhoti chain: har entry point ka selftest/wire."""
    res = {}
    cmds = {
        "kram jaanch": [sys.executable, "tools/kram.py", "jaanch"],
        "sutradhar wire": [sys.executable, "tools/sutradhar.py", "wire"],
        "self_improve": [sys.executable, "tools/self_improve.py", "selftest"],
        "praat": [sys.executable, "tools/local_story/praat_pitch.py", "selftest"],
    }
    for k, c in cmds.items():
        try:
            r = subprocess.run(c, cwd=str(ROOT), capture_output=True, text=True, timeout=240)
            tail = (r.stdout or "").strip().split("\n")[-1][:60]
            res[k] = {"ok": r.returncode == 0, "tail": tail}
        except Exception as e:
            res[k] = {"ok": False, "tail": type(e).__name__}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    all_m = mods()
    reach = reachable()
    refs = referenced()
    reach_all = reach | refs
    orphan = [r for r in all_m if r not in reach_all and r not in ENTRIES]
    coll = collisions()
    w = wires()
    sm = smoke() if not a.json else {}
    report = {"modules": len(all_m), "reachable": len(reach), "orphan": orphan,
              "collisions": {k: v for k, v in coll.items()}, "wires": w, "smoke": sm}
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=1)); return
    print(f"modules {len(all_m)} | entry se pahunch {len(reach)} | naam se use {len(refs)} | door (orphan) {len(orphan)}")
    if orphan:
        print("\nDOOR PADE MODULES (kisi entry se nahi judte):")
        for o in orphan: print("  -", o)
    print("\nCOLLISION (ek naam, do jagah):", "koi nahi" if not coll else "")
    for k, v in coll.items(): print(f"  {k}: {v}")
    print("\nWIRE:")
    for k, v in w.items(): print(" ", k, v)
    print("\nSMOKE:")
    for k, v in sm.items(): print(f"  {'PASS' if v['ok'] else 'FAIL'} {k} — {v['tail']}")
    ok = not orphan and not coll and all(v.get("ok") for v in sm.values())
    print("\n" + ("SAB JUDA AUR CHALU" if ok else "KUCH Hissa DOOR/BROKEN hai (upar dekho)"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
