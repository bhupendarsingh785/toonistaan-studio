#!/usr/bin/env python3
"""
World QA — audio_judge.py ke saath chalne wale naye gate (PASS / WARN / FAIL).
Yeh woh cheezein pakadta hai jo kaan ko "nakli" lagti hain:
  holes      : background ka poori tarah band hona (asli duniya kabhi chup nahi)
  stereo     : mono = koi jagah/disha nahi
  pauses     : bina ruke bolna (vakya ke baad saans nahi)
  breathing  : lambe ruke (scene ko saans) — har minute kam se kam ek
  mud        : 300 Hz se neeche ka bhaaripan
  loudness   : YouTube/phone ke liye LUFS

python tools/world/world_qa.py --audio out.mp3 [--json qa.json]
"""
import argparse, json, subprocess, sys
import numpy as np

SR = 48000

def decode(p):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).reshape(-1, 2).T.astype(np.float64)

def lufs(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", p, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    s = e[e.rfind("Summary"):]
    for ln in s.splitlines():
        if ln.strip().startswith("I:"): return float(ln.split()[1])
    return None

def tri(v, ok, warn):
    lo, hi = ok
    if lo <= v <= hi: return "PASS"
    wl, wh = warn
    return "WARN" if wl <= v <= wh else "FAIL"

def judge(path):
    x = decode(path); m = x.mean(0); n = x.shape[1]; dur = n / SR
    hop = 240
    fr = np.lib.stride_tricks.sliding_window_view(np.pad(m, (0, 480)), 480)[::hop]
    d = 20 * np.log10(np.sqrt(np.mean(fr ** 2, 1)) + 1e-12)
    holes = float((d < -55).mean() * 100)
    mid, side = (x[0] + x[1]) / 2, (x[0] - x[1]) / 2
    width = float(np.sqrt(np.mean(side ** 2)) / (np.sqrt(np.mean(mid ** 2)) + 1e-12))
    # pauses: speech = loudest frames; gap = 14 dB below speech level (bed may continue)
    top = np.percentile(d, 90); sp = d > top - 14
    runs, i = [], 0
    while i < len(sp):
        if not sp[i]:
            j = i
            while j < len(sp) and not sp[j]: j += 1
            runs.append((j - i) * hop / SR); i = j
        else: i += 1
    g = np.array([r for r in runs if r >= 0.1]) if runs else np.zeros(1)
    import os
    side = os.path.splitext(path)[0] + ".pauses.json"
    src = "mix"
    if os.path.exists(side):   # duniya.py ka voice-stem naap (FX ruke ko bhar dete hain)
        g = np.array(json.load(open(side))["voice_gaps_s"] or [0]); src = "voice-stem"
    sent_pm = float((g >= 0.42).sum() / (dur / 60))
    breath_pm = float((g >= 1.0).sum() / (dur / 60))
    S = np.abs(np.fft.rfft(m[: min(n, SR * 120)])) ** 2; f = np.fft.rfftfreq(min(n, SR * 120), 1 / SR)
    mud = float(10 * np.log10(S[(f > 20) & (f < 300)].sum() / (S[(f >= 300) & (f < 4000)].sum() + 1e-12)))
    L = lufs(path)
    res = {
        "holes_pct":      {"value": round(holes, 2), "want": "< 0.5", "verdict": tri(holes, (0, 0.5), (0, 2))},
        "stereo_width":   {"value": round(width, 3), "want": "0.08–0.45", "verdict": tri(width, (0.08, 0.45), (0.04, 0.6))},
        "sentence_pauses_per_min": {"value": round(sent_pm, 1), "want": "≥ 8", "verdict": tri(sent_pm, (8, 60), (5, 60))},
        "breaths_per_min": {"value": round(breath_pm, 2), "want": "≥ 1", "verdict": tri(breath_pm, (1, 20), (0.5, 20))},
        "mud_db":         {"value": round(mud, 1), "want": "≤ -4 (low vs mid)", "verdict": tri(mud, (-40, -4), (-40, 0))},
        "lufs":           {"value": L, "want": "-16 ±1.5", "verdict": tri(L if L is not None else 0, (-17.5, -14.5), (-19, -13))},
        "duration_s":     round(dur, 1),
        "pauses_measured_on": src,
    }
    cues = os.path.splitext(path)[0] + ".cues.json"
    if os.path.exists(cues):                       # spotting: awaaz wale shabd jinki awaaz system ke paas nahi
        sh = (json.load(open(cues, encoding="utf-8")).get("sheet") or {})
        miss = len(sh.get("missing", []))
        res["missing_sounds"] = {"value": miss, "want": "0 (warna knowledge/missing-sounds.json dekho)", "verdict": "PASS" if miss == 0 else "WARN"}
    vs = [v["verdict"] for v in res.values() if isinstance(v, dict)]
    res["overall"] = "FAIL" if "FAIL" in vs else ("WARN" if "WARN" in vs else "PASS")
    return res

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--audio", nargs="+", required=True); ap.add_argument("--json")
    a = ap.parse_args()
    out = {p: judge(p) for p in a.audio}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if a.json: open(a.json, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
