#!/usr/bin/env python3
"""ASTRA Engine Router — chaaron engine ek darwaze se.

Sawaal: "kaun engine chalega?" — jawab ab insaan nahi, yeh file deti hai.
Chain: sarvam -> edge -> piper -> espeak -> elevenlabs
  - jo pehla engine tayyar mile, wahi render karta hai
  - fail ho to agla apne aap (fallback), aur report me likha jata hai kaun kya kiya
  - har kirdaar ki awaaz astra/voices.json se aati hai (ek kirdaar = ek awaaz)

Commands:
  python tools/engine_router.py status              # kaun tayyar hai
  python tools/engine_router.py plan  story.txt     # kaun si line kaun engine (kuch render nahi)
  python tools/engine_router.py render story.txt --out output/story.wav
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ROOT / "engines"
# Chaar engine (Sarvam isme nahi — woh alag engine hai).
# Sarvam chahiye to: ASTRA_INCLUDE_SARVAM=1  ya  --engine sarvam
ORDER = ["edge", "elevenlabs", "piper", "espeak"]
OPTIONAL_ENGINES = ["sarvam"]


def active_order() -> list[str]:
    """Kaam ka chain — Sarvam sirf jab khud maanga jaye."""
    import os
    order = list(ORDER)
    if os.environ.get("ASTRA_INCLUDE_SARVAM") == "1":
        order.append("sarvam")
    return order

# engine -> (kaunsi file chahiye, kaunsa env var chahiye, kaunsa engine folder)
FIX = {
    "sarvam":     "GitHub secret SARVAM_API_KEY daalo (dashboard.sarvam.ai se key).",
    "edge":       "pip install edge-tts  (internet chahiye; GitHub runner par chalta hai).",
    "piper":      "piper binary + hi_IN model: https://huggingface.co/rhasspy/piper-voices (offline chalega).",
    "espeak":     "sudo apt-get install espeak-ng  (Linux).",
    "elevenlabs": "GitHub secret ELEVENLABS_API_KEY daalo (free plan par sirf premade voices).",
}

SPEC = {
    "sarvam":      {"env": "SARVAM_API_KEY",     "folder": None,      "kind": "api"},
    "edge":        {"env": None,                 "folder": "EDGE",    "kind": "cli", "bin": "edge-tts"},
    "piper":       {"env": None,                 "folder": "PIPER",   "kind": "cli", "bin": "piper"},
    "espeak":      {"env": None,                 "folder": "ESPEAK",  "kind": "cli", "bin": "espeak-ng"},
    "elevenlabs":  {"env": "ELEVENLABS_API_KEY", "folder": "ELEVENLABS", "kind": "api"},
}


@dataclass
class EngineState:
    name: str
    ready: bool
    reason: str


@dataclass
class Plan:
    line: str
    character: str
    engine: str
    fallbacks: list[str] = field(default_factory=list)


def _ffmpeg() -> str | None:
    """ffmpeg dhundo: PATH par, warna imageio ka bundled."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _which(binary: str) -> bool:
    return shutil.which(binary) is not None


def engine_status() -> list[EngineState]:
    """Har engine: tayyar hai ya nahi, aur kyun."""
    out: list[EngineState] = []
    for name in active_order():
        spec = SPEC[name]
        if spec["kind"] == "api":
            if not os.environ.get(spec["env"]):
                out.append(EngineState(name, False, f"{spec['env']} nahi mila"))
            else:
                out.append(EngineState(name, True, "key mila"))
            continue
        problems = []
        folder = ENGINES / spec["folder"]
        if not folder.exists():
            problems.append(f"folder missing: engines/{spec['folder']}")
        if spec.get("bin") and not _which(spec["bin"]):
            problems.append(f"binary missing: {spec['bin']}")
        out.append(EngineState(name, not problems, "; ".join(problems) or "tayyar"))
    return out


def ready_engines() -> list[str]:
    return [s.name for s in engine_status() if s.ready]


def choose_engine(character: str, ready: list[str] | None = None) -> tuple[str | None, list[str]]:
    """Pehla tayyar engine do; baaki fallback list."""
    ready = ready if ready is not None else ready_engines()
    if not ready:
        return None, []
    first, rest = ready[0], ready[1:]
    return first, rest


def load_voices() -> dict:
    path = ROOT / "astra" / "voices.json"
    if not path.exists():
        return {}
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}


def parse_story(text: str) -> list[tuple[str, str]]:
    """'किरदार: line' format padho. Bina naam wali line = vachak (narrator)."""
    lines = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if ":" in s:
            who, said = s.split(":", 1)
            who, said = who.strip(), said.strip()
            if 1 <= len(who) <= 24 and said:
                lines.append((who, said))
                continue
        lines.append(("vachak", s))
    return lines


def build_plan(text: str) -> list[Plan]:
    ready = ready_engines()
    plans = []
    for who, said in parse_story(text):
        eng, fb = choose_engine(who, ready)
        plans.append(Plan(line=said, character=who, engine=eng or "NONE", fallbacks=fb))
    return plans


def _call_provider(engine: str, text: str, character: str, out: Path, bhaav: str = "") -> bool:
    """Asli render — tools/voice_provider.py ke functions se."""
    sys.path.insert(0, str(ROOT))
    from tools import voice_provider as vp
    if engine == "sarvam":
        vp.sarvam_tts(text, character, str(out), bhaav=bhaav or None)
    elif engine == "piper":
        vp.piper_tts(text, character, str(out), bhaav=bhaav or None)
    elif engine == "elevenlabs":
        try:
            vp.eleven_tts(text, character, str(out), bhaav=bhaav or None)
        except TypeError:
            vp.eleven_tts(text, character, str(out))
    elif engine == "free":
        from tools import free_api as fa
        if not fa.speak(text, str(out), bhaav or None):
            raise RuntimeError("free tts render fail (internet?)")
    elif engine == "espeak":
        vp.espeak_tts(text, character, str(out), bhaav=bhaav or None)
    elif engine == "edge":
        if not vp.edge_tts(text, character, str(out), bhaav=bhaav or None):
            raise RuntimeError("edge-tts render fail (internet/proxy?)")
    else:
        raise RuntimeError(f"{engine} abhi router se render nahi hota")
    return out.exists() and out.stat().st_size > 1000


def _guarded(engine: str, text: str, character: str, out: Path, bhaav: str = ""):
    """Cache + retry + quality check ke saath ek engine call."""
    from tools import tts_guard as tg
    def fn(dst):
        _call_provider(engine, text, character, Path(dst), bhaav=bhaav)
    path, meta = tg.render(engine, character, text,
                           {"out": str(out), "bhaav": bhaav or "neutral"}, fn)
    return path.exists() and path.stat().st_size > 1000, meta


def render_line(text: str, character: str, out: Path,
                engine: str | None = None, fallbacks: list[str] | None = None,
                bhaav: str = "") -> tuple[bool, list[dict]]:
    """Ek line, chain ke saath. Har koshish ka hisaab wapas milta hai."""
    chain = [e for e in ([engine] if engine else []) + (fallbacks or []) if e]
    if not chain:
        chain = ready_engines()
    log = []
    for eng in chain:
        try:
            ok, meta = _guarded(eng, text, character, out, bhaav=bhaav)
            note = ("cache se" if meta.get("cached") else "banaya")
            log.append({"engine": eng, "ok": ok, "note": note})
            if ok:
                return True, log
        except Exception as exc:
            log.append({"engine": eng, "ok": False, "note": f"{type(exc).__name__}: {str(exc)[:160]}"})
    return False, log


def render_story_parallel(text: str, out_dir: Path, workers: int = 4) -> dict:
    """Kai line ek saath (parallel) — waqt bachta hai, order wahi rehta hai."""
    out_dir.mkdir(parents=True, exist_ok=True)
    plans = build_plan(text)
    def job(item):
        i, p = item
        out = out_dir / f"{i:03d}_{p.character}.wav"
        ok, log = render_line(p.line, p.character, out, p.engine, p.fallbacks)
        return {"n": i, "character": p.character, "line": p.line, "ok": ok,
                "file": str(out) if ok else None, "tries": log}
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as ex:
        results = list(ex.map(job, list(enumerate(plans, 1))))
    results.sort(key=lambda r: r["n"])
    done = [r["file"] for r in results if r["ok"]]
    return {"lines": len(results), "ok": len(done), "joined": None, "results": results,
            "workers": workers}


def render_story(text: str, out_dir: Path) -> dict:
    """Poori kahani: har line apne engine se, phir jod kar ek file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    plans = build_plan(text)
    results = []
    for i, p in enumerate(plans, 1):
        out = out_dir / f"{i:03d}_{p.character}.wav"
        ok, log = render_line(p.line, p.character, out, p.engine, p.fallbacks)
        results.append({"n": i, "character": p.character, "line": p.line,
                        "ok": ok, "file": str(out) if ok else None, "tries": log})
    done = [r["file"] for r in results if r["ok"]]
    joined = None
    if done:
        joined = str(out_dir / "story.wav")
        listf = out_dir / "list.txt"
        listf.write_text("\n".join(f"file '{Path(f).name}'" for f in done), encoding="utf-8")
        exe = _ffmpeg()
        if exe:
            subprocess.run([exe, "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                            "-i", str(listf), "-c", "copy", joined], capture_output=True)
        if not Path(joined).exists():
            joined = None  # ffmpeg na ho to bhi lines alag-alag safe rehti hain
    return {"lines": len(results), "ok": len(done), "joined": joined, "results": results}


def cmd_status() -> int:
    states = engine_status()
    for s in states:
        print(f"{'[READY]' if s.ready else '[ --  ]'} {s.name:11s} {s.reason}")
    ready = [s.name for s in states if s.ready]
    print(f"\nChain: {' -> '.join(active_order())}")
    print(f"Sarvam (alag engine): {'chain me' if 'sarvam' in active_order() else 'sirf --engine sarvam / ASTRA_INCLUDE_SARVAM=1 par'}")
    print(f"Abhi chalenge: {', '.join(ready) if ready else 'koi nahi'}")
    return 0 if ready else 1


def problems() -> list[dict]:
    """Har engine ki dikkat + uska seedha hal."""
    out = []
    for st in engine_status():
        if st.ready:
            continue
        out.append({"engine": st.name, "dikkat": st.reason, "hal": FIX.get(st.name, "")})
    return out


def cmd_problems(as_json: bool = False) -> int:
    items = problems()
    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0 if not items else 1
    if not items:
        print("Koi dikkat nahi — sab engine tayyar hain.")
        return 0
    print(f"{len(items)} dikkat mili:\n")
    for i, it in enumerate(items, 1):
        print(f"{i}. {it['engine'].upper()}")
        print(f"   dikkat: {it['dikkat']}")
        print(f"   hal   : {it['hal']}\n")
    return 1


def cmd_plan(path: str) -> int:
    text = Path(path).read_text(encoding="utf-8")
    plans = build_plan(text)
    if not plans:
        print("kuch line nahi mili")
        return 1
    for p in plans:
        print(f"{p.character:12s} -> {p.engine:10s} (fallback: {', '.join(p.fallbacks) or '-'})  | {p.line[:40]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ASTRA engine router")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    pr = sub.add_parser("problems"); pr.add_argument("--json", action="store_true")
    p2 = sub.add_parser("plan"); p2.add_argument("story")
    p3 = sub.add_parser("render"); p3.add_argument("story"); p3.add_argument("--out", default="output/router.wav")
    a = ap.parse_args()
    if a.cmd == "status":
        return cmd_status()
    if a.cmd == "problems":
        return cmd_problems(a.json)
    if a.cmd == "plan":
        return cmd_plan(a.story)
    text = Path(a.story).read_text(encoding="utf-8")
    rep = render_story(text, Path(a.out).parent if a.out else ROOT / "output")
    print(json.dumps({"lines": rep["lines"], "ok": rep["ok"], "joined": rep["joined"]},
                     ensure_ascii=False, indent=2))
    for r in rep["results"]:
        mark = "OK " if r["ok"] else "FAIL"
        tried = " -> ".join(f"{t['engine']}:{t['note'][:28]}" for t in r["tries"])
        print(f"[{mark}] {r['character']:12s} {r['line'][:30]:32s} {tried}")
    return 0 if rep["ok"] == rep["lines"] else 1


if __name__ == "__main__":
    sys.exit(main())
