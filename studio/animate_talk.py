#!/usr/bin/env python3
"""Tasveer ko 'zinda' karo (free, offline): awaaz ke saath munh hilna (lip-sync), aankh jhapakna,
saans/sir ki halki chaal, dheema camera. Chehra YuNet se apne aap milta hai.
python animate_talk.py image.jpg voice.(wav|mp3) out.mp4 [--w 1920 --h 1080 --tail 0.8]
Kai chehre hon to sabse bada chehra bolta hai (--face N se chuno, 0 = sabse bada)."""
import sys, os, subprocess, tempfile, wave
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
a = sys.argv[1:]
IMG, AUD, OUT = a[0], a[1], a[2]
W = int(a[a.index("--w") + 1]) if "--w" in a else 1920
H = int(a[a.index("--h") + 1]) if "--h" in a else 1080
TAIL = float(a[a.index("--tail") + 1]) if "--tail" in a else 0.8
FACE = int(a[a.index("--face") + 1]) if "--face" in a else 0
FPS = 30

# ---- audio -> munh khulne ki matra (0..1) har frame ----
tmp = tempfile.mkdtemp()
wav = os.path.join(tmp, "a.wav")
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", AUD, "-ac", "1", "-ar", "16000", wav], check=True)
with wave.open(wav) as w:
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
dur = len(x) / 16000 + TAIL
N = int(dur * FPS)
hop = 16000 // FPS
rms = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2)) if i * hop < len(x) else 0 for i in range(N)])
open_ = np.clip((rms - 0.012) / (np.percentile(rms[rms > 0.012], 90) if (rms > 0.012).any() else 1), 0, 1)
open_ = np.convolve(open_, [0.25, 0.5, 0.25], "same")  # naram

# ---- image + chehra ----
src = cv2.imread(IMG)
h0, w0 = src.shape[:2]
src = src[int(h0 * .02):int(h0 * .94), int(w0 * .02):int(w0 * .94)]  # watermark kona hatao
src = cv2.resize(src, (int(W * 1.12), int(H * 1.12)), interpolation=cv2.INTER_CUBIC)
SH, SW = src.shape[:2]
det = cv2.FaceDetectorYN.create(os.path.join(HERE, "models", "yunet.onnx"), "", (SW, SH), 0.7, 0.3, 20)
_, faces = det.detect(src)
if faces is None:
    sys.exit("chehra nahi mila: is tasveer ke liye animate_talk mat chalao")
faces = sorted(faces, key=lambda f: -f[2] * f[3])
f = faces[min(FACE, len(faces) - 1)]
fx, fy, fw, fh = f[:4]
reye, leye, nose, rmo, lmo = f[4:14].reshape(5, 2)
mouth_c = (rmo + lmo) / 2
mw = np.linalg.norm(lmo - rmo) * 1.15
eye_d = np.linalg.norm(leye - reye)

yy, xx = np.mgrid[0:SH, 0:SW].astype(np.float32)

# munh ke andar ka andhera (patli line) pehle se banao; khinchne par khula munh banega
base = src.copy()
mx, my = mouth_c
OPEN_PX = fh * 0.12  # poora khula munh kitne pixel
# sirf neeche ka hoth aur thodi neeche jaati hai (upar ka hoth wahi rehta)
gx = np.exp(-((xx - mx) / (mw * 0.62)) ** 2)
below = np.clip((yy - my) / (fh * 0.02), 0, 1) * np.exp(-np.clip(yy - my - fh * 0.05, 0, None) / (fh * 0.22))
gm = gx * below
# munh ke andar ka rang (gehra laal-bhura), feathered ellipse mask
inner_col = np.array([22, 18, 52], np.float32)  # BGR

def eye_mask(e):
    return np.exp(-(((xx - e[0]) / (eye_d * 0.38)) ** 2 + ((yy - e[1]) / (eye_d * 0.22)) ** 2))
ge = eye_mask(reye) + eye_mask(leye)
eye_y = (reye[1] + leye[1]) / 2

# jhapakne ka samay: har 2.5-4.5 s
rng = np.random.default_rng(7)
blinks, t = [], 0.8
while t < dur:
    blinks.append(t); t += rng.uniform(2.5, 4.5)
def blink_amt(tt):
    for b in blinks:
        d = tt - b
        if 0 <= d < 0.18:
            return np.sin(np.pi * d / 0.18)
    return 0.0

pivot = np.array([fx + fw / 2, fy + fh * 1.3])  # gardan ke paas se sir hilta
cmd = ["ffmpeg", "-loglevel", "warning", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
       "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
       "-af", "apad", "-c:a", "aac", "-b:a", "128k", "-shortest", OUT]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for i in range(N):
    tt = i / FPS
    o = open_[i]
    b = blink_amt(tt)
    # 1) munh: mouth line ke aas-paas vertical khichaav (neeche ka hoth neeche)
    d = o * OPEN_PX
    mapy = yy - d * gm
    # 2) aankh: palak band (aankh ki line par daba do)
    se = 1 - 0.85 * b * np.clip(ge, 0, 1)
    mapy = np.where(ge > 0.02, eye_y + (mapy - eye_y) / np.maximum(se, 0.12), mapy)
    fr = cv2.remap(base, xx, mapy.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if d > 1.0:  # khule munh ka andar wala hissa (hothon ke beech)
        m = np.zeros((SH, SW), np.float32)
        cv2.ellipse(m, (int(mx), int(my + d * 0.5)), (int(mw * 0.30 * min(1, 0.6 + o)), int(d * 0.5)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
        m = cv2.GaussianBlur(m, (0, 0), max(1.0, d * 0.12))[..., None] * 0.92
        fr = (fr * (1 - m) + inner_col * m).astype(np.uint8)
    if b > 0.3:  # band aankh par halki palak ki chhaya
        lid = np.clip(ge * b, 0, 1)[..., None] * 0.25
        fr = (fr * (1 - lid) + np.array([70, 90, 120]) * lid).astype(np.uint8)
    # 3) sir/saans ki chaal + dheema zoom
    ang = 0.7 * np.sin(2 * np.pi * tt / 3.7) + 0.5 * o * np.sin(2 * np.pi * tt * 1.3)
    sc = 1.0 + 0.004 * np.sin(2 * np.pi * tt / 3.2) + 0.04 * (tt / dur)
    M = cv2.getRotationMatrix2D((float(pivot[0]), float(pivot[1])), ang, sc)
    M[1, 2] += -3 * o + 2 * np.sin(2 * np.pi * tt / 3.2)
    fr = cv2.warpAffine(fr, M, (SW, SH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    ox, oy = (SW - W) // 2, (SH - H) // 2
    p.stdin.write(np.ascontiguousarray(fr[oy:oy + H, ox:ox + W]).tobytes())
p.stdin.close(); p.wait()
print("DONE", OUT, f"{dur:.1f}s", "chehre:", len(faces))
