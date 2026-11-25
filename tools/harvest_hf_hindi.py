#!/usr/bin/env python3
"""harvest_hf_hindi.py — HuggingFace ke Hindi speech datasets se awaaz + SAHI transcript laao.

Kyun ye behtar: har clip ke saath shabd-ba-shabd Devanagari text milta hai —
wahi cheez awaaz bank aur cloning ke liye chahiye thi.

  python tools/harvest_hf_hindi.py --n 40            # 40 clip laao
  python tools/harvest_hf_hindi.py --report
"""
from __future__ import annotations
import argparse, json, subprocess, sys, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "voices" / "hindi_hf"; OUT.mkdir(parents=True, exist_ok=True)
IDX = ROOT / "knowledge" / "hf-hindi-voices.json"
SR = 24000
DATASETS = ["TheAIchemist13/hindi_asr_dataset", "hamees/asr-task-hindi"]


def _curl(url, out=None, timeout=120):
    cmd = ["curl", "-sL", "--max-time", str(timeout), url]
    if out:
        subprocess.run(cmd + ["-o", str(out)], check=False)
        return Path(out)
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def rows(ds, offset, length):
    q = urllib.parse.quote(ds, safe="")
    raw = _curl(f"https://datasets-server.huggingface.co/rows?dataset={q}&config=default&split=train"
                f"&offset={offset}&length={length}")
    try:
        return json.loads(raw).get("rows", [])
    except Exception:
        return []


def _ff():
    import ffbin
    return ffbin.ensure() or "ffmpeg"


def measure(p: Path) -> dict:
    import numpy as np, soundfile as sf
    y, sr = sf.read(str(p)); y = y.mean(1) if y.ndim > 1 else y
    n = int(0.02 * sr)
    e = np.array([np.sqrt((y[i:i + n] ** 2).mean()) for i in range(0, max(1, len(y) - n), n)])
    snr = 20 * np.log10((float(np.percentile(e, 90)) + 1e-9) / (float(np.percentile(e, 10)) + 1e-9))
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
    return {"sec": round(len(y) / sr, 1), "peak": round(float(np.max(np.abs(y))), 3),
            "snr_db": round(float(snr), 1), "f0_hz": round(f0, 1),
            "ling": "stri" if f0 >= 165 else ("aadmi" if f0 > 0 else "?")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    idx = json.loads(IDX.read_text(encoding="utf-8")) if IDX.exists() else []
    if a.report:
        print(json.dumps({"clips": len(idx), "sec": round(sum(x["sec"] for x in idx), 1),
                          "mb": round(sum(Path(x["file"]).stat().st_size for x in idx) / 1e6, 1),
                          "with_text": sum(1 for x in idx if x.get("text"))}, ensure_ascii=False))
        return 0
    have = {x["file"] for x in idx}
    got = 0
    for ds in DATASETS:
        off = 0
        while got < a.n and off < 400:
            rs = rows(ds, off, 10)
            if not rs:
                break
            for r in rs:
                if got >= a.n:
                    break
                row = r.get("row", {})
                aud = row.get("audio") or []
                src = aud[0].get("src") if isinstance(aud, list) and aud else None
                text = (row.get("transcriptions") or row.get("text") or row.get("sentence") or "").strip()
                if not src or len(text) < 8:
                    continue
                tmp = OUT / "_tmp.bin"
                _curl(src, tmp)
                if not tmp.exists() or tmp.stat().st_size < 3000:
                    tmp.unlink(missing_ok=True); continue
                name = f"{ds.split('/')[0][:10]}_{len(idx)+1:03d}.wav"
                dst = OUT / name
                subprocess.run([_ff(), "-v", "error", "-y", "-i", str(tmp), "-ac", "1", "-ar", str(SR),
                                "-af", "highpass=f=90", str(dst)], capture_output=True)
                tmp.unlink(missing_ok=True)
                if not dst.exists():
                    continue
                m = measure(dst)
                rel = str(dst.relative_to(ROOT))
                if rel in have:
                    continue
                ok = m["snr_db"] >= 10 and m["f0_hz"] > 60 and 0.8 <= m["sec"] <= 30
                idx.append({"file": rel, "text": text, "dataset": ds, "ok": ok, **m})
                print(("OK  " if ok else "XX  ") + name, m["sec"], "s |", m["f0_hz"], "Hz |", text[:40])
                got += 1
            off += 10
            if got >= a.n:
                break
    IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nlaaye: {got} | kul: {len(idx)} | {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
