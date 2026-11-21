#!/usr/bin/env python3
"""World Tests — duniya ke industry/AI tarike, ek hi jagah.

Jo tarike add ho rahe hain (jo abhi tak nahi the):
  1. DIFFERENTIAL  — do engine se ek hi line, dono ki duration/rms tulna (koi bahut ajeeb ho to flag)
  2. SOAK          — 25 lines lagataar (memory/leak/dheemapan pakadna)
  3. PAIRWISE      — engine × format × bhaav ka coverage % (kitne jode test hue)
  4. MUTATION-LITE — text/cache me jaan-boojh kar kharabi daalo, system pakde ya na
  5. REGRESSION    — purane golden naap se tulna (kuch chup-chaap bigda to)
  6. RISK-BASED    — sabse khatarnak 5 case pehle (lamba, khaali, bad engine, mp3, parallel)

CLI: python tools/world_tests.py [--engine espeak] [--soak 25]
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import worktmp as wt

LINE = "दादी ने कहा, बेटा आ जा पास, आज बारिश होगी।"


def _probe(p: Path) -> tuple[float, float]:
    import numpy as np
    from imageio_ffmpeg import get_ffmpeg_exe
    if not p.exists():
        return 0.0, 0.0
    raw = subprocess.run([get_ffmpeg_exe(), "-v", "quiet", "-i", str(p), "-f", "s16le",
                          "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    return round(len(x) / 16000, 2), round(float(np.sqrt((x ** 2).mean())), 4) if len(x) else 0.0


def differential(tmp: Path) -> list[str]:
    from tools import engine_router as er
    bad, durs = [], {}
    for eng in ("free", "espeak", "piper", "edge"):
        f = tmp / f"diff_{eng}.wav"
        ok, _ = er.render_line(LINE, "dadi", f, engine=eng)
        if not ok:
            bad.append(f"differential: {eng} fail")
            continue
        durs[eng] = _probe(f)[0]
    if durs:
        lo, hi = min(durs.values()), max(durs.values())
        if hi > lo * 3 and lo > 0.2:
            bad.append(f"differential: duration me 3x farq {durs}")
    return bad


def soak(tmp: Path, engine: str, n: int) -> list[str]:
    from tools import engine_router as er
    bad, times = [], []
    for i in range(n):
        text = f"पंक्ति संख्या {i}: दादी बोल रही हैं, बेटा ध्यान से सुनो।"
        f = tmp / f"soak_{i}.wav"
        t0 = time.time()
        ok, _ = er.render_line(text, "dadi", f, engine=engine)
        times.append(time.time() - t0)
        if not ok:
            bad.append(f"soak: line {i} fail")
        if i > 3 and times[i] > times[0] * 6 + 2:
            bad.append(f"soak: dheema ho raha ({times[0]:.1f}s → {times[i]:.1f}s)")
            break
    return bad


def pairwise(tmp: Path, engine: str) -> list[str]:
    from tools import engine_router as er
    engines = [engine]
    formats = [".wav", ".mp3"]
    bhavs = ["neutral", "dukh", "gussa"]
    pairs, done = set(), set()
    bad = []
    for e, f, b in product(engines, formats, bhavs):
        pairs.add((e, f)); pairs.add((b, f)); pairs.add((e, b))
        out = tmp / f"pw_{b}{f}"
        ok, _ = er.render_line("बेटा आ जा पास।", "dadi", out, engine=e, bhaav=b)
        if ok:
            done.add((e, f)); done.add((b, f)); done.add((e, b))
        else:
            bad.append(f"pairwise: {e}/{f}/{b} fail")
    cover = round(100 * len(done & pairs) / max(1, len(pairs)))
    if cover < 100:
        bad.append(f"pairwise coverage {cover}%")
    return bad


def mutation_lite(tmp: Path) -> list[str]:
    """Jaan-boojh kar kharab cache file — system use reject kare."""
    from tools import render_cache as rc
    bad = []
    f = tmp / "mutant.wav"
    f.write_bytes(b"RIFF" + b"\x00" * 500)          # nakli/kharab wav
    if rc._usable(f):
        bad.append("mutation: kharab file 'usable' boli")
    # adhoora mp3
    g = tmp / "mutant.mp3"
    g.write_bytes(b"ID3\x04" + b"\x00" * 300)
    return bad


def regression(tmp: Path, engine: str) -> list[str]:
    from tools import engine_router as er
    gm = ROOT / "tests" / "world_golden.json"
    f = tmp / "reg.wav"
    er.render_line(LINE, "dadi", f, engine=engine)
    dur = _probe(f)[0]
    cur = {"engine": engine, "dur": round(dur, 1)}
    if not gm.exists():
        gm.write_text(json.dumps(cur, indent=1), encoding="utf-8")
        return []
    old = json.loads(gm.read_text(encoding="utf-8"))
    if abs(old.get("dur", 0) - cur["dur"]) > 2.0:
        return [f"regression: dur {old.get('dur')} → {cur['dur']}"]
    return []


def risk_based(tmp: Path, engine: str) -> list[str]:
    """Sabse khatarnak case pehle — inme fail = bada khatra."""
    from tools import engine_router as er
    bad = []
    risks = [
        ("lamba", "कहानी " * 200, engine, ".wav"),
        ("khaali", "", engine, ".wav"),
        ("bad_engine", LINE, "nahi_hai", ".wav"),
        ("mp3", LINE, engine, ".mp3"),
    ]
    for name, text, eng, ext in risks:
        out = tmp / f"risk_{name}{ext}"
        try:
            ok, log = er.render_line(text, "dadi", out, engine=eng)
        except Exception as exc:
            bad.append(f"risk {name}: crash {type(exc).__name__}")
            continue
        expect = bool(eng in ("free", "espeak", "piper", "edge") and any(c.isalpha() for c in text))
        if ok != expect:
            bad.append(f"risk {name}: ok={ok} ummeed={expect}")
    # parallel 6
    with ThreadPoolExecutor(max_workers=6) as pool:
        res = list(pool.map(lambda i: er.render_line(LINE, "dadi", tmp / f"risk_p{i}.wav", engine=engine)[0],
                            range(6)))
    if not all(res):
        bad.append(f"risk parallel: {res.count(False)} fail")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description="world-class test battery")
    ap.add_argument("--engine", default="espeak")
    ap.add_argument("--soak", type=int, default=15)
    a = ap.parse_args()
    tmp = wt.work_tmp("world_tests")
    tests = {
        "differential": lambda: differential(tmp),
        "soak": lambda: soak(tmp, a.engine, a.soak),
        "pairwise": lambda: pairwise(tmp, a.engine),
        "mutation": lambda: mutation_lite(tmp),
        "regression": lambda: regression(tmp, a.engine),
        "risk_based": lambda: risk_based(tmp, a.engine),
    }
    total = 0
    for name, fn in tests.items():
        t0 = time.time()
        try:
            bad = fn()
        except Exception as exc:
            bad = [f"test crash: {type(exc).__name__}: {str(exc)[:70]}"]
        total += len(bad)
        print(f"{name:13s} {'OK' if not bad else 'FAIL'} {round(time.time()-t0,1)}s")
        for b in bad:
            print("             -", b)
    print(json.dumps({"problems": total, "engine": a.engine}, ensure_ascii=False))
    return 0 if total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
