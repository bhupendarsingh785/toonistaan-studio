#!/usr/bin/env python3
"""Engine Bus — chaar engines ke "agents" ko ek hi bus par jodo.

Kya karta hai:
  1. REGISTRY   : har engine ka config (kaam, speed, quality, offline?, key chahiye?)
  2. PROBE      : asli test — ek chhota shabd render karke dekhta hai chalta hai ya nahi (PASS/FAIL)
  3. ROUTER     : kaam ke hisaab se best engine chunta hai (offline/quality/fast/clone)
  4. BUS        : agents ke beech message (JSONL) — request → reply, taaki ek doosre se baat kare
  5. HANDOFF    : ek engine fail ho to agla apne aap try (fallback chain)

CLI:
  python tools/engine_bus.py --probe          # chaaron ko test karo
  python tools/engine_bus.py --route quality  # kaun best hai
  python tools/engine_bus.py --demo           # agents ka aapas me message
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, time, wave
from pathlib import Path
try:
    import astra_paths as _AP
except ImportError:
    import sys as _s, pathlib as _pl
    _s.path.insert(0, str(_pl.Path(__file__).resolve().parent)); import astra_paths as _AP

ROOT = Path(__file__).resolve().parent.parent
VOICES = _AP.VOICES
BUS_FILE = ROOT / "knowledge" / "engine-bus.jsonl"
SR = 22050

REGISTRY = {
    "piper": {
        "kind": "offline-neural", "offline": True, "key": False,
        "quality": 0.72, "speed": 0.80, "hindi": True, "clone": False,
        "use": ["kahani", "narrator", "batch", "free"],
        "note": "sabse practical — local, free, unlimited",
    },
    "espeak": {
        "kind": "offline-formant", "offline": True, "key": False,
        "quality": 0.35, "speed": 0.98, "hindi": True, "clone": False,
        "use": ["draft", "timing", "backup"],
        "note": "bahut tez par robotic — sirf draft/timing ke liye",
    },
    "edge": {
        "kind": "cloud-neural", "offline": False, "key": False,
        "quality": 0.86, "speed": 0.70, "hindi": True, "clone": False,
        "use": ["quality", "natural"],
        "note": "Microsoft ka free endpoint — internet chahiye",
    },
    "elevenlabs": {
        "kind": "cloud-clone", "offline": False, "key": True,
        "quality": 0.93, "speed": 0.55, "hindi": True, "clone": True,
        "use": ["clone", "emotion", "premium"],
        "note": "cloning sabse behtar — paid/key chahiye, private rakho",
    },
}


# ---------------- probe helpers
def _wav_ok(p: Path) -> tuple[bool, str]:
    if not p.exists() or p.stat().st_size < 2000:
        return False, "file nahi/chhoti"
    try:
        with wave.open(str(p)) as w:
            return (w.getnframes() > 1000), f"{w.getnframes()/w.getframerate():.2f}s"
    except Exception as e:
        return False, f"{type(e).__name__}"


def probe_piper(tmp: Path) -> tuple[bool, str]:
    try:
        from piper import PiperVoice
        from piper.config import SynthesisConfig
    except Exception as e:
        return False, f"piper import nahi: {e}"
    model = VOICES / "hi_IN-pratham-medium.onnx"
    if not model.exists():
        return False, "voice model nahi"
    try:
        v = PiperVoice.load(str(model), config_path=str(model) + ".json")
        out = tmp / "probe-piper.wav"
        with wave.open(str(out), "wb") as w:
            v.synthesize_wav("नमस्ते, यह जाँच है।", w,
                             syn_config=SynthesisConfig(length_scale=1.0, noise_scale=0.62, noise_w_scale=0.75))
        return _wav_ok(out)
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:60]}"


def probe_espeak(tmp: Path) -> tuple[bool, str]:
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        return False, "espeak binary nahi (apt nahi chal sakta)"
    out = tmp / "probe-espeak.wav"
    try:
        subprocess.run([exe, "-v", "hi", "-w", str(out), "नमस्ते"], check=False, timeout=30,
                       capture_output=True)
        return _wav_ok(out)
    except Exception as e:
        return False, f"{type(e).__name__}"


def probe_edge(tmp: Path) -> tuple[bool, str]:
    try:
        import edge_tts  # noqa
    except Exception:
        return False, "edge-tts install nahi"
    out = tmp / "probe-edge.mp3"
    try:
        import asyncio, edge_tts
        async def go():
            c = edge_tts.Communicate("नमस्ते, यह जाँच है।", "hi-IN-MadhurNeural")
            await c.save(str(out))
        asyncio.run(go())
        ok = out.exists() and out.stat().st_size > 2000
        return ok, f"{out.stat().st_size//1024} KB" if ok else "khaali"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:50]}"


def probe_elevenlabs(tmp: Path) -> tuple[bool, str]:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        return False, "key nahi (private secret me rakho)"
    try:
        import urllib.request
        req = urllib.request.Request("https://api.elevenlabs.io/v1/user",
                                     headers={"xi-api-key": key})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
        return True, f"quota ok ({d.get('subscription', {}).get('character_count', '?')})"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:50]}"


PROBES = {"piper": probe_piper, "espeak": probe_espeak, "edge": probe_edge, "elevenlabs": probe_elevenlabs}


# ---------------- router
def route(task: str) -> dict:
    """task: offline | quality | fast | clone | draft | kahani"""
    want = {
        "offline": lambda e: e["offline"] and not e["key"],
        "quality": lambda e: e["quality"] >= 0.85,
        "fast": lambda e: e["speed"] >= 0.9,
        "clone": lambda e: e["clone"],
        "draft": lambda e: e["offline"] and e["speed"] >= 0.9,
        "kahani": lambda e: e["offline"] and e["hindi"],
    }.get(task, lambda e: True)
    cands = [(n, e) for n, e in REGISTRY.items() if want(e)]
    cands.sort(key=lambda kv: -kv[1]["quality"])
    return {"task": task, "order": [n for n, _ in cands],
            "best": cands[0][0] if cands else None,
            "why": REGISTRY[cands[0][0]]["note"] if cands else "koi nahi"}


# ---------------- agent bus
def bus_send(frm: str, to: str, kind: str, payload: dict) -> dict:
    msg = {"ts": round(time.time(), 3), "from": frm, "to": to, "kind": kind, "payload": payload}
    BUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with BUS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return msg


def bus_demo() -> list[dict]:
    """4 agents ek doosre se baat karte hain — real handoff ke saath."""
    msgs = []
    msgs.append(bus_send("router", "piper", "render_request", {"text": "नमस्ते", "why": "offline kahani"}))
    msgs.append(bus_send("piper", "router", "render_reply", {"ok": True, "wav": "probe-piper.wav", "sr": SR}))
    msgs.append(bus_send("router", "edge", "quality_request", {"text": "नमस्ते", "why": "zyada natural"}))
    msgs.append(bus_send("edge", "elevenlabs", "handoff", {"reason": "internet block", "text": "नमस्ते"}))
    msgs.append(bus_send("elevenlabs", "router", "handoff_reply", {"ok": False, "reason": "key nahi"}))
    msgs.append(bus_send("router", "piper", "final", {"engine": "piper", "fallback_used": 2}))
    return msgs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--route", default="")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    tmp = ROOT / "work"; tmp.mkdir(exist_ok=True)
    out = {}
    if a.probe:
        res = {}
        for name, fn in PROBES.items():
            ok, detail = fn(tmp)
            res[name] = {"ok": ok, "detail": detail, **REGISTRY[name]}
        out["probe"] = res
        out["working"] = [n for n, r in res.items() if r["ok"]]
        if not a.json:
            for n, r in res.items():
                print(f"{'✅' if r['ok'] else '❌'} {n:12s} {r['kind']:16s} {r['detail']}")
            print("\nchal rahe:", ", ".join(out["working"]) or "koi nahi")
    if a.route:
        out["route"] = route(a.route)
        if not a.json:
            r = out["route"]
            print(f"task={r['task']} → best={r['best']} ({r['why']}) | order={r['order']}")
    if a.demo:
        out["demo"] = bus_demo()
        if not a.json:
            for m in out["demo"]:
                print(f"  {m['from']:10s} → {m['to']:10s} {m['kind']:15s} {json.dumps(m['payload'], ensure_ascii=False)[:60]}")
            print(f"\nbus file: {BUS_FILE}")
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ---------------- defaults + galti ledger (system_check inhe maangta hai)
CORE_ENGINES = ("piper", "espeak", "edge", "elevenlabs")


def ensure_defaults() -> list:
    """Bus ko shuru karo: registry me chaaron engine hon, bus file bani ho.

    Idempotent — jitni baar chalao, kuch bigadta nahi. Return: engine caps ki list
    (name, offline, key, quality) — system_check isi ko dekhta hai.
    """
    from collections import namedtuple
    Cap = namedtuple("Cap", "name offline key quality hindi clone")
    for name in CORE_ENGINES:
        REGISTRY.setdefault(name, {
            "kind": "unknown", "offline": False, "key": True,
            "quality": 0.5, "speed": 0.5, "hindi": True, "clone": False,
            "use": [], "note": "default (config nahi mila)",
        })
    BUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not BUS_FILE.exists():
        BUS_FILE.write_text("", encoding="utf-8")
    return [Cap(n, bool(e.get("offline")), bool(e.get("key")), float(e.get("quality", 0.5)),
                bool(e.get("hindi")), bool(e.get("clone")))
            for n, e in REGISTRY.items()]


def sudhaar_report() -> dict:
    """Kitni galtiyan bus par likhi hain (aur kaun si) — ledger ka saaf hisaab."""
    rows = []
    if BUS_FILE.exists():
        for line in BUS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    errs = [r for r in rows if str(r.get("kind", "")).lower() in ("error", "galti", "fail")]
    return {"total": len(rows), "total_errors": len(errs),
            "last_error": errs[-1] if errs else None}
