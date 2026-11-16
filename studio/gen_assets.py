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


def prompt_for(sc):
    p = sc["img"]
    for k, v in ep.get("cast", {}).items():
        p = p.replace(k, v)
    return p + ep.get("style", "")


# voices first (fast)
# Behtar awaaz (Microsoft neural, free, internet chahiye): madhur (aadmi), swara (aurat) -> .mp3
EDGE = {"madhur": "hi-IN-MadhurNeural", "swara": "hi-IN-SwaraNeural"}
from concurrent.futures import ThreadPoolExecutor as _TPE
_voice_jobs = []
for sc in ep["scenes"]:
    for i, (voice, text) in enumerate(sc["lines"]):
        _voice_jobs.append((sc["id"], i, voice, text))

def _mkvoice(job):
    sid, i, voice, text = job
    wav = f"{out}/{sid}_{i}.wav"
    if os.path.exists(wav) or os.path.exists(wav[:-4] + ".mp3"):
        return
    v = EDGE.get(voice, "hi-IN-MadhurNeural")
    r = subprocess.run([sys.executable, "-m", "edge_tts", "--text", text, "--voice", v,
                        "--rate=" + ep.get("voice_rate", "-6%"), "--write-media", wav[:-4] + ".mp3"],
                       capture_output=True)
    if r.returncode != 0:
        print("VOICE_FAIL", sid, i, r.stderr.decode()[-120:], flush=True)

# awaaz parallel (4 ek saath) — pehle ek-ek karke dheere tha
with _TPE(max_workers=4) as ex:
    list(ex.map(_mkvoice, _voice_jobs))
print("VOICES_OK", flush=True)

# Variants: "variants": N (episode ya scene level) -> <id>_v0.jpg .. v{N-1}; best ko <id>.jpg naam do.
# Sirf kuch scene dobara: python gen_assets.py ep.json out s04,s06   (purani file hata kar naya seed)
only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
NEG = ep.get("negative", " no text, no watermark")

import hashlib, shutil, threading
from concurrent.futures import ThreadPoolExecutor
lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library")
os.makedirs(lib, exist_ok=True)

jobs = []   # (jpg, url, key)
for sc in ep["scenes"]:
    if only and sc["id"] not in only:
        continue
    if sc.get("use"):      # dusre scene ki tasveer (crop/camera alag)
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
               f"?width={ep.get('w', 1280)}&height={ep.get('h', 720)}&nologo=true&seed={base + v * 101}")
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
        except Exception as e:
            print("IMG_RETRY", os.path.basename(jpg), str(e)[:60], flush=True)
        time.sleep(4 + attempt * 3)
    print("IMG_FAIL", os.path.basename(jpg), flush=True)
    return False

# tez: 4 images ek saath (pehle ek-ek karke 45 sec wait karta tha)
if jobs:
    with ThreadPoolExecutor(max_workers=min(4, len(jobs))) as ex:
        list(ex.map(fetch, jobs))

print("ALL_DONE", flush=True)
