#!/usr/bin/env python3
"""prosody_real.py — ASLI insanon ki awaaz se seekho, TTS ko waisa banao.

Training ke dauran jo asli recordings jama hui (library + harvest), unse naapo:
  • sur ka beech aur failaav (kitna upar-neeche jaata hai)
  • bolne ki raftaar (shabd/s)
  • rukne ka pattern (kitni baar, kitna lamba)
  • awaaz ki saafai (HNR) aur chamak (centroid)
Yahi "asli profile" banti hai. Phir TTS ki awaaz ko usi profile ki taraf le jaate hain:
  • sur ka failaav badhao (robotic = flat sur)
  • raftaar asli jaisi
  • comma par asli jaisa rukna
  • halki smoothing (buzz kam)

  python tools/prosody_real.py learn          # asli profile banao
  python tools/prosody_real.py show
  python tools/prosody_real.py test --file x.wav
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
K = ROOT / "knowledge"
SR = 16000
PROFILE = K / "real-speech-profile.json"


def decode(p, sec=25.0, sr=SR):
    import ffbin
    ff = ffbin.ensure() or "ffmpeg"
    raw = subprocess.run([ff, "-v", "quiet", "-t", str(sec), "-i", str(p),
                          "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True).stdout
    if len(raw) < sr:
        return None
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return x / (np.max(np.abs(x)) + 1e-9)


def stats(x, sr=SR):
    win, hop = int(0.04 * sr), int(0.02 * sr)
    f0, e = [], []
    for i in range(0, max(1, len(x) - win), hop):
        s = x[i:i + win]
        rms = float(np.sqrt((s ** 2).mean()))
        e.append(rms)
        if rms < 0.012:
            continue
        ac = np.correlate(s, s, "full")[len(s) - 1:]
        lo, hi = int(sr / 450), min(int(sr / 70), len(ac) - 1)
        if hi > lo:
            f0.append(sr / (np.argmax(ac[lo:hi]) + lo + 1e-9))
    e = np.array(e) if e else np.array([0.0])
    f0 = np.array([v for v in f0 if 70 < v < 450]) if f0 else np.array([0.0])
    thr = 0.12 * (np.percentile(e, 95) + 1e-9)
    voiced = e > thr
    # rukne ke hisse
    pauses, run = [], 0
    for v in voiced:
        if not v:
            run += 1
        elif run:
            pauses.append(run * 0.02)
            run = 0
    if run:
        pauses.append(run * 0.02)
    n = 1024
    if len(x) > n * 2:
        fr = np.lib.stride_tricks.sliding_window_view(x, n)[:: n // 2]
        X = np.abs(np.fft.rfft(fr * np.hanning(n), axis=1)) + 1e-10
        f = np.fft.rfftfreq(n, 1 / sr)
        spec = X.mean(0)
        cent = float((spec * f).sum() / (spec.sum() + 1e-12))
        harm = float(spec[(f > 80) & (f < 4000)].sum() / (spec.sum() + 1e-12))
    else:
        cent, harm = 0.0, 0.0
    return {
        "f0_med": round(float(np.median(f0)), 1),
        "f0_range": round(float(np.percentile(f0, 90) - np.percentile(f0, 10)), 1),
        "voiced_ratio": round(float(voiced.mean()), 3),
        "pause_mean": round(float(np.mean(pauses)) if pauses else 0.0, 3),
        "pause_count_per_min": round(len(pauses) / max(1e-6, len(x) / sr / 60), 1),
        "centroid": round(cent, 0),
        "harm_ratio": round(harm, 3),
        "sec": round(len(x) / sr, 2),
    }


def learn(limit=40):
    files = []
    for d in ((_AP.WORK / "voice_harvest"), _AP.INPUT):
        if not d.exists():
            continue
        for p in sorted(d.glob("*")):
            if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".ogx", ".oga"):
                files.append(p)
        if len(files) > limit:
            break
    # sirf bolne wali clips (speech hissa > 35%)
    rows = []
    for p in files[:limit]:
        x = decode(p)
        if x is None:
            continue
        st = stats(x)
        if st["voiced_ratio"] < 0.35 or st["f0_med"] < 70:
            continue
        rows.append({"file": p.name, **st})
    if not rows:
        print("asli speech clips nahi mile"); return 1
    agg = {
        "clips": len(rows),
        "f0_med": round(float(np.median([r["f0_med"] for r in rows])), 1),
        "f0_range": round(float(np.median([r["f0_range"] for r in rows])), 1),
        "voiced_ratio": round(float(np.median([r["voiced_ratio"] for r in rows])), 3),
        "pause_mean": round(float(np.median([r["pause_mean"] for r in rows])), 3),
        "pause_per_min": round(float(np.median([r["pause_count_per_min"] for r in rows])), 1),
        "centroid": round(float(np.median([r["centroid"] for r in rows])), 0),
        "harm_ratio": round(float(np.median([r["harm_ratio"] for r in rows])), 3),
    }
    PROFILE.write_text(json.dumps({"agg": agg, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("asli profile:", json.dumps(agg, ensure_ascii=False))
    return 0


def show():
    if not PROFILE.exists():
        print("pehle learn chalao"); return
    d = json.loads(PROFILE.read_text(encoding="utf-8"))
    print(json.dumps(d["agg"], ensure_ascii=False, indent=1))


def test(path):
    x = decode(path)
    if x is None:
        print("padha nahi ja saka"); return
    st = stats(x)
    print("clip:", json.dumps(st, ensure_ascii=False))
    if PROFILE.exists():
        agg = json.loads(PROFILE.read_text(encoding="utf-8"))["agg"]
        print(f"asli f0_range {agg['f0_range']} vs clip {st['f0_range']} | "
              f"pause/min {agg['pause_per_min']} vs {st['pause_count_per_min']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["learn", "show", "test"])
    ap.add_argument("--file", default="")
    a = ap.parse_args()
    if a.cmd == "learn":
        return learn()
    if a.cmd == "show":
        show(); return 0
    test(a.file); return 0


if __name__ == "__main__":
    raise SystemExit(main())
