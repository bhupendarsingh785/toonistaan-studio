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
# Sirf PREMADE voices — free plan par yahi chalti hain (library voices 402 deti hain)
# Sirf 2 PREMADE voices (free plan par 100% chalti hain): Adam + Rachel.
# Bachche/dadi ka farak speed + pitch se banate hain.
ADAM = "pNInz6obpgDQGcFmaJgB"
RACHEL = "21m00Tcm4TlvDq8ikWAM"
DEFAULT_VOICES = {
    "male_adult": ADAM,
    "female_adult": RACHEL,
    "male_young": ADAM,
    "female_young": RACHEL,
    "male_old": ADAM,
    "female_old": RACHEL,
}
SAFE_VOICE = {"male": "pNInz6obpgDQGcFmaJgB", "female": "21m00Tcm4TlvDq8ikWAM"}

# hamare kirdaar -> kaunsi voice + settings
# (voice, speed, pitch) — pitch 1.0 = normal, 1.2 = bachcha, 0.9 = budha
KIRDAAR_VOICE = {
    "madhur": ("male_adult", 0.95, 1.0),
    "swara": ("female_adult", 0.97, 1.02),
    "swara_bachcha": ("female_young", 1.05, 1.18),
    "madhur_bachcha": ("male_young", 1.05, 1.16),
    "swara_dadi": ("female_old", 0.88, 0.92),
    "madhur_dada": ("male_old", 0.88, 0.90),
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
    voice_name, speed, pitch = KIRDAAR_VOICE.get(kirdaar, ("male_adult", 1.0, 1.0))
    env_override = os.environ.get(f"ELEVEN_VOICE_{voice_name.split('_')[0].upper()}", "").strip()
    voice_id = env_override or DEFAULT_VOICES.get(voice_name, DEFAULT_VOICES["male_adult"])
    payload = {
        "text": text,
        "model_id": os.environ.get("ELEVEN_MODEL", "eleven_multilingual_v2"),
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.8,
            "style": 0.0,
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
        # 402/403/404 = ye voice free plan me nahi -> safe premade voice se dobara
        if e.code in (401, 402, 403, 404, 422):
            gender = "female" if voice_name.startswith("female") else "male"
            safe_id = SAFE_VOICE[gender]
            if voice_id != safe_id:
                url2 = f"https://api.elevenlabs.io/v1/text-to-speech/{safe_id}"
                try:
                    audio = _post(url2, payload, {"xi-api-key": key, "Content-Type": "application/json",
                                                  "Accept": "audio/mpeg"})
                    if len(audio) > 2000:
                        open(out, "wb").write(audio)
                        print("ELEVEN_OK_SAFE", kirdaar, gender, len(audio), flush=True)
                        return True
                except Exception as e2:
                    print("ELEVEN_FAIL_SAFE", str(e2)[:60], flush=True)
        return False
    except Exception as e:
        print("ELEVEN_FAIL", str(e)[:80], flush=True)
        return False
    if len(audio) < 2000:
        print("ELEVEN_FAIL chhota audio", len(audio), flush=True)
        return False
    open(out, "wb").write(audio)
    if abs(speed - 1.0) > 0.02 or abs(pitch - 1.0) > 0.02:
        tmp = out.replace(".mp3", "_s.mp3")
        chain = []
        if abs(pitch - 1.0) > 0.02:
            chain.append(f"asetrate=44100*{pitch:.3f}")
            chain.append("aresample=44100")
            chain.append(f"atempo={1/pitch:.4f}")
        if abs(speed - 1.0) > 0.02:
            chain.append(f"atempo={speed:.3f}")
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", out,
                            "-filter:a", ",".join(chain), tmp], capture_output=True)
        if r.returncode == 0 and os.path.exists(tmp):
            os.replace(tmp, out)
    print("ELEVEN_OK", kirdaar, voice_name, len(audio), flush=True)
    return True


if __name__ == "__main__":
    print("elevenlabs key:", "hai" if have_eleven() else "nahi (edge-tts chalega)")
    if len(sys.argv) > 1:
        ok = eleven_tts(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "madhur", "/tmp/v.mp3")
        print("bani:", ok)
