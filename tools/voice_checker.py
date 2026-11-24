#!/usr/bin/env python3
"""voice_checker.py — apni awaaz khud jaanchne wala checker (insaan ke naap se).

Har file par 8 cheezein naapta hai aur saaf batata hai: theek / dhyan do / kharab.
  • sur (F0)            — insaan: aurat 165-255 Hz, aadmi 85-155, bachcha 250-400
  • jitter (sur ka kaanp) — insaan 0.14-0.5 %
  • shimmer (zor ka kaanp)— insaan 1.6-3.3 %
  • HNR (saafai)         — insaan 20-26 dB
  • raftaar              — kahani 2.8-4.5 shabd-jaisa/sek
  • rukna                — 15-60 ruk / minute, koi ruk 1.5s se lambi nahi
  • jhatke (clicks)      — 0-5
  • clipping             — peak < 0.99, khaali hissa < 25%

  python tools/voice_checker.py --file out.mp3
  python tools/voice_checker.py --audit-dir /scratch/output --md
  python tools/voice_checker.py --loop 3        # 3 baar khud jaanch (sudhaar ke baad)
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
K = ROOT / "knowledge"
REPORT = K / "voice-check-report.json"
BASELINE = K / "voice-baseline.json"

NORM = {
    "jitter": (0.14, 0.5, 1.2),      # (achha min, achha max, bardasht)
    "shimmer": (1.6, 3.3, 6.0),
    "hnr": (20.0, 26.0, 15.0),
    "rate": (2.8, 4.5, 5.5),
    "pause_per_min": (15, 60, 90),
    "max_pause": (0.0, 1.5, 2.5),
    "clicks": (0, 5, 20),
    "peak": (0.0, 0.99, 1.0),
}

# asli insaan ki connected speech se seekha hua baseline (agar bana ho)
if BASELINE.exists():
    try:
        _n = json.loads(BASELINE.read_text(encoding="utf-8")).get("norms")
        if _n:
            NORM.update({k: tuple(v) for k, v in _n.items()})
    except Exception:
        pass


def load(path, sr=24000):
    import ffbin
    ff = ffbin.ensure() or "ffmpeg"
    raw = subprocess.run([ff, "-v", "quiet", "-i", str(path), "-f", "f32le",
                          "-ac", "1", "-ar", str(sr), "-"], capture_output=True).stdout
    if len(raw) < sr // 2:
        return None, sr
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64), sr


def measure(path):
    x, sr = load(path)
    if x is None:
        return {"ok": False, "why": "audio padhi nahi ja saki"}
    peak_raw = float(np.max(np.abs(x))) if len(x) else 0.0
    x = x / (peak_raw + 1e-9)
    out = {"file": Path(path).name, "ok": True, "sec": round(len(x) / sr, 1),
           "peak": round(peak_raw, 3)}
    # sur + jitter/shimmer/HNR (praat)
    try:
        import parselmouth
        from parselmouth.praat import call
        # Praat har format nahi padhta (ogg/webm) — pehle wav me badlo
        import tempfile, subprocess as _sp
        import ffbin as _fb
        _ff = _fb.ensure() or "ffmpeg"
        _td = tempfile.mkdtemp()
        _w = Path(_td) / "a.wav"
        _sp.run([_ff, "-v", "quiet", "-y", "-i", str(path), "-ac", "1", "-ar", "24000", str(_w)],
                capture_output=True)
        snd = parselmouth.Sound(str(_w) if _w.exists() else str(path))
        pp = call(snd, "To PointProcess (periodic, cc)", 70, 450)
        out["jitter"] = round(call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3) * 100, 2)
        out["shimmer"] = round(call([snd, pp], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6) * 100, 2)
        h = call(snd, "To Harmonicity (cc)", 0.01, 70, 0.1, 1.0)
        out["hnr"] = round(call(h, "Get mean", 0, 0), 1)
        pitch = snd.to_pitch()
        out["f0"] = round(call(pitch, "Get mean", 0, 0, "Hertz"), 1)
    except Exception as e:
        out["praat_error"] = type(e).__name__
    # raftaar / rukna / jhatke
    n = int(0.02 * sr)
    e = np.array([np.sqrt((x[i:i + n] ** 2).mean()) for i in range(0, max(1, len(x) - n), n)])
    thr = 0.10 * (np.percentile(e, 95) + 1e-9)
    voiced = e > thr
    out["voiced"] = round(float(voiced.mean()), 2)
    from scipy.signal import find_peaks
    pk, _ = find_peaks(e, height=thr, distance=6)
    out["rate"] = round(len(pk) / (len(x) / sr), 2)
    runs, run = [], 0
    for v in voiced:
        if not v:
            run += 1
        else:
            if run:
                runs.append(run * 0.02)
            run = 0
    if run:
        runs.append(run * 0.02)
    runs_big = [r for r in runs if r >= 0.15]        # micro-gap ko rukna nahi maante
    out["pause_per_min"] = round(len(runs_big) / max(1e-6, len(x) / sr / 60), 1)
    out["max_pause"] = round(max(runs_big) if runs_big else 0.0, 2)
    # jhatke: high-pass ke baad akele, bahut tez impulse (speech transient nahi)
    from scipy import signal as ss
    k = max(3, int(0.005 * sr))
    hp = x - ss.savgol_filter(x, 2 * k + 1 if 2 * k + 1 < len(x) else len(x) - 1, 2)
    sd = float(np.std(hp)) + 1e-9
    imp = np.abs(hp) > 8 * sd
    # akele impulse (aas-paas 5ms me kuch nahi)
    cnt = 0
    idx = np.flatnonzero(imp)
    if len(idx):
        gaps = np.diff(idx)
        cnt = int(np.sum(gaps > k) + 1) if len(idx) else 0
    out["clicks"] = cnt

    return out


def judge(m):
    """Har naap ko theek / dhyan / kharab me baanto (insaan ke norm se)."""
    rows = []
    def add(name, val, norm, unit=""):
        lo, hi, tol = norm
        if name == "hnr":
            ok = val >= lo
            warn = val >= tol
        elif name in ("max_pause", "clicks", "peak"):
            ok = val <= hi
            warn = val <= tol
        else:
            ok = lo <= val <= hi
            warn = (lo * 0.7) <= val <= tol
        rows.append({"naam": name, "value": val, "insaan": f"{lo}-{hi}{unit}",
                     "verdict": "theek" if ok else ("dhyan do" if warn else "kharab")})
    if "jitter" in m: add("jitter", m["jitter"], NORM["jitter"], "%")
    if "shimmer" in m: add("shimmer", m["shimmer"], NORM["shimmer"], "%")
    if "hnr" in m: add("hnr", m["hnr"], NORM["hnr"], " dB")
    if "rate" in m: add("rate", m["rate"], NORM["rate"], "/s")
    if "pause_per_min" in m: add("pause_per_min", m["pause_per_min"], NORM["pause_per_min"], "/min")
    if "max_pause" in m: add("max_pause", m["max_pause"], NORM["max_pause"], "s")
    if "clicks" in m: add("clicks", m["clicks"], NORM["clicks"])
    if "peak" in m: add("peak", m["peak"], NORM["peak"])
    bad = [r for r in rows if r["verdict"] == "kharab"]
    warn = [r for r in rows if r["verdict"] == "dhyan do"]
    score = max(0, 100 - 18 * len(bad) - 7 * len(warn))
    return {"rows": rows, "score": score,
            "verdict": "PASS" if not bad and score >= 75 else ("SUDHAAR" if score >= 45 else "FAIL")}


def show(m, j):
    print(f"\n=== {m['file']} ({m.get('sec')}s) — score {j['score']}/100 → {j['verdict']}")
    for r in j["rows"]:
        mark = {"theek": "OK ", "dhyan do": "~~ ", "kharab": "XX "}[r["verdict"]]
        print(f"  {mark} {r['naam']:<14} {r['value']:>8} (insaan {r['insaan']})")


def learn_baseline(files):
    """Asli recordings se baseline naapo — phir wahi hamare audio ka paimana hai.

    (Sustained-vowel ke norm connected speech par lagana galat tha — isliye apne hi
    asli clips se seekhte hain.)
    """
    rows = []
    for f in files:
        m = measure(f)
        if m.get("ok") and m.get("jitter") is not None:
            rows.append(m)
    if not rows:
        print("koi asli clip naapi nahi gayi"); return 1
    med = lambda k: float(np.median([r[k] for r in rows]))
    norms = {
        "jitter": [round(med("jitter") * 0.6, 2), round(med("jitter") * 1.4, 2), round(med("jitter") * 2.0, 2)],
        "shimmer": [round(med("shimmer") * 0.6, 2), round(med("shimmer") * 1.4, 2), round(med("shimmer") * 2.0, 2)],
        "hnr": [round(med("hnr") * 0.85, 1), round(med("hnr") * 1.3, 1), round(med("hnr") * 0.7, 1)],
        "rate": [2.8, 4.5, 5.5],
        "pause_per_min": [15, 60, 90],
        "max_pause": [0.0, 1.5, 2.5],
        "clicks": [0, 5, 20],
        "peak": [0.0, 0.99, 1.0],
    }
    BASELINE.write_text(json.dumps({"clips": len(rows), "norms": norms,
                                    "source": [r["file"] for r in rows]},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("baseline bana:", json.dumps(norms, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--audit-dir", default="")
    ap.add_argument("--loop", type=int, default=1)
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--learn-baseline", default="")
    a = ap.parse_args()
    if a.learn_baseline:
        fs = [p for p in Path(a.learn_baseline).glob("*")
              if p.suffix.lower() in (".ogg", ".mp3", ".wav", ".ogx", ".oga")]
        return learn_baseline(fs[:12])
    files = []
    if a.file:
        files = [Path(a.file)]
    elif a.audit_dir:
        files = sorted([p for p in Path(a.audit_dir).glob("*.mp3")] +
                       [p for p in Path(a.audit_dir).glob("*.wav")])
    else:
        print("kuch do: --file ya --audit-dir"); return 0
    allrows = []
    for _ in range(max(1, a.loop)):
        for f in files:
            m = measure(f)
            if not m.get("ok"):
                print("XX", f.name, m.get("why")); continue
            j = judge(m)
            show(m, j)
            allrows.append({"measure": m, "judge": j})
        REPORT.write_text(json.dumps(allrows, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = sum(1 for r in allrows if r["judge"]["verdict"] == "FAIL")
    print(f"\n{len(allrows)} file jaanchi | FAIL {bad} | report: {REPORT}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
