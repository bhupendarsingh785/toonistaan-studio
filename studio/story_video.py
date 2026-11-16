#!/usr/bin/env python3
"""Kahani video banao (koi bhi lambai: 1 min se 10 min tak, jitne scene utni lambi).
python story_video.py episode.json assets_dir out.mp4 [--w 1920 --h 1080]
assets_dir: <scene_id>.jpg aur <scene_id>_<n>.wav (gen_assets.py se)
Har scene: camera chal (in/out/left/right/fastin/shake), crossfade, Hindi awaaz,
mood music (ducking ke saath), SFX, Hindi subtitle (Chromium se), title card, .srt"""
import json, os, sys, wave, subprocess, tempfile, shutil
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfx  # noqa: E402
try:
    import motion  # noqa: E402
    motion.ensure_models(verbose=True)
except Exception as _e:
    print("motion models:", str(_e)[:80], flush=True)

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 44100; FPS = 30; XF = 0.6; LEAD = 0.6; TAIL = 0.9; GAP = 0.35
args = sys.argv[1:]
EP, AS, OUT = args[0], args[1], args[2]
W = int(args[args.index("--w") + 1]) if "--w" in args else 1920
H = int(args[args.index("--h") + 1]) if "--h" in args else 1080
ep = json.load(open(EP, encoding="utf-8"))
tmp = tempfile.mkdtemp(prefix="story_")


def load_wav(p):
    if not os.path.exists(p) and os.path.exists(p[:-4] + ".mp3"):  # edge-tts mp3 -> wav
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", p[:-4] + ".mp3", "-ar", "24000", "-ac", "1", p], check=True)
    with wave.open(p) as w:
        sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2: x = x.reshape(-1, 2).mean(1)
    if sr != SR:
        x = np.interp(np.linspace(0, len(x) - 1, int(len(x) * SR / sr)), np.arange(len(x)), x)
    return x


# ---------- timeline ----------

def _fallback_card(path, title="", mood="calm"):
    """Tasveer na mile to ek sundar card banao (video kabhi fail na ho)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    pal = {"horror": ((8, 8, 14), (44, 12, 20)), "sad": ((12, 18, 32), (52, 62, 84)),
           "happy": ((10, 26, 46), (0, 170, 150)), "action": ((26, 11, 11), (200, 90, 30)),
           "romance": ((40, 10, 40), (240, 120, 170)), "calm": ((14, 20, 36), (60, 90, 140))}.get(mood, ((14, 20, 36), (60, 90, 140)))
    img = Image.new("RGB", (W, H), pal[0])
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / max(1, H - 1)
        d.line([(0, y), (W, y)], fill=(int(pal[0][0]*(1-k)+pal[1][0]*k),
                                       int(pal[0][1]*(1-k)+pal[1][1]*k),
                                       int(pal[0][2]*(1-k)+pal[1][2]*k)))
    fp = os.path.join(HERE, "fonts", "Hind-Bold.ttf")
    try:
        f = ImageFont.truetype(fp, int(H * 0.05))
    except Exception:
        f = ImageFont.load_default()
    if title:
        tw = d.textlength(title, font=f)
        d.text(((W - tw) / 2, H * 0.45), title, font=f, fill=(255, 255, 255))
    img.save(path, quality=90)
    return True

scenes = []; t = 0.0
for i, sc in enumerate(ep["scenes"]):
    lines = []
    k = 0
    while os.path.exists(f"{AS}/{sc['id']}_{k}.wav") or os.path.exists(f"{AS}/{sc['id']}_{k}.mp3"):
        lines.append(load_wav(f"{AS}/{sc['id']}_{k}.wav")); k += 1
    speech = sum(len(a) for a in lines) / SR + GAP * max(0, len(lines) - 1)
    dur = max(4.0, LEAD + speech + TAIL) + (XF if i else 0)
    scenes.append(dict(sc=sc, start=t, dur=dur, lines=lines))
    t += dur - XF
TOTAL = t + XF
print(f"scenes={len(scenes)} total={TOTAL:.1f}s")

# ---------- audio ----------
N = int(SR * (TOTAL + 0.5)); voice = np.zeros(N); fx = np.zeros(N); subs = []
for i, s in enumerate(scenes):
    p = s["start"] + (XF if i else 0) + LEAD
    texts = [l[1] for l in s["sc"]["lines"]]
    for a, txt in zip(s["lines"], texts):
        k = int(p * SR); voice[k:k + len(a)] += a * 0.95
        subs.append((p, p + len(a) / SR, txt)); p += len(a) / SR + GAP
    for j, name in enumerate(s["sc"].get("sfx", [])):
        x = sfx.ALL[name](); x = x / (np.abs(x).max() + 1e-9) * 0.35
        k = int((s["start"] + 0.3 + j * 0.8) * SR); x = x[: max(0, min(len(x), N - k))]; fx[k:k + len(x)] += x

music = np.zeros(N); fade = int(SR * XF * 2)
for i, s in enumerate(scenes):
    if i and s["sc"].get("music") == scenes[i - 1]["sc"].get("music"): continue
    j = i
    while j + 1 < len(scenes) and scenes[j + 1]["sc"].get("music") == s["sc"].get("music"): j += 1
    a, b = s["start"], scenes[j]["start"] + scenes[j]["dur"]
    m = sfx.music(s["sc"].get("music", "happy"), b - a + XF)
    m = m / (np.abs(m).max() + 1e-9); f = min(fade, len(m) // 3)
    m[:f] *= np.linspace(0, 1, f); m[-f:] *= np.linspace(1, 0, f)
    k = int(a * SR); m = m[: N - k]; music[k:k + len(m)] += m
# ducking: voice envelope
envv = np.convolve(np.abs(voice), np.ones(int(SR * 0.3)) / int(SR * 0.3), "same")
duck = np.where(envv > 0.01, 0.07, 0.22)
duck = np.convolve(duck, np.ones(int(SR * 0.25)) / int(SR * 0.25), "same")
mix = voice + fx + music * duck
mix = np.clip(mix / (np.abs(mix).max() + 1e-9) * 0.89, -1, 1)
apath = f"{tmp}/mix.wav"
with wave.open(apath, "w") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())

# ---------- awaaz mili ya nahi ----------
_tot_lines = sum(len(s2["lines"]) for s2 in scenes)
print("VOICE_LINES", _tot_lines, flush=True)
if _tot_lines == 0:
    print("WARN: koi awaaz file nahi mili — video me sirf music hoga", flush=True)

# ---------- missing images ka intezaam (video fail na ho) ----------
for sc in ep["scenes"]:
    src_id = sc.get("use", sc["id"])
    p_img = f"{AS}/{src_id}.jpg"
    if not (os.path.exists(p_img) and os.path.getsize(p_img) > 3000):
        print("IMG_MISSING", src_id, "-> card bana rahe hain", flush=True)
        _fallback_card(p_img, title=str(sc.get("img", ""))[:40], mood=str(sc.get("music", "calm")))

# ---------- subtitle + title PNGs (Chromium shapes Hindi correctly) ----------
def html_png(items):
    js = json.dumps(items, ensure_ascii=False)
    node = f"""
const {{ chromium }} = require('playwright');
(async () => {{
 const b = await chromium.launch(); const p = await b.newPage({{viewport:{{width:{W},height:{H}}}}});
 for (const it of {js}) {{
  await p.setContent(`<html><body style="margin:0;background:transparent;width:{W}px;height:{H}px;font-family:Hind">${{it.html}}</body></html>`);
  await p.evaluate(() => document.fonts.ready);
  await p.screenshot({{path: it.path, omitBackground: true}});
 }}
 await b.close();
}})();"""
    open(f"{tmp}/r.js", "w").write(node)
    subprocess.run(["node", f"{tmp}/r.js"], check=True)

items = []
fs = int(H * 0.052)
for n, (a, b, txt) in enumerate(subs):
    items.append({"path": f"{tmp}/sub{n}.png", "html":
        f'<div style="position:absolute;left:6%;right:6%;bottom:{int(H*0.06)}px;text-align:center;font-weight:700;'
        f'font-size:{fs}px;line-height:1.35;color:#fff;text-shadow:0 0 6px #000,0 3px 8px #000,0 0 2px #000">{txt}</div>'})
tc = ep.get("title_card")
if tc:
    items.append({"path": f"{tmp}/title.png", "html":
        f'<div style="position:absolute;top:30%;width:100%;text-align:center;color:#ffd84a;font-weight:700;font-size:{int(H*0.12)}px;'
        f'text-shadow:0 0 12px #000,0 6px 18px #000">{tc[0]}</div><div style="position:absolute;top:50%;width:100%;text-align:center;'
        f'color:#fff;font-size:{int(H*0.05)}px;font-weight:700;text-shadow:0 0 8px #000">{tc[1]}</div>'})
html_png(items)

# ---------- video clips ----------
def cam_filter(cam, frames, crop=None):
    n = max(frames - 1, 1)
    c = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    z = {"in": f"z='1+0.14*on/{n}':{c}", "out": f"z='1.14-0.14*on/{n}':{c}",
         "fastin": f"z='1+0.32*on/{n}':{c}",
         "left": f"z='1.15':x='(iw-iw/zoom)*on/{n}':y='ih/2-(ih/zoom/2)'",
         "right": f"z='1.15':x='(iw-iw/zoom)*(1-on/{n})':y='ih/2-(ih/zoom/2)'",
         "shake": f"z='1.12':{c}"}[cam]
    pre = "crop=iw*0.92:ih*0.92:iw*0.02:ih*0.02,"
    if crop:  # [x, y, w, h] 0-1: ek wide tasveer se close shot (nayi image banaye bina)
        x, y, w, h = crop
        pre += f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},"
    f = f"{pre}scale={W*3//2}:{H*3//2},zoompan={z}:d={frames}:s={W}x{H}:fps={FPS}"
    if cam == "shake":
        f += (f",crop={W-60}:{H-34}:x='30+18*sin(t*23)':y='17+10*sin(t*31)',scale={W}:{H},"
              "eq=eval=frame:brightness='0.45*gt(mod(t\\,2.7)\\,2.55)'")
    return f + ",eq=saturation=1.08:contrast=1.03,vignette=PI/6,format=yuv420p"

USE_MOTION = ep.get("motion", True) and "--no-motion" not in args
if USE_MOTION:
    try:
        import motion  # kirdaar alag layer, bolna, aankh, VFX
    except Exception as e:  # models na hon to purana tareeka
        print("motion band:", e); USE_MOTION = False
NARRATORS = set(ep.get("narrators", ["madhur", "pratham", "madhur_dada_narrator"]))
SHEETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sheets")


def _abs_actor(a_):
    """sheet/prop ke naam ko poora path banao (studio/sheets/)"""
    a_ = json.loads(json.dumps(a_))
    if not os.path.isabs(a_["sheet"]):
        a_["sheet"] = os.path.join(SHEETS, a_["sheet"])
    if a_.get("prop") and not os.path.isabs(a_["prop"]["sheet"]):
        a_["prop"]["sheet"] = os.path.join(SHEETS, a_["prop"]["sheet"])
    return a_


def scene_mouth_by_voice(i, s, frames):
    """har awaaz (voice) ka alag munh-curve: kai kirdaar ek scene mein"""
    out = {}
    p = (XF if i else 0) + LEAD
    hop = SR // FPS
    for a, (vname, _) in zip(s["lines"], s["sc"]["lines"]):
        m = out.setdefault(vname, np.zeros(frames, np.float32))
        k0 = int(p * FPS)
        for f_ in range(int(len(a) / SR * FPS)):
            if k0 + f_ < frames:
                seg = a[f_ * hop:(f_ + 1) * hop]
                m[k0 + f_] = np.sqrt(np.mean(seg ** 2)) if len(seg) else 0
        p += len(a) / SR + GAP
    return {k: motion.normalise_mouth(v) for k, v in out.items()}


def scene_mouth(i, s, frames):
    """kirdaar ki lines (narrator nahi) ki awaaz se har frame ka munh"""
    m = np.zeros(frames, np.float32)
    p = (XF if i else 0) + LEAD
    hop = SR // FPS
    for a, (vname, _) in zip(s["lines"], s["sc"]["lines"]):
        if vname not in NARRATORS:
            k0 = int(p * FPS)
            for f_ in range(int(len(a) / SR * FPS)):
                if k0 + f_ < frames:
                    seg = a[f_ * hop:(f_ + 1) * hop]
                    m[k0 + f_] = np.sqrt(np.mean(seg ** 2)) if len(seg) else 0
        p += len(a) / SR + GAP
    return motion.normalise_mouth(m)


import hashlib, shutil as _sh
from concurrent.futures import ProcessPoolExecutor
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "clips")
os.makedirs(CACHE, exist_ok=True)


def render_clip(i):
    """ek scene ka clip (alag process mein chalta: kai scene ek saath banenge)"""
    if WORKERS > 1:
        import cv2 as _cv; _cv.setNumThreads(1)  # har worker ek core (aapas mein na takraayein)
    s = scenes[i]
    frames = int(round(s["dur"] * FPS)); out = f"{tmp}/c{i:03d}.mp4"
    img_path = f"{AS}/{s['sc'].get('use', s['sc']['id'])}.jpg"
    ai_clip = f"{AS}/{s['sc']['id']}.mp4"
    if os.path.exists(ai_clip):
        # GPU worker (Kaggle/Colab) ka asli chalta AI clip: scene ki lambai tak dheema/loop (ping-pong), 1080p, rang
        cdur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", ai_clip],
                                    capture_output=True, text=True).stdout.strip() or 0)
        speed = max(0.5, min(1.0, cdur / s["dur"])) if cdur else 1.0  # 2x se zyada dheema nahi
        vf = (f"crop=iw*0.92:ih*0.92:iw*0.02:ih*0.02,setpts=PTS/{speed:.3f},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
              "eq=saturation=1.06:contrast=1.03,vignette=PI/6,format=yuv420p")
        # chhota clip ho to ulta chala kar jodo (jhatka nahi)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", ai_clip, "-filter_complex",
                        f"[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,loop=-1:size=32767,{vf}[v]",
                        "-map", "[v]", "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", out], check=True)
        return out, s["dur"], f"AI clip ({cdur:.1f}s)"
    mouth = scene_mouth(i, s, frames) if USE_MOTION else None
    # cache: same tasveer + same settings + same awaaz = purana clip turant (sirf badle scene dobara bante)
    hsh = hashlib.md5()
    hsh.update(open(img_path, "rb").read())
    hsh.update(json.dumps({k: s["sc"].get(k) for k in ("cam", "vfx", "crop", "people", "emotion", "actors")}, sort_keys=True).encode())
    hsh.update(f"{W}x{H}:{frames}:{i}:{USE_MOTION}:v2".encode())
    if mouth is not None:
        hsh.update(np.round(mouth, 3).tobytes())
    cpath = os.path.join(CACHE, hsh.hexdigest()[:20] + ".mp4")
    if os.path.exists(cpath):
        _sh.copy(cpath, out); return out, s["dur"], "cache"
    info = None
    if USE_MOTION:
        enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                                "-r", str(FPS), "-i", "-", "-vf", "eq=saturation=1.08:contrast=1.03,vignette=PI/6,format=yuv420p",
                                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-threads", "1", out], stdin=subprocess.PIPE)
        try:
            info = motion.render_scene(img_path, frames, W, H, cam=s["sc"].get("cam", "in"), mouth=mouth,
                                       vfx=s["sc"].get("vfx"), crop=s["sc"].get("crop"), seed=i + 1,
                                       people=s["sc"].get("people"), emotion=s["sc"].get("emotion", "neutral"),
                                       actors=[_abs_actor(a_) for a_ in s["sc"].get("actors", [])] or None,
                                       mouths=scene_mouth_by_voice(i, s, frames),
                                       write=lambda f_: enc.stdin.write(f_.tobytes()))
        except Exception as e:
            print("motion fail, zoompan:", i, e, flush=True); info = None
        finally:
            enc.stdin.close(); enc.wait()
        if enc.returncode != 0:
            info = None
    if info is None:  # purana zoompan (motion band ya fail)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-i", img_path,
                        "-vf", cam_filter(s["sc"].get("cam", "in") if s["sc"].get("cam", "in") in
                                          ("in", "out", "fastin", "left", "right", "shake") else "in", frames, s["sc"].get("crop")),
                        "-frames:v", str(frames), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", out], check=True)
    _sh.copy(out, cpath)
    return out, s["dur"], info or "zoompan"


WORKERS = int(args[args.index("--jobs") + 1]) if "--jobs" in args else max(1, os.cpu_count() or 1)
# lambe scene pehle (sab worker barabar busy)
order = sorted(range(len(scenes)), key=lambda k: -scenes[k]["dur"])
results = {}
if WORKERS > 1:
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        for k, r in zip(order, ex.map(render_clip, order)):
            results[k] = r; print("clip", k, f"{r[1]:.1f}s", r[2], flush=True)
else:
    for k in order:
        results[k] = render_clip(k); print("clip", k, f"{results[k][1]:.1f}s", results[k][2], flush=True)
clips = [(results[k][0], results[k][1]) for k in range(len(scenes))]

# xfade chain
inp = []; [inp.extend(["-i", c]) for c, _ in clips]
fc = []; last = "[0:v]"; off = 0.0
for i in range(1, len(clips)):
    off += clips[i - 1][1] - XF
    fc.append(f"{last}[{i}:v]xfade=transition={'fade' if i % 3 else 'smoothleft'}:duration={XF}:offset={off:.3f}[x{i}]")
    last = f"[x{i}]"
# overlays: title + subtitles
k = len(clips); ov_inputs = []
if tc:
    ov_inputs.append(("title", 0.3, 4.2))
for n, (a, b, _) in enumerate(subs):
    ov_inputs.append((f"sub{n}", a, b))
for j, (name, a, b) in enumerate(ov_inputs):
    inp.extend(["-i", f"{tmp}/{name}.png"])
    fc.append(f"{last}[{k + j}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[o{j}]"); last = f"[o{j}]"
inp.extend(["-i", apath]); ai = k + len(ov_inputs)
cmd = ["ffmpeg", "-loglevel", "error", "-y", *inp, "-filter_complex", ";".join(fc), "-map", last, "-map", f"{ai}:a",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
       "-af", "loudnorm=I=-16:TP=-1.5", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", OUT]
subprocess.run(cmd, check=True)

def ts(x):
    h, r = divmod(x, 3600); m, s = divmod(r, 60); return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s%1)*1000):03d}"
with open(os.path.splitext(OUT)[0] + ".srt", "w", encoding="utf-8") as f:
    for n, (a, b, txt) in enumerate(subs, 1): f.write(f"{n}\n{ts(a)} --> {ts(b)}\n{txt}\n\n")
shutil.rmtree(tmp, ignore_errors=True)
print("DONE", OUT, f"{TOTAL:.1f}s")
