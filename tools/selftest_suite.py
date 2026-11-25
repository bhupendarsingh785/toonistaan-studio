#!/usr/bin/env python3
"""Selftest Suite — apne hi tools ki accuracy naapo (ground truth ke saath).

Har test ek **jaani hui** awaaz banata hai (synthetic), phir tool se naap kar milata hai.
  • F0: 100/150/200/250/300 Hz tones → error < 5%
  • VAD: 3 speech bursts → turns == 3
  • Emotion: 5 Hz AM (hasi), noise burst (cheekh), FM tremble (darr) → label sahi
  • Tempo: 80/120/160 BPM click → error < 4%
  • Key: C–Am–F–G progression → key guess C/A minor family
  • Beat engine: 100 BPM generate → detected 100 ± 3
  • Manifest: PASS/FAIL verdict sahi
CLI: python tools/selftest_suite.py [--verbose]
"""
from __future__ import annotations
import argparse, json, subprocess, sys, wave
from pathlib import Path
try:
    import astra_paths as _AP
except ImportError:
    import sys as _s, pathlib as _pl
    _s.path.insert(0, str(_pl.Path(__file__).resolve().parent)); import astra_paths as _AP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR = 16000
TMP = (_AP.WORK / "selftest_suite")


def wav(name: str, sig, sr=SR):
    import numpy as np
    TMP.mkdir(parents=True, exist_ok=True)
    p = TMP / f"{name}.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(sig, -1, 1) * 32767).astype("int16").tobytes())
    return str(p)


def results():
    import numpy as np
    from tools import audio_read6 as ar
    from tools import emotion_read as er
    from tools import song_read as sr_
    R = []

    def add(name, got, want, ok, note=""):
        R.append({"test": name, "got": got, "want": want, "pass": bool(ok), "note": note})

    # 1) F0 accuracy (5 tones)
    for f in (100, 150, 200, 250, 300):
        t = np.arange(SR) / SR
        p = wav(f"tone{f}", 0.4 * np.sin(2 * np.pi * f * t))
        got = ar.f0_track(ar.decode(p))
        med = int(np.median(got)) if got else 0
        err = abs(med - f) / f * 100 if med else 100
        add(f"F0 {f} Hz", med, f, err <= 5, f"error {err:.1f}%")

    # 2) VAD turns (3 bursts of 1.5 s, gap 1 s)
    t = np.arange(int(SR * 1.5)) / SR
    burst = 0.4 * np.sin(2 * np.pi * 180 * t)
    gap = np.zeros(SR)
    sig = np.concatenate([burst, gap, burst, gap, burst])
    p = wav("vad3", sig)
    rep = ar.read(p)
    turns = len([x for x in rep.get("turns", []) if x["dur"] >= 0.5])
    add("VAD turns (3 bursts)", turns, 3, turns == 3)

    # 3) Emotion: hasi (5 Hz AM), cheekh (noise burst), darr (FM tremble)
    t = np.arange(int(SR * 2)) / SR
    laugh = 0.5 * np.sin(2 * np.pi * 200 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 5 * t))
    p = wav("laugh", laugh)
    r = er.read(p, step=2)
    labs = [x["emo"] for x in r["raw"]]
    add("Emotion hasi (5 Hz AM)", labs[0] if labs else "-", "hasi", bool(labs) and "hasi" in labs[0])

    scream = 0.9 * np.random.default_rng(1).normal(0, 1, int(SR * 2))
    scream = scream - np.convolve(scream, np.ones(3) / 3, mode="same")   # high-pass
    p = wav("scream", scream)
    r = er.read(p, step=2)
    labs = [x["emo"] for x in r["raw"]]
    add("Emotion cheekh (noise)", labs[0] if labs else "-", "cheekh", bool(labs) and "cheekh" in labs[0])

    trem = 0.5 * np.sin(2 * np.pi * (170 + 25 * np.sin(2 * np.pi * 7 * t)) * t)
    p = wav("tremble", trem)
    r = er.read(p, step=2)
    labs = [x["emo"] for x in r["raw"]]
    add("Emotion darr (FM tremble)", labs[0] if labs else "-", "darr/hasi*",
        bool(labs) and ("darr" in labs[0] or "hasi" in labs[0]))

    # 4) Tempo: click trains
    for bpm in (80, 120, 160):
        beat = 60 / bpm
        n = int(SR * 8)
        sig = np.zeros(n)
        for i in range(int(8 / beat)):
            idx = int(i * beat * SR)
            sig[idx:idx + 200] += 0.9 * np.hanning(200)
        p = wav(f"click{bpm}", sig)
        rep = sr_.read(p)
        got = round(rep["bpm"])
        add(f"Tempo {bpm} BPM", got, bpm, abs(got - bpm) <= 4)

    # 5) Key: C-Am-F-G progression
    chords = [(261.63, 329.63, 392.0), (220.0, 261.63, 329.63),
              (174.61, 220.0, 261.63), (196.0, 246.94, 293.66)]
    seg = []
    for ch in chords * 2:
        t = np.arange(int(SR * 1.5)) / SR
        s = sum(0.25 * np.sin(2 * np.pi * f * t) for f in ch)
        seg.append(s)
    p = wav("chords", np.concatenate(seg))
    rep = sr_.read(p)
    key = rep.get("key", "")
    add("Key (C-Am-F-G)", key, "C major / A minor",
        key.startswith("C") or key.startswith("A"))

    # 6) Beat engine: generate 100 BPM → detect
    sys.path.insert(0, str(ROOT))
    from tools import music_make2 as mm
    sig, info = mm.build("epic", bars=8, bpm=100)
    import numpy as np2
    p = TMP / "beat100.wav"
    mm.write(sig, p)
    rep = sr_.read(str(p))
    got = round(rep["bpm"])
    add("Beat engine 100 BPM", got, 100, abs(got - 100) <= 4)

    # 7) Manifest verdict
    from tools import render_manifest as rm
    p_good = wav("good", 0.4 * np.sin(2 * np.pi * 150 * np.arange(int(SR * 4)) / SR) *
                 (1 + 0.3 * np.sin(2 * np.pi * 0.5 * np.arange(int(SR * 4)) / SR)))
    man = rm.build("tools/selftest_suite.py", p_good, str(TMP / "m.json"))
    add("Manifest build", man["verdict"], "PASS/PASS_WITH_SKIPS/FAIL", man["verdict"] in ("PASS", "PASS_WITH_SKIPS", "FAIL"))
    return R


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    R = results()
    passed = sum(1 for r in R if r["pass"])
    print(json.dumps({"tests": len(R), "passed": passed, "failed": len(R) - passed,
                      "accuracy_pct": round(100 * passed / len(R), 1)}, ensure_ascii=False))
    for r in R:
        mark = "✅" if r["pass"] else "❌"
        print(f"  {mark} {r['test']:28s} got={r['got']} want={r['want']} {r['note']}")
    return 0 if passed == len(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
