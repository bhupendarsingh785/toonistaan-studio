"""Server-side: free scene images (Pollinations) + Hindi voices (Piper) for an episode JSON.
Run with Blender's bundled python:  PY gen_assets.py episode.json outdir
"""
import json, os, sys, time, subprocess, urllib.request, urllib.parse

PIPER = "/opt/tools/piper/piper"
VOICES = {"pratham": "/opt/tools/voices/hi_pratham.onnx", "priyamvada": "/opt/tools/voices/hi_priyamvada.onnx"}
# Piper na ho to edge-tts se hi kaam chalao (Cloud Shell / GitHub Actions me Piper nahi hota)
HAVE_PIPER = os.path.exists(PIPER)

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
EDGE = {"madhur": "hi-IN-MadhurNeural", "swara": "hi-IN-SwaraNeural", "pratham": "hi-IN-MadhurNeural", "priyamvada": "hi-IN-SwaraNeural"}
for sc in ep["scenes"]:
    for i, (voice, text) in enumerate(sc["lines"]):
        wav = f"{out}/{sc['id']}_{i}.wav"
        if os.path.exists(wav) or os.path.exists(wav[:-4] + ".mp3"):
            continue
        if voice in EDGE:
            r = subprocess.run([sys.executable, "-m", "edge_tts", "--text", text, "--voice", EDGE[voice],
                                "--rate=" + ep.get("voice_rate", "-6%"), "--write-media", wav[:-4] + ".mp3"],
                               capture_output=True)
            if r.returncode == 0:
                continue
            voice = "pratham" if voice == "madhur" else "priyamvada"  # internet na ho to Piper
        if not HAVE_PIPER:
            # Piper nahi hai -> edge-tts se dobara koshish (dheere, saaf awaaz)
            fb = "hi-IN-MadhurNeural" if voice in ("pratham", "madhur") else "hi-IN-SwaraNeural"
            r2 = subprocess.run([sys.executable, "-m", "edge_tts", "--text", text, "--voice", fb,
                                 "--rate=" + ep.get("voice_rate", "-6%"), "--write-media", wav[:-4] + ".mp3"],
                                capture_output=True)
            if r2.returncode == 0:
                continue
            print("VOICE_FAIL", sc["id"], i, r2.stderr.decode()[-200:], flush=True)
            continue
        subprocess.run([PIPER, "-m", VOICES[voice], "-f", wav, "--length_scale", "1.05",
                        "--sentence_silence", "0.25"], input=text.encode(), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("VOICES_OK", flush=True)

# Variants: "variants": N (episode ya scene level) -> <id>_v0.jpg .. v{N-1}; best ko <id>.jpg naam do.
# Sirf kuch scene dobara: python gen_assets.py ep.json out s04,s06   (purani file hata kar naya seed)
only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
NEG = ep.get("negative", " no text, no watermark")
for sc in ep["scenes"]:
    if only and sc["id"] not in only:
        continue
    n = sc.get("variants", ep.get("variants", 1))
    base = sc.get("seed", seed)
    for v in range(n):
        jpg = f"{out}/{sc['id']}.jpg" if n == 1 else f"{out}/{sc['id']}_v{v}.jpg"
        if os.path.exists(jpg) and os.path.getsize(jpg) > 5000:
            continue
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt_for(sc) + "," + NEG) +
               f"?width={ep.get('w', 1280)}&height={ep.get('h', 720)}&nologo=true&seed={base + v * 101}")
        for attempt in range(8):
            data = subprocess.run(["curl", "-sL", "-m", "150", url], capture_output=True).stdout
            if len(data) > 5000:
                open(jpg, "wb").write(data)
                print("IMG_OK", os.path.basename(jpg), len(data), flush=True)
                break
            time.sleep(50)
        else:
            print("IMG_FAIL", os.path.basename(jpg), flush=True)
        time.sleep(46)
print("ALL_DONE", flush=True)
