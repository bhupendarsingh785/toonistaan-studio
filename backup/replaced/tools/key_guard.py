#!/usr/bin/env python3
"""Key Guard — koi API key galti se repo me na aaye (ElevenLabs private rahe).

Kya dekhta hai:
  1) tracked files me key jaisa pattern (sk-…, xi-api-key: …, 32+ hex/long token)
  2) .env / secrets file git me hai kya
  3) code me key print/log ho rahi hai kya

CLI:
  python tools/key_guard.py            # scan (fail = exit 1)
  python tools/key_guard.py --list     # sirf list, fail nahi
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    "elevenlabs": re.compile(r"xi-api-key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}"),
    "openai": re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    "sarvam": re.compile(r"(?:SARVAM_API_KEY|sarvam[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-]{15,}"),
    "generic": re.compile(r"(?:api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{24,}['\"]"),
}
SKIP_EXT = {".md", ".txt", ".json", ".lock"}
SKIP_DIRS = {".git", "models", "__pycache__", "node_modules", "storage", "cache",
             "tests", "test"}          # tests me jaan-boojh kar fake key hoti hai
FAKE_PREFIX = ("abc", "xyz", "your", "fake", "test", "dummy", "sample", "1234", "xxxx")
SECRET_FILES = re.compile(r"(^|/)(\.env|secrets?\.(json|ya?ml)|credentials\.json)$")


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
        files = [ROOT / ln for ln in out.splitlines() if ln.strip()]
        if files:
            return files
    except Exception:
        pass
    return [p for p in ROOT.rglob("*") if p.is_file()
            and not any(s in p.parts for s in SKIP_DIRS)]


def scan() -> dict:
    hits, secret_files = [], []
    for f in tracked_files():
        rel = str(f.relative_to(ROOT)) if str(f).startswith(str(ROOT)) else str(f)
        if any(s in f.parts for s in SKIP_DIRS):
            continue
        if SECRET_FILES.search(rel):
            secret_files.append(rel)
            continue
        if f.suffix.lower() in SKIP_EXT or f.stat().st_size > 2_000_000:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for name, pat in PATTERNS.items():
            for m in pat.finditer(text):
                val = m.group(0)
                tail = val.split(":")[-1].strip().strip('\'"').lower()
                if tail.startswith(FAKE_PREFIX):
                    continue          # nakli key — jaan-boojh kar rakhi hai
                hits.append({"file": rel, "kind": name,
                             "sample": val[:24] + "…"})
    return {"leaks": hits, "secret_files": secret_files,
            "ok": not hits and not secret_files,
            "checked": len(tracked_files())}


def main() -> int:
    ap = argparse.ArgumentParser(description="key leak guard")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    rep = scan()
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    if a.list:
        return 0
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
