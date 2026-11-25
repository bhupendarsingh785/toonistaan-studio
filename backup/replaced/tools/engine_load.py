#!/usr/bin/env python3
"""Engine Load — kathin kaam par engine kitna smooth hai (speed + sahi).

Test:
  1. ek hi line 5 baar   → cache se tez hona chahiye (2nd se fast)
  2. 8 lines parallel    → sab banein, koi fail na ho, threads me race na ho
  3. 3000 akshar lamba   → poori file, khamosh na ho
  4. do engine ek saath  → dono sahi (shared cache me takkar na ho)

CLI: python tools/engine_load.py --engine piper
"""
from __future__ import annotations
import argparse, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import worktmp as wt

LINES = [
    "दादी ने कहा, बेटा आ जा पास।",
    "बारिश शुरू हो गई और हवा तेज़ हो गई।",
    "वह जंगल के रास्ते से गुजरा, पत्ते खड़खड़ाए।",
    "नदी किनारे बच्चे खेल रहे थे।",
    "अचानक दरवाज़े पर कोई दस्तक देने लगा।",
    "माँ ने चूल्हे पर रोटी बनाई और चाय बनाई।",
    "स्टेशन पर ट्रेन आने की घोषणा हुई।",
    "सब लोग चुप हो गए, सन्नाटा छा गया।",
]
LONG = ("यह एक बहुत लंबी कहानी है जिसमें दादी, बच्चे, जंगल, नदी और बारिश सब आते हैं। " * 16)  # ~1300 akshar


def _dur_rms(p: Path) -> tuple[float, float]:
    import subprocess
    import numpy as np
    from imageio_ffmpeg import get_ffmpeg_exe
    raw = subprocess.run([get_ffmpeg_exe(), "-v", "quiet", "-i", str(p), "-f", "s16le",
                          "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    return (round(len(x) / 16000, 2), round(float(np.sqrt((x ** 2).mean())), 4)) if len(x) else (0.0, 0.0)


def run(engine: str, tmp: Path, workers: int = 4) -> dict:
    from tools import engine_router as er
    tmp.mkdir(parents=True, exist_ok=True)
    rep: dict = {"engine": engine}

    # 1) ek hi line 5 baar (cache ka asar)
    times = []
    for i in range(5):
        out = tmp / f"{engine}_same_{i}.wav"
        t0 = time.time()
        ok, _ = er.render_line(LINES[0], "dadi", out, engine=engine)
        times.append(round(time.time() - t0, 2))
        if not ok:
            rep["cache_bug"] = f"repeat {i} fail"
    rep["repeat_times"] = times
    rep["cache_faster"] = times[-1] <= max(0.2, times[0] * 0.8)

    # 2) 8 lines parallel
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(er.render_line, LINES[i], "dadi",
                            tmp / f"{engine}_p{i}.wav", engine) for i in range(len(LINES))]
        for f in futs:
            try:
                ok, _log = f.result()
                results.append(bool(ok))
                if not ok:
                    rep.setdefault("parallel_errors", []).append(
                        (_log[-1]["note"][:110] if _log else "reason nahi mila"))
            except Exception as exc:
                results.append(False)
                rep.setdefault("parallel_errors", []).append(f"{type(exc).__name__}: {str(exc)[:80]}")
    rep["parallel_ok"] = sum(results)
    rep["parallel_total"] = len(results)
    rep["parallel_seconds"] = round(time.time() - t0, 1)

    # 3) 3000 akshar
    out = tmp / f"{engine}_long.wav"
    t0 = time.time()
    ok, _ = er.render_line(LONG, "dadi", out, engine=engine)
    d, rms = _dur_rms(out) if out.exists() else (0, 0)
    rep["long"] = {"ok": ok, "dur": d, "rms": rms, "seconds": round(time.time() - t0, 1)}

    # 4) do engine ek saath (shared cache)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(er.render_line, LINES[1], "dadi", tmp / f"{engine}_mix_a.wav", engine)
        f2 = pool.submit(er.render_line, LINES[2], "dadi", tmp / f"{engine}_mix_b.wav", "free")
        ok_a = f1.result()[0]
        ok_b = f2.result()[0]
    rep["mixed"] = {"ok": bool(ok_a and ok_b), "seconds": round(time.time() - t0, 1)}
    rep["score"] = sum([
        rep.get("cache_faster", False),
        rep["parallel_ok"] == rep["parallel_total"],
        rep["long"]["ok"] and rep["long"]["rms"] > 0.005,
        rep["mixed"]["ok"],
    ]) * 25
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description="engine load test")
    ap.add_argument("--engine", default="")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    engines = [a.engine] if a.engine else ["free", "piper", "espeak", "edge"]
    tmp = wt.work_tmp("engine_load")
    bad = []
    for e in engines:
        try:
            r = run(e, tmp, a.workers)
        except Exception as exc:
            r = {"engine": e, "score": 0, "error": f"{type(exc).__name__}: {str(exc)[:90]}"}
        print(json.dumps(r, ensure_ascii=False))
        if r.get("score", 0) < 100:
            bad.append(e)
    print(json.dumps({"weak": bad}, ensure_ascii=False))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
