#!/usr/bin/env python3
"""Library Add — nayi awaaz library me daalo (duplicate na aaye).

Niyam:
  1. Pehle hash se dekho — wahi file pehle se hai to **skip** (dobara nahi)
  2. Naam se bhi dekho (thunder/rain jaisa kaam pehle se ho to bata do, par naya rakho)
  3. Mono 64 kbps mp3 banao (halka), 60 s se lamba ho to trim
  4. library/ambience (ya di gayi category) me rakho
  5. DEFAULT_INDEX me entry likho (tags + license + duration)

CLI:
  python tools/library_add.py add --files a.mp3 b.wav --category ambience --tags thunder,rain
  python tools/library_add.py check --files a.mp3
"""
from __future__ import annotations
import argparse, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "astra" / "library"
LIBPY = ROOT / "astra" / "library.py"
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a"}


def _ff() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def library_hashes() -> dict[str, str]:
    out = {}
    for p in LIB.rglob("*"):
        if p.suffix.lower() in AUDIO_EXT:
            try:
                out[_sha(p)] = str(p.relative_to(ROOT))
            except Exception:
                continue
    return out


def slug(name: str) -> str:
    s = re.sub(r"\.(mp3|wav|ogg|m4a)$", "", name.lower())
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:60]


def convert(src: Path, dest: Path, max_seconds: int = 60) -> bool:
    """Mono 64 kbps mp3 — halka aur saaf."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_ff(), "-loglevel", "error", "-y", "-i", str(src), "-t", str(max_seconds),
           "-ac", "1", "-ar", "24000", "-b:a", "64k", str(dest)]
    return subprocess.run(cmd, capture_output=True).returncode == 0 and dest.exists() and dest.stat().st_size > 2000


def duration(path: Path) -> float:
    try:
        import soundfile as sf
        return round(len(sf.read(str(path))[0]) / sf.read(str(path))[1], 2)
    except Exception:
        return 0.0


def fingerprint(path: Path, n: int = 64, seconds: int = 10) -> "list[float]":
    """Awaaz ka spectrum fingerprint — naam badalne par bhi duplicate pakadta hai."""
    import numpy as np
    raw = subprocess.run([_ff(), "-v", "quiet", "-i", str(path), "-t", str(seconds),
                          "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    if len(x) == 0:
        return [0.0] * n
    sp = np.abs(np.fft.rfft(x))
    if sp.sum() == 0:
        return [0.0] * n
    bins = np.array_split(sp[: len(sp) // n * n], n)
    v = np.array([b.mean() for b in bins])
    return list(v / (np.linalg.norm(v) + 1e-9))


def similarity(a, b) -> float:
    """Do audio kitne ek jaise hain (0 = alag, 1 = bilkul same)."""
    fa, fb = fingerprint(Path(a)), fingerprint(Path(b))
    return float(sum(x * y for x, y in zip(fa, fb)))


def find_duplicate(src: Path, threshold: float = 0.95) -> str | None:
    """Library me pehle se wahi awaaz hai kya (spectrum se)."""
    f_new = fingerprint(src)
    best, best_sim = None, 0.0
    for p in LIB.rglob("*"):
        if p.suffix.lower() not in AUDIO_EXT:
            continue
        sim = float(sum(x * y for x, y in zip(f_new, fingerprint(p))))
        if sim > best_sim:
            best, best_sim = p, sim
    return str(best.relative_to(ROOT)) if best and best_sim >= threshold else None


def register(entry_id: str, rel_file: str, tags: list[str], license_note: str, secs: float) -> bool:
    """DEFAULT_INDEX me entry jodo (file ke aakhir wale dict me)."""
    src = LIBPY.read_text(encoding="utf-8")
    if f'"{entry_id}"' in src:
        return False
    block = (f' "{entry_id}": {{\n'
             f'  "file": "{rel_file}",\n'
             f'  "tags": [{", ".join(json.dumps(t, ensure_ascii=False) for t in tags)}],\n'
             f'  "license": {json.dumps(license_note, ensure_ascii=False)},\n'
             f'  "duration": {secs}\n'
             f' }},\n')
    marker = "DEFAULT_INDEX = {"
    start = src.index(marker)
    # dict ka aakhri closing brace dhoondo
    depth = 0
    end = None
    for i in range(start + len(marker) - 1, len(src)):
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return False
    # pehle wale entry ke baad comma hona chahiye, warna syntax toot jata hai
    before = src[:end].rstrip()
    if not before.endswith(","):
        before += ","
    new = before + "\n" + block.rstrip().rstrip(",") + "\n" + src[end:]
    LIBPY.write_text(new, encoding="utf-8")
    return True


def add(files: list[str], category: str = "ambience", tags: list[str] | None = None,
        license_note: str = "user upload", prefix: str = "") -> dict:
    tags = tags or []
    hashes = library_hashes()
    added, skipped = [], []
    for f in files:
        src = Path(f)
        if not src.exists():
            skipped.append({"file": src.name, "why": "file nahi mili"}); continue
        h = _sha(src)
        if h in hashes:
            skipped.append({"file": src.name, "why": f"pehle se hai: {hashes[h]}"}); continue
        entry_id = (prefix + "_" if prefix else "") + slug(src.name)
        dest = LIB / category / f"{entry_id}.mp3"
        if not convert(src, dest):
            skipped.append({"file": src.name, "why": "convert fail"}); continue
        secs = duration(dest)
        rel = str(dest.relative_to(ROOT / "astra" / "library"))
        if not register(entry_id, rel, tags or [category], license_note, secs):
            skipped.append({"file": src.name, "why": "index me nahi juda"}); continue
        hashes[h] = str(dest.relative_to(ROOT))
        added.append({"id": entry_id, "file": rel, "seconds": secs,
                      "kb": round(dest.stat().st_size / 1024)})
    return {"added": added, "skipped": skipped, "added_count": len(added), "skipped_count": len(skipped)}


def check(files: list[str]) -> dict:
    hashes = library_hashes()
    rows = []
    for f in files:
        p = Path(f)
        rows.append({"file": p.name, "exists": p.exists(),
                     "duplicate": hashes.get(_sha(p)) if p.exists() else None})
    return {"rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser(description="library me nayi awaaz daalo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("add", "check"):
        s = sub.add_parser(name)
        s.add_argument("--files", nargs="+", required=True)
        if name == "add":
            s.add_argument("--category", default="ambience")
            s.add_argument("--tags", default="")
            s.add_argument("--license", default="user upload")
            s.add_argument("--prefix", default="")
    a = ap.parse_args()
    if a.cmd == "check":
        print(json.dumps(check(a.files), ensure_ascii=False, indent=2)); return 0
    rep = add(a.files, a.category, [t.strip() for t in a.tags.split(",") if t.strip()],
              a.license, a.prefix)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if rep["added_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
