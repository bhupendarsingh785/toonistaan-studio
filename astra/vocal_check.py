#!/usr/bin/env python3
"""
ASTRA — Vocal Check: render ke baad awaaz ki jaanch (bina torch, pitch-based).

Kaam: cues.json se har kirdaar ki lines ka hissa nikaal kar **pitch** naapta hai
(sabse bharosemand cheez jo insaan sun kar bhi pehchanta hai), phir:
  1. Do alag kirdaar ki pitch **bahut paas** ho to shak (same lagenge)
  2. Ek hi kirdaar ki pitch me bahut zyada utar-chadhav ho to shak

Sach: ye identity nahi batata, sirf naap hai. Threshold asli render par calibrate kiya gaya.

Chalao:
  python3 astra/vocal_check.py kahani.mp3 kahani.cues.json
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PITCH_CLOSE_HZ = 8.0      # itne paas = same lagenge (calibrated)
PITCH_SPREAD_LIMIT = 90.0 # ek kirdaar ke andar itna se zyada range = shak


def _lines(cues):
    out = []
    for sc in cues.get("scenes", []):
        for c in sc.get("cues", []):
            if c.get("type") != "dialogue":
                continue
            who = c.get("who") or c.get("kirdaar")
            st = float(c.get("start", 0))
            du = float(c.get("dur", 1.0))
            if who and du >= 0.4:
                out.append((who, st, min(du, 6.0)))
    return out


def _pitch_of(audio, start, dur):
    import vocal_light as VL
    cmd = [VL.ff(), "-loglevel", "error", "-ss", f"{max(0.0, start):.2f}",
           "-t", f"{max(0.3, dur):.2f}", "-i", audio, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        return None
    x = np.frombuffer(r.stdout, dtype=np.float32)
    if len(x) < 8000:
        return None
    p = VL.pitch_track(x)
    pv = p[(p > 60) & (p < 400)]
    if len(pv) < 5:
        return None
    return float(np.median(pv)), float(np.percentile(pv, 90) - np.percentile(pv, 10))


def check(audio_path, cues_path=None, cues=None, verbose=True):
    if cues is None:
        if not cues_path or not os.path.exists(cues_path):
            return {"ok": False, "reason": "cues nahi mile"}
        cues = json.load(open(cues_path, encoding="utf-8"))
    lines = _lines(cues)
    if not lines:
        return {"ok": False, "reason": "cues me dialogue nahi mila"}

    per = {}
    for who, st, du in lines:
        r = _pitch_of(audio_path, st, du)
        if r:
            per.setdefault(who, []).append(r)
    if not per:
        return {"ok": False, "reason": "pitch naap nahi paya"}

    med = {k: float(np.median([x[0] for x in v])) for k, v in per.items()}
    spread = {k: float(np.median([x[1] for x in v])) for k, v in per.items()}

    close = []
    ks = sorted(med)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            d = abs(med[ks[i]] - med[ks[j]])
            if d < PITCH_CLOSE_HZ:
                close.append({"a": ks[i], "b": ks[j], "pitch_diff_hz": round(d, 1),
                              "pitch_a": round(med[ks[i]], 1), "pitch_b": round(med[ks[j]], 1)})
    wide = [{"kirdaar": k, "pitch_range_hz": round(v, 1)} for k, v in spread.items()
            if v > PITCH_SPREAD_LIMIT]

    ok = not close
    rep = {
        "ok": ok,
        "audio": os.path.basename(audio_path),
        "characters": len(med),
        "lines_checked": len(lines),
        "pitch_per_character": {k: round(v, 1) for k, v in sorted(med.items())},
        "too_close_pairs": close,
        "wide_pitch_characters": wide,
        "verdict": "PASS" if ok else f"SHAK: {len(close)} jodi ki pitch bahut paas",
        "note": f"pitch {PITCH_CLOSE_HZ} Hz se kam farak = same lagenge. Sirf naap hai.",
    }
    if verbose:
        print("VOCAL_CHECK", rep["verdict"], "| kirdaar", rep["characters"],
              "| paas jodi", len(close), flush=True)
        for c in close[:6]:
            print(f"   SHAK {c['a']} ({c['pitch_a']}Hz) ~ {c['b']} ({c['pitch_b']}Hz)", flush=True)
    return rep


def main():
    if len(sys.argv) < 3:
        print("usage: vocal_check.py <audio> <cues.json>")
        return 1
    rep = check(sys.argv[1], sys.argv[2])
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
