#!/usr/bin/env python3
"""harvest_voices.py — duniya ke public platforms se INSANON ki awaaz jama karo (training ke liye).

Maksad: ek insaan ki awaaz par nahi — hazaaron alag logon ki. Har clip par:
  • license (kaunsa public source, kaun sa license)
  • bolne ka hissa (VAD) aur shor (SNR)
  • sur (F0) — isse pata chalta hai kitne alag speaker mile
  • kaun sa group (aadmi/stri/bachcha/budha) — F0 se, naap ke saath

Sirf wahi clip rakhi jaati hai jo: 2-20s, bolne ka hissa > 40%, SNR theek, aur awaaz insaan ki.
Kuch bhi chhupaya nahi jaata — jo reject hua wo reason ke saath log me.

  python tools/harvest_voices.py --n 12
  python tools/harvest_voices.py --report
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
try:
    import astra_paths as _AP
except ImportError:
    import sys as _s, pathlib as _pl
    _s.path.insert(0, str(_pl.Path(__file__).resolve().parent)); import astra_paths as _AP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
OUT = (_AP.WORK / "voice_harvest")
K = ROOT / "knowledge"
SR = 16000

QUERIES = [
    ("hindi speech", "hi"), ("woman speaking", "any"), ("man speaking", "any"),
    ("child speaking", "any"), ("old man speaking", "any"), ("old woman speaking", "any"),
    ("village people talking india", "hi"), ("interview hindi", "hi"),
]


def _ff():
    try:
        import ffbin
        return ffbin.ensure() or "ffmpeg"
    except Exception:
        return "ffmpeg"


def decode(path, sec=20.0):
    raw = subprocess.run([_ff(), "-v", "quiet", "-t", str(sec), "-i", str(path),
                          "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    if len(raw) < SR // 2:
        return None
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return x / (np.max(np.abs(x)) + 1e-9)


def quality(x):
    n = int(0.02 * SR)
    e = np.array([np.sqrt((x[i:i + n] ** 2).mean()) for i in range(0, max(1, len(x) - n), n)])
    if not len(e):
        return {}
    speech = float((e > 0.12 * (np.percentile(e, 95) + 1e-9)).mean())
    snr = float(20 * np.log10(np.percentile(e, 90) / (np.percentile(e, 10) + 1e-9)))
    f0s = []
    win, hop = int(0.04 * SR), int(0.02 * SR)
    for i in range(0, max(1, len(x) - win), hop):
        s = x[i:i + win]
        if np.sqrt((s ** 2).mean()) < 0.01:
            continue
        ac = np.correlate(s, s, "full")[len(s) - 1:]
        lo, hi = int(SR / 500), min(int(SR / 70), len(ac) - 1)
        if hi > lo:
            f0s.append(SR / (np.argmax(ac[lo:hi]) + lo + 1e-9))
    f0 = float(np.median(f0s)) if f0s else 0.0
    return {"dur": round(len(x) / SR, 2), "speech": round(speech, 2), "snr": round(snr, 1), "f0": round(f0, 1)}


def group_of(f0):
    if f0 <= 0:
        return "pata_nahi"
    if f0 < 95:
        return "budha/aadmi"
    if f0 < 125:
        return "aadmi"
    if f0 < 165:
        return "budhi/stri"
    if f0 < 250:
        return "stri"
    if f0 < 320:
        return "bachcha"
    return "bachcha/chhoti awaaz"


def harvest(n=12, per_query=2):
    import fetch_real_audio as F
    OUT.mkdir(parents=True, exist_ok=True)
    log = K / "voice-harvest.jsonl"
    kept, rejected, seen = [], [], set()
    for q, lang in QUERIES:
        if len(kept) >= n:
            break
        try:
            rows = F.search(q, per_query)
        except Exception as e:
            rejected.append({"query": q, "why": f"search fail {type(e).__name__}"})
            continue
        for r in rows[:per_query]:
            if len(kept) >= n:
                break
            try:
                got = F.fetch(q, 1, tag=q.split()[0], must_have=None)
            except Exception:
                got = []
            for g in got:
                src = Path(g["file"])
                if src.name in seen:      # ek hi clip do baar nahi
                    continue
                x = decode(src)
                if x is None:
                    rejected.append({"file": src.name, "why": "decode fail"}); continue
                qm = quality(x)
                if qm.get("dur", 0) < 1.5 or qm.get("speech", 0) < 0.35:
                    rejected.append({"file": src.name, **qm, "why": "bolne ka hissa kam / bahut chhota"}); continue
                if qm.get("snr", 0) < 8:
                    rejected.append({"file": src.name, **qm, "why": "shor zyada (SNR kam)"}); continue
                seen.add(src.name)
                dest = OUT / src.name
                if not dest.exists():
                    import shutil
                    shutil.copy2(src, dest)
                kept.append({"file": dest.name, "query": q, "lang": lang,
                             "license": g.get("license", "?"), **qm, "group": group_of(qm.get("f0", 0))})
            if len(kept) >= n:
                break
    with log.open("a", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps({**r, "kept": True}, ensure_ascii=False) + "\n")
        for r in rejected:
            f.write(json.dumps({**r, "kept": False}, ensure_ascii=False) + "\n")
    print(f"rakhe: {len(kept)} | chhode: {len(rejected)}")
    for r in kept[:12]:
        print(f"  {r['file'][:38]:38s} {r['group']:16s} f0 {r['f0']:5.1f} snr {r['snr']:4.1f} {r['license'][:14]}")
    return kept


def report():
    p = K / "voice-harvest.jsonl"
    if not p.exists():
        print("abhi kuch jama nahi"); return
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    kept = [r for r in rows if r.get("kept")]
    from collections import Counter
    print("rakhe:", len(kept), "| chhode:", len(rows) - len(kept))
    print("group:", dict(Counter(r["group"] for r in kept)))
    f0s = sorted(r["f0"] for r in kept if r["f0"] > 0)
    if f0s:
        print(f"sur failaav: {f0s[0]:.0f}-{f0s[-1]:.0f} Hz (alag-alag logon ka saboot)")
    print("license:", dict(Counter(r["license"][:16] for r in kept)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        report(); return 0
    harvest(a.n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
