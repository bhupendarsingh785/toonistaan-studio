#!/usr/bin/env python3
"""bug_hunt.py — code me asli bug dhoondho (AST se, andaaze se nahi).

Rules (har ek asli bug ki taraf ishara karta hai):
  E1 bare-except        : `except:` — KeyboardInterrupt bhi nigal jaata hai
  E2 silent-swallow     : `except Exception: pass` — bug chhup jaata hai
  E3 mutable-default    : def f(x=[]) / {} — ek hi list sab calls me
  E4 dup-key            : dict me ek hi key do baar (doosri chup-chaap jeet jaati hai)
  E5 eq-none            : x == None
  E6 float-eq           : float ko == se compare
  E7 shadow-builtin     : list/dict/str/id ko variable naam banana
  E8 exit-in-lib        : library module me sys.exit()
  E9 marker             : TODO/FIXME/XXX/HACK
  E10 open-no-with      : open() bina with (file leak)

  python tools/bug_hunt.py            # summary + top list
  python tools/bug_hunt.py --json
"""
from __future__ import annotations
import argparse, ast, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
SKIP = ("purana/", "backup/", "__pycache__")
BUILTINS = {"list", "dict", "set", "str", "id", "type", "sum", "min", "max", "bytes", "input", "format", "hash"}
LIB_ENTRY = {"sutradhar.py", "system_doctor.py", "kram.py", "system_audit.py"}


def files():
    for p in TOOLS.rglob("*.py"):
        rel = str(p.relative_to(TOOLS))
        if any(s in rel for s in SKIP):
            continue
        yield rel, p


def _inside_with(tree, call):
    for w in ast.walk(tree):
        if isinstance(w, (ast.With, ast.AsyncWith)):
            for item in w.items:
                for sub in ast.walk(item.context_expr):
                    if sub is call:
                        return True
    return False


def check(rel, src):
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [("E0 syntax", e.lineno or 0, str(e)[:60])]
    for n in ast.walk(tree):
        # E1/E2
        if isinstance(n, ast.ExceptHandler):
            if n.type is None:
                out.append(("E1 bare-except", n.lineno, "except:"))
            elif isinstance(n.type, ast.Name) and n.type.id == "Exception" and len(n.body) == 1 \
                    and isinstance(n.body[0], ast.Pass):
                out.append(("E2 silent-swallow", n.lineno, "except Exception: pass"))
        # E3
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in list(n.args.defaults) + [x for x in n.args.kw_defaults if x]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    out.append(("E3 mutable-default", n.lineno, f"{n.name}()"))
            if rel not in LIB_ENTRY:
                pass
        # E4
        if isinstance(n, ast.Dict):
            keys = []
            for k in n.keys:
                if isinstance(k, ast.Constant):
                    keys.append(k.value)
            dups = {k for k in keys if keys.count(k) > 1}
            for k in dups:
                out.append(("E4 dup-key", n.lineno, f"key {k!r} do baar"))
        # E5/E6
        if isinstance(n, ast.Compare):
            for op, cmp_ in zip(n.ops, n.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(cmp_, ast.Constant) and cmp_.value is None:
                    out.append(("E5 eq-none", n.lineno, "x == None"))
                if isinstance(op, ast.Eq) and isinstance(cmp_, ast.Constant) and isinstance(cmp_.value, float):
                    out.append(("E6 float-eq", n.lineno, f"== {cmp_.value}"))
        # E7
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id in BUILTINS:
            out.append(("E7 shadow-builtin", n.lineno, n.id))
        # E8
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "exit" \
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "sys" \
                and rel not in LIB_ENTRY and "__main__" not in src:
            out.append(("E8 exit-in-lib", n.lineno, "sys.exit()"))
        # E10 — sirf wo open() jo `with` ke andar nahi (AST se)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open":
            if not _inside_with(tree, n):
                out.append(("E10 open-no-with", n.lineno, "open()"))
    for i, line in enumerate(src.splitlines(), 1):
        u = line.upper()
        for m in ("TODO", "FIXME", "XXX", "HACK"):
            if m in u:
                out.append(("E9 marker", i, m))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    allf = list(files())
    found = defaultdict(list)
    for rel, p in allf:
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for rule, ln, msg in check(rel, src):
            found[rule].append((rel, ln, msg))
    if a.json:
        print(json.dumps({k: v for k, v in found.items()}, ensure_ascii=False, indent=1)); return
    total = sum(len(v) for v in found.values())
    print(f"files {len(allf)} | bug-ish {total}")
    for rule in sorted(found):
        v = found[rule]
        print(f"\n{rule}: {len(v)}")
        for rel, ln, msg in v[:6]:
            print(f"   {rel}:{ln}  {msg}")
        if len(v) > 6:
            print(f"   ... {len(v)-6} aur")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
