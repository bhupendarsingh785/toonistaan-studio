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
    "bachcha": "priya", "sunita": "shreya", "driver": "manan", "bhoot": "aayan",
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
    "madhur": 112, "ramesh": 118, "salim": 138, "chaiwala": 150, "announce": 168,
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
    "madhur": 1.0, "arjun": 1.0, "ramesh": 0.86, "salim": 1.03, "driver": 1.02,
    "constable": 0.97, "doctor": 1.0, "chaiwala": 1.15, "madhur_bachcha": 1.12,
    # jawan aurat
    "meera": 1.04, "sunita": 1.03, "aurat": 1.03, "chachi": 1.02, "bhabhi": 1.05,
    "swara": 1.02, "behen": 1.16, "maa": 0.94,
    # bacche / bacchi
    "bachcha": 1.30, "swara_bachcha": 1.30,
    # daravani
    "bhoot": 0.80, "chudail": 0.88,
    "announce": 1.35,
}


# ---------------------------------------------------------------- awaaz ki list (astra/voices.json)
def _load_voices():
    """astra/voices.json se kirdaar, speaker, pitch, pace, hz padho.
    JSON me jo ho wahi jeetta hai; jo nahi hai wo neeche wale default rahenge."""
    import os as _os, json as _json
    here = _os.path.dirname(_os.path.abspath(__file__))
    path = _os.path.join(_os.path.dirname(here), "astra", "voices.json")
    if not _os.path.exists(path):
        return {}
    try:
        data = _json.load(open(path, encoding="utf-8"))
        return data.get("characters", {})
    except Exception:
        return {}


VOICES = _load_voices()
for _k, _v in VOICES.items():
    if _v.get("sarvam"):
        SARVAM_SPEAKER[_k] = _v["sarvam"]
    if isinstance(_v.get("pitch"), (int, float)):
        SARVAM_PITCH[_k] = float(_v["pitch"])
    if isinstance(_v.get("hz"), (int, float)):
        SARVAM_TARGET_HZ[_k] = int(_v["hz"])


# ---------------------------------------------------------------- umar / kism ke hisaab se awaaz ka rang
# dadi ki awaaz ladki jaisi nahi lagni chahiye — isliye kism ke hisaab se
# pitch, raftaar aur kampan (tremolo) alag. Ye filter har engine ke baad lagta hai.
AGE_STYLE = {
    # kism                pitch-guna, atempo, tremolo (freq, depth) ya None, lowpass, highpass
    "female_old":   (0.94, 0.93, (3.2, 0.16), 7200, None),
    "male_old":     (0.95, 0.94, (3.0, 0.14), 7600, None),
    "child":        (1.00, 1.02, None, None, 180),
    "creature":     (0.96, 0.92, (5.0, 0.35), 6000, None),
    "announce":     (1.00, 1.00, None, None, 260),
}


def _kism(kirdaar):
    v = VOICES.get(kirdaar) or {}
    return v.get("kism") or ""


def age_filters(kirdaar):
    """Us kirdaar ke umar/kism ke ffmpeg filters (list)."""
    st = AGE_STYLE.get(_kism(kirdaar))
    if not st:
        return []
    pitch, tempo, trem, lp, hp = st
    out = []
    if abs(pitch - 1.0) > 0.01:
        out.append(f"asetrate=44100*{pitch:.3f}")
        out.append("aresample=44100")
        out.append(f"atempo={1/pitch:.4f}")
    if abs(tempo - 1.0) > 0.01:
        out.append(f"atempo={tempo:.3f}")
    if trem:
        out.append(f"tremolo=f={trem[0]}:d={trem[1]}")
    if lp:
        out.append(f"lowpass=f={lp}")
    if hp:
        out.append(f"highpass=f={hp}")
    return out


def fit_to_target(path, kirdaar, verbose=True, rounds=1):
    """Awaaz ko us kirdaar ke target Hz par le jao — 2-3 chhote kadam me.

    Pehle sabko ek hi Hz par kheencha gaya tha (wo galat tha).
    Yahan HAR kirdaar ka apna target hai (voices.json me `hz`).
    """
    target = SARVAM_TARGET_HZ.get(kirdaar)
    if not target or not os.path.exists(path):
        return None
    try:
        import shutil, subprocess, tempfile
        ff = shutil.which("ffmpeg")
        if not ff:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        cur = _measure_pitch(path)
        if not cur:
            return None
        for _ in range(int(rounds)):
            if abs(cur - target) / float(target) <= 0.08:
                break
            factor = max(0.55, min(1.60, float(target) / float(cur)))
            tmp = tempfile.mktemp(suffix=".mp3")
            af = f"aresample=44100,rubberband=pitch={factor:.4f}:formant=preserved"
            r = subprocess.run([ff, "-loglevel", "error", "-y", "-i", path, "-filter:a", af,
                                "-ac", "1", "-ar", "44100", "-b:a", "128k", tmp], capture_output=True)
            if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 2000:
                break
            try:
                os.replace(tmp, path)
            except OSError:
                import shutil as _sh
                _sh.move(tmp, path)          # alag device par os.replace fail hota hai
            nxt = _measure_pitch(path)
            if not nxt or abs(nxt - cur) < 2:
                break
            cur = nxt
        if verbose:
            print("FIT", kirdaar, f"-> {round(cur)}Hz (chaha {target})", flush=True)
        return round(cur)
    except Exception as e:
        print("FIT_FAIL", str(e)[:60], flush=True)
    return None


def shape_age(path, kirdaar):
    """File par umar ke filters laga do (jagah par hi badal deta hai)."""
    flt = age_filters(kirdaar)
    if not flt or not os.path.exists(path):
        return False
    try:
        import shutil, subprocess, tempfile
        ff = shutil.which("ffmpeg")
        if not ff:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        tmp = tempfile.mktemp(suffix=".mp3")
        r = subprocess.run([ff, "-loglevel", "error", "-y", "-i", path,
                            "-filter:a", ",".join(flt), "-ac", "1", "-ar", "44100",
                            "-b:a", "128k", tmp], capture_output=True)
        if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 2000:
            os.replace(tmp, path)
            return True
    except Exception as e:
        print("AGE_SHAPE_FAIL", str(e)[:60], flush=True)
    return False


def voice_cast():
    """Poori list — naam, kism, speaker, pitch, hz."""
    out = {}
    for k, v in VOICES.items():
        out[k] = {"naam": v.get("naam", k), "kism": v.get("kism", ""),
                  "sarvam": SARVAM_SPEAKER.get(k), "pitch": SARVAM_PITCH.get(k),
                  "pace": v.get("pace"), "hz": SARVAM_TARGET_HZ.get(k)}
    return out


SARVAM_PACE = {
    "ramesh": 0.98, "salim": 1.02, "chaiwala": 1.06, "announce": 1.12,
    "aurat": 1.0, "maa": 0.98, "behen": 1.12,
    "madhur": 1.0, "arjun": 1.02, "meera": 1.0, "chacha": 0.98, "chachi": 1.05,
    "dadi": 0.97, "pandit": 0.97, "constable": 0.95, "doctor": 0.98, "bachcha": 1.1,
    "sunita": 1.0, "driver": 1.0, "bhoot": 0.9, "chudail": 0.92, "mukhiya": 0.97,
    "kaka": 0.95, "bhabhi": 1.02,
    "swara": 1.0, "swara_bachcha": 1.08, "madhur_bachcha": 1.06,
    "swara_dadi": 0.97, "madhur_dada": 0.97,
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


# ---------------------------------------------------------------- PIPER (offline, free)
PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN"
PIPER_VOICES = {
    "male": "pratham",
    "female": "priyamvada",
}


def _piper_dir():
    d = os.environ.get("ASTRA_PIPER_DIR") or os.path.expanduser("~/.cache/astra_piper")
    os.makedirs(d, exist_ok=True)
    return d


def have_piper():
    """piper install hai? (model baad me download hoga)"""
    try:
        import importlib.util
        return importlib.util.find_spec("piper") is not None
    except Exception:
        return False


def _piper_model(gender="male"):
    """Hindi voice model — ek baar download, phir offline."""
    name = PIPER_VOICES.get(gender, "pratham")
    d = _piper_dir()
    onnx = os.path.join(d, f"hi_IN-{name}-medium.onnx")
    conf = onnx + ".json"
    if os.path.exists(onnx) and os.path.exists(conf) and os.path.getsize(onnx) > 1_000_000:
        return onnx
    import urllib.request
    for f in (os.path.basename(onnx), os.path.basename(conf)):
        url = f"{PIPER_BASE}/{name}/medium/{f}"
        try:
            urllib.request.urlretrieve(url, os.path.join(d, f))
        except Exception as e:
            print("PIPER_DL_FAIL", f, str(e)[:50], flush=True)
            return None
    return onnx if os.path.exists(onnx) else None


def _piper_gender(kirdaar):
    """Kirdaar female hai ya male — awaaz chunne ke liye."""
    female = {"maa", "behen", "aurat", "meera", "sunita", "chachi", "bhabhi", "swara",
              "swara_dadi", "dadi", "chudail", "kavya", "ritu", "tanya", "priya",
              "kavitha", "neha", "roopa", "swara_bachcha", "bachchi"}
    return "female" if str(kirdaar).lower() in female else "male"



_PIPER_SESSIONS = {}

def _piper_session(model_path):
    """Piper model ek hi baar load ho (har line par 2-3 second bachta hai)."""
    if model_path in _PIPER_SESSIONS:
        return _PIPER_SESSIONS[model_path]
    try:
        from piper import PiperVoice
        voice = PiperVoice.load(model_path)
        _PIPER_SESSIONS[model_path] = voice
        return voice
    except Exception:
        _PIPER_SESSIONS[model_path] = None
        return None


def _piper_inprocess(text, model, out_path, length_scale=1.0):
    """Bina subprocess — seedha python se (tez)."""
    voice = _piper_session(model)
    if voice is None:
        return False
    try:
        import wave
        from piper import SynthesisConfig
        cfg = SynthesisConfig(length_scale=float(length_scale))
        with wave.open(out_path, "wb") as wf:
            voice.synthesize_wav(text, wf, syn_config=cfg)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 3000
    except Exception:
        return False


def piper_tts(text, kirdaar="madhur", out="out.wav", bhaav=None):
    """PIPER = poora OFFLINE (internet band ho to bhi chalta hai). 0 kharch."""
    if not have_piper():
        return False
    model = _piper_model(_piper_gender(kirdaar))
    if not model:
        return False
    tmp = out + ".piper.wav"
    pace = SARVAM_PACE.get(kirdaar, 1.0)
    _st = _bhaav_style(bhaav)
    pace = pace * _st["pace"]                      # bhaav se raftaar
    ls = 1.0 / max(0.6, min(1.5, pace))
    # tez raasta: model ek baar load, phir seedha python se
    fast_ok = _piper_inprocess(str(text), model, tmp, length_scale=ls)
    if not fast_ok:                                  # in-process fail to CLI (backup)
        cmd = [sys.executable, "-m", "piper", "--model", model, "--output_file", tmp,
               "--length_scale", f"{ls:.3f}"]
        try:
            r = subprocess.run(cmd, input=str(text).encode("utf-8"), capture_output=True, timeout=180)
        except Exception:
            return False
        if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 3000:
            print("PIPER_FAIL", (r.stderr or b"")[-120:].decode("utf-8", "ignore"), flush=True)
            return False

    # kirdaar ka pitch (baaki engines jaisa hi)
    pitch = SARVAM_PITCH.get(kirdaar, 1.0) * _st["pitch"]   # bhaav se sur
    ff = None
    try:
        import shutil
        ff = shutil.which("ffmpeg")
        if not ff:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return False
    # ---- ek hi ffmpeg pass: sur + target Hz + umar + highpass + loudnorm ----
    target = SARVAM_TARGET_HZ.get(kirdaar)
    total_pitch = float(pitch)
    if target:
        try:
            cur = _measure_pitch(tmp)
            if cur and cur > 0:
                # target tak le jao, par ek hi baar (dobara naapo mat — waqt bachta hai)
                total_pitch *= max(0.6, min(1.6, float(target) / float(cur)))
        except Exception:
            pass
    af = []
    if abs(total_pitch - 1.0) > 0.02:
        af.append(f"rubberband=pitch={total_pitch:.4f}:formant=preserved")
    af.append("highpass=f=60")
    af += age_filters(kirdaar)
    af.append("volume=1.1")          # loudnorm se sasta, kaam kaafi hai
    r2 = subprocess.run([ff, "-loglevel", "error", "-y", "-i", tmp,
                         "-filter:a", ",".join(af), "-ac", "1", "-ar", "24000",
                         "-b:a", "128k", out], capture_output=True)
    try:
        os.remove(tmp)
    except Exception:
        pass
    return r2.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 3000


EDGE_VOICES = {"male": "hi-IN-MadhurNeural", "female": "hi-IN-SwaraNeural",
               "child": "hi-IN-SwaraNeural", "old_female": "hi-IN-SwaraNeural",
               "old_male": "hi-IN-MadhurNeural"}


def edge_tts(text: str, kirdaar: str = "madhur", out: str = "out.mp3",
             bhaav=None) -> bool:
    """Microsoft Edge ki neural awaaz — internet chahiye, key nahi.

    Sandbox me proxy + apna CA chahiye, isliye SSL context khud banate hain
    (edge_tts andar certifi hardcode karta hai — usse override karte hain).
    """
    import asyncio, os, ssl
    from pathlib import Path
    style = _bhaav_style(bhaav)
    kism = _kism(kirdaar)
    voice = EDGE_VOICES.get(kism, EDGE_VOICES["male"])
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import edge_tts
        import edge_tts.communicate as C
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        ca = os.environ.get("SSL_CERT_FILE")
        if ca and os.path.exists(ca):
            ctx.load_verify_locations(cafile=ca)
        C._SSL_CTX = ctx
        rate = f"{int((style['pace'] - 1.0) * 100):+d}%"
        pitch = f"{int((style['pitch'] - 1.0) * 50):+d}Hz"
        com = edge_tts.Communicate(str(text), voice, rate=rate, pitch=pitch,
                                   proxy=os.environ.get("HTTPS_PROXY") or None)
        asyncio.run(com.save(str(out_path)))
        return out_path.exists() and out_path.stat().st_size > 1000
    except Exception:
        import shutil, subprocess
        binary = shutil.which("edge-tts")
        if not binary:
            return False
        cmd = [binary, "--voice", voice, "--text", str(text),
               "--write-media", str(out_path)]
        proxy = os.environ.get("HTTPS_PROXY")
        if proxy:
            cmd += ["--proxy", proxy]
        r = subprocess.run(cmd, capture_output=True)
        return r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1000


def have_edge() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:
        import shutil
        return shutil.which("edge-tts") is not None


def have_espeak() -> bool:
    """espeak-ng ka library hai? (pip ka espeakng-loader — binary ki zaroorat nahi)."""
    try:
        import espeakng_loader  # noqa: F401
        return True
    except Exception:
        import shutil
        return shutil.which("espeak-ng") is not None


def espeak_tts(text: str, kirdaar: str = "madhur", out: str = "out.wav",
               bhaav=None) -> bool:
    """espeak-ng se awaaz — offline, bina kisi key ke. Bhaav se raftaar/sur badalta hai."""
    import ctypes, wave
    from pathlib import Path
    style = _bhaav_style(bhaav)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import espeakng_loader
        lib = ctypes.CDLL(espeakng_loader.get_library_path())
        data_path = espeakng_loader.get_data_path().encode()
    except Exception:
        import shutil, subprocess
        binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if not binary:
            return False
        rate = int(150 * style["pace"])
        r = subprocess.run([binary, "-v", "hi", "-s", str(rate), "-w", str(out_path), text],
                           capture_output=True)
        return r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1000
    lib.espeak_Initialize(2, 0, data_path, 0)
    if lib.espeak_SetVoiceByName(b"hi") != 0:
        lib.espeak_SetVoiceByName(b"en")
    lib.espeak_SetParameter(1, int(150 * style["pace"]), 0)      # 1 = rate (words/min)
    lib.espeak_SetParameter(3, int(max(0, min(99, 50 * style["pitch"]))), 0)  # 3 = pitch
    chunks: list[bytes] = []

    CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short),
                          ctypes.c_int, ctypes.c_void_p)

    def _cb(wav, n, events):
        if wav and n > 0:
            raw = ctypes.cast(wav, ctypes.POINTER(ctypes.c_char * (n * 2))).contents
            chunks.append(bytes(bytearray(raw)))
        return 0

    cb = CB(_cb)
    lib.espeak_SetSynthCallback(cb)
    lib.espeak_Synth(str(text).encode("utf-8"), 0, 0, 1, 0, 0, None, None)
    audio = b"".join(chunks)
    if not audio:
        return False
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(audio)
    return out_path.stat().st_size > 1000


def have_sarvam():
    return bool(sarvam_key())


_LEARNED_CACHE: dict = {}


def _learned_style() -> dict:
    """teacher_student.py se seekha hua style (naapa hua) — cache ke saath."""
    if _LEARNED_CACHE:
        return _LEARNED_CACHE
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parent.parent / "astra" / "learned_style.json"
    if f.exists():
        try:
            _LEARNED_CACHE.update(json.loads(f.read_text(encoding="utf-8")).get("style", {}))
        except Exception:
            pass
    return _LEARNED_CACHE


def _bhaav_style(bhaav) -> dict:
    """Style ka sach: pehle **seekha hua (naapa hua)**, warna bhavna.py ka default."""
    emo = str(bhaav or "neutral")
    base = {"emotion": "neutral", "pitch": 1.0, "pace": 1.0, "energy": 1.0, "gap_ms": 220}
    try:
        from tools import bhavna
        base = dict(bhavna.style(emo))
    except Exception:
        pass
    learned = _learned_style().get(emo)
    if learned:
        base.update({k: learned[k] for k in ("pitch", "pace", "energy", "gap_ms") if k in learned})
        base["source"] = "learned"
    else:
        base["source"] = "default"
    return base


# ---------------------------------------------------------------- bhaav (emotion) style
# (temperature, pace-guna, pitch-guna) — Sarvam ke andar bhaav laane ke liye
EMOTION_STYLE = {
    "calm":      (0.70, 1.00, 1.00),
    "normal":    (0.70, 1.00, 1.00),
    "sad":       (0.62, 0.94, 0.96),   # dheema, dabba hua
    "dukh":      (0.62, 0.94, 0.96),
    "emotional": (0.66, 0.96, 0.97),
    "scared":    (0.86, 1.08, 1.06),   # tez, kaanpta
    "dar":       (0.86, 1.08, 1.06),
    "happy":     (0.82, 1.06, 1.07),
    "khushi":    (0.82, 1.06, 1.07),
    "excited":   (0.88, 1.12, 1.10),
    "angry":     (0.90, 1.10, 0.97),   # tez, gehra
    "gussa":     (0.90, 1.10, 0.97),
    "surprised": (0.85, 1.08, 1.08),
    "whisper":   (0.60, 0.92, 1.02),
}

# Hindi me swabhavik rukavat ke liye jodne wale shabd
_JOINERS = (" और ", " पर ", " लेकिन ", " क्योंकि ", " इसलिए ", " फिर ", " जब ", " जैसे ", " मगर ")


def prep_text(text):
    """Sarvam ko insan jaisi Hindi do: number shabd, comma, saaf spacing."""
    t = str(text).strip()
    if not t:
        return t
    t = re.sub(r"\s+", " ", t)
    # angrezi ank -> Hindi shabd (chhote ank)
    _num = {0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पाँच", 6: "छह",
            7: "सात", 8: "आठ", 9: "नौ", 10: "दस", 11: "ग्यारह", 12: "बारह",
            20: "बीस", 30: "तीस", 40: "चालीस", 50: "पचास", 100: "सौ"}
    def _n(m):
        try:
            v = int(m.group(0))
        except Exception:
            return m.group(0)
        return _num.get(v, m.group(0))
    t = re.sub(r"\b\d{1,3}\b", _n, t)
    # jodne wale shabd se pehle comma (swabhavik saans)
    for j in _JOINERS:
        t = t.replace(j, " " + j.strip() + ", ")
    t = re.sub(r",\s*,+", ",", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+([,.।!?])", r"\1", t)
    if not t.endswith((".", "।", "?", "!", "…")):
        t += "।"
    return t


def sarvam_tts(text, kirdaar="madhur", out="out.wav", bhaav=None):
    """Sarvam bulbul se awaaz — bhaav (emotion) ke saath. Fail -> False."""
    key = sarvam_key()
    if not key:
        return False
    import base64
    speaker = os.environ.get(f"SARVAM_SPEAKER_{kirdaar.upper()}") or SARVAM_SPEAKER.get(kirdaar, "shubh")
    temp0, pace0, pitch0 = EMOTION_STYLE.get(str(bhaav or "calm").lower(), EMOTION_STYLE["calm"])
    _st = _bhaav_style(bhaav)                      # bhavna.py (11 bhaav)
    pace0 = pace0 * _st["pace"]
    pitch0 = pitch0 * _st["pitch"]
    payload = {
        "text": prep_text(text)[:2400],
        "language_code": os.environ.get("SARVAM_LANG", "hi-IN"),
        "speaker": speaker,
        "model": os.environ.get("SARVAM_MODEL", "bulbul:v3"),
        "pace": round(float(os.environ.get("SARVAM_PACE", SARVAM_PACE.get(kirdaar, 1.0))) * pace0, 3),
        # naapa hua calibration: pitch param 0.3 ≈ +21% F0  =>  1.0 ≈ 70%
        "pitch": round(float(os.environ.get("SARVAM_PITCH_PARAM", "0")) + (pitch0 - 1.0) / 0.7, 3),
        "loudness": round(1.0 * _st["energy"], 3),
        "temperature": float(os.environ.get("SARVAM_TEMP", str(temp0))),
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
    pitch = SARVAM_PITCH.get(kirdaar, 1.0) * pitch0
    if abs(pitch - 1.0) > 0.02:
        try:
            import shutil, subprocess, tempfile
            ff = shutil.which("ffmpeg")
            if not ff:
                import imageio_ffmpeg
                ff = imageio_ffmpeg.get_ffmpeg_exe()
            tmp = tempfile.mktemp(suffix=".wav")
            _af = [f"asetrate=24000*{pitch:.3f}", "aresample=44100", f"atempo={1/pitch:.4f}"]
            _af += age_filters(kirdaar)
            af = ",".join(_af)
            r = subprocess.run([ff, "-loglevel", "error", "-y", "-i", out, "-filter:a", af,
                                "-ac", "1", "-ar", "44100", tmp], capture_output=True)
            if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 2000:
                os.replace(tmp, out)
        except Exception as e:
            print("SARVAM_PITCH_FAIL", str(e)[:50], flush=True)

    # (closed-loop tuning band — usne sab kirdaaron ko ek hi pitch par le liya tha)

    try:
        _naturalize(out, text)
    except Exception:
        pass

    # pitch jaanch: target se bahut door ho to batao (chupaya nahi jaata)
    try:
        _t = SARVAM_TARGET_HZ.get(kirdaar)
        _p = _measure_pitch(out)
        if _t and _p:
            if abs(_p - _t) / _t > 0.30:
                print("SARVAM_PITCH_MISS", kirdaar, f"chaha {_t}Hz mila {round(_p)}Hz", flush=True)
            elif os.environ.get("ASTRA_VERBOSE_PITCH"):
                print("SARVAM_PITCH_OK", kirdaar, f"{round(_p)}Hz", flush=True)
    except Exception:
        pass

    print("SARVAM_OK", kirdaar, speaker, payload["pace"], f"pitch={pitch}", len(audio), flush=True)
    return True


def _measure_pitch(path):
    """Awaaz ki median pitch (Hz) — ffmpeg se decode (mp3/wav dono)."""
    sr = 16000
    ff = None
    try:
        import shutil
        ff = shutil.which("ffmpeg")
        if not ff:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
    r = subprocess.run([ff, "-loglevel", "error", "-i", path, "-t", "8",
                        "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True)
    if r.returncode != 0 or len(r.stdout) < sr:
        return None
    x = np.frombuffer(r.stdout, dtype=np.float32)
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
    if abs(factor - 1.0) < 0.04:
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
        # doosra pass: ab naap kar bacha hua farak theek karo
        cur2 = _measure_pitch(path)
        if cur2 and cur2 > 0:
            f2 = max(0.8, min(1.25, target / cur2))
            if abs(f2 - 1.0) > 0.04:
                tmp2 = tempfile.mktemp(suffix=".wav")
                af2 = f"asetrate=44100*{f2:.4f},aresample=44100,atempo={1/f2:.4f}"
                r2 = subprocess.run([ff, "-loglevel", "error", "-y", "-i", path, "-filter:a", af2,
                                     "-ac", "1", "-ar", "44100", tmp2], capture_output=True)
                if r2.returncode == 0 and os.path.exists(tmp2) and os.path.getsize(tmp2) > 2000:
                    os.replace(tmp2, path)
        return True
    return False


def _naturalize(path, text):
    """Bolne ki raftaar normal karo: na khinch kar bolna, na bahut jaldi.

    Hindi narration ~ 12.5 akshar/second. Isse zyada lamba = khinch raha hai.
    """
    if not text:
        return False
    n_chars = len(re.sub(r"\s+", "", text))
    if n_chars < 8:
        return False
    cur = _dur_seconds(path)
    if not cur or cur <= 0.2:
        return False
    target = n_chars / 12.5
    ratio = cur / target              # >1 = dheema/khincha hua
    if ratio <= 1.12 and ratio >= 0.80:
        return False                  # theek hai, chhedo mat
    factor = max(0.85, min(1.30, ratio))   # atempo se theek karo
    if abs(factor - 1.0) < 0.04:
        return False
    ff = None
    try:
        import shutil
        ff = shutil.which("ffmpeg")
        if not ff:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return False
    import tempfile
    tmp = tempfile.mktemp(suffix=".wav")
    r = subprocess.run([ff, "-loglevel", "error", "-y", "-i", path,
                        "-filter:a", f"atempo={factor:.4f}",
                        "-ac", "1", "-ar", "44100", tmp], capture_output=True)
    if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 2000:
        os.replace(tmp, path)
        return True
    return False


def _dur_seconds(path):
    ff = None
    try:
        import shutil
        ff = shutil.which("ffmpeg")
        if not ff:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return 0.0
    r = subprocess.run([ff, "-i", path], capture_output=True)
    for line in (r.stderr or b"").decode("utf-8", "ignore").splitlines():
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m2, sec = t.split(":")
            return int(h) * 3600 + int(m2) * 60 + float(sec)
    return 0.0


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
    if abs(speed - 1.0) > 0.02 or abs(pitch - 1.0) > 0.02 or age_filters(kirdaar):
        tmp = out.replace(".mp3", "_s.mp3")
        chain = []
        if abs(pitch - 1.0) > 0.02:
            chain.append(f"asetrate=44100*{pitch:.3f}")
            chain.append("aresample=44100")
            chain.append(f"atempo={1/pitch:.4f}")
        if abs(speed - 1.0) > 0.02:
            chain.append(f"atempo={speed:.3f}")
        chain += age_filters(kirdaar)
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
