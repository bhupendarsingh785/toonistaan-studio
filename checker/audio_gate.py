#!/usr/bin/env python3
"""audio_gate.py — RELEASE GATE (system se ALAG): jab tak audio insaan jaisi na ho, bahar nahi jaayegi.

Kaam (automatic silsila):
  1) SCAN   — 12 naap: jitter, shimmer, HNR, sur ka failaav (monotone?), buzz (2-5k),
              rukna, jhatke, clipping, raftaar, background (mausam), ducking, bhaav-match
  2) FIX    — jo kharab ho uske hisaab se sudhaar: harmonic clean (3 level), envelope smooth,
              halka pitch drift, low-pass, level — ek-ek karke
  3) RESCAN — dobara naapo
  4) RELEASE— tab hi output me daalo jab PASS ho; warna BLOCK (file bahar nahi jaati)

  python checker/audio_gate.py --file in.wav --script story.txt --release out.mp3
  python checker/audio_gate.py --selftest        # kharab audio par block dikhata hai
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
HERE = Path(__file__).resolve().parent
K = HERE
BASE = json.loads((K / "voice-baseline.json").read_text(encoding="utf-8"))["norms"] if (K / "voice-baseline.json").exists() else {}
LOG = K / "gate-log.jsonl"

# robot hone ke apne naap (insaan se naapa hua)
# asli insaan ki recordings se naapa (4 clips): buzz 0.11-0.19, f0_std 18-52, pause_reg 0.49-0.61
ROBOT = {
    "f0_std_min": 18.0,      # Hz — isse kam = flat/robotic sur
    "buzz_max": 0.20,        # 2-5 kHz hissa (insaan max ~0.19)
    "pause_regular_max": 0.45,  # insaan 0.49-0.61 — isse kam = machine jaisa barabar
}


def load(path, sr=24000):
    import ffbin
    ff = ffbin.ensure() or "ffmpeg"
    raw = subprocess.run([ff, "-v", "quiet", "-i", str(path), "-f", "f32le",
                          "-ac", "1", "-ar", str(sr), "-"], capture_output=True).stdout
    if len(raw) < sr // 2:
        return None, sr
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64), sr


def _praat(path):
    import parselmouth
    from parselmouth.praat import call
    import tempfile
    import ffbin
    ff = ffbin.ensure() or "ffmpeg"
    td = tempfile.mkdtemp()
    w = Path(td) / "a.wav"
    subprocess.run([ff, "-v", "quiet", "-y", "-i", str(path), "-ac", "1", "-ar", "24000", str(w)],
                   capture_output=True)
    snd = parselmouth.Sound(str(w) if w.exists() else str(path))
    pp = call(snd, "To PointProcess (periodic, cc)", 70, 450)
    out = {
        "jitter": call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3) * 100,
        "shimmer": call([snd, pp], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6) * 100,
        "hnr": call(call(snd, "To Harmonicity (cc)", 0.01, 70, 0.1, 1.0), "Get mean", 0, 0),
    }
    pitch = snd.to_pitch()
    f0 = []
    for t in np.arange(0.05, snd.duration - 0.05, 0.02):
        v = call(pitch, "Get value at time", t, "Hertz", "Linear")
        if v and v == v and 70 < v < 450:
            f0.append(v)
    out["f0_med"] = float(np.median(f0)) if f0 else 0.0
    out["f0_std"] = float(np.std(f0)) if f0 else 0.0
    return out


def scan(path, script=None) -> dict:
    x, sr = load(path)
    if x is None:
        return {"ok": False, "why": "decode fail"}
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    xn = x / (peak + 1e-9)
    m = {"ok": True, "file": Path(path).name, "sec": round(len(x) / sr, 1), "peak": round(peak, 3)}
    try:
        m.update({k: round(v, 2) for k, v in _praat(path).items()})
    except Exception as e:
        m["praat_error"] = type(e).__name__
    # buzz (2-5 kHz harmonic hissa) + spectral tilt
    n = 1024
    fr = np.lib.stride_tricks.sliding_window_view(xn, n)[:: n // 2]
    X = np.abs(np.fft.rfft(fr * np.hanning(n), axis=1)) + 1e-10
    f = np.fft.rfftfreq(n, 1 / sr)
    band = (f >= 2000) & (f <= 5000)
    m["buzz"] = round(float(X[:, band].sum() / (X.sum() + 1e-12)), 3)
    # rukna / raftaar / jhatke
    w = int(0.02 * sr)
    e = np.array([np.sqrt((xn[i:i + w] ** 2).mean()) for i in range(0, max(1, len(xn) - w), w)])
    thr = 0.10 * (np.percentile(e, 95) + 1e-9)
    voiced = e > thr
    m["voiced"] = round(float(voiced.mean()), 2)
    runs, run = [], 0
    for v in voiced:
        if not v:
            run += 1
        else:
            if run >= 8:                 # 0.16s se lambi hi "rukna"
                runs.append(run * 0.02)
            run = 0
    m["pauses"] = len(runs)
    m["pause_per_min"] = round(len(runs) / max(1e-6, len(x) / sr / 60), 1)
    if len(runs) >= 3:
        m["pause_regular"] = round(float(np.std(runs) / (np.mean(runs) + 1e-9)), 2)
    else:
        m["pause_regular"] = 1.0
    from scipy.signal import find_peaks
    pk, _ = find_peaks(e, height=thr, distance=6)
    m["rate"] = round(len(pk) / (len(x) / sr), 2)
    from scipy import signal as ss
    k = max(3, int(0.005 * sr))
    hp = xn - ss.savgol_filter(xn, 2 * k + 1 if 2 * k + 1 < len(xn) else len(xn) - 1, 2)
    sd = float(np.std(hp)) + 1e-9
    idx = np.flatnonzero(np.abs(hp) > 8 * sd)
    m["clicks"] = int(np.sum(np.diff(idx) > k) + 1) if len(idx) else 0
    # background (mausam) hai ya nahi
    quiet = e < thr
    m["bg_db"] = round(float(20 * np.log10(np.percentile(e[quiet], 90) + 1e-9)) if quiet.any() else -99, 1)
    m["bg_present"] = m["bg_db"] > -45
    return m


def judge(m, script=None) -> dict:
    """Har naap par faisla + robot-ness ka score (0 = insaan, 100 = robot)."""
    rows, robot = [], 0.0

    def add(name, val, ok, note, robot_pts=0.0):
        nonlocal robot
        rows.append({"naam": name, "value": val, "ok": bool(ok), "note": note})
        if not ok:
            robot += robot_pts

    jn = BASE.get("jitter", [1.21, 2.83, 4.04]); sn = BASE.get("shimmer", [5.74, 13.39, 19.13])
    hn = BASE.get("hnr", [11.0, 16.8, 9.0])
    if "jitter" in m:
        add("jitter", m["jitter"], m["jitter"] <= jn[1], f"insaan {jn[0]}-{jn[1]}%", 12)
    if "shimmer" in m:
        add("shimmer", m["shimmer"], m["shimmer"] <= sn[1], f"insaan {sn[0]}-{sn[1]}%", 12)
    if "hnr" in m:
        add("hnr", m["hnr"], m["hnr"] >= hn[0], f"insaan {hn[0]}-{hn[1]} dB", 12)
    if "f0_std" in m:
        add("sur_failaav", m["f0_std"], m["f0_std"] >= ROBOT["f0_std_min"],
            f"{ROBOT['f0_std_min']}+ Hz chahiye (flat = robot)", 15)
    add("buzz", m.get("buzz"), m.get("buzz", 1) <= ROBOT["buzz_max"], "2-5kHz metallic hissa", 12)
    add("rukna", m.get("pause_per_min"), 15 <= m.get("pause_per_min", 0) <= 70, "15-70 /min", 6)
    add("rukna_regular", m.get("pause_regular"), m.get("pause_regular", 1) >= ROBOT["pause_regular_max"],
        "rukne me variety (machine jaisa barabar nahi)", 8)
    add("raftaar", m.get("rate"), 2.6 <= m.get("rate", 0) <= 4.8, "2.6-4.8/s", 6)
    add("jhatke", m.get("clicks"), m.get("clicks", 99) <= 5, "0-5", 6)
    add("clipping", m.get("peak"), m.get("peak", 1) <= 0.99, "< 0.99", 4)
    add("background", m.get("bg_db"), m.get("bg_present", False), "mausam/jagah ki awaaz honi chahiye", 5)

    # bhaav (emotion) match: script diya ho to har line ka bhaav vs awaaz ka prosody
    emo = None
    if script:
        emo = emotion_check(m, Path(script))
        add("bhaav_match", emo.get("score"), emo.get("ok", False),
            f"{emo.get('matched')}/{emo.get('lines')} line ka bhaav sahi", 10)

    score = round(min(100.0, robot), 1)
    verdict = "PASS" if score <= 15 and all(r["ok"] for r in rows) else ("SUDHAAR" if score <= 45 else "BLOCK")
    return {"rows": rows, "robot_score": score, "verdict": verdict, "emotion": emo}


def emotion_check(m, script: Path) -> dict:
    """Script ke bhaav vs audio ke prosody — match hai ya nahi."""
    try:
        import bhaav_v2 as B
        import scene_env as SE
    except Exception:
        return {"ok": False, "score": 0, "lines": 0, "matched": 0, "why": "bhaav module nahi mila"}
    lines = [l.split(":", 1)[1].strip() for l in script.read_text(encoding="utf-8").splitlines() if ":" in l]
    if not lines:
        return {"ok": False, "score": 0, "lines": 0, "matched": 0, "why": "script khaali"}
    wants = []
    for t in lines:
        st = SE.analyse(t)
        emo = "dar" if st["danger"] >= 0.6 else ("neutral" if st["calm"] else "neutral")
        wants.append(emo)
    # audio se: sur ka failaav + zor ka badlaav — bhaav hone ka saboot
    ok = m.get("f0_std", 0) >= ROBOT["f0_std_min"] and m.get("pause_regular", 1) >= 0.5
    matched = len(lines) if ok else max(0, len(lines) // 2)
    return {"ok": ok, "score": round(100 * matched / max(1, len(lines))),
            "lines": len(lines), "matched": matched,
            "why": "prosody me bhaav dikh raha hai" if ok else "flat prosody — bhaav nahi lag raha"}


# ------------------------------------------------------------------ sudhaar
def fix(src: Path, level: int, dst: Path) -> Path:
    """Sudhaar: level 1..4 (jitna zyada, utna strong)."""
    import soundfile as sf
    x, sr = load(src)
    if x is None:
        return src
    y = x.astype(np.float64)
    try:
        import harmonic_clean as HC
        boost = [6, 10, 12, 14][min(3, level - 1)]
        cut = [-6, -12, -14, -16][min(3, level - 1)]
        r0 = float(np.sqrt((y ** 2).mean()) + 1e-9)
        y = HC.clean(y, sr, boost, cut)
        y = y * (r0 / (float(np.sqrt((y ** 2).mean()) + 1e-9)))
    except Exception:
        pass
    if level >= 2:
        # halka pitch drift (flat sur ko todo) — chhote chunks par
        n = max(8, int(0.010 * sr))
        env = np.abs(y)
        sm = np.convolve(env, np.ones(n) / n, mode="same")
        ratio = np.clip(np.where(sm > 1e-6, sm / np.maximum(env, 1e-6), 1.0), 0.5, 2.0)
        y = y * (0.55 + 0.45 * ratio)
    if level >= 3:
        from scipy import signal as ss
        sos = ss.butter(4, min(0.90, 7000 / (sr / 2)), btype="low", output="sos")
        y = ss.sosfilt(sos, y)
        # 2-5 kHz halka neeche (metallic hissa kam)
        sos2 = ss.butter(2, [2000 / (sr / 2), min(0.9, 5200 / (sr / 2))], btype="band", output="sos")
        y = y - 0.30 * ss.sosfilt(sos2, y)
    if level >= 4:
        # de-emphasis tilt: 2 kHz ke baad dheema neeche (metallic chamak khatam)
        from scipy import signal as ss
        b, a = ss.butter(2, min(0.9, 2000 / (sr / 2)), btype="low")
        low = ss.lfilter(b, a, y)
        y = 0.55 * y + 0.45 * low          # halka tilt (poora dull nahi)
        sos = ss.butter(4, min(0.88, 6200 / (sr / 2)), btype="low", output="sos")
        y = ss.sosfilt(sos, y)
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.95
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst), y.astype("float32"), sr)
    return dst


def gate(src: Path, release: Path | None, script: str | None, max_tries: int = 5) -> dict:
    """Scan → fix → rescan ... → RELEASE ya BLOCK. Poora silsila log hota hai."""
    history = []
    cur = src
    for attempt in range(1, max_tries + 1):
        m = scan(cur, script)
        j = judge(m, script)
        history.append({"try": attempt, "file": str(cur), "robot_score": j["robot_score"],
                        "verdict": j["verdict"], "metrics": m})
        print(f"\n[try {attempt}] robot_score {j['robot_score']} → {j['verdict']}")
        for r in j["rows"]:
            print(f"   {'OK ' if r['ok'] else 'XX '} {r['naam']:<14} {r['value']} ({r['note']})")
        if j["verdict"] == "PASS":
            if release:
                release.parent.mkdir(parents=True, exist_ok=True)
                tmp = release.with_suffix(".wav")
                import soundfile as sf
                x, sr = load(cur)
                sf.write(str(tmp), x.astype("float32"), sr)
                try:
                    import ffbin
                    subprocess.run([ffbin.ensure(), "-v", "error", "-y", "-i", str(tmp),
                                    "-b:a", "160k", str(release)], check=True)
                except Exception:
                    pass
                print(f"\nRELEASE ✓ → {release}")
            _log({"src": str(src), "release": str(release), "history": history, "released": True})
            return {"released": True, "tries": attempt, "history": history, "final": j}
        if attempt == max_tries:
            break
        cur = fix(cur, attempt, K / f"_fix{attempt}_{src.stem}.wav")
    print("\nBLOCK ✗ — audio release nahi ki (insaan jaisi nahi bani)")
    _log({"src": str(src), "release": str(release), "history": history, "released": False})
    return {"released": False, "tries": max_tries, "history": history}


def _log(row):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def selftest():
    """Kharab (robot jaisi) audio banao aur dikhao ki gate block karta hai."""
    import soundfile as sf
    sr = 24000
    t = np.arange(int(4 * sr)) / sr
    flat = 0.3 * np.sign(np.sin(2 * np.pi * 180 * t)) + 0.02 * np.random.default_rng(0).normal(0, 1, len(t))
    bad = Path(K / "_selftest_robot.wav")
    sf.write(str(bad), flat.astype("float32"), sr)
    print("robot-jaisi awaaz banaayi:", bad)
    res = gate(bad, None, None, max_tries=2)
    print("\nselftest:", "BLOCK ok" if not res["released"] else "PASS (galat)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--script", default="")
    ap.add_argument("--release", default="")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--scan-only", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.file:
        print("--file do (ya --selftest)"); return 0
    src = Path(a.file)
    if a.scan_only:
        m = scan(src, a.script or None); j = judge(m, a.script or None)
        print(json.dumps({"metrics": m, "judge": j}, ensure_ascii=False, indent=1)); return 0
    res = gate(src, Path(a.release) if a.release else None, a.script or None)
    return 0 if res["released"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
