#!/usr/bin/env python3
"""ASTRA Voice Clone — kisi ki bhi awaaz copy karke poori script usi awaaz me.

Kaam kaise hota hai (3 step):
  1) enroll  — 5-15 second ki recording + uska exact transcript + ijazat (consent)
  2) speak   — script ki har line us awaaz me banti hai
  3) mix     — lines jod kar ek file (background ke saath, agar chahiye)

Backends (jo machine par chale, wahi use hoga):
  indicf5  — free, reference audio + transcript se cloning (GPU chahiye)
  xtts     — Coqui XTTS-v2 (GPU/CPU, dheema par chalta hai)
  piper    — cloning NAHI karta (sirf fallback; saaf-saaf batata hai)

Ijazat (consent) lazmi:
  Bina consent ke enroll nahi hota. Ye guard jaan-boojh kar rakha hai —
  kisi ki awaaz uski permission ke bina copy karna galat hai.

Commands:
  python tools/voice_clone.py backends
  python tools/voice_clone.py enroll --name dadi --audio dadi.wav --transcript "..." --consent
  python tools/voice_clone.py voices
  python tools/voice_clone.py speak --name dadi --script story.txt --out output/dadi/
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICES = ROOT / "voices"          # cloned voices yahan rehti hain
OUT = ROOT / "output"


class ConsentMissing(PermissionError):
    pass


@dataclass
class Voice:
    name: str
    audio: str
    transcript: str
    consent: bool
    backend: str = "indicf5"
    note: str = ""


# ------------------------------------------------------------------ backends
def backend_status() -> list[dict]:
    out = []
    # indicf5: model + GPU
    try:
        import torch  # noqa
        has_torch = True
    except Exception:
        has_torch = False
    out.append({"name": "indicf5", "ready": has_torch,
                "why": "torch mila" if has_torch else "torch nahi (pip install torch; 8GB+ RAM/GPU)"})
    try:
        import TTS  # noqa  (Coqui)
        xtts = True
    except Exception:
        xtts = False
    out.append({"name": "xtts", "ready": xtts,
                "why": "Coqui TTS mila" if xtts else "Coqui TTS nahi (pip install TTS)"})
    piper = shutil.which("piper") is not None
    out.append({"name": "piper", "ready": piper,
                "why": "piper mila (par ye cloning NAHI karta)" if piper else "piper nahi"})
    return out


def pick_backend() -> str | None:
    for b in backend_status():
        if b["ready"] and b["name"] != "piper":
            return b["name"]
    return None


# ------------------------------------------------------------------ voices
def _voice_dir(name: str) -> Path:
    return VOICES / name


def enroll_from_media(name: str, media: str, consent: bool, seconds: float = 12.0,
                      transcript: str = "", backend: str = "") -> Voice:
    """Video/audio se awaaz nikaal kar enroll — extract + clean + (transcript)."""
    from tools import voice_extract as ve
    if not consent:
        raise ConsentMissing(
            "Ijazat ke bina enroll nahi hoga. --consent do (awaaz uski hi ho ya likhit permission ho).")
    d = _voice_dir(name); d.mkdir(parents=True, exist_ok=True)
    meta = ve.run(media, str(d), seconds=seconds, do_clean=True)
    text = (transcript or meta.get("transcript") or "").strip()
    if not text:
        raise ValueError("transcript nahi mila — recording me jo bola gaya wahi --transcript me do")
    v = Voice(name=name, audio=meta["reference"], transcript=text, consent=True,
              backend=backend or (pick_backend() or "piper"),
              note=f"media se nikaala: {os.path.basename(media)} ({meta['duration_sec']}s)")
    (d / "voice.json").write_text(json.dumps(v.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return v


def enroll(name: str, audio: str, transcript: str, consent: bool, backend: str = "") -> Voice:
    if not consent:
        raise ConsentMissing(
            "Ijazat ke bina enroll nahi hoga. --consent do (aur yaad rakho: "
            "awaaz uski hi honi chahiye ya likhit permission ho).")
    src = Path(audio)
    if not src.exists():
        raise FileNotFoundError(f"recording nahi mili: {audio}")
    if not transcript.strip():
        raise ValueError("transcript khali hai — recording me jo bola gaya, bilkul wahi likho")
    d = _voice_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, d / "reference.wav")
    v = Voice(name=name, audio=str(d / "reference.wav"), transcript=transcript.strip(),
              consent=True, backend=backend or (pick_backend() or "piper"),
              note="consent: user ne di")
    (d / "voice.json").write_text(json.dumps(v.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return v


def list_voices() -> list[Voice]:
    out = []
    if not VOICES.exists():
        return out
    for d in sorted(VOICES.iterdir()):
        f = d / "voice.json"
        if f.exists():
            try:
                out.append(Voice(**json.loads(f.read_text(encoding="utf-8"))))
            except Exception:
                continue
    return out


def load_voice(name: str) -> Voice:
    f = _voice_dir(name) / "voice.json"
    if not f.exists():
        raise FileNotFoundError(f"voice nahi mili: {name} (pehle enroll karo)")
    return Voice(**json.loads(f.read_text(encoding="utf-8")))


# ------------------------------------------------------------------ render
def _render_line(backend: str, voice: Voice, text: str, out: Path) -> bool:
    """Ek line us awaaz me. Backend ke hisaab se rasta."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if backend == "indicf5":
        cmd = [sys.executable, str(ROOT / "indicf5_fix_v1" / "indicf5_render.py"),
               "--text", text, "--ref-audio", voice.audio, "--ref-text", voice.transcript,
               "--out", str(out), "--device", os.environ.get("CLONE_DEVICE", "cpu")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("  indicf5 fail:", (r.stderr or r.stdout).strip()[-160:])
            return False
        return out.exists() and out.stat().st_size > 1000
    if backend == "xtts":
        try:
            from TTS.api import TTS  # noqa
        except Exception:
            return False
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        tts.tts_to_file(text=text, speaker_wav=voice.audio, language="hi", file_path=str(out))
        return out.exists() and out.stat().st_size > 1000
    return False


EMOTIONS = ("neutral", "dukh", "khushi", "gussa", "dar", "pyaar", "hasai", "rona")


def parse_line(line: str) -> tuple[str, str]:
    """Line se bhaav nikalo: '[dukh] बेटा...' ya 'दादी [gussa]: ...'"""
    import re
    m = re.search(r"\[(" + "|".join(EMOTIONS) + r")\]", line)
    if not m:
        return "neutral", line.strip()
    emo = m.group(1)
    text = (line[:m.start()] + line[m.end():]).strip()
    text = re.sub(r"^[:\-\s]+", "", text)      # bacha hua colon hatao
    # "दादी : बेटा..." jaisa speaker prefix hatao (chhota naam hi)
    text = re.sub(r"^[^:\n]{1,20}:\s*", "", text)
    return emo, text


def speak(name: str, script_path: str, out_dir: str) -> dict:
    v = load_voice(name)
    backend = v.backend if v.backend in [b["name"] for b in backend_status() if b["ready"]] else pick_backend()
    lines = [l.strip() for l in Path(script_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    od = Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    done, failed = [], []
    for i, raw_line in enumerate(lines, 1):
        emo, line = parse_line(raw_line)
        f = od / f"{i:03d}_{emo}.wav"
        ok = bool(backend) and _render_line(backend, v, line, f)
        row = {"n": i, "emotion": emo, "line": line, "file": str(f) if ok else None}
        (done if ok else failed).append(row)
        print(("ok  " if ok else "FAIL"), i, f"[{emo}]", line[:38])
    return {"voice": name, "backend": backend or "koi nahi", "ok": len(done),
            "failed": len(failed), "out": str(od), "lines": done + failed}


def cmd_backends() -> int:
    for b in backend_status():
        print(f"{'[READY]' if b['ready'] else '[ --  ]'} {b['name']:9s} {b['why']}")
    print(f"\nChuna jayega: {pick_backend() or 'koi nahi (cloning ke liye indicf5 ya xtts chahiye)'}")
    return 0


def cmd_voices() -> int:
    vs = list_voices()
    if not vs:
        print("koi voice enroll nahi hui")
        return 0
    for v in vs:
        print(f"{v.name:12s} backend={v.backend:9s} consent={'haan' if v.consent else 'NAHI'} "
              f"| {v.transcript[:40]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ASTRA voice clone (consent ke saath)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backends"); sub.add_parser("voices")
    e = sub.add_parser("enroll")
    e.add_argument("--name", required=True); e.add_argument("--audio", required=True)
    e.add_argument("--transcript", required=True); e.add_argument("--consent", action="store_true")
    e.add_argument("--backend", default="")
    e.add_argument("--from-media", default="", help="video ya audio file (mp4/mp3/wav)")
    e.add_argument("--seconds", type=float, default=12.0)
    s = sub.add_parser("speak")
    s.add_argument("--name", required=True); s.add_argument("--script", required=True)
    s.add_argument("--out", default=str(OUT / "clone"))
    a = ap.parse_args()
    if a.cmd == "backends":
        return cmd_backends()
    if a.cmd == "voices":
        return cmd_voices()
    if a.cmd == "enroll":
        try:
            if a.from_media:
                v = enroll_from_media(a.name, a.from_media, a.consent, a.seconds,
                                      a.transcript or "", a.backend)
            else:
                v = enroll(a.name, a.audio, a.transcript, a.consent, a.backend)
            print(json.dumps(v.__dict__, ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            print(f"[x] {type(exc).__name__}: {exc}")
            return 1
    rep = speak(a.name, a.script, a.out)
    print(json.dumps({k: rep[k] for k in ("voice", "backend", "ok", "failed", "out")},
                     ensure_ascii=False, indent=2))
    return 0 if rep["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
