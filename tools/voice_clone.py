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
import time
import numpy as np
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICES = ROOT / "voices"          # cloned voices yahan rehti hain
OUT = ROOT / "output"


class ConsentMissing(PermissionError):
    pass


@dataclass
class Voice:
    name: str
    audio: str                      # main reference (purana format bhi chalta rahe)
    transcript: str
    consent: bool
    backend: str = "indicf5"
    note: str = ""
    references: list = field(default_factory=list)   # [{audio, transcript, emotion, quality}]
    consent_note: str = ""
    consent_at: str = ""


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


def pick_backend(need_transcript: bool = False) -> str | None:
    """need_transcript=True ho to sirf wahi backend jo transcript maangta hai (indicf5)."""
    ready = [b["name"] for b in backend_status() if b["ready"] and b["name"] != "piper"]
    if not ready:
        return None
    if need_transcript:
        return "indicf5" if "indicf5" in ready else None
    # bina transcript: xtts pehle (usko transcript nahi chahiye)
    return "xtts" if "xtts" in ready else ready[0]


# ------------------------------------------------------------------ quality
def reference_quality(path: str) -> dict:
    """Reference ki jaanch: lambai, bolne ka hissa, shor ka andaza."""
    from tools import voice_extract as ve
    x = ve._load(path, 16000)
    dur = len(x) / 16000
    w = int(0.05 * 16000)
    rms = np.array([np.sqrt((x[i:i + w] ** 2).mean()) for i in range(0, max(1, len(x) - w), w)])
    floor = float(np.percentile(rms, 10)) if len(rms) else 0.0
    # bolne ka hissa: median ke aadhe se upar (constant awaaz bhi "bolna" gine)
    thr = max(0.01, float(np.median(rms)) * 0.5) if len(rms) else 0.01
    talk = float((rms > thr).mean()) if len(rms) else 0.0
    ok = dur >= 3.0 and talk >= 0.25
    why = []
    if dur < 3.0:
        why.append(f"bahut chhoti ({dur:.1f}s, kam se kam 3s)")
    if talk < 0.25:
        why.append(f"bolne ka hissa kam ({talk*100:.0f}%)")
    return {"duration_sec": round(dur, 2), "talk_ratio": round(talk, 2),
            "noise_floor": round(floor, 4), "ok": ok, "why": "; ".join(why)}


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
    q = reference_quality(meta["reference"])
    v = Voice(name=name, audio=meta["reference"], transcript=text, consent=True,
              backend=backend or (pick_backend() or "piper"),
              note=f"media se nikaala: {os.path.basename(media)} ({meta['duration_sec']}s); "
                   f"quality: {q['talk_ratio']*100:.0f}% bolna",
              references=[{"audio": meta["reference"], "transcript": text,
                           "emotion": "neutral", "quality": q}],
              consent_note="user ne --consent diya",
              consent_at=time.strftime("%Y-%m-%d %H:%M"))
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
    transcript = (transcript or "").strip()
    if not transcript:
        # transcript na ho to XTTS — usko sirf audio chahiye
        backend = backend or pick_backend(need_transcript=False)
        if backend == "indicf5":
            raise ValueError("indicf5 ko transcript chahiye; transcript na ho to backend xtts rakho")
    q = reference_quality(str(src))
    if not q["ok"]:
        raise ValueError(f"reference theek nahi: {q['why']} — saaf 3-15 second ki recording do")
    d = _voice_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, d / "reference.wav")
    v = Voice(name=name, audio=str(d / "reference.wav"), transcript=transcript.strip(),
              consent=True, backend=backend or (pick_backend() or "piper"),
              note=f"consent diya; quality: {q['talk_ratio']*100:.0f}% bolne ka hissa, {q['duration_sec']}s"
                   + ("" if transcript else "; transcript nahi (xtts backend)"),
              references=[{"audio": str(d / "reference.wav"), "transcript": transcript.strip(),
                           "emotion": "neutral", "quality": q}],
              consent_note="user ne --consent diya",
              consent_at=time.strftime("%Y-%m-%d %H:%M"))
    (d / "voice.json").write_text(json.dumps(v.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return v


def add_reference(name: str, audio: str, transcript: str, emotion: str = "neutral") -> Voice:
    """Usi awaaz ka doosra sample jodo (bhaav ya alag line) — cloning behtar hota hai."""
    v = load_voice(name)
    if not transcript.strip():
        raise ValueError("transcript khali hai")
    q = reference_quality(audio)
    if not q["ok"]:
        raise ValueError(f"reference theek nahi: {q['why']}")
    d = _voice_dir(name)
    dst = d / f"ref_{emotion}_{len(v.references)+1}.wav"
    shutil.copy2(audio, dst)
    v.references.append({"audio": str(dst), "transcript": transcript.strip(),
                         "emotion": emotion, "quality": q})
    (d / "voice.json").write_text(json.dumps(v.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return v


def pick_reference(v: Voice, emotion: str) -> tuple[str, str]:
    """Bhaav ka sample ho to wahi, warna neutral."""
    refs = v.references or [{"audio": v.audio, "transcript": v.transcript, "emotion": "neutral"}]
    for r in refs:
        if r.get("emotion") == emotion:
            return r["audio"], r["transcript"]
    for r in refs:
        if r.get("emotion") == "neutral":
            return r["audio"], r["transcript"]
    return refs[0]["audio"], refs[0]["transcript"]


def chunk_text(text: str, max_chars: int = 180) -> list[str]:
    """Lambi line ko chhote hisson me (clone models ki limit ke liye)."""
    if len(text) <= max_chars:
        return [text]
    parts, cur = [], ""
    for piece in text.replace("।", "।\n").split("\n"):
        piece = piece.strip()
        if not piece:
            continue
        if len(cur) + len(piece) + 1 > max_chars and cur:
            parts.append(cur); cur = piece
        else:
            cur = (cur + " " + piece).strip()
    if cur:
        parts.append(cur)
    return parts


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
def _render_line(backend: str, voice: Voice, text: str, out: Path, emotion: str = "neutral") -> bool:
    """Ek line us awaaz me. Backend ke hisaab se rasta."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if backend == "indicf5":
        ref_audio, ref_text = pick_reference(voice, emotion)
        cmd = [sys.executable, str(ROOT / "indicf5_fix_v1" / "indicf5_render.py"),
               "--text", text, "--ref-audio", ref_audio, "--ref-text", ref_text,
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
        ref_audio, _ = pick_reference(voice, emotion)
        tts.tts_to_file(text=text, speaker_wav=ref_audio, language="hi", file_path=str(out))
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


def _piper_fallback(voice: Voice, text: str, out: Path) -> bool:
    """Cloning backend na chale to piper se bol do — par file naam me saaf likha jaye."""
    import subprocess
    exe = shutil.which("piper")
    if not exe:
        return False
    model = os.environ.get("PIPER_MODEL", "")
    if not model or not Path(model).exists():
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([exe, "--model", model, "--output_file", str(out)],
                       input=text.encode(), capture_output=True)
    return r.returncode == 0 and out.exists() and out.stat().st_size > 1000


def speak(name: str, script_path: str, out_dir: str) -> dict:
    v = load_voice(name)
    backend = v.backend if v.backend in [b["name"] for b in backend_status() if b["ready"]] else pick_backend()
    lines = [l.strip() for l in Path(script_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    od = Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    done, failed = [], []
    used_fallback = 0
    for i, raw_line in enumerate(lines, 1):
        emo, line = parse_line(raw_line)
        pieces = chunk_text(line)
        made = []
        ok_all = bool(backend)
        for j, piece in enumerate(pieces, 1):
            f = od / (f"{i:03d}_{emo}.wav" if len(pieces) == 1 else f"{i:03d}_{emo}_{j}.wav")
            ok = bool(backend) and _render_line(backend, v, piece, f, emotion=emo)
            if not ok and shutil.which("piper"):          # saaf nishan ke saath fallback
                fb = od / f"{i:03d}_{emo}_{j}_piper_fallback.wav"
                ok = _piper_fallback(v, piece, fb)
                if ok:
                    used_fallback += 1
                    f = fb
            ok_all = ok_all and ok
            if ok:
                made.append(str(f))
        row = {"n": i, "emotion": emo, "line": line, "files": made,
               "file": made[0] if made else None,
               "fallback": any("piper_fallback" in m for m in made)}
        (done if ok_all else failed).append(row)
        print(("ok  " if ok_all else "FAIL"), i, f"[{emo}]", line[:38])
    return {"voice": name, "backend": backend or "koi nahi", "ok": len(done),
            "failed": len(failed), "fallback_lines": sum(1 for r in done if r.get("fallback")),
            "out": str(od), "lines": done + failed}


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
    ar = sub.add_parser("add-reference")
    ar.add_argument("--name", required=True); ar.add_argument("--audio", required=True)
    ar.add_argument("--transcript", required=True); ar.add_argument("--emotion", default="neutral")
    sub.add_parser("audit")
    s = sub.add_parser("speak")
    s.add_argument("--name", required=True); s.add_argument("--script", required=True)
    s.add_argument("--out", default=str(OUT / "clone"))
    a = ap.parse_args()
    if a.cmd == "backends":
        return cmd_backends()
    if a.cmd == "voices":
        return cmd_voices()
    if a.cmd == "add-reference":
        try:
            v = add_reference(a.name, a.audio, a.transcript, a.emotion)
            print(json.dumps({"voice": v.name, "references": len(v.references)}, ensure_ascii=False))
            return 0
        except Exception as exc:
            print(f"[x] {type(exc).__name__}: {exc}")
            return 1
    if a.cmd == "audit":
        rows = [{"voice": v.name, "consent": v.consent, "consent_at": v.consent_at,
                 "consent_note": v.consent_note, "refs": len(v.references),
                 "emotions": sorted({r.get("emotion", "neutral") for r in (v.references or [])})}
                for v in list_voices()]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0 if all(r["consent"] for r in rows) else 1
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
