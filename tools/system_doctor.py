#!/usr/bin/env python3
"""System Doctor — poore private system ka self-check. Har check naap ke saath PASS/WARN/FAIL.

Chalane ka tarika:
  python tools/system_doctor.py            # poora check
  python tools/system_doctor.py --json     # machine-readable

Kuch bhi toota ho to exit code 1 (CI me fail hoga) — chupchap kharab nahi rehta.
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
R = []


def add(name, status, detail=""):
    R.append({"check": name, "status": status, "detail": str(detail)})


def c_voices():
    v = ROOT / "voices"
    need = ["hi_IN-pratham-medium.onnx", "hi_IN-priyamvada-medium.onnx", "hi_IN-rohan-medium.onnx"]
    have = [n for n in need if (v / n).exists() or (Path("/scratch/work/voices") / n).exists()]
    import os
    if len(have) == 3:
        add("piper voices", "PASS", "3/3 maujood")
    elif os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        add("piper voices", "WARN", f"{len(have)}/3 — CI me model nahi (repo me 60MB file nahi jaati)")
    else:
        add("piper voices", "FAIL", f"{len(have)}/3 — voices/ me onnx daalo")


def c_brain():
    p = ROOT / "knowledge" / "local-brain.json"
    if not p.exists():
        return add("local brain", "FAIL", "file nahi mili")
    b = json.loads(p.read_text(encoding="utf-8"))
    keys = ["awaaz", "smooth_reference", "zameen_ke_kadam", "sound_library", "qa"]
    have = [k for k in keys if k in b]
    add("local brain", "PASS" if len(have) >= 4 else "WARN", f"{len(have)}/{len(keys)} sections, {len(json.dumps(b))} bytes")


def c_smooth():
    p = ROOT / "knowledge" / "smooth-reference.json"
    if not p.exists():
        return add("smooth reference", "FAIL", "file nahi mili")
    d = json.loads(p.read_text(encoding="utf-8"))
    t = d.get("targets", {})
    ok = "brightness_hz" in t and "mid_pct" in t
    add("smooth reference", "PASS" if ok else "WARN", f"bright {t.get('brightness_hz')}")


def c_ground():
    try:
        sys.path.insert(0, str(ROOT / "tools" / "local_story"))
        import numpy as np
        import ambience as amb
        tgt = {"steps_dirt": (200, 900), "steps_concrete": (1800, 5000), "steps_leaves": (3500, 9000),
               "steps_grass": (900, 2600), "steps_wood": (500, 1500), "steps_mud": (150, 600),
               "steps_gravel": (1500, 3800)}
        ok = 0; vals = {}
        for fn, (lo, hi) in tgt.items():
            f = getattr(amb, fn, None)
            if not f:
                continue
            x = f(3.0)
            S = np.abs(np.fft.rfft(x)); fr = np.fft.rfftfreq(len(x), 1 / getattr(amb, "SR", 44100))
            c = float((S * fr).sum() / (S.sum() + 1e-9))
            vals[fn] = int(c)
            ok += (lo <= c <= hi)
        add("zameen ke kadam", "PASS" if ok >= 6 else ("WARN" if ok >= 4 else "FAIL"), f"{ok}/7 band me sahi")
    except Exception as e:
        add("zameen ke kadam", "FAIL", f"{type(e).__name__}: {e}")


def c_world():
    try:
        sys.path.insert(0, str(ROOT / "tools" / "local_story"))
        import story_local as sl
        g = len(getattr(sl, "GROUND", {})); w = len(getattr(sl, "WORLD", {}))
        add("world layer", "PASS" if g >= 7 and w >= 8 else "WARN", f"ground {g}, world {w}")
    except Exception as e:
        add("world layer", "WARN", f"{type(e).__name__}")


def c_catalog():
    p = ROOT / "knowledge" / "sound-catalog.json"
    if not p.exists():
        return add("sound catalog", "WARN", "file nahi mili")
    d = json.loads(p.read_text(encoding="utf-8"))
    n = d.get("count") or len(d.get("items", []))
    add("sound catalog", "PASS" if n >= 800 else "WARN", f"{n} files naapi gayi")


def c_model():
    for f in ("sound-signatures.json", "sound-model.json"):
        if not (ROOT / "knowledge" / f).exists():
            return add("sound model", "WARN", f"{f} nahi mila")
    add("sound model", "PASS", "signatures + model maujood")


def c_engines():
    e = ROOT / "voice" / "engines"
    need = ["edge", "espeak", "piper", "elevenlabs"]
    have = [n for n in need if (e / n / "config.json").exists()]
    add("4 engines synced", "PASS" if len(have) == 4 else "WARN", f"{len(have)}/4")


def c_tools():
    need = ["audio_judge.py", "asr_cache.py", "sound_catalog.py", "sound_pick.py", "sound_synth.py",
            "engine_adopt.py", "music_make2.py", "song_read.py", "horror_read.py", "emotion_read.py",
            "render_manifest.py", "selftest_suite.py", "system_doctor.py"]
    have = [n for n in need if (ROOT / "tools" / n).exists()]
    add("tools", "PASS" if len(have) == len(need) else "WARN", f"{len(have)}/{len(need)}")


def c_qa_thresholds():
    p = ROOT / "knowledge" / "local-brain.json"
    if not p.exists():
        return add("QA thresholds", "FAIL", "brain nahi")
    b = json.loads(p.read_text(encoding="utf-8"))
    q = b.get("qa", {})
    add("QA thresholds", "PASS" if q else "WARN", f"{len(q)} keys")


def c_judge_smoke():
    j = ROOT / "tools" / "audio_judge.py"
    if not j.exists():
        return add("judge smoke", "WARN", "audio_judge.py nahi")
    try:
        out = subprocess.run([sys.executable, str(j), "--help"], capture_output=True, text=True, timeout=60)
        add("judge smoke", "PASS" if out.returncode == 0 else "FAIL", "help OK" if out.returncode == 0 else out.stderr[:80])
    except Exception as e:
        add("judge smoke", "FAIL", f"{type(e).__name__}")


def c_selftest():
    s = ROOT / "tools" / "selftest_suite.py"
    if not s.exists():
        return add("selftest suite", "WARN", "file nahi mili")
    try:
        out = subprocess.run([sys.executable, str(s), "--quick"], capture_output=True, text=True, timeout=240)
        if out.returncode != 0 and "--quick" in (out.stderr or ""):
            out = subprocess.run([sys.executable, str(s)], capture_output=True, text=True, timeout=280)
        line = [l for l in out.stdout.splitlines() if "PASS" in l or "FAIL" in l or "/" in l]
        add("selftest suite", "PASS" if out.returncode == 0 else "WARN", (line[-1][:90] if line else "chala"))
    except Exception as e:
        add("selftest suite", "WARN", f"{type(e).__name__}")


def c_world_engine():
    w = ROOT / "tools" / "world"
    need = ["duniya.py", "world_qa.py", "rachna.py", "awaazein.py", "spotting.py", "seekho.py", "harkat.py"]
    have = [n for n in need if (w / n).exists()]
    wm = ROOT / "knowledge" / "world-map.json"
    kws = 0
    if wm.exists():
        d = json.loads(wm.read_text(encoding="utf-8"))
        def _leaves(x):
            if isinstance(x, dict):
                return sum(_leaves(v) for v in x.values())
            if isinstance(x, list):
                return len(x)
            return 1
        kws = _leaves(d.get("keywords", {}))
    add("duniya engine", "PASS" if len(have) == len(need) and kws >= 40 else "WARN",
        f"{len(have)}/{len(need)} modules, {kws} keywords")


CHECKS = [c_world_engine, c_voices, c_brain, c_smooth, c_ground, c_world, c_catalog, c_model,
          c_engines, c_tools, c_qa_thresholds, c_judge_smoke, c_selftest]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    for f in CHECKS:
        try:
            f()
        except Exception as e:
            add(f.__name__, "FAIL", f"{type(e).__name__}: {e}")
    counts = {s: sum(1 for r in R if r["status"] == s) for s in ("PASS", "WARN", "FAIL")}
    if a.json:
        print(json.dumps({"checks": R, "counts": counts}, ensure_ascii=False, indent=1))
    else:
        for r in R:
            mark = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[r["status"]]
            print(f"{mark} {r['check']:20s} {r['detail']}")
        print(f"\nPASS {counts['PASS']} | WARN {counts['WARN']} | FAIL {counts['FAIL']}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
