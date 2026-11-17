#!/usr/bin/env python3
"""
ASTRA VOICE PROVIDERS — awaaz ke liye kai raste (bina key bhi chalta hai).

Kram (jo mile wahi pehle):
  1. ElevenLabs   -> sabse insan jaisi awaaz (free 10k akshar/mahina). Key: ELEVENLABS_API_KEY
  2. edge-tts     -> Microsoft neural Hindi (free, hamesha). Key ki zaroorat nahi.

ElevenLabs key FREE milti hai: https://elevenlabs.io/app/settings/api-keys
GitHub secret: ELEVENLABS_API_KEY

Kirdaar -> ElevenLabs voice (default multilingual voice ids; apni voice id bhi daal sakte ho
env ELEVEN_VOICE_MADHUR / ELEVEN_VOICE_SWARA me).
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# ElevenLabs ke public multilingual voices (stable ids)
DEFAULT_VOICES = {
    "male_adult": "pNInz6obpgDQGcFmaJgB",     # Adam - deep male
    "female_adult": "EXAVITQu4vr4xnSDxMaL",   # Sarah - warm female
    "male_young": "TX3LPaxmHKxFdv7VOQHJ",     # Liam - young male
    "female_young": "XB0fDUnXU5powFXDhCwa",   # Charlotte
    "male_old": "onwK4e9ZLuTAKqWW03F9",       # Daniel - mature
    "female_old": "pFZP5JQG7iQjIQuC4Bku",     # Lily
}

# hamare kirdaar -> kaunsi voice + settings
KIRDAAR_VOICE = {
    "madhur": ("male_adult", 0.92, 1.0),        # (voice, speed, style)
    "swara": ("female_adult", 0.95, 1.0),
    "swara_bachcha": ("female_young", 1.06, 1.15),
    "madhur_bachcha": ("male_young", 1.06, 1.15),
    "swara_dadi": ("female_old", 0.88, 0.9),
    "madhur_dada": ("male_old", 0.88, 0.9),
}


def eleven_key():
    k = (os.environ.get("ELEVENLABS_API_KEY") or "").strip().strip('"').strip("'")
    return re.sub(r"[^A-Za-z0-9_\-]", "", k)


def have_eleven():
    return bool(eleven_key())


def _post(url, data, headers, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def eleven_tts(text, kirdaar="madhur", out="out.mp3"):
    """ElevenLabs se awaaz. Fail -> False."""
    key = eleven_key()
    if not key:
        return False
    voice_name, speed, style = KIRDAAR_VOICE.get(kirdaar, ("male_adult", 1.0, 1.0))
    env_override = os.environ.get(f"ELEVEN_VOICE_{voice_name.split('_')[0].upper()}", "").strip()
    voice_id = env_override or DEFAULT_VOICES.get(voice_name, DEFAULT_VOICES["male_adult"])
    payload = {
        "text": text,
        "model_id": os.environ.get("ELEVEN_MODEL", "eleven_multilingual_v2"),
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.8,
            "style": min(1.0, max(0.0, (style - 1.0) * 2)),
            "use_speaker_boost": True,
        },
    }
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    try:
        audio = _post(url, payload, {"xi-api-key": key, "Content-Type": "application/json",
                                     "Accept": "audio/mpeg"})
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:160]
        except Exception:
            pass
        print("ELEVEN_FAIL", e.code, body, flush=True)
        return False
    except Exception as e:
        print("ELEVEN_FAIL", str(e)[:80], flush=True)
        return False
    if len(audio) < 2000:
        print("ELEVEN_FAIL chhota audio", len(audio), flush=True)
        return False
    open(out, "wb").write(audio)
    if abs(speed - 1.0) > 0.02:
        tmp = out.replace(".mp3", "_s.mp3")
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", out,
                            "-filter:a", f"atempo={speed:.3f}", tmp], capture_output=True)
        if r.returncode == 0 and os.path.exists(tmp):
            os.replace(tmp, out)
    print("ELEVEN_OK", kirdaar, voice_name, len(audio), flush=True)
    return True


if __name__ == "__main__":
    print("elevenlabs key:", "hai" if have_eleven() else "nahi (edge-tts chalega)")
    if len(sys.argv) > 1:
        ok = eleven_tts(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "madhur", "/tmp/v.mp3")
        print("bani:", ok)
