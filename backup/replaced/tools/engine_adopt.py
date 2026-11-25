#!/usr/bin/env python3
"""Engine Adopt — naya engine/audio aaye to: kya lena hai, kya chhodna hai (naap ke saath).

Niyam (Swag ka):
  • poora replace nahi — sirf **kamzori** replace karo, majbooti rakho
  • adopt tabhi jab naap me hamare target ke kareeb ya behtar ho
  • naam tabhi badlo jab engine **hamare se behtar** ho (warna hamara naam hi rahe)

CLI:
  python tools/engine_adopt.py --audio naya_engine.mp3 [--baseline hamara.mp3] [--out v.json]
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR = 16000
TARGET = {"mid_pct": (55, 65), "high_pct": (20, 30), "bright_hz": (1900, 2200),
          "echo": (0.0, 0.78), "speech_pct": (65, 90), "rms_dbfs": (-20, -16)}


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def load(p: str):
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", p, "-f", "f32le", "-ac", "1",
                        "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def measure(p: str) -> dict:
    import numpy as np
    x = load(p)
    if not len(x):
        return {"ok": False}
    n = len(x)
    S = np.abs(np.fft.rfft(x * np.hanning(n))); f = np.fft.rfftfreq(n, 1 / SR); tot = S.sum() + 1e-9
    w = 256
    e = np.array([np.sqrt((x[i:i + w] ** 2).mean()) for i in range(0, max(1, n - w), w)])
    speech = float((e > 10 ** (-38 / 20)).mean() * 100)
    k = 16
    env = np.array([np.abs(x[i:i + k]).mean() for i in range(0, max(1, n - k), k)])
    echo = 0.0
    if len(env) > 60:
        ee = env - env.mean(); a = np.correlate(ee, ee, "full")[len(ee) - 1:]
        a = a / (a[0] + 1e-12); step = k / SR
        l, h = int(0.017 / step), int(0.031 / step)
        echo = round(float(np.max(np.abs(a[l:h + 1]))), 3) if h > l else 0.0
    # F0 clusters (2-means)
    vals = []
    for i in range(0, n - 2048, 1024):
        s = x[i:i + 2048] - x[i:i + 2048].mean()
        if float(np.sqrt((s ** 2).mean())) < 0.008:
            continue
        ac = np.correlate(s, s, "full")[len(s) - 1:]; ac = ac / (ac[0] + 1e-12)
        lo, hi = int(SR / 450), int(SR / 70); band = ac[lo:min(hi, len(s) - 2)]
        if len(band) < 3 or band.max() < 0.3:
            continue
        ii = np.arange(1, len(band) - 1)
        loc = ii[(band[ii] >= band[ii - 1]) & (band[ii] >= band[ii + 1])]
        st = [q for q in loc if band[q] >= 0.9 * band.max()]
        vals.append(SR / (lo + (int(st[0]) if st else int(np.argmax(band)))))
    cl = []
    if vals:
        v = np.log2(np.array(vals))
        c = np.array([np.percentile(v, 20), np.percentile(v, 80)])
        for _ in range(25):
            lab = np.abs(v[:, None] - c[None, :]).argmin(1)
            for j in range(2):
                if (lab == j).any():
                    c[j] = v[lab == j].mean()
        cl = sorted(int(2 ** q) for q in c)
    return {"ok": True, "dur": round(n / SR, 1), "speech_pct": round(speech, 1),
            "mid_pct": round(100 * float(S[(f >= 300) & (f < 3000)].sum() / tot)),
            "high_pct": round(100 * float(S[f >= 3000].sum() / tot)),
            "low_pct": round(100 * float(S[f < 300].sum() / tot)),
            "bright_hz": round(float((S * f).sum() / tot)),
            "rms_dbfs": round(20 * float(np.log10(max(1e-9, np.sqrt((x ** 2).mean())))), 1),
            "echo": echo, "f0_clusters": cl}


def verdict(m: dict) -> dict:
    if not m.get("ok"):
        return {"verdict": "REJECT", "why": "decode fail"}
    score, notes = 0, []
    for k, (lo, hi) in TARGET.items():
        v = m.get(k)
        if v is None:
            continue
        if lo <= v <= hi:
            score += 1
            notes.append(f"{k} ✅ {v}")
        else:
            notes.append(f"{k} ❌ {v} (chahiye {lo}–{hi})")
    pct = round(100 * score / len(TARGET))
    v = "ADOPT (behtar/barabar)" if pct >= 83 else ("MERGE (sirf achhe hisse lo)" if pct >= 50 else "REJECT (kamzor)")
    return {"verdict": v, "match_pct": pct, "notes": notes}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--baseline", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    m = measure(a.audio)
    v = verdict(m)
    rep = {"candidate": a.audio, "measures": m, **v}
    if a.baseline:
        b = measure(a.baseline); bv = verdict(b)
        rep["baseline"] = {"file": a.baseline, "measures": b, **bv}
        rep["behtar_kis_me"] = {
            "bright": "candidate" if m.get("bright_hz", 0) > b.get("bright_hz", 0) else "baseline",
            "echo_kam": "candidate" if m.get("echo", 1) < b.get("echo", 1) else "baseline",
            "speech": "candidate" if m.get("speech_pct", 0) > b.get("speech_pct", 0) else "baseline"}
    if a.out:
        Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("verdict", "match_pct", "notes")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
