"""Server-side: free scene images (Pollinations) + Hindi voices (Piper) for an episode JSON.
Run with Blender's bundled python:  PY gen_assets.py episode.json outdir
"""
import json, os, sys, time, subprocess, urllib.request, urllib.parse

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


def prompt_for(sc):
    p = sc["img"]
    for k, v in ep.get("cast", {}).items():
        p = p.replace(k, v)
    base = p + ep.get("style", "")
    try:
        return ai_enhance(sc, base)
    except Exception:
        return base


# voices first (fast) — edge-tts (free neural), Piper optional
EDGE = {"madhur": "hi-IN-MadhurNeural", "swara": "hi-IN-SwaraNeural",
        "pratham": "hi-IN-MadhurNeural", "priyamvada": "hi-IN-SwaraNeural"}
HAVE_PIPER = os.path.exists(PIPER)
from concurrent.futures import ThreadPoolExecutor as _TPE

def _mkvoice(job):
    sid, i, voice, text = job
    wav = f"{out}/{sid}_{i}.wav"
    if os.path.exists(wav) or os.path.exists(wav[:-4] + ".mp3"):
        return True
    v = EDGE.get(voice, "hi-IN-MadhurNeural")
    for tryv in (v, "hi-IN-SwaraNeural" if v == "hi-IN-MadhurNeural" else "hi-IN-MadhurNeural"):
        r = subprocess.run([sys.executable, "-m", "edge_tts", "--text", text, "--voice", tryv,
                            "--rate=" + ep.get("voice_rate", "-6%"), "--write-media", wav[:-4] + ".mp3"],
                           capture_output=True)
        if r.returncode == 0 and os.path.exists(wav[:-4] + ".mp3"):
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

_vjobs = [(sc["id"], i, voice, text) for sc in ep["scenes"] for i, (voice, text) in enumerate(sc["lines"])]
if _vjobs:
    with _TPE(max_workers=min(4, len(_vjobs))) as ex:
        list(ex.map(_mkvoice, _vjobs))
print("VOICES_OK", flush=True)

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
               f"?width={IW}&height={IH}&nologo=true&seed={base + v * 101}")
        jobs.append((jpg, url, key))

print("IMG_QUEUE", len(jobs), flush=True)

def fetch(job):
    jpg, url, key = job
    for attempt in range(6):
        try:
            data = subprocess.run(["curl", "-sL", "-m", "90", url], capture_output=True).stdout
            if len(data) > 5000:
                open(jpg, "wb").write(data)
                try:
                    open(f"{lib}/{key}.jpg", "wb").write(data)
                except Exception:
                    pass
                print("IMG_OK", os.path.basename(jpg), len(data), flush=True)
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
