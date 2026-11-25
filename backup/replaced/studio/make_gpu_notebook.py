#!/usr/bin/env python3
"""Episode JSON + scene tasveerein -> ek Kaggle/Colab notebook (free GPU) jo har scene ki tasveer ko
asli chalta AI clip banata hai (image-to-video). Notebook mein sab andar hai (tasveerein base64), kuch host nahi karna.
python make_gpu_notebook.py episode.json assets_dir out.ipynb [s02,s05]   (khaali = jin scene mein 'motion' likha hai)
Clip wapas: notebook clips.zip deta hai -> Ample upload page -> server -> assets_dir/<id>.mp4 -> story_video apne aap use karta."""
import json, sys, base64, os

ep_path, adir, out = sys.argv[1], sys.argv[2], sys.argv[3]
only = set(sys.argv[4].split(",")) if len(sys.argv) > 4 and sys.argv[4] else None
ep = json.load(open(ep_path, encoding="utf-8"))
jobs = []
for sc in ep["scenes"]:
    if only and sc["id"] not in only:
        continue
    if not only and not sc.get("motion"):
        continue
    img = os.path.join(adir, sc.get("use", sc["id"]) + ".jpg")
    if not os.path.exists(img):
        print("tasveer nahi:", img); continue
    desc = sc["img"]
    for k, v in ep.get("cast", {}).items():
        desc = desc.replace(k, v)
    motion = sc.get("motion") or "subtle natural movement, the character breathes and blinks, gentle camera push in"
    jobs.append({"id": sc["id"], "prompt": f"{motion}. {desc}. smooth cinematic animation, consistent character, 3D animated film",
                 "seconds": min(5.0, max(3.0, float(sc.get("motion_seconds", 4)))),
                 "image_b64": base64.b64encode(open(img, "rb").read()).decode()})
print(len(jobs), "jobs")

md = lambda s: {"cell_type": "markdown", "metadata": {}, "source": s}
code = lambda s: {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s}
cells = [
 md("# Toonistaan GPU Worker (free GPU)\n"
    "Har scene ki tasveer -> asli chalta AI video clip.\n\n"
    "**Kaggle:** Settings → Accelerator → **GPU T4 x2** (ya P100), Internet **On**. **Colab:** Runtime → Change runtime type → **T4 GPU**.\n"
    "Phir upar se **Run all**. Aakhir mein `clips.zip` download karke Claude ke diye upload link par daal do.\n\n"
    "Engine: **LTX-Video** (Lightricks, diffusers `LTXImageToVideoPipeline`, open-weights licence: $10M se kam kamaai par commercial theek). "
    "Memory kam pade to `WIDTH`/`HEIGHT` ghatao (dono 32 se divide hone chahiye)."),
 code("WIDTH, HEIGHT = 768, 448   # 32 se divide (kam memory: 704x384 / 512x288 nahi: 288 theek, 512 theek)\nFPS = 24\nSTEPS = 30\nGUIDANCE = 3.0\nSEED = 7"),
 code("import subprocess, sys\nsubprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', 'diffusers', 'transformers', 'accelerate',\n"
      "                'sentencepiece', 'ftfy', 'imageio', 'imageio-ffmpeg'], check=True)\nimport torch\nprint('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NAHI MILA - GPU on karo!')"),
 code("JOBS = " + json.dumps(jobs, ensure_ascii=False)),
 code("import os, io, base64, time, zipfile, torch\nfrom PIL import Image\nfrom diffusers import LTXImageToVideoPipeline\nfrom diffusers.utils import export_to_video\n"
      "assert WIDTH % 32 == 0 and HEIGHT % 32 == 0, 'WIDTH/HEIGHT 32 se divide hone chahiye'\n"
      "# T4/P100 par bf16 nahi: float32 (2B model ~8 GB, surakshit); A100/L4 par bf16 (tez)\n"
      "dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() and torch.cuda.get_device_capability()[0] >= 8 else torch.float32\n"
      "os.makedirs('clips', exist_ok=True)\n"
      "NEG = 'worst quality, inconsistent motion, blurry, jittery, distorted face, extra limbs, deformed hands, flicker, text, watermark'\n"
      "pipe = LTXImageToVideoPipeline.from_pretrained('Lightricks/LTX-Video', torch_dtype=dtype)\n"
      "pipe.enable_model_cpu_offload()\npipe.vae.enable_tiling()\nprint('model taiyaar', dtype)"),
 code("for j in JOBS:\n    path = f\"clips/{j['id']}.mp4\"\n    if os.path.exists(path):\n        print('pehle se', path); continue\n"
      "    img = Image.open(io.BytesIO(base64.b64decode(j['image_b64']))).convert('RGB').resize((WIDTH, HEIGHT))\n"
      "    n = int(j['seconds'] * FPS) // 8 * 8 + 1\n    t0 = time.time()\n    g = torch.Generator('cuda').manual_seed(SEED)\n"
      "    try:\n        frames = pipe(image=img, prompt=j['prompt'], negative_prompt=NEG, width=WIDTH, height=HEIGHT,\n"
      "                      num_frames=n, num_inference_steps=STEPS, guidance_scale=GUIDANCE, generator=g).frames[0]\n"
      "    except torch.cuda.OutOfMemoryError:\n        print('MEMORY KAM:', j['id'], '-> WIDTH/HEIGHT chhota karke dobara chalao'); torch.cuda.empty_cache(); continue\n"
      "    export_to_video(frames, path, fps=FPS)\n    print(j['id'], 'ban gaya', round(time.time() - t0), 'sec')\n"
      "    torch.cuda.empty_cache()"),
 code("with zipfile.ZipFile('clips.zip', 'w') as z:\n    for f in sorted(os.listdir('clips')):\n        z.write(os.path.join('clips', f), f)\n"
      "print('clips.zip taiyaar:', round(os.path.getsize('clips.zip') / 1e6, 1), 'MB')\n"
      "try:\n    from google.colab import files; files.download('clips.zip')   # Colab\nexcept Exception:\n"
      "    print('Kaggle: right side Output -> clips.zip -> Download')"),
]
nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                   "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("notebook:", out, round(os.path.getsize(out) / 1e3), "KB")
