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

import numpy as np
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
    # (voice, speed, pitch) — bachche aur bade me saaf farak
    "madhur": ("male_adult", 0.94, 0.96),        # narrator: bhaari, dheema
    "swara": ("female_adult", 0.97, 1.00),       # aurat
    "swara_bachcha": ("female_young", 1.12, 1.42),  # bachchi: patli + tez
    "madhur_bachcha": ("male_young", 1.10, 1.38),   # ladka: patla + tez
    "swara_dadi": ("female_old", 0.84, 0.86),    # dadi: bhaari + dheemi
    "madhur_dada": ("male_old", 0.82, 0.84),     # dada: sabse bhaari
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


# ---------------------------------------------------------------- Sarvam AI (bulbul)
SARVAM_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_SPEAKER = {
    # narrator
    "madhur": "shubh",
    # 16 kirdaar — har ek ki alag awaaz
    "arjun": "rahul", "meera": "ritu", "chacha": "dev", "chachi": "kavya",
    "dadi": "roopa", "pandit": "ashutosh", "constable": "ratan", "doctor": "varun",
    "bachcha": "soham", "sunita": "shreya", "driver": "manan", "bhoot": "aayan",
    "chudail": "ishita", "mukhiya": "sumit", "kaka": "kabir", "bhabhi": "pooja",
    "ramesh": "aditya", "salim": "rohan", "chaiwala": "sunny", "announce": "mani",
    "aurat": "neha", "maa": "kavitha", "behen": "tanya",
    # purane naam (compat)
    "swara": "ritu", "swara_bachcha": "priya", "madhur_bachcha": "rahul",
    "swara_dadi": "kavya", "madhur_dada": "dev",
}
# umar (age) ke hisaab se awaaz ki unchaai — dadi, ladki, bacchi, jawan, budha sab alag
# har kirdaar ki awaaz kis pitch par baithe (Hz me) — isse takraav nahi hota
SARVAM_TARGET_HZ = {
    "madhur": 104, "ramesh": 118, "salim": 132, "chaiwala": 148, "announce": 168,
    "constable": 126, "driver": 122, "doctor": 112,
    "maa": 232, "behen": 252, "aurat": 200, "meera": 210, "sunita": 205,
    "chachi": 225, "bhabhi": 215, "swara": 240, "swara_dadi": 190, "dadi": 186,
    "bachcha": 285, "swara_bachcha": 275,
    "bhoot": 88, "chudail": 172, "arjun": 110, "rahul": 115, "dev": 98,
    "kaka": 92, "pandit": 100, "mukhiya": 96, "madhur_dada": 90, "kavya": 220,
    "ritu": 235, "tanya": 258, "priya": 270, "kavitha": 228, "neha": 212,
    "rohan": 128, "aditya": 116, "shubh": 106, "mani": 120, "sunny": 140,
    "roopa": 196, "soham": 280, "aayan": 86,
}


SARVAM_PITCH = {
    # budhe / dadi
    "dadi": 0.86, "chacha": 0.94, "pandit": 0.92, "mukhiya": 0.90, "kaka": 0.95,
    "madhur_dada": 0.88, "swara_dadi": 0.87,
    # jawan mard
    "madhur": 1.0, "arjun": 1.0, "ramesh": 0.94, "salim": 1.03, "driver": 1.02,
    "constable": 0.97, "doctor": 1.0, "chaiwala": 1.06, "madhur_bachcha": 1.12,
    # jawan aurat
    "meera": 1.04, "sunita": 1.03, "aurat": 1.03, "chachi": 1.02, "bhabhi": 1.05,
    "swara": 1.02, "behen": 1.16, "maa": 0.94,
    # bacche / bacchi
    "bachcha": 1.34, "swara_bachcha": 1.30,
    # daravani
    "bhoot": 0.80, "chudail": 0.88,
    "announce": 1.12,
}


SARVAM_PACE = {
    "ramesh": 0.98, "salim": 1.02, "chaiwala": 1.06, "announce": 1.12,
    "aurat": 1.0, "maa": 0.90, "behen": 1.12,
    "madhur": 1.0, "arjun": 1.02, "meera": 1.0, "chacha": 0.92, "chachi": 1.05,
    "dadi": 0.86, "pandit": 0.88, "constable": 0.95, "doctor": 0.98, "bachcha": 1.1,
    "sunita": 1.0, "driver": 1.0, "bhoot": 0.78, "chudail": 0.82, "mukhiya": 0.9,
    "kaka": 0.95, "bhabhi": 1.02,
    "swara": 1.0, "swara_bachcha": 1.08, "madhur_bachcha": 1.06,
    "swara_dadi": 0.9, "madhur_dada": 0.88,
}
SARVAM_TEMP = {
    "madhur": 0.85, "arjun": 0.8, "meera": 0.8, "chacha": 0.78, "chachi": 0.82,
    "dadi": 0.8, "pandit": 0.75, "constable": 0.7, "doctor": 0.7, "bachcha": 0.85,
    "sunita": 0.78, "driver": 0.75, "bhoot": 0.9, "chudail": 0.9, "mukhiya": 0.75,
    "kaka": 0.75, "bhabhi": 0.8, "ramesh": 0.8, "salim": 0.82, "chaiwala": 0.85,
    "announce": 0.6, "aurat": 0.8, "maa": 0.85, "behen": 0.85,
    "swara": 0.8, "swara_bachcha": 0.75, "madhur_bachcha": 0.78,
    "swara_dadi": 0.82, "madhur_dada": 0.8,
}



def sarvam_key():
    k = (os.environ.get("SARVAM_API_KEY") or "").strip().strip('"').strip("'")
    return re.sub(r"[^A-Za-z0-9\-_]", "", k)


def have_sarvam():
    return bool(sarvam_key())


def sarvam_tts(text, kirdaar="madhur", out="out.wav"):
    """Sarvam bulbul se awaaz (Hindi storytelling). Fail -> False."""
    key = sarvam_key()
    if not key:
        return False
    import base64
    speaker = os.environ.get(f"SARVAM_SPEAKER_{kirdaar.upper()}") or SARVAM_SPEAKER.get(kirdaar, "shubh")
    payload = {
        "text": str(text)[:2400],
        "language_code": os.environ.get("SARVAM_LANG", "hi-IN"),
        "speaker": speaker,
        "model": os.environ.get("SARVAM_MODEL", "bulbul:v3"),
        "pace": float(os.environ.get("SARVAM_PACE", SARVAM_PACE.get(kirdaar, 1.0))),
        "temperature": float(os.environ.get("SARVAM_TEMP", "0.7")),
        "speech_sample_rate": 24000,
        "output_audio_codec": "wav",
    }
    try:
        raw = _post(SARVAM_URL, payload, {"api-subscription-key": key,
                                          "Content-Type": "application/json"})
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:200]
        except Exception:
            pass
        print("SARVAM_FAIL", e.code, body, flush=True)
        return False
    except Exception as e:
        print("SARVAM_FAIL", str(e)[:80], flush=True)
        return False
    try:
        data = json.loads(raw.decode("utf-8", "ignore"))
        audios = data.get("audios") or []
        if not audios:
            print("SARVAM_FAIL khaali audios", flush=True)
            return False
        audio = base64.b64decode(audios[0])
    except Exception as e:
        print("SARVAM_FAIL decode", str(e)[:60], flush=True)
        return False
    if len(audio) < 2000:
        print("SARVAM_FAIL chhota", len(audio), flush=True)
        return False
    open(out, "wb").write(audio)

    # pitch (umar ke hisaab se) — dadi bhaari, bacchi patli
    pitch = SARVAM_PITCH.get(kirdaar, 1.0)
    if abs(pitch - 1.0) > 0.02:
        try:
            import shutil, subprocess, tempfile
            ff = shutil.which("ffmpeg")
            if not ff:
                import imageio_ffmpeg
                ff = imageio_ffmpeg.get_ffmpeg_exe()
            tmp = tempfile.mktemp(suffix=".wav")
            af = f"asetrate=24000*{pitch:.3f},aresample=44100,atempo={1/pitch:.4f}"
            r = subprocess.run([ff, "-loglevel", "error", "-y", "-i", out, "-filter:a", af,
                                "-ac", "1", "-ar", "44100", tmp], capture_output=True)
            if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 2000:
                os.replace(tmp, out)
        except Exception as e:
            print("SARVAM_PITCH_FAIL", str(e)[:50], flush=True)

    # ---- closed loop: naap kar target pitch par le jao (awaazein na milen) ----
    try:
        _tune_to_target(out, kirdaar)
    except Exception as e:
        print("SARVAM_TUNE_SKIP", str(e)[:50], flush=True)

    print("SARVAM_OK", kirdaar, speaker, payload["pace"], f"pitch={pitch}", len(audio), flush=True)
    return True


def _measure_pitch(path):
    """Awaaz ki median pitch (Hz) — autocorrelation se."""
    import wave
    try:
        with wave.open(path) as w:
            sr = w.getframerate()
            raw = w.readframes(min(w.getnframes(), sr * 8))
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return None
    if len(x) < sr // 2:
        return None
    win, hop = int(sr * 0.04), int(sr * 0.02)
    vals = []
    for i in range(0, len(x) - win, hop):
        f = x[i:i + win] - x[i:i + win].mean()
        if np.sqrt((f ** 2).mean()) < 1e-3:
            continue
        ac = np.correlate(f, f, "full")[len(f) - 1:]
        lo, hi = int(sr / 400), min(int(sr / 70), len(ac) - 1)
        if hi <= lo + 2:
            continue
        lag = lo + int(np.argmax(ac[lo:hi]))
        if lag:
            vals.append(sr / lag)
    if len(vals) < 5:
        return None
    return float(np.median(vals))


def _tune_to_target(path, kirdaar):
    """Awaaz ko target Hz ke kareeb le jao (sur nahi bigadta)."""
    target = SARVAM_TARGET_HZ.get(kirdaar)
    if not target:
        return False
    cur = _measure_pitch(path)
    if not cur or cur <= 0:
        return False
    factor = target / cur
    factor = max(0.72, min(1.42, factor))
    if abs(factor - 1.0) < 0.03:
        return False
    import subprocess, tempfile
    ff = None
    try:
        import shutil
        ff = shutil.which("ffmpeg")
        if not ff:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return False
    tmp = tempfile.mktemp(suffix=".wav")
    af = f"asetrate=44100*{factor:.4f},aresample=44100,atempo={1/factor:.4f}"
    r = subprocess.run([ff, "-loglevel", "error", "-y", "-i", path, "-filter:a", af,
                        "-ac", "1", "-ar", "44100", tmp], capture_output=True)
    if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 2000:
        os.replace(tmp, path)
        return True
    return False


def list_voices():
    """Account par jo voices available hain (free plan par sirf kuch)."""
    key = eleven_key()
    if not key:
        return []
    try:
        req = urllib.request.Request("https://api.elevenlabs.io/v1/voices",
                                     headers={"xi-api-key": key, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=40) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        print("VOICES_LIST_FAIL", str(e)[:70], flush=True)
        return []
    out = []
    for v in (data.get("voices") or []):
        labels = v.get("labels") or {}
        out.append({"id": v.get("voice_id"), "name": v.get("name"),
                    "gender": (labels.get("gender") or "").lower(),
                    "category": v.get("category") or ""})
    return out


_CACHE = {}


def pick_voice(gender="male"):
    """Account ki available list se male/female voice chuno (cache)."""
    if gender in _CACHE:
        return _CACHE[gender]
    vs = list_voices()
    cand = [v for v in vs if v["gender"] == gender] or vs
    if not cand:
        _CACHE[gender] = ADAM
        return ADAM
    # premade pehle
    cand.sort(key=lambda v: 0 if v["category"] == "premade" else 1)
    _CACHE[gender] = cand[0]["id"]
    print("VOICE_PICK", gender, cand[0]["name"], cand[0]["category"], flush=True)
    return cand[0]["id"]


def eleven_tts(text, kirdaar="madhur", out="out.mp3"):
    """ElevenLabs se awaaz. Fail -> False."""
    key = eleven_key()
    if not key:
        return False
    voice_name, speed, pitch = KIRDAAR_VOICE.get(kirdaar, ("male_adult", 1.0, 1.0))
    env_override = os.environ.get(f"ELEVEN_VOICE_{voice_name.split('_')[0].upper()}", "").strip()
    gender = "female" if voice_name.startswith("female") else "male"
    voice_id = env_override or pick_voice(gender) or DEFAULT_VOICES.get(voice_name, ADAM)
    payload = {
        "text": text,
        "model_id": os.environ.get("ELEVEN_MODEL", "eleven_flash_v2_5"),
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
            body = e.read().decode("utf-8", "ignore")[:400]
        except Exception:
            pass
        print("ELEVEN_FAIL", e.code, body, flush=True)
        # 402/403/404 = ye voice free plan me nahi -> safe premade voice se dobara
        if e.code in (401, 402, 403, 404, 422):
            gender = "female" if voice_name.startswith("female") else "male"
            safe_id = SAFE_VOICE[gender]
            # (a) doosra model try karo
            alt = "eleven_multilingual_v2" if payload["model_id"] != "eleven_multilingual_v2" else "eleven_flash_v2_5"
            for mid in (alt, "eleven_turbo_v2_5"):
                try:
                    pl = dict(payload); pl["model_id"] = mid
                    au = _post(f"https://api.elevenlabs.io/v1/text-to-speech/{safe_id}", pl,
                               {"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
                    if len(au) > 2000:
                        open(out, "wb").write(au)
                        print("ELEVEN_OK_MODEL", kirdaar, mid, len(au), flush=True)
                        return True
                except Exception as e3:
                    print("ELEVEN_MODEL_FAIL", mid, str(e3)[:50], flush=True)
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
