#!/usr/bin/env python3
"""harvest_hindi.py — archive.org se ASLI Hindi insaan ki awaaz laao (public domain).

Kyun archive.org: ye sandbox me khula hai, aur LibriVox ki Hindi audiobooks
public domain hain — yaani asli insaan, saaf recording, kanoon ke hisaab se theek.

  python tools/harvest_hindi.py --n 6            # 6 clips laao
  python tools/harvest_hindi.py --report         # kya jama hai
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "voices" / "hindi"
OUT.mkdir(parents=True, exist_ok=True)
IDX = ROOT / "knowledge" / "hindi-voices.json"
ITEMS = ["panchatantra_2604_librivox", "msw041_2605_librivox"]


def search_items(n=12, query='language:"Hindi" AND mediatype:audio'):
    """archive.org par Hindi audio dhoondo (audiobook, bhashan, radio)."""
    import json as _j, urllib.parse as _up
    q = _up.quote(query)
    url = (f"https://archive.org/advancedsearch.php?q={q}"
           "&fl[]=identifier&fl[]=title&fl[]=downloads&rows=60&sort[]=downloads+desc&output=json")
    raw = _curl(url) or "{}"
    try:
        docs = _j.loads(raw)["response"]["docs"]
    except Exception:
        return []
    return [d["identifier"] for d in docs][:n]
SR = 24000


def _curl(url, out=None, timeout=180):
    cmd = ["curl", "-sL", "--max-time", str(timeout), url]
    if out:
        cmd += ["-o", str(out)]
        subprocess.run(cmd, check=False)
        return Path(out)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout


def _ff():
    import ffbin
    return ffbin.ensure() or "ffmpeg"


def files_of(item):
    import json as _j
    meta = _j.loads(_curl(f"https://archive.org/metadata/{item}") or "{}")
    lic = (meta.get("metadata", {}) or {}).get("licenseurl", "?")
    out = []
    for f in meta.get("files", []):
        n = f.get("name", "")
        if n.lower().endswith("_64kb.mp3"):
            out.append((n, int(f.get("size", 0)), lic))
    return out


def clip(item, name, start=20, dur=25):
    """Ek saaf hissa kaato (shuru ka intro chhod kar) aur wav me rakho."""
    src = OUT / f"_{name}"
    url = f"https://archive.org/download/{item}/{name}"
    _curl(url, src)
    if not src.exists() or src.stat().st_size < 50_000:
        return None
    dst = OUT / f"{item[:18]}_{name.replace('_64kb.mp3','')}_{int(start)}s.wav"
    subprocess.run([_ff(), "-v", "error", "-y", "-ss", str(start), "-t", str(dur), "-i", str(src),
                    "-ac", "1", "-ar", str(SR), "-af", "highpass=f=90", str(dst)], capture_output=True)
    src.unlink(missing_ok=True)
    return dst if dst.exists() else None


def measure(p: Path) -> dict:
    import numpy as np, soundfile as sf
    y, sr = sf.read(str(p)); y = y.mean(1) if y.ndim > 1 else y
    peak = float(np.max(np.abs(y))) if len(y) else 0
    # asli SNR: bolne ke frames vs chupp ke frames
    n = int(0.02 * sr)
    e = np.array([np.sqrt((y[i:i + n] ** 2).mean()) for i in range(0, max(1, len(y) - n), n)])
    speech = float(np.percentile(e, 90)); noise = float(np.percentile(e, 10))
    snr = 20 * np.log10((speech + 1e-9) / (noise + 1e-9))
    f0 = 0.0
    try:
        import parselmouth
        from parselmouth.praat import call
        snd = parselmouth.Sound(str(p)); pit = snd.to_pitch()
        v = [call(pit, "Get value at time", t, "Hertz", "Linear")
             for t in np.arange(0.05, max(0.1, snd.duration - 0.05), 0.03)]
        v = [q for q in v if q and q == q and 60 < q < 450]
        f0 = float(np.median(v)) if v else 0.0
    except Exception:
        pass
    return {"sec": round(len(y) / sr, 1), "peak": round(peak, 3),
            "snr_db": round(float(snr), 1), "f0_hz": round(f0, 1),
            "ling": "stri" if f0 >= 165 else ("aadmi" if f0 > 0 else "?")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    idx = json.loads(IDX.read_text(encoding="utf-8")) if IDX.exists() else []
    if a.report:
        print(json.dumps({"clips": len(idx), "dir": str(OUT),
                          "total_mb": round(sum(f.stat().st_size for f in OUT.glob("*.wav")) / 1e6, 1),
                          "rows": idx}, ensure_ascii=False, indent=1))
        return 0
    got = 0
    items = ITEMS
    if a.n > 10:
        items = list(dict.fromkeys(ITEMS + search_items(a.n // 2)))
        print("items:", len(items))
    for item in items:
        for name, size, lic in files_of(item):
            if got >= a.n:
                break
            p = clip(item, name, start=20 + (got % 4) * 8, dur=25)
            if not p:
                continue
            m = measure(p)
            ok = m["snr_db"] >= 12 and m["f0_hz"] > 60
            idx.append({"file": str(p.relative_to(ROOT)), "source": f"archive.org/{item}/{name}",
                        "license": lic, "ok": ok, **m})
            print(("OK  " if ok else "XX  ") + p.name, m)
            got += 1
            if got >= a.n:
                break
    IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nlaaye: {got} | kul jama: {len(idx)} | storage: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
