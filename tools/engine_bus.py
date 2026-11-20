#!/usr/bin/env python3
"""Engine Bus — 24 engine aapas me baat karein aur kaam todkar jaldi poora karein.

Faisla (design):
  - Har engine apni "capability" batata hai (kya bol sakta hai, kaunse bhaav, offline?, kitna tez, kitna mehnga)
  - Coordinator project ko chhote hisson (parts) me todta hai
  - Har hissa us engine ko jata hai jo us kaam ke liye theek hai (bhaav + awaaz + speed)
  - Ek awaaz (kirdaar) hamesha ek hi engine par rehti hai → awaaz nahi badalti
  - Koi engine fail ho to us ka hissa doosre capable engine ko chala jata hai (bhaav wahi rehta hai)
  - Aadha kaam bhi bachta hai: har part ka file + manifest likha jata hai (resume)

Commands:
  python tools/engine_bus.py register --name piper --capabilities piper.json
  python tools/engine_bus.py status
  python tools/engine_bus.py plan --script story.txt
  python tools/engine_bus.py run --script story.txt --out output/bus
"""
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUS = Path(os.environ.get("ASTRA_BUS_DIR", ROOT / "bus"))


# --------------------------------------------------------------- capabilities
@dataclass
class Capability:
    """Ek engine kya kar sakta hai."""
    name: str
    emotions: list = field(default_factory=lambda: ["neutral"])
    languages: list = field(default_factory=lambda: ["hi"])
    offline: bool = False
    speed: float = 1.0          # 1.0 = normal, 2.0 = do guna tez
    cost: float = 0.0           # 0 = free, 1 = mehnga
    max_chars: int = 400
    healthy: bool = True

    @staticmethod
    def from_dict(d: dict) -> "Capability":
        base = {k: d[k] for k in ("name",) if k in d}
        cap = Capability(name=base.get("name", "?"))
        for k in ("emotions", "languages", "offline", "speed", "cost", "max_chars", "healthy"):
            if k in d:
                setattr(cap, k, d[k])
        return cap


def registry_path() -> Path:
    return BUS / "engines.json"


def register(cap: Capability) -> None:
    BUS.mkdir(parents=True, exist_ok=True)
    reg = load_registry()
    reg[cap.name] = cap.__dict__
    _atomic_write(registry_path(), reg)


def load_registry() -> dict:
    p = registry_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def engines() -> list[Capability]:
    return [Capability.from_dict({"name": k, **v}) for k, v in load_registry().items()]


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


# --------------------------------------------------------------- kaam baantna
def pick_engine(part, caps: list[Capability], locked: dict | None = None) -> Capability | None:
    """Ek hisse ke liye best engine: pehle bhaav, phir awaaz lock, phir speed/cost."""
    locked = locked or {}
    usable = [c for c in caps if c.healthy]
    if not usable:
        return None
    if part.character in locked:                     # awaaz wahi rahe
        for c in usable:
            if c.name == locked[part.character]:
                return c
    fits = [c for c in usable if part.emotion in c.emotions or part.emotion == "neutral"]
    if not fits:
        fits = usable
    fits.sort(key=lambda c: (-(c.speed / (1.0 + c.cost)), c.cost))
    return fits[0]


@dataclass
class Part:
    n: int
    character: str
    emotion: str
    text: str
    engine: str = ""
    file: str = ""
    ok: bool = False
    tries: int = 0
    error: str = ""


def split_script(text: str, max_chars: int = 220) -> list[Part]:
    """Script → parts. Format: 'नाम [bhaav]: line'  ya  '[bhaav] line'."""
    import re
    parts: list[Part] = []
    n = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        emo = "neutral"
        m = re.search(r"\[(\w+)\]", line)
        if m:
            emo = m.group(1)
            line = (line[:m.start()] + line[m.end():]).strip(" :-")
        who = "sutradhar"
        if ":" in line:
            head, tail = line.split(":", 1)
            if 0 < len(head.strip()) <= 24:
                who, line = head.strip(), tail.strip()
        # lambi line ko todo (engine ki limit ke hisaab se)
        while len(line) > max_chars:
            cut = line.rfind("।", 0, max_chars)
            cut = cut if cut > 40 else max_chars
            n += 1
            parts.append(Part(n=n, character=who, emotion=emo, text=line[:cut].strip()))
            line = line[cut:].strip()
        if line:
            n += 1
            parts.append(Part(n=n, character=who, emotion=emo, text=line))
    return parts


def plan(text: str, caps: list[Capability]) -> list[Part]:
    """Kaun hissa kis engine par jayega — pehle se tay."""
    parts = split_script(text)
    locked: dict[str, str] = {}
    for p in parts:
        cap = pick_engine(p, caps, locked)
        if cap:
            p.engine = cap.name
            locked.setdefault(p.character, cap.name)
    return parts


def run(text: str, out_dir: str, renderer=None, caps: list[Capability] | None = None,
        retry_next: bool = True) -> dict:
    """Parts ko chalाओ. renderer(engine, part, out_path) -> bool."""
    caps = caps if caps is not None else engines()
    od = Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    parts = plan(text, caps)
    locked: dict[str, str] = {}
    t0 = time.time()
    done = 0
    for p in parts:
        cap = pick_engine(p, caps, locked)
        if not cap:
            p.error = "koi engine available nahi"
            continue
        p.engine = cap.name
        locked.setdefault(p.character, cap.name)
        out = od / f"{p.n:03d}_{p.character}_{p.emotion}.wav"
        ok = False
        tried = set()
        while not ok:
            p.tries += 1
            tried.add(cap.name)
            try:
                ok = bool(renderer(cap.name, p, str(out))) if renderer else False
                if ok:
                    p.file = str(out); p.ok = True; done += 1
                    break
                p.error = "render fail"
            except Exception as exc:
                p.error = f"{type(exc).__name__}: {str(exc)[:100]}"
            if not retry_next:
                break
            nxt = [c for c in caps if c.healthy and c.name not in tried]
            if not nxt:
                break
            cap = pick_engine(p, nxt, {})       # bhaav wahi, engine doosra
            p.engine = cap.name if cap else p.engine
        if not ok:
            print(f"FAIL {p.n} [{p.character}/{p.emotion}] {p.error[:60]}", flush=True)
    manifest = {"script_parts": len(parts), "done": done, "failed": len(parts) - done,
                "seconds": round(time.time() - t0, 2),
                "parts": [p.__dict__ for p in parts]}
    _atomic_write(od / "manifest.json", manifest)
    return manifest


def status() -> dict:
    caps = engines()
    return {"engines": len(caps), "healthy": sum(1 for c in caps if c.healthy),
            "list": [c.__dict__ for c in caps]}


def main() -> int:
    ap = argparse.ArgumentParser(description="engine bus (24 engine taalmel)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register")
    r.add_argument("--name", required=True)
    r.add_argument("--capabilities", default="")
    r.add_argument("--emotions", default="neutral")
    r.add_argument("--offline", action="store_true")
    r.add_argument("--speed", type=float, default=1.0)
    r.add_argument("--cost", type=float, default=0.0)
    sub.add_parser("status")
    pl = sub.add_parser("plan"); pl.add_argument("--script", required=True)
    rn = sub.add_parser("run"); rn.add_argument("--script", required=True); rn.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "register":
        if a.capabilities and Path(a.capabilities).exists():
            cap = Capability.from_dict(json.loads(Path(a.capabilities).read_text(encoding="utf-8")))
            cap.name = a.name
        else:
            cap = Capability(name=a.name, emotions=[e.strip() for e in a.emotions.split(",") if e.strip()],
                             offline=a.offline, speed=a.speed, cost=a.cost)
        register(cap)
        print(json.dumps(cap.__dict__, ensure_ascii=False, indent=2)); return 0
    if a.cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2)); return 0
    text = Path(a.script).read_text(encoding="utf-8")
    if a.cmd == "plan":
        print(json.dumps([p.__dict__ for p in plan(text, engines())], ensure_ascii=False, indent=1)); return 0
    rep = run(text, a.out)
    print(json.dumps({k: rep[k] for k in ("script_parts", "done", "failed", "seconds")},
                     ensure_ascii=False, indent=2))
    return 0 if rep["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
