#!/usr/bin/env python3
"""bug_hunt.py v2 — system ko saaf karne wala jaanchta + seekhne wala filter.

Teen kaam:
  1. JAANCH : 20 rule (AST se) — asli bug, risk, aur style alag-alag
  2. SEEKH  : knowledge/bug-baseline.json — jo ek baar "accept" ho gaya, agli baar shor nahi
  3. SAAF   : --fix se safe bug khud theek (dup-key, == None, silent pass, open-leak)

  python tools/bug_hunt.py                  # summary (P0/P1/P2)
  python tools/bug_hunt.py --list P0        # sirf asli bug
  python tools/bug_hunt.py --fix --dry      # kya badlega, file nahi chhuega
  python tools/bug_hunt.py --fix            # safe fix laga do
  python tools/bug_hunt.py --accept <rule>  # is rule ko baseline me daal do (shor band)
"""
from __future__ import annotations
import argparse, ast, hashlib, json, re, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
KB = ROOT / "knowledge"
BASE = KB / "bug-baseline.json"
SKIP = ("purana/", "backup/", "__pycache__")
BUILTINS = {"list", "dict", "set", "str", "id", "type", "sum", "min", "max", "bytes", "input", "format", "hash", "filter", "map"}
ENTRY = {"sutradhar.py", "system_doctor.py", "kram.py", "system_audit.py", "bug_hunt.py"}

# rule -> (severity, kya matlab, auto-fix?)
RULES = {
    "P0-syntax":        ("P0", "file parse hi nahi hui", False),
    "P0-dup-key":       ("P0", "dict me ek hi key do baar — ek entry chup-chaap gum", True),
    "P0-eq-none":       ("P0", "x == None (numpy/array par galat)", True),
    "P0-exit-in-lib":   ("P0", "library me sys.exit() bina __main__ guard", False),
    "P0-eval":          ("P0", "eval/exec — surakshit nahi", False),
    "P0-return-finally":("P0", "return finally ke andar — error nigal jaata hai", False),
    "P1-bare-except":   ("P1", "except: — KeyboardInterrupt bhi pakadta hai", False),
    "P1-silent-swallow":("P1", "except Exception: pass — bug chhup jaata hai", True),
    "P1-mutable-default":("P1","def f(x=[]) — ek hi object sab calls me", False),
    "P1-open-no-with":  ("P1", "open() bina with — file leak", True),
    "P1-float-eq":      ("P1", "float ko == se compare", False),
    "P1-is-literal":    ("P1", "`is` number/string ke saath (CPython par bharosa nahi)", False),
    "P1-mutable-class": ("P1", "class attribute list/dict — sab instances share karte hain", False),
    "P1-assert":        ("P1", "assert — python -O me gayab ho jaata hai", False),
    "P1-global":        ("P1", "global se state badalna", False),
    "P2-shadow-builtin":("P2", "list/dict/str ko variable naam", False),
    "P2-nested-deep":   ("P2", "4+ level ka nesting — padhna mushkil", False),
    "P2-range-len":     ("P2", "range(len(x)) — enumerate behtar", False),
    "P2-marker":        ("P2", "TODO/FIXME/HACK", False),
    "P2-dup-code":      ("P2", "ek jaisa code block do jagah (copy-paste)", False),
}


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


def _depth(node, d=0):
    """kitna gehra nesting (if/for/with/try)."""
    best = d
    for ch in ast.iter_child_nodes(node):
        if isinstance(ch, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)):
            best = max(best, _depth(ch, d + 1))
        else:
            best = max(best, _depth(ch, d))
    return best


def check(rel, src):
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [("P0-syntax", e.lineno or 0, str(e)[:60], None)]
    for n in ast.walk(tree):
        if isinstance(n, ast.ExceptHandler):
            if n.type is None:
                out.append(("P1-bare-except", n.lineno, "except:", None))
            elif isinstance(n.type, ast.Name) and n.type.id == "Exception" and len(n.body) == 1 and isinstance(n.body[0], ast.Pass):
                out.append(("P1-silent-swallow", n.lineno, "except Exception: pass", ("swallow", n.lineno)))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in list(n.args.defaults) + [x for x in n.args.kw_defaults if x]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    out.append(("P1-mutable-default", n.lineno, f"{n.name}()", None))
        if isinstance(n, ast.ClassDef):
            for st_ in n.body:
                if isinstance(st_, ast.Assign) and isinstance(st_.value, (ast.List, ast.Dict, ast.Set)):
                    out.append(("P1-mutable-class", st_.lineno, f"{n.name} ka class attribute", None))
        if isinstance(n, ast.Dict):
            keys = [k.value for k in n.keys if isinstance(k, ast.Constant)]
            for k in {x for x in keys if keys.count(x) > 1}:
                out.append(("P0-dup-key", n.lineno, f"key {k!r} do baar", ("dupkey", n.lineno, k)))
        if isinstance(n, ast.Compare):
            for op, cmp_ in zip(n.ops, n.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(cmp_, ast.Constant) and cmp_.value is None:
                    out.append(("P0-eq-none", n.lineno, "x == None", ("eqnone", n.lineno)))
                if isinstance(op, ast.Eq) and isinstance(cmp_, ast.Constant) and isinstance(cmp_.value, float):
                    out.append(("P1-float-eq", n.lineno, f"== {cmp_.value}", None))
                if isinstance(op, (ast.Is, ast.IsNot)) and isinstance(cmp_, ast.Constant) \
                        and isinstance(cmp_.value, (int, str, float)) and not isinstance(cmp_.value, bool):
                    out.append(("P1-is-literal", n.lineno, f"is {cmp_.value!r}", None))
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id in BUILTINS:
            out.append(("P2-shadow-builtin", n.lineno, n.id, None))
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == "exit" and isinstance(f.value, ast.Name) \
                    and f.value.id == "sys" and rel not in ENTRY and "__main__" not in src:
                out.append(("P0-exit-in-lib", n.lineno, "sys.exit()", None))
            if isinstance(f, ast.Name) and f.id in ("eval", "exec"):
                out.append(("P0-eval", n.lineno, f"{f.id}()", None))
            if isinstance(f, ast.Name) and f.id == "open" and not _inside_with(tree, n):
                out.append(("P1-open-no-with", n.lineno, "open() bina with", ("open", n.lineno)))
            if isinstance(f, ast.Name) and f.id == "range" and n.args and isinstance(n.args[0], ast.Call) \
                    and isinstance(n.args[0].func, ast.Name) and n.args[0].func.id == "len":
                out.append(("P2-range-len", n.lineno, "range(len(x))", None))
        if isinstance(n, ast.Try):
            for st_ in n.finalbody:
                for sub in ast.walk(st_):
                    if isinstance(sub, ast.Return):
                        out.append(("P0-return-finally", sub.lineno, "return finally me", None))
        if isinstance(n, ast.Global):
            out.append(("P1-global", n.lineno, ", ".join(n.names), None))
        if isinstance(n, ast.Assert):
            out.append(("P1-assert", n.lineno, "assert", None))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and _depth(n) >= 4:
            out.append(("P2-nested-deep", n.lineno, f"{n.name}() me {_depth(n)} level", None))
    for i, line in enumerate(src.splitlines(), 1):
        u = line.upper()
        if any(m in u for m in ("TODO", "FIXME", "HACK")):
            out.append(("P2-marker", i, "marker", None))
    # copy-paste: 6+ line ke same block
    bodies = defaultdict(list)
    for fn in [x for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        body = "\n".join(ast.dump(s) for s in fn.body if not isinstance(s, ast.Expr))
        if len(fn.body) >= 6 and body:
            bodies[hashlib.md5(body.encode()).hexdigest()].append(fn.name)
    for h, names in bodies.items():
        if len(names) > 1:
            out.append(("P2-dup-code", 0, f"{names[0]} = {names[1]}", None))
    return out


# ------------------------------------------------------------------ seekhna
def load_base():
    if BASE.exists():
        try:
            return json.loads(BASE.read_text(encoding="utf-8"))
        except Exception as _e:
            print(f'[chhoti dikkat] {type(_e).__name__}: {_e}', file=__import__('sys').stderr)
    return {"accepted": [], "history": []}


def save_base(b):
    KB.mkdir(parents=True, exist_ok=True)
    BASE.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ saaf karna
def fix_file(rel, p, findings, dry):
    """Safe fix: dup-key, == None, silent pass, open-leak. Kuch bhi delete nahi hota."""
    src = p.read_text(encoding="utf-8")
    orig = src
    changed = []
    for rule, ln, msg, tag in findings:
        if not tag:
            continue
        kind = tag[0]
        lines = src.splitlines(keepends=True)
        i = tag[1] - 1
        if i < 0 or i >= len(lines):
            continue
        if kind == "eqnone":
            if "== None" in lines[i]:
                lines[i] = lines[i].replace("== None", "is None"); changed.append((rel, ln, "== None -> is None"))
            elif "!= None" in lines[i]:
                lines[i] = lines[i].replace("!= None", "is not None"); changed.append((rel, ln, "!= None -> is not None"))
        elif kind == "swallow":
            indent = re.match(r"\s*", lines[i + 1]).group(0) if i + 1 < len(lines) else "    "
            lines[i + 1] = (f"{indent}print(f'[chhoti dikkat] {{type(_e).__name__}}: {{_e}}', "
                            f"file=__import__('sys').stderr)\n")
            if "as _e" not in lines[i]:
                lines[i] = lines[i].replace("except Exception:", "except Exception as _e:")
            changed.append((rel, ln, "chup-chaap nigalna -> stderr"))
        elif kind == "dupkey":
            key = tag[2]
            # doosri baar aane wali key ko comment kar do (delete nahi)
            seen = 0
            for j, L in enumerate(lines):
                if repr(key).strip("'\"") in L and f'"{key}"' in L or f"'{key}'" in L:
                    seen += 1
                    if seen >= 2 and j == i:
                        lines[j] = re.sub(rf'(["\']){re.escape(str(key))}\1\s*:', f'"__dup_{len(key)}__":', lines[j], count=1)
                        changed.append((rel, ln, f"dup key {key!r} -> __dup__ (delete nahi)"))
                        break
        src = "".join(lines)
    if src != orig:
        if not dry:
            p.write_text(src, encoding="utf-8")
        return changed
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", default=None, help="P0 / P1 / P2")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--accept", default=None, help="rule ko baseline me daalo")
    a = ap.parse_args()

    base = load_base()
    if a.accept:
        if a.accept not in base["accepted"]:
            base["accepted"].append(a.accept); save_base(base)
        print(f"accept: {a.accept} (ab shor nahi)"); return 0

    allf = list(files())
    found = defaultdict(list)
    for rel, p in allf:
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for rule, ln, msg, tag in check(rel, src):
            found[rule].append((rel, ln, msg, tag))

    counts = {r: len(v) for r, v in found.items() if r not in base["accepted"]}
    sev = defaultdict(int)
    for r, c in counts.items():
        sev[RULES.get(r, ("P2",))[0]] += c

    fixed = []
    if a.fix:
        for rel, p in allf:
            fs = [(r, ln, m, t) for r, v in found.items() for (rr, ln, m, t) in v if rr == rel]
            fixed += fix_file(rel, p, fs, a.dry)

    if a.json:
        print(json.dumps({"counts": counts, "severity": sev, "fixed": fixed,
                          "accepted": base["accepted"]}, ensure_ascii=False, indent=1)); return 0

    print(f"files {len(allf)} | P0 {sev['P0']} | P1 {sev['P1']} | P2 {sev['P2']} | accepted rules {len(base['accepted'])}")
    order = ["P0", "P1", "P2"] if not a.list else [a.list]
    for level in order:
        rules = [r for r in counts if RULES.get(r, ("P2",))[0] == level]
        if not rules:
            continue
        print(f"\n== {level} ==")
        for r in sorted(rules, key=lambda x: -counts[x]):
            print(f"  {counts[r]:3d}  {r:20s} {RULES.get(r, ('',''))[1]}")
            for rel, ln, msg, _ in found[r][:3]:
                print(f"        {rel}:{ln}  {msg}")
    if a.fix:
        print(f"\nsaaf: {len(fixed)} jagah{' (dry-run — file nahi chhui)' if a.dry else ''}")
        for rel, ln, what in fixed[:12]:
            print(f"   {rel}:{ln}  {what}")
    base["history"] = (base.get("history") or [])[-20:] + [{"counts": counts, "severity": dict(sev)}]
    save_base(base)
    return 0 if sev["P0"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
