#!/usr/bin/env python3
"""Sound ID — asli awaaz ki "fingerprint" seekho, phir pehchano (kaun si awaaz hai).

Feature (2 s, 16 kHz):
  centroid, low/mid/high %, F0 (CMNDF median), harmonicity, AM rate (1–20 Hz),
  attack (ms), zero-crossing rate, bandwidth

Do kaam:
  --train  : catalog ki files se har class ki signature (min/median/max) banao
  --id     : naya audio → kaunsi class (distance se) + confidence + 'pata nahi'

CLI:
  python tools/sound_id.py --train --catalog catalog.json --out signatures.json
  python tools/sound_id.py --id --audio x.mp3 --signatures signatures.json
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR = 16000


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def load(p: str, seconds: float = 2.0):
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-t", str(seconds), "-i", str(p),
                        "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def features(x) -> dict | None:
    import numpy as np
    if len(x) < SR // 4:
        return None
    n = len(x)
    S = np.abs(np.fft.rfft(x * np.hanning(n))); f = np.fft.rfftfreq(n, 1 / SR); tot = S.sum() + 1e-9
    # F0 (CMNDF median)
    f0s = []
    for i in range(0, n - 2048, 1024):
        s = x[i:i + 2048] - x[i:i + 2048].mean()
        if float(np.sqrt((s ** 2).mean())) < 0.006:
            continue
        m = len(s); d = np.zeros(m // 2)
        for tau in range(1, m // 2):
            diff = s[:m - tau] - s[tau:]
            d[tau] = float(np.dot(diff, diff))
        cm = np.ones_like(d); run = 0.0
        for tau in range(1, len(d)):
            run += d[tau]; cm[tau] = d[tau] * tau / (run + 1e-12)
        lo, hi = int(SR / 450), min(int(SR / 60), len(cm) - 1)
        if hi <= lo + 1:
            continue
        band = cm[lo:hi]; k = lo + int(np.argmin(band))
        if cm[k] < 0.5:
            f0s.append(SR / k)
    f0 = int(sorted(f0s)[len(f0s) // 2]) if f0s else 0
    # harmonicity: autocorr peak
    s = x - x.mean()
    ac = np.correlate(s, s, "full")[len(s) - 1:]; ac = ac / (ac[0] + 1e-12)
    lo, hi = int(SR / 450), min(int(SR / 60), len(ac) - 1)
    harm = float(ac[lo:hi].max()) if hi > lo else 0.0
    # AM rate: envelope ka 1–20 Hz peak
    env = np.abs(x); w = 64
    e = np.array([env[i:i + w].mean() for i in range(0, max(1, n - w), w)])
    am_rate = 0.0
    if len(e) > 32:
        e = e - e.mean(); F = np.abs(np.fft.rfft(e)); fr = np.fft.rfftfreq(len(e), w / SR)
        m = (fr >= 1) & (fr <= 20)
        if m.any():
            am_rate = float(fr[m][np.argmax(F[m])])
    # attack (ms): 10% → 90% of peak envelope
    peak = float(np.max(np.abs(x))) + 1e-9
    idx = np.where(np.abs(x) > 0.1 * peak)[0]
    attack = round(1000 * (idx[0] / SR), 1) if len(idx) else 0
    zcr = float(np.mean(np.abs(np.diff(np.sign(x))) > 0) * 100)
    return {"centroid_hz": round(float((S * f).sum() / tot)),
            "low_pct": round(100 * float(S[f < 300].sum() / tot)),
            "mid_pct": round(100 * float(S[(f >= 300) & (f < 3000)].sum() / tot)),
            "high_pct": round(100 * float(S[f >= 3000].sum() / tot)),
            "f0_hz": f0, "harmonicity": round(harm, 2), "am_rate_hz": round(am_rate, 1),
            "attack_ms": attack, "zcr_pct": round(zcr, 1),
            "rms_dbfs": round(20 * float(np.log10(max(1e-9, float(np.sqrt((x ** 2).mean()))))), 1)}


KEYS = ["centroid_hz", "low_pct", "mid_pct", "high_pct", "harmonicity", "am_rate_hz", "attack_ms", "zcr_pct"]
SCALE = {"centroid_hz": 4000, "low_pct": 40, "mid_pct": 40, "high_pct": 40,
         "harmonicity": 1.0, "am_rate_hz": 10, "attack_ms": 200, "zcr_pct": 30}


def train(catalog: dict, base: str, limit_per: int = 60) -> dict:
    import numpy as np
    sig = {}
    by = {}
    for r in catalog["items"]:
        by.setdefault(r["cat"], []).append(r["file"])
    for cat, files in by.items():
        feats = []
        for fn in files[:limit_per]:
            p = Path(base) / fn
            if not p.exists():
                continue
            x = load(str(p))
            f = features(x)
            if f:
                feats.append(f)
        if len(feats) < 3:
            continue
        arr = {k: [f[k] for f in feats] for k in KEYS}
        sig[cat] = {"n": len(feats),
                    **{k: [round(float(np.percentile(v, 20)), 2), round(float(np.median(v)), 2),
                           round(float(np.percentile(v, 80)), 2)] for k, v in arr.items()}}
    return sig


def identify(audio: str, sig: dict) -> dict:
    f = features(load(audio))
    if not f:
        return {"ok": False, "why": "audio bahut chhota"}
    best = []
    for cat, s in sig.items():
        d = 0.0
        for k in KEYS:
            lo, med, hi = s[k]
            spread = max(1e-6, (hi - lo) / 2)
            v = f[k]
            z = 0.0 if lo <= v <= hi else (min(abs(v - lo), abs(v - hi)) / spread)
            d += min(2.0, z) ** 2
        best.append((d ** 0.5, cat))
    best.sort()
    d0, c0 = best[0]
    d1 = best[1][0] if len(best) > 1 else d0 + 1
    conf = round(max(0.0, min(1.0, (d1 - d0) / (d1 + 1e-6))), 2)
    return {"ok": True, "guess": c0 if conf >= 0.15 else "pata nahi", "confidence": conf,
            "runner_up": best[1][1] if len(best) > 1 else None, "features": f,
            "distances": [(round(d, 2), c) for d, c in best[:4]]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--id", action="store_true")
    ap.add_argument("--catalog", default="")
    ap.add_argument("--base", default="/scratch/input")
    ap.add_argument("--signatures", default="signatures.json")
    ap.add_argument("--audio", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.train:
        cat = json.loads(Path(a.catalog).read_text(encoding="utf-8"))
        sig = train(cat, a.base)
        Path(a.signatures).write_text(json.dumps(sig, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({"classes": list(sig), "count": len(sig)}, ensure_ascii=False))
    if a.id:
        sig = json.loads(Path(a.signatures).read_text(encoding="utf-8"))
        r = identify(a.audio, sig)
        if a.out:
            Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: r[k] for k in ("guess", "confidence", "runner_up", "distances") if k in r},
                         ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
