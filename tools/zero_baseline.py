#!/usr/bin/env python3
"""zero_baseline.py — ZERO point yaad rakho aur usse neeche mat jaane do.

  python tools/zero_baseline.py --show          # baseline kya hai
  python tools/zero_baseline.py --check file.mp3 # naya audio zero se behtar hai ya kharab
  python tools/zero_baseline.py --restore        # cast/clarity ki settings zero par wapas

"zero" bolne par: naya kaam band, settings zero par wapas, aur zero se neeche kuch nahi.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
Z = ROOT / "baseline" / "zero" / "zero.json"


def load():
    return json.loads(Z.read_text(encoding="utf-8"))


def show():
    z = load()
    print(json.dumps(z, ensure_ascii=False, indent=1))


def metrics(path):
    import numpy as np, soundfile as sf
    from scipy import signal as ss
    y, sr = sf.read(str(path)); y = y.mean(1) if y.ndim > 1 else y
    n = int(0.02 * sr)
    e = np.array([np.sqrt((y[i:i + n] ** 2).mean()) for i in range(0, len(y) - n, n)])
    thr = 0.08 * (np.percentile(e, 95) + 1e-9); v = e > thr
    runs, r = [], 0
    for q in v:
        if not q: r += 1
        else:
            if r >= 5: runs.append(r * 0.02)
            r = 0
    env = np.abs(y); sos = ss.butter(2, [20 / (sr / 2), 80 / (sr / 2)], btype="band", output="sos")
    mod = ss.sosfilt(sos, env - np.convolve(env, np.ones(400) / 400, mode="same"))
    rough = float(np.std(mod) / (np.std(y) + 1e-9))
    return {"ruke_per_min": round(len([x for x in runs if x >= 0.15]) / (len(y) / sr / 60), 1),
            "sabse_lambi_chupp_s": round(max(runs) if runs else 0, 2),
            "roughness": round(rough, 4), "dur": round(len(y) / sr, 1)}


def check(path):
    if not Path(path).exists() or Path(path).stat().st_size < 1000:
        print(f"File nahi mili ya khaali hai: {path}  (pehle cast_build chalao — uski galti upar dekho)")
        return 3
    z = load()["naap"]; m = metrics(path)
    print("zero :", z)
    print("naya :", m)
    bad = []
    if m["ruke_per_min"] > z["ruke_per_min"] * 1.25: bad.append("rukna zyada")
    if m["sabse_lambi_chupp_s"] > z["sabse_lambi_chupp_s"] * 1.25: bad.append("chupp lambi")
    if m["roughness"] > z["roughness"] * 1.15: bad.append("kharaash zyada")
    print("\n" + ("ZERO se behtar/samaan ✓" if not bad else f"ZERO se NEECHE ✗ — {', '.join(bad)}"))
    return 0 if not bad else 2


def restore():
    z = load()
    p = ROOT / "tools" / "cast_build.py"; s = p.read_text(encoding="utf-8")
    import re
    for who, c in z["cast"].items():
        s = re.sub(rf'"{who}":\s*dict\([^)]*\)',
                   f'"{who}":  dict(engine="{c["engine"]}", pitch={c["pitch"]}, tempo={c["tempo"]}, '
                   f'tilt={c["tilt"]}, breath={c["breath"]}, vib={c["vib"]}, form="{c["form"]}")', s)
    p.write_text(s, encoding="utf-8")
    print("cast settings ZERO par wapas")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true"); ap.add_argument("--check", default="")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    if a.check: return check(a.check)
    if a.restore: return restore() or 0
    show(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
