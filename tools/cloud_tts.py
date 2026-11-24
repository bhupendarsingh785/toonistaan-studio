#!/usr/bin/env python3
"""cloud_tts.py — natural awaaz ke liye cloud TTS (piper local, par robotic).

Kaun chalta hai (key env me honi chahiye — chat me kabhi nahi):
  SARVAM_API_KEY      → api.sarvam.ai (bulbul, Hindi natural, per-speaker)
  ELEVENLABS_API_KEY  → elevenlabs.io (sabse natural Hindi)
  (edge-tts/gTTS network se block hain — is sandbox me nahi chalte)

  python tools/cloud_tts.py --status
  python tools/cloud_tts.py --say "नमस्ते" --out a.wav --voice anushka
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))

SARVAM_SPEAKERS = {"anushka": "anushka", "manisha": "manisha", "vidya": "vidya",
                   "arya": "arya", "abhilash": "abhilash", "karun": "karun",
                   "hitesh": "hitesh"}
EL_VOICES = {"anushka": "21m00Tcm4TlvDq8ikWAM", "manisha": "EXAVITQu4vr4xnSDxMaL"}


def status() -> dict:
    s = {"sarvam": bool(os.environ.get("SARVAM_API_KEY")),
         "elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY")),
         "piper": True}
    s["best"] = "elevenlabs" if s["elevenlabs"] else ("sarvam" if s["sarvam"] else "piper")
    return s


def _curl(url, headers, data=None, out=None):
    cmd = ["curl", "-sS", "-X", "POST", url, "--max-time", "120"]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    if data is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    if out:
        cmd += ["-o", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def sarvam_say(text: str, out: Path, speaker="anushka", lang="hi-IN") -> bool:
    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"inputs": [text], "target_language_code": lang, "speaker": SARVAM_SPEAKERS.get(speaker, speaker),
               "model": "bulbul:v2", "speech_sample_rate": 24000}
    rc, so, se = _curl("https://api.sarvam.ai/text-to-speech",
                       {"api-subscription-key": key}, payload, out)
    return rc == 0 and out.exists() and out.stat().st_size > 2000


def eleven_say(text: str, out: Path, voice="anushka", model="eleven_multilingual_v2") -> bool:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        return False
    vid = EL_VOICES.get(voice, voice)
    out.parent.mkdir(parents=True, exist_ok=True)
    rc, so, se = _curl(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
                       {"xi-api-key": key, "Accept": "audio/mpeg"},
                       {"text": text, "model_id": model,
                        "voice_settings": {"stability": 0.4, "similarity_boost": 0.75}}, out)
    return rc == 0 and out.exists() and out.stat().st_size > 2000


def say(text: str, out: Path, voice="anushka") -> str:
    """Sabse achha jo available ho, wahi use karo (elevenlabs > sarvam > piper)."""
    if eleven_say(text, out, voice):
        return "elevenlabs"
    if sarvam_say(text, out, voice):
        return "sarvam"
    from tools.voice_provider import piper_tts
    piper_tts(text, "गौरी", str(out))
    return "piper"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--say", default="")
    ap.add_argument("--out", default="/scratch/work/cloud.wav")
    ap.add_argument("--voice", default="anushka")
    a = ap.parse_args()
    if a.status:
        print(json.dumps(status(), ensure_ascii=False)); return 0
    if a.say:
        used = say(a.say, Path(a.out), a.voice)
        print(json.dumps({"used": used, "out": a.out}, ensure_ascii=False)); return 0
    print(json.dumps(status(), ensure_ascii=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
