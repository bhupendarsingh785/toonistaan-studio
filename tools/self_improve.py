#!/usr/bin/env python3
"""self_improve.py — audio se seekha hua loop: fail padho -> upay nikalo -> naapo -> yaad rakho.

Chaina (China ke research paper wale system jaisa, par hamare audio ke liye):
  1. PADHO   : plan.json / qa json / marks — kya fail hua (CER, harsh, level, holes)
  2. SOCHO   : rulebook se upay (kaunsa parameter, kitna)
  3. NAAPO   : upay ka asar (pehle/baad ke numbers)
  4. YAAD    : knowledge/improve-log.jsonl me likho (agla render inhe pehle dekhe)

  python tools/self_improve.py --plan /scratch/work/drama/plan.json --ref /scratch/work/ref_china.wav
"""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path
import numpy as np

KN = Path(__file__).resolve().parent.parent / "knowledge"
SR = 16000

# rulebook: (naam, condition, upay)
RULES = [
    ("harsh_high",  "harsh > 0.70",            "female: 3.2k par -3 dB, 6.2k par -2 dB, 250 Hz +1.5 dB"),
    ("mod_low",     "mod < 0.55",              "amplitude micro: 4.3 Hz 7% + 2.1 Hz 4%"),
    ("cer_high",    "CER > 0.25",              "shabd sadha roop (nukta/chandrabindu hatao) + PSOLA_DEPTH 0"),
    ("level_low",   "voice < bed+6 dB",        "bed ko -8 dB par le aao (voice dominant)"),
    ("peak_hot",    "peak > 0.95",             "master me volume 0.78 + alimiter 0.80"),
    ("f0_flat",     "F0std < 5 st (ek line)",  "prosody curve depth 1.6x + Praat curve"),
]


def load(p):
    from imageio_ffmpeg import get_ffmpeg_exe
    raw = subprocess.run([get_ffmpeg_exe(), "-v", "quiet", "-i", str(p), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def measure(p):
    x = load(p)
    if not len(x): return {}
    n = min(len(x), SR * 15)
    S = np.abs(np.fft.rfft(x[:n] * np.hanning(n))); f = np.fft.rfftfreq(n, 1 / SR)
    harsh = float(S[(f >= 2000) & (f < 4500)].sum() / (S[(f >= 800) & (f < 2000)].sum() + 1e-9))
    k = 800; env = np.array([np.sqrt((x[i:i + k] ** 2).mean()) for i in range(0, len(x) - k, k)])
    mod = float(np.std(np.diff(env)) / (np.mean(env) + 1e-9))
    f0 = []
    for i in range(0, len(x) - 640, 160):
        fr = x[i:i + 640]
        if float(np.sqrt((fr ** 2).mean())) < 0.01: continue
        fr = fr - fr.mean(); ac = np.correlate(fr, fr, "full")[639:]
        lo, hi = int(SR / 450), int(SR / 70); seg = ac[lo:hi]
        if not len(seg): continue
        lag = lo + int(np.argmax(seg))
        if ac[lag] > 0.3 * ac[0]: f0.append(SR / lag)
    f0 = np.array(f0) if len(f0) else np.array([1.0])
    st = 12 * np.log2(f0 / np.median(f0))
    return {"harsh": round(harsh, 2), "mod": round(mod, 3), "f0_std": round(float(st.std()), 2),
            "f0_med": round(float(np.median(f0))), "peak": round(float(np.abs(x).max()), 2),
            "rms_db": round(float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9)), 1)}


def propose(m):
    out = []
    if m.get("harsh", 0) > 0.70: out.append(RULES[0][2])
    if m.get("mod", 1) < 0.55: out.append(RULES[1][2])
    if m.get("f0_std", 9) < 5: out.append(RULES[5][2])
    if m.get("peak", 0) > 0.95: out.append(RULES[4][2])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", action="append", default=[])
    ap.add_argument("--ref", default=None)
    ap.add_argument("--log", default=str(KN / "improve-log.jsonl"))
    a = ap.parse_args()
    rows = []
    if a.ref:
        m = measure(a.ref)
        rows.append({"kind": "reference", "file": Path(a.ref).name, "naap": m, "upay": []})
        print("REF:", m)
    for p in a.audio:
        m = measure(p); up = propose(m)
        rows.append({"kind": "ours", "file": Path(p).name, "naap": m, "upay": up})
        print(Path(p).name, m, "→", up)
    KN.mkdir(parents=True, exist_ok=True)
    with open(a.log, "a", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("log:", a.log)


if __name__ == "__main__":
    main()
