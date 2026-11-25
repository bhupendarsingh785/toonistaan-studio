"""Server-side: free scene images (Pollinations) + Hindi voices (Piper) for an episode JSON.
Run with Blender's bundled python:  PY gen_assets.py episode.json outdir
"""
import json, os, sys, time, subprocess, urllib.request, urllib.parse
import numpy as np

PIPER = "/opt/tools/piper/piper"
VOICES = {"pratham": "/opt/tools/voices/hi_pratham.onnx", "priyamvada": "/opt/tools/voices/hi_priyamvada.onnx"}

ep = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
seed = ep.get("seed", 11)


try:
    import ai as _ai
except Exception:
    _ai = None

def ai_enhance(sc, base_prompt):
    """Key ho to scene ka image prompt AI se behtar karo. Na ho to wahi wapas."""
    if _ai is None or not _ai.have_any_key():
        return base_prompt
    cast = ", ".join(ep.get("cast", {}).values())[:300]
    out = _ai.enhance_image_prompt(sc.get("img", ""), ep.get("style", ""), cast)
    if out:
        print("IMG_PROMPT_AI", sc.get("id"), flush=True)
        return out + ep.get("style", "")
    return base_prompt


STYLE_LOCK = ("3D animated cartoon movie still, Pixar style stylized character design, "
               "consistent character face and clothes, bright cinematic lighting, high detail, 8k")
STYLE_AVOID = ("photorealistic, real photograph, real human photo, blurry, dark, low quality, "
               "text, watermark, deformed face, extra fingers")

def prompt_for(sc):
    p = sc["img"]
    for k, v in ep.get("cast", {}).items():
        p = p.replace(k, v)
    cast_line = ""
    if ep.get("cast"):
        cast_line = " | characters: " + "; ".join(ep["cast"].values())[:400]
    # scene pehle (warna AI har scene me wahi tasveer bana deta hai), phir style + kirdaar
    base = (f"{p}. {STYLE_LOCK}. same characters and same clothes as described: {cast_line.strip(' |')}"
            f"{ep.get('style', '')}. negative: {STYLE_AVOID}")
    try:
        out = ai_enhance(sc, base)
        return out if out else base
    except Exception:
        return base


# voices first (fast) — edge-tts (free neural), Piper optional
# (voice -> (edge voice, pitch factor))  — pitch 1.0 = normal, >1 = patli/bachche jaisi
EDGE = {
    "madhur":     ("hi-IN-MadhurNeural", 1.0),    # aadmi
    "pratham":    ("hi-IN-MadhurNeural", 1.0),    # aadmi (purana naam)
    "swara":      ("hi-IN-SwaraNeural", 1.0),     # aurat
    "priyamvada": ("hi-IN-SwaraNeural", 1.0),     # aurat (purana naam)
    "bachcha":    ("hi-IN-SwaraNeural", 1.22),    # bachcha (patli awaaz)
    "child":      ("hi-IN-SwaraNeural", 1.22),
    "budha":      ("hi-IN-MadhurNeural", 0.90),   # budha (bhaari awaaz)
    "dadi":       ("hi-IN-SwaraNeural", 0.92),    # dadi
    "aurat":      ("hi-IN-SwaraNeural", 1.0),
    "aadmi":      ("hi-IN-MadhurNeural", 1.0),
}
HAVE_PIPER = os.path.exists(PIPER)
from concurrent.futures import ThreadPoolExecutor as _TPE

AWAZ_TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "awaaz.py")

# hamare naam -> awaaz tool ke kirdaar
AWAZ_KIRDAAR = {
    "bachcha": "swara_bachcha", "child": "swara_bachcha",
    "dadi": "swara_dadi", "budha": "madhur_dada",
    "madhur": "madhur", "pratham": "madhur",
    "swara": "swara", "priyamvada": "swara", "aurat": "swara", "aadmi": "madhur",
}


def _voice_by_tool(text, voice, mp3):
    """tools/awaaz.py se awaaz: kirdaar + bhaav (darr/khushi/dukh) + saaf chain. Fail -> False."""
    if not os.path.exists(AWAZ_TOOL):
        return False
    k = AWAZ_KIRDAAR.get(voice, "madhur")
    r = subprocess.run([sys.executable, AWAZ_TOOL, "bolo", text, "--kirdaar", k, "-o", mp3],
                       capture_output=True)
    ok = r.returncode == 0 and os.path.exists(mp3) and os.path.getsize(mp3) > 1500
    if ok:
        print("VOICE_TOOL", os.path.basename(mp3), k, flush=True)
    return ok


def _mkvoice(job):
    sid, i, voice, text = job
    wav = f"{out}/{sid}_{i}.wav"
    if os.path.exists(wav) or os.path.exists(wav[:-4] + ".mp3"):
        return True
    v, pitch = EDGE.get(voice, ("hi-IN-MadhurNeural", 1.0))
    mp3 = wav[:-4] + ".mp3"
    if _voice_by_tool(text, voice, mp3):
        return True
    for tryv in (v, "hi-IN-SwaraNeural" if v == "hi-IN-MadhurNeural" else "hi-IN-MadhurNeural"):
        r = subprocess.run([sys.executable, "-m", "edge_tts", "--text", text, "--voice", tryv,
                            "--rate=" + ep.get("voice_rate", "-6%"), "--write-media", mp3],
                           capture_output=True)
        if r.returncode == 0 and os.path.exists(mp3):
            if abs(pitch - 1.0) > 0.01:
                tmp = mp3.replace(".mp3", "_p.mp3")
                f = pitch
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", mp3,
                                "-filter:a", f"asetrate=24000*{f},aresample=24000,atempo={1/f:.4f}",
                                tmp], capture_output=True)
                if os.path.exists(tmp) and os.path.getsize(tmp) > 1000:
                    os.replace(tmp, mp3)
            return True
    if HAVE_PIPER:
        try:
            subprocess.run([PIPER, "-m", VOICES.get(voice, VOICES["pratham"]), "-f", wav,
                            "--length_scale", "1.05", "--sentence_silence", "0.25"],
                           input=text.encode(), check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass
    print("VOICE_FAIL", sid, i, flush=True)
    return False

VOICE_MAP = ep.get("voices", {})   # jaise {"CHHOTU":"bachcha","DADI":"dadi"}

def voice_for(sc, voice, text):
    """Episode ke 'voices' map se kirdaar ki awaaz chuno."""
    if VOICE_MAP:
        blob = (sc.get("img", "") + " " + text).upper()
        for name, v in VOICE_MAP.items():
            if name.upper() in blob:
                return v
    return voice

_vjobs = [(sc["id"], i, voice_for(sc, voice, text), text) for sc in ep["scenes"] for i, (voice, text) in enumerate(sc["lines"])]
if _vjobs:
    with _TPE(max_workers=min(4, len(_vjobs))) as ex:
        list(ex.map(_mkvoice, _vjobs))
_made = 0
try:
    _made = len([f for f in os.listdir(out) if f.endswith((".mp3", ".wav"))])
except Exception:
    pass
print("VOICES_OK", _made, "files", flush=True)

# Variants: "variants": N (episode ya scene level) -> <id>_v0.jpg .. v{N-1}; best ko <id>.jpg naam do.
# Sirf kuch scene dobara: python gen_assets.py ep.json out s04,s06   (purani file hata kar naya seed)
only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
NEG = ep.get("negative", " no text, no watermark")
FAST = bool(ep.get("fast"))
IW = int(ep.get("w", 1280) * (0.8 if FAST else 1))
IH = int(ep.get("h", 720) * (0.8 if FAST else 1))

import hashlib, shutil
from concurrent.futures import ThreadPoolExecutor as _TPE2
lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library")
os.makedirs(lib, exist_ok=True)

jobs = []
for sc in ep["scenes"]:
    if only and sc["id"] not in only:
        continue
    if sc.get("use"):
        continue
    n = sc.get("variants", ep.get("variants", 1))
    base = sc.get("seed", seed)
    for v in range(n):
        jpg = f"{out}/{sc['id']}.jpg" if n == 1 else f"{out}/{sc['id']}_v{v}.jpg"
        if os.path.exists(jpg) and os.path.getsize(jpg) > 5000:
            continue
        key = hashlib.md5((prompt_for(sc) + str(base + v * 101)).encode()).hexdigest()[:16]
        if os.path.exists(f"{lib}/{key}.jpg"):
            shutil.copy(f"{lib}/{key}.jpg", jpg)
            print("IMG_LIB", os.path.basename(jpg), flush=True)
            continue
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt_for(sc) + "," + NEG) +
               f"?width={IW}&height={IH}&nologo=true&model=flux&enhance=true&seed={base + v * 101 + (abs(hash(sc['id'])) % 97) * 7}")
        jobs.append((jpg, url, key))

print("IMG_QUEUE", len(jobs), flush=True)

def fetch(job):
    jpg, url, key = job
    for attempt in range(6):
        try:
            data = subprocess.run(["curl", "-sL", "-m", "90", url], capture_output=True).stdout
            if len(data) > 5000:
                # ---- clarity agent: dhundhli tasveer dobara banao ----
                score = 999.0
                try:
                    import cv2 as _cv
                    _img = _cv.imdecode(np.frombuffer(data, np.uint8), _cv.IMREAD_COLOR)
                    if _img is not None:
                        g = _cv.cvtColor(_img, _cv.COLOR_BGR2GRAY)
                        score = float(_cv.Laplacian(g, _cv.CV_64F).var())
                except Exception:
                    pass
                if score < 12 and attempt < 3:
                    print("IMG_BLUR", os.path.basename(jpg), round(score, 1), "-> dobara", flush=True)
                    url = url.split("&seed=")[0] + "&seed=" + str(int(time.time()) % 99999)
                    time.sleep(2)
                    continue
                open(jpg, "wb").write(data)
                try:
                    open(f"{lib}/{key}.jpg", "wb").write(data)
                except Exception:
                    pass
                print("IMG_OK", os.path.basename(jpg), len(data), "sharp", round(score, 1), flush=True)
                return True
        except Exception:
            pass
        time.sleep(3 + attempt * 3)
    print("IMG_FAIL", os.path.basename(jpg), flush=True)
    return False

if jobs:
    with _TPE2(max_workers=min(3 if FAST else 2, len(jobs))) as ex:
        res = list(ex.map(fetch, jobs))
    missed = [j for j, ok in zip(jobs, res) if not ok]
    if missed:
        print("IMG_RETRY_SERIAL", len(missed), flush=True)
        for j in missed:
            fetch(j)

print("ALL_DONE", flush=True)
