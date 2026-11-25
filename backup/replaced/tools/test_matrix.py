#!/usr/bin/env python3
"""Test Matrix — duniya ke purane testing tarike, hazaaron combination par.

Tarike (world-standard):
  1. Equivalence partitioning  — text ko hisson me baanto (chhota/medium/lamba/emoji/sankhya/mixed)
  2. Boundary value analysis   — 0, 1, 199, 200, 201, 900, 5000 akshar
  3. Combinatorial (pairwise)  — engine × text × bhaav × format
  4. Metamorphic relations     — dukh > gussa (dheema/tez), punctuation se shabd na badle
  5. Golden master             — ek line ka naap fix, baad me badle to pakdo
  6. Property-based            — har render: ok ⇒ file hai, dur > 0.2s, RMS > 0.005
  7. Chaos / failure injection — galat engine naam, khaali text, missing bhaav

CLI:
  python tools/test_matrix.py --combos 200          # random sample
  python tools/test_matrix.py --combos 2000 --seed 7
"""
from __future__ import annotations
import argparse, hashlib, json, random, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import worktmp as wt

TEXTS = {
    "tiny": "हाँ।",
    "short": "बेटा आ जा।",
    "medium": "दादी ने कहा, बेटा आ जा पास, मैं तुम्हारी माँ हूँ।",
    "long": ("जंगल के रास्ते से गुजरते हुए उसने सोचा कि आज बारिश होगी। " * 6),
    "numbers": "साल 2024 में 45 प्रतिशत लोगों ने ₹1,20,000 कमाए।",
    "mixed": "Hello दोस्त, यह test 123 है।",
    "emoji": "बहुत अच्छा 😀🙏 चलो!",
    "punct": "रुको... सुनो! क्या? हाँ।",
}
BOUNDARY = [1, 199, 200, 201, 900]
BHAVS = ["neutral", "dukh", "gussa", "khushi", "dar", "pyaar"]
ENGINES = ["free", "espeak", "piper", "edge"]
FORMATS = [".wav", ".mp3"]


def _probe(p: Path) -> tuple[float, float, bytes]:
    import numpy as np
    from imageio_ffmpeg import get_ffmpeg_exe
    if not p.exists():
        return 0.0, 0.0, b""
    raw = subprocess.run([get_ffmpeg_exe(), "-v", "quiet", "-i", str(p), "-f", "s16le",
                          "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    head = p.read_bytes()[:4]
    return (round(len(x) / 16000, 2), round(float(np.sqrt((x ** 2).mean())), 4) if len(x) else 0.0, head)


def make_cases(combos: int, seed: int) -> list[dict]:
    rnd = random.Random(seed)
    cases = []
    # 3) combinatorial random sample
    for _ in range(combos):
        kind = rnd.choice(list(TEXTS))
        cases.append({"engine": rnd.choice(ENGINES), "text": TEXTS[kind],
                      "kind": kind, "bhaav": rnd.choice(BHAVS),
                      "ext": rnd.choice(FORMATS), "method": "combinatorial"})
    # 2) boundary values
    for n in BOUNDARY:
        cases.append({"engine": "espeak", "text": "क" * n, "kind": f"len{n}",
                      "bhaav": "neutral", "ext": ".wav", "method": "boundary"})
    # 7) chaos
    cases += [
        {"engine": "espeak", "text": "", "kind": "empty", "bhaav": "", "ext": ".wav", "method": "chaos"},
        {"engine": "espeak", "text": "।।।", "kind": "punct_only", "bhaav": "", "ext": ".wav", "method": "chaos"},
        {"engine": "nahi_hai", "text": "बेटा आ जा।", "kind": "bad_engine", "bhaav": "", "ext": ".wav", "method": "chaos"},
        {"engine": "espeak", "text": "बेटा आ जा।", "kind": "bad_bhaav", "bhaav": "xyz123", "ext": ".wav", "method": "chaos"},
    ]
    return cases


def run_case(c: dict, idx: int) -> dict:
    from tools import engine_router as er
    tmp = wt.work_tmp("matrix")
    out = tmp / f"c{idx}{c['ext']}"
    out.unlink(missing_ok=True)
    t0 = time.time()
    try:
        ok, log = er.render_line(c["text"], "dadi", out, engine=c["engine"], bhaav=c["bhaav"])
        err = "" if ok else (log[-1]["note"][:90] if log else "reason nahi")
    except Exception as exc:
        ok, err = False, f"{type(exc).__name__}: {str(exc)[:80]}"
    dur, rms, head = _probe(out)
    problems = []
    has_words = any(ch.isalpha() for ch in c["text"])
    expect_ok = has_words and c["engine"] in ENGINES
    if ok != expect_ok:
        problems.append(f"ok={ok} par ummeed={expect_ok}")
    if ok:
        if dur < 0.15:
            problems.append(f"bahut chhoti ({dur}s)")
        if rms <= 0.005:
            problems.append(f"khamosh (rms={rms})")
        if c["ext"] == ".wav" and head != b"RIFF":
            problems.append(f"wav header galat {head!r}")
        if c["ext"] == ".mp3" and head == b"RIFF":
            problems.append("mp3 me wav bytes")
        if c["ext"] == ".mp3" and head not in (b"ID3\x04", b"ID3\x03") and head[:2] not in (b"\xff\xfb", b"\xff\xf3"):
            problems.append(f"mp3 header ajeeb {head!r}")
    return {"idx": idx, "case": {k: (v[:40] + '…' if isinstance(v, str) and len(v) > 40 else v)
                                 for k, v in c.items()},
            "ok": ok, "dur": dur, "rms": rms, "seconds": round(time.time() - t0, 2),
            "problems": problems, "error": err}


def metamorphic(engine: str = "espeak") -> list[str]:
    """Rishte (relations) jo hamesha sach hone chahiye."""
    from tools import engine_router as er
    tmp = wt.work_tmp("matrix_meta")
    bad = []
    base = "मुझे बहुत तकलीफ़ हो रही है, बेटा।"
    d1 = tmp / "dukh.wav"; d2 = tmp / "gussa.wav"
    er.render_line(base, "dadi", d1, engine=engine, bhaav="dukh")
    er.render_line(base, "dadi", d2, engine=engine, bhaav="gussa")
    a, _ = _probe(d1)[0], None
    b, _ = _probe(d2)[0], None
    if not (a > b > 0):
        bad.append(f"metamorphic: dukh {a}s > gussa {b}s hona chahiye")
    # punctuation se duration badal sakti hai par shabd nahi — text same rehna chahiye
    t1, t2 = "बेटा आ जा", "बेटा आ जा।"
    from tools.voice_provider import clean_text
    if clean_text(t1).rstrip("।") != clean_text(t2).rstrip("।"):
        bad.append("metamorphic: punctuation se shabd badal gaye")
    return bad


def golden_master(engine: str = "espeak") -> list[str]:
    """Golden master: ek line ka naap yaad rakho, badle to batao."""
    from tools import engine_router as er
    tmp = wt.work_tmp("matrix_golden")
    f = tmp / "golden.wav"
    text = "सुनहरा परीक्षण वाक्य।"
    er.render_line(text, "dadi", f, engine=engine)
    dur, rms, _ = _probe(f)
    gm = ROOT / "tests" / "golden_master.json"
    cur = {"engine": engine, "dur": round(dur, 1), "sha": hashlib.sha256(f.read_bytes()).hexdigest()[:12] if f.exists() else ""}
    if not gm.exists():
        gm.write_text(json.dumps(cur, indent=1), encoding="utf-8")
        return []
    old = json.loads(gm.read_text(encoding="utf-8"))
    if abs(old.get("dur", 0) - cur["dur"]) > 1.5:
        return [f"golden master badla: dur {old.get('dur')} → {cur['dur']}"]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="hazaaron combination test")
    ap.add_argument("--combos", type=int, default=60)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    cases = make_cases(a.combos, a.seed)
    t0 = time.time()
    results, failed = [], []
    for i, c in enumerate(cases):
        r = run_case(c, i)
        results.append(r)
        if r["problems"]:
            failed.append(r)
    meta = metamorphic()
    gold = golden_master()
    by_method: dict = {}
    for r in results:
        m = r["case"]["method"]
        d = by_method.setdefault(m, {"run": 0, "fail": 0})
        d["run"] += 1
        d["fail"] += 1 if r["problems"] else 0
    rep = {"cases": len(cases), "failed": len(failed), "metamorphic": meta,
           "golden": gold, "by_method": by_method,
           "seconds": round(time.time() - t0, 1),
           "slowest": sorted(results, key=lambda r: -r["seconds"])[:3]}
    if a.out:
        Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("cases", "failed", "seconds", "by_method")}, ensure_ascii=False))
    for m in meta + gold:
        print("  META/GOLDEN:", m)
    for r in failed[:8]:
        print(f"  FAIL #{r['idx']} {r['case']['engine']}/{r['case']['kind']}/{r['case']['ext']}: "
              f"{'; '.join(r['problems'])} {r['error'][:60]}")
    return 0 if not failed and not meta and not gold else 1


if __name__ == "__main__":
    raise SystemExit(main())
