#!/usr/bin/env python3
"""Engine Stress — chaar engine par ek hi tarah ke kathin test (bug dhoondhne ke liye).

Har engine par 7 test:
  1. normal line            → file bane, 0.5 s se lambi ho
  2. khaali text            → saaf False (jhoothi success nahi)
  3. sirf punctuation "।।।" → saaf False
  4. lamba text (600 akshar)→ tukdon me tootkar poori file bane
  5. .wav maanga            → asli WAV header (RIFF)
  6. bhaav ka asar          → dukh > gussa ki duration (dheema vs tez)
  7. silence check          → file khamosh nahi (RMS > 0.01)

CLI:
  python tools/engine_stress.py                 # chaar engine
  python tools/engine_stress.py --engine piper
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LONG = ("यह एक लंबा वाक्य है जिसमें कहानी के बहुत सारे शब्द हैं और बच्चे सुनते हैं। " * 9)
LINE = "बेटा, आ जा पास। मैं तुम्हारी माँ हूँ।"


def _ff() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()


def _audio(path: Path) -> tuple[float, float]:
    """(duration, rms) — asli naap."""
    import numpy as np
    raw = subprocess.run([_ff(), "-v", "quiet", "-i", str(path), "-f", "s16le",
                          "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    if len(x) == 0:
        return 0.0, 0.0
    return round(len(x) / 16000, 2), round(float(np.sqrt((x ** 2).mean())), 4)


def _render(engine: str, text: str, out: Path, bhaav: str = "") -> bool:
    from tools import engine_router as er
    ok, _log = er.render_line(text, "dadi", out, engine=engine, bhaav=bhaav)
    return bool(ok)


def stress_engine(engine: str, tmp: Path) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    res = {}

    def put(name: str, ok: bool, note: str = "") -> None:
        res[name] = {"ok": bool(ok), "note": note}

    # 1 normal
    f = tmp / f"{engine}_normal.wav"
    t0 = time.time()
    ok = _render(engine, LINE, f)
    d, rms = _audio(f) if f.exists() else (0, 0)
    put("normal", ok and d > 0.5 and rms > 0.005, f"{d}s rms={rms} {round(time.time()-t0,1)}s")

    # 2 khaali
    put("empty_text", not _render(engine, "", tmp / f"{engine}_empty.wav"), "khaali par fail hona chahiye")

    # 3 sirf punctuation
    put("punctuation_only", not _render(engine, "।।।", tmp / f"{engine}_punct.wav"),
        "bina akshar fail hona chahiye")

    # 4 lamba text
    f4 = tmp / f"{engine}_long.wav"
    ok4 = _render(engine, LONG, f4)
    d4, rms4 = _audio(f4) if f4.exists() else (0, 0)
    put("long_text", ok4 and d4 > 8, f"{d4}s (600+ akshar)")

    # 5 wav header
    f5 = tmp / f"{engine}_fmt.wav"
    _render(engine, "नमस्ते", f5)
    head = f5.read_bytes()[:4] if f5.exists() else b""
    put("wav_header", head == b"RIFF", f"header={head!r}")

    # 6 bhaav asar
    fd = tmp / f"{engine}_dukh.wav"; fg = tmp / f"{engine}_gussa.wav"
    _render(engine, "मुझे बहुत तकलीफ़ हो रही है, बेटा।", fd, "dukh")
    _render(engine, "मुझे बहुत तकलीफ़ हो रही है, बेटा।", fg, "gussa")
    dd, _ = _audio(fd) if fd.exists() else (0, 0)
    dg, _ = _audio(fg) if fg.exists() else (0, 0)
    put("bhaav_pace", dd > dg > 0, f"dukh {dd}s > gussa {dg}s")

    # 7 silence
    put("not_silent", rms > 0.01, f"rms={rms}")

    passed = sum(1 for r in res.values() if r["ok"])
    return {"engine": engine, "passed": passed, "total": len(res),
            "score": round(100 * passed / len(res)), "tests": res}


def main() -> int:
    ap = argparse.ArgumentParser(description="engine stress test")
    ap.add_argument("--engine", default="")
    a = ap.parse_args()
    engines = [a.engine] if a.engine else ["free", "piper", "espeak", "edge"]
    tmp = Path("/tmp/engine_stress")
    rows, bad = [], []
    for e in engines:
        try:
            r = stress_engine(e, tmp)
        except Exception as exc:
            r = {"engine": e, "score": 0, "error": f"{type(exc).__name__}: {str(exc)[:90]}",
                 "tests": {}}
        rows.append(r)
        failed = [k for k, v in r.get("tests", {}).items() if not v.get("ok")]
        print(f"{e:8s} {r.get('score', 0):3d}%  fail: {', '.join(failed) or '—'}")
        for k in failed:
            print(f"          {k}: {r['tests'][k]['note']}")
        if failed:
            bad.append(e)
    print(json.dumps({"engines": [r["engine"] for r in rows], "weak": bad}, ensure_ascii=False))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
