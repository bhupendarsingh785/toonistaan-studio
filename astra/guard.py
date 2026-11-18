#!/usr/bin/env python3
"""
ASTRA GUARD — galti se ya kisi aur se kuch delete na ho.

Do tarah se kaam karta hai:

1) CI (GitHub Actions, guard.yml):
   har push par pichhle commit se tulna karta hai. Agar ek saath
   LIMIT se zyada file gayab hui ho -> unhe wapas laata hai aur
   revert commit karta hai. (bina puche kuch delete nahi hone deta)

2) Local pre-commit hook (optional):
   python3 astra/guard.py --hook-install
   phir har commit par badi deletion rok di jayegi.

Chalao:
  python3 astra/guard.py check          # report (kuch nahi badalta)
  python3 astra/guard.py restore        # gayab files wapas laao
  python3 astra/guard.py snapshot       # checksum snapshot banao
  python3 astra/guard.py verify         # snapshot se tulna
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIB = os.path.join(HERE, "library")
SNAP = os.path.join(HERE, "library-snapshot.json")

# kitni files ek saath gayab hona "galti" maana jaye
LIMIT_FILES = 2
LIMIT_PCT = 0.5      # library ka 0.5% se zyada bhi shak


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def deleted_in_last_commit(ref="HEAD"):
    """Pichhle commit me delete hui files."""
    code, out, _ = git("diff", "--name-status", f"{ref}~1", ref)
    if code != 0:
        return []
    gone = []
    for line in out.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0]
        if status.startswith("D"):
            gone.append(parts[-1])
    return gone


def count_files(path=LIB):
    n = 0
    for _root, _dirs, files in os.walk(path):
        n += len(files)
    return n


def check(verbose=True):
    gone = deleted_in_last_commit()
    total = count_files()
    lib_gone = [g for g in gone if g.startswith("astra/library/")]
    limit = max(LIMIT_FILES, int(total * LIMIT_PCT / 100))
    bad = len(gone) > limit or len(lib_gone) > 2
    if verbose:
        print(f"GUARD files={total} deleted_last_commit={len(gone)} "
              f"(library={len(lib_gone)}) limit={limit} -> {'SHAK' if bad else 'OK'}")
        for g in gone[:10]:
            print("   gayab:", g)
    return {"bad": bad, "deleted": gone, "library_deleted": lib_gone, "files": total}


def missing_vs_snapshot():
    """Snapshot ke hisaab se jo file abhi nahi hai."""
    if not os.path.exists(SNAP):
        return []
    old = json.load(open(SNAP))
    miss = []
    for rel in old.get("files", {}):
        if not os.path.exists(os.path.join(HERE, rel)):
            miss.append("astra/" + rel)
    return miss


def restore(verbose=True):
    """Gayab files wapas laao — commit se ya snapshot se."""
    gone = deleted_in_last_commit()
    miss = missing_vs_snapshot()
    targets = list(dict.fromkeys(gone + miss))
    if not targets:
        if verbose:
            print("GUARD restore: kuch gayab nahi")
        return 0
    back = 0
    for path in targets:
        ok = False
        for ref in ("HEAD", "HEAD~1", "HEAD~2", "origin/main"):
            code, _o, err = git("checkout", ref, "--", path)
            if code == 0 and os.path.exists(os.path.join(ROOT, path)):
                ok = True
                if verbose:
                    print(f"   wapas: {path} (se {ref})")
                break
        if ok:
            back += 1
        elif verbose:
            print(f"   FAIL: {path}")
    if verbose:
        print(f"GUARD restore: {back}/{len(gone)} file wapas laayi")
    return back


def snapshot():
    """Har file ka checksum — pata rahe kya tha."""
    data = {}
    for root, _dirs, files in os.walk(LIB):
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, HERE)
            try:
                h = hashlib.md5(open(p, "rb").read()).hexdigest()
                data[rel] = {"size": os.path.getsize(p), "md5": h}
            except Exception:
                continue
    json.dump({"count": len(data), "files": data}, open(SNAP, "w"), indent=0)
    print(f"GUARD snapshot: {len(data)} files")
    return len(data)


def verify():
    """Snapshot se tulna — kaunsi file gayab/badli."""
    if not os.path.exists(SNAP):
        print("GUARD verify: snapshot nahi hai")
        return 1
    old = json.load(open(SNAP))
    cur = {}
    for root, _dirs, files in os.walk(LIB):
        for f in files:
            p = os.path.join(root, f)
            cur[os.path.relpath(p, HERE)] = hashlib.md5(open(p, "rb").read()).hexdigest()
    missing = [k for k in old["files"] if k not in cur]
    changed = [k for k, v in cur.items() if k in old["files"] and old["files"][k]["md5"] != v]
    print(f"GUARD verify: pehle {old['count']} | ab {len(cur)} | gayab {len(missing)} | badli {len(changed)}")
    for m in missing[:10]:
        print("   GAYAB:", m)
    return 0 if not missing else 2


def hook_install():
    hook = os.path.join(ROOT, ".git", "hooks", "pre-commit")
    body = """#!/bin/sh
python3 astra/guard.py check || exit 1
"""
    os.makedirs(os.path.dirname(hook), exist_ok=True)
    open(hook, "w").write(body)
    os.chmod(hook, 0o755)
    print("GUARD hook laga diya (.git/hooks/pre-commit)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "restore", "snapshot", "verify", "hook-install"])
    a = ap.parse_args()
    if a.cmd == "check":
        return 0 if not check()["bad"] else 1
    if a.cmd == "restore":
        restore()
        return 0
    if a.cmd == "snapshot":
        snapshot()
        return 0
    if a.cmd == "verify":
        return verify()
    hook_install()
    return 0


if __name__ == "__main__":
    sys.exit(main())
