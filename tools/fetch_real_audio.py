#!/usr/bin/env python3
"""fetch_real_audio.py — asli recording web se laao (test ke liye, Wikimedia Commons).

  python tools/fetch_real_audio.py --query "hindi speech" --n 2
  python tools/fetch_real_audio.py --set test        # test ke liye chaar tarah ki awaaz

Sirf Commons (free license) se; har file ke saath license/page likha jaata hai.
"""
from __future__ import annotations
import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path("/scratch/work/real")
API = "https://commons.wikimedia.org/w/api.php"
UA = "AstraAudioTest/1.0 (audio engine testing; https://github.com/bhupendarsingh785/toonistaan-studio) python-urllib"


def _curl(url: str, out: str | None = None, timeout: int = 90):
    """curl se laao (Wikimedia API urllib par 429 deta hai, curl theek chalta hai)."""
    import subprocess
    cmd = ["curl", "-sL", "-A", UA, "--max-time", str(timeout)]
    if out:
        cmd += ["-o", out, "-w", "%{http_code}"]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout


def _get(url: str, timeout=40, tries: int = 3):
    """Wikimedia 429 deta hai to thoda ruk kar dobara (politely)."""
    import time
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last = e
            time.sleep(3 * (i + 1))
    raise last


def search(query: str, n: int = 3, ext=("ogg", "oga", "wav", "mp3", "flac", "opus")):
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:audio {query}", "gsrnamespace": 6, "gsrlimit": n * 3,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata",
    })
    import time
    raw = _curl(f"{API}?{q}")
    time.sleep(1.5)
    data = json.loads(raw)
    pages = (data.get("query") or {}).get("pages") or {}
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        url = (ii.get("url") or "").split("?")[0]     # Wikimedia URL me ?utm... juda hota hai
        if not url or not url.lower().endswith(ext):
            continue
        meta = ii.get("extmetadata") or {}
        out.append({
            "title": p.get("title"), "url": url, "size": ii.get("size"),
            "license": (meta.get("LicenseShortName") or {}).get("value", "?"),
            "page": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(p.get('title','').replace(' ', '_'))}",
        })
        if len(out) >= n:
            break
    return out


def fetch(query: str, n: int = 2, tag: str = "") -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    got = []
    for row in search(query, n):
        name = (tag or "clip") + "_" + Path(urllib.parse.unquote(row["url"])).name
        name = "".join(ch for ch in name if ch.isalnum() or ch in "._-")[:80]
        dest = OUT / name
        if not dest.exists():
            try:
                code = _curl(row["url"], out=str(dest))
                if not code.startswith("2"):
                    raise RuntimeError("http " + code)
            except Exception as e:
                print("  XX download fail:", row["title"], repr(e)[:60])
                continue
        row["file"] = str(dest)
        got.append(row)
        print(f"  OK {dest.name}  {dest.stat().st_size//1024} KB  [{row['license']}]")
    return got


SETS = {
    "test": [
        ("hindi speech", 1, "hi_speech"),
        ("traffic street noise", 1, "noise_street"),
        ("two people conversation", 1, "conv2"),
        ("rain ambience", 1, "rain"),
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="")
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--tag", default="")
    ap.add_argument("--set", default="")
    a = ap.parse_args()
    rows = []
    if a.set:
        for q, n, tag in SETS.get(a.set, []):
            print(f"[{tag}] {q}")
            rows += fetch(q, n, tag)
    elif a.query:
        rows = fetch(a.query, a.n, a.tag)
    else:
        ap.error("--query ya --set do")
    if rows:
        idx = OUT / "index.json"
        old = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else []
        idx.write_text(json.dumps(old + rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print("index:", idx, "|", len(rows), "naye clip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
