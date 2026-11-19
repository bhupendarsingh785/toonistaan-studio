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

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ROOT / "engines"
ORDER = ["sarvam", "edge", "piper", "espeak", "elevenlabs"]

# engine -> (kaunsi file chahiye, kaunsa env var chahiye, kaunsa engine folder)
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
    for name in ORDER:
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


def _call_provider(engine: str, text: str, character: str, out: Path) -> bool:
    """Asli render — tools/voice_provider.py ke functions se."""
    sys.path.insert(0, str(ROOT))
    from tools import voice_provider as vp
    if engine == "sarvam":
        vp.sarvam_tts(text, character, str(out))
    elif engine == "piper":
        vp.piper_tts(text, character, str(out))
    elif engine == "elevenlabs":
        vp.eleven_tts(text, character, str(out))
    elif engine == "edge":
        bin_ = shutil.which("edge-tts")
        if not bin_:
            raise RuntimeError("edge-tts binary nahi hai")
        subprocess.run([bin_, "--voice", "hi-IN-MadhurNeural", "--text", text,
                        "--write-media", str(out)], check=True, capture_output=True)
    else:
        raise RuntimeError(f"{engine} abhi router se render nahi hota")
    return out.exists() and out.stat().st_size > 1000


def render_line(text: str, character: str, out: Path,
                engine: str | None = None, fallbacks: list[str] | None = None) -> tuple[bool, list[dict]]:
    """Ek line, chain ke saath. Har koshish ka hisaab wapas milta hai."""
    chain = [e for e in ([engine] if engine else []) + (fallbacks or []) if e]
    if not chain:
        chain = ready_engines()
    log = []
    for eng in chain:
        try:
            ok = _call_provider(eng, text, character, out)
            log.append({"engine": eng, "ok": ok, "note": "banaya" if ok else "khaali file"})
            if ok:
                return True, log
        except Exception as exc:
            log.append({"engine": eng, "ok": False, "note": f"{type(exc).__name__}: {str(exc)[:160]}"})
    return False, log


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
    print(f"\nChain: {' -> '.join(ORDER)}")
    print(f"Abhi chalenge: {', '.join(ready) if ready else 'koi nahi'}")
    return 0 if ready else 1


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
    p2 = sub.add_parser("plan"); p2.add_argument("story")
    p3 = sub.add_parser("render"); p3.add_argument("story"); p3.add_argument("--out", default="output/router.wav")
    a = ap.parse_args()
    if a.cmd == "status":
        return cmd_status()
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
