"""Toonistaan motion engine (free, CPU, bina GPU): ek tasveer ko chalti-firti scene banata hai.
- Kirdaar ko background se alag (PP-HumanSeg, opencv_zoo, Apache-2.0) -> 2.5D parallax camera
- Bolna: awaaz ke saath munh (lip-sync), aankh jhapakna, sir/saans ki chaal (YuNet chehra)
- VFX: rain, leaves, dust, birds, rays, fireflies, lightning
story_video.py ise har scene ke liye bulata hai. Akela test: python motion.py img.jpg out.mp4 [voice.mp3]"""
import os, sys, subprocess, tempfile, wave
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models")
FPS = 30
_seg = None

# ---------------------------------------------------------------- models
_MODEL_URLS = {
    "humanseg.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/human_segmentation_pphumanseg/human_segmentation_pphumanseg_2023mar.onnx",
    "yunet.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
}

def ensure_models(verbose=True):
    """Zaroori model na ho to khud download kar lo (internet ho to). Fail ho to False."""
    import urllib.request
    os.makedirs(MODELS, exist_ok=True)
    ok = True
    for name, url in _MODEL_URLS.items():
        path = os.path.join(MODELS, name)
        if os.path.exists(path) and os.path.getsize(path) > 100_000:
            continue
        try:
            if verbose:
                print("model download:", name, flush=True)
            tmp = path + ".part"
            urllib.request.urlretrieve(url, tmp)
            if os.path.getsize(tmp) > 100_000:
                os.replace(tmp, path)
            else:
                ok = False
        except Exception as e:
            if verbose:
                print("model fail:", name, str(e)[:80], flush=True)
            ok = False
    return ok




# ------------------------------------------------------------------ audio -> munh
def mouth_curve(audio_path, n_frames, start_s=0.0, fps=FPS):
    """har frame ke liye munh kitna khula (0..1). audio_path=None -> sab 0"""
    out = np.zeros(n_frames, np.float32)
    if not audio_path:
        return out
    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, "a.wav")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", audio_path, "-ac", "1", "-ar", "16000", wav], check=True)
    with wave.open(wav) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    hop = 16000 // fps
    k0 = int(start_s * fps)
    for i in range(n_frames - k0):
        seg = x[i * hop:(i + 1) * hop]
        if len(seg) == 0:
            break
        out[k0 + i] = np.sqrt(np.mean(seg ** 2))
    return out


def normalise_mouth(rms):
    on = rms > 0.012
    if not on.any():
        return np.zeros_like(rms)
    o = np.clip((rms - 0.012) / (np.percentile(rms[on], 85) - 0.012 + 1e-6), 0, 1)
    o = np.convolve(o, [0.2, 0.6, 0.2], "same")
    # bolte waqt bhi har syllable par thoda band (zyada asli lagta)
    return np.clip(o, 0, 1).astype(np.float32)


# ------------------------------------------------------------------ insaan ka mask
def person_mask(img):
    global _seg
    if _seg is None:
        _seg = cv2.dnn.readNet(os.path.join(MODELS, "humanseg.onnx"))
    h, w = img.shape[:2]
    b = (cv2.dnn.blobFromImage(cv2.resize(img, (192, 192)), 1.0, (192, 192), swapRB=True) / 255.0 - 0.5) / 0.5
    _seg.setInput(b.astype(np.float32))
    p = _seg.forward()[0, 1]
    m = cv2.resize(p, (w, h), interpolation=cv2.INTER_CUBIC)
    m = (m > 0.5).astype(np.uint8)
    # sabse bade tukde rakho, chhote dhabbe hatao
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > 0.01 * w * h:
            keep[lab == i] = 1
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    # Note: door ke chhote poore-body kirdaar par ye model kaam nahi karta (test: GrabCut fallback galat jagah
    # kaat raha tha, isliye band). Aise scene mein sirf camera + VFX chalta hai, artifacts nahi.
    soft = cv2.GaussianBlur(keep.astype(np.float32), (0, 0), max(2, w / 500))
    area = keep.mean()
    return soft, area


def clean_plate(img, mask):
    """kirdaar ke peeche ka background bharo (inpaint), taaki parallax mein khaali jagah na dikhe"""
    h, w = img.shape[:2]
    s = 480 / w
    small = cv2.resize(img, (480, int(h * s)))
    m = cv2.resize((mask > 0.15).astype(np.uint8) * 255, (480, int(h * s)))
    m = cv2.dilate(m, np.ones((15, 15), np.uint8))
    fill = cv2.inpaint(small, m, 9, cv2.INPAINT_TELEA)
    fill = cv2.resize(fill, (w, h), interpolation=cv2.INTER_CUBIC)
    mm = cv2.GaussianBlur(cv2.resize(m, (w, h)).astype(np.float32) / 255, (0, 0), 6)[..., None]
    return (img * (1 - mm) + fill * mm).astype(np.uint8)


# ------------------------------------------------------------------ chehra + bolna
class Talker:
    def __init__(self, img):
        h, w = img.shape[:2]
        # chhoti copy par dhundho (bade chehre par YuNet kabhi chook jaata), kai size aazmao
        faces = None
        for dw in (960, 640, 1280):
            s = min(1.0, dw / w)
            small = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
            det = cv2.FaceDetectorYN.create(os.path.join(MODELS, "yunet.onnx"), "", (small.shape[1], small.shape[0]), 0.6, 0.3, 20)
            _, f_ = det.detect(small)
            if f_ is not None and len(f_):
                faces = f_.copy(); faces[:, :14] /= s
                break
        self.ok = faces is not None and len(faces) > 0
        if not self.ok:
            return
        f = sorted(faces, key=lambda f: -f[2] * f[3])[0]
        self.fx, self.fy, self.fw, self.fh = [float(v) for v in f[:4]]
        if self.fh < h * 0.08:  # bahut chhota chehra: lip-sync ka fayda nahi
            self.ok = False
            return
        reye, leye, nose, rmo, lmo = f[4:14].reshape(5, 2)
        self.mx, self.my = (rmo + lmo) / 2
        self.mw = float(np.linalg.norm(lmo - rmo)) * 1.15
        self.reye, self.leye = reye, leye
        self.eye_d = float(np.linalg.norm(leye - reye))
        # kaam sirf chehre ke dabbe mein (tez)
        x0 = int(max(0, self.fx - self.fw * 0.3)); x1 = int(min(w, self.fx + self.fw * 1.3))
        y0 = int(max(0, self.fy - self.fh * 0.2)); y1 = int(min(h, self.fy + self.fh * 1.35))
        self.box = (x0, y0, x1, y1)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        self.xx, self.yy = xx, yy
        fh = self.fh
        gx = np.exp(-((xx - self.mx) / (self.mw * 0.62)) ** 2)
        below = np.clip((yy - self.my) / (fh * 0.02), 0, 1) * np.exp(-np.clip(yy - self.my - fh * 0.05, 0, None) / (fh * 0.22))
        self.gm = gx * below
        def em(e):
            return np.exp(-(((xx - e[0]) / (self.eye_d * 0.38)) ** 2 + ((yy - e[1]) / (self.eye_d * 0.2)) ** 2))
        self.ge = np.clip(em(reye) + em(leye), 0, 1)
        self.eye_y = float((reye[1] + leye[1]) / 2)
        # bhaunh (aankh ke upar) - bolte waqt halki upar
        def bm(e):
            return np.exp(-(((xx - e[0]) / (self.eye_d * 0.45)) ** 2 + ((yy - (e[1] - self.eye_d * 0.32)) / (self.eye_d * 0.16)) ** 2))
        self.gb = np.clip(bm(reye) + bm(leye), 0, 1)
        # bhaav ke liye: munh ke kone, bhaunh ka andar wala hissa (naak ki taraf)
        def g2(c, sx, sy):
            return np.exp(-(((xx - c[0]) / sx) ** 2 + ((yy - c[1]) / sy) ** 2))
        self.gc = np.clip(g2(rmo, self.mw * 0.22, fh * 0.07) + g2(lmo, self.mw * 0.22, fh * 0.07), 0, 1)
        mid = (reye + leye) / 2
        self.gbi = np.clip(g2(mid + [-self.eye_d * 0.22, -self.eye_d * 0.3], self.eye_d * 0.2, self.eye_d * 0.13) +
                           g2(mid + [self.eye_d * 0.22, -self.eye_d * 0.3], self.eye_d * 0.2, self.eye_d * 0.13), 0, 1)
        self.inner = np.array([22, 18, 52], np.float32)
        self.teeth = np.array([215, 222, 230], np.float32)

    # bhaav: (kone upar+, bhaunh upar+, andar-bhaunh upar+, aankh khuli (1 = normal), munh kam se kam khula)
    EMO = {"neutral": (0, 0, 0, 1.0, 0), "happy": (1.0, 0.3, 0, 0.85, 0), "sad": (-0.9, 0, 1.0, 0.85, 0),
           "angry": (-0.4, -1.0, -0.6, 0.85, 0), "surprised": (0, 1.4, 0.4, 1.25, 0.35), "scared": (-0.4, 0.9, 1.0, 1.18, 0.15)}

    def apply(self, img, o, blink, brow, emotion="neutral", k=1.0, gaze=0.0, micro=None):
        """img: poori tasveer (copy hoti hai sirf box) ; o munh 0..1 ; blink 0..1 ; brow 0..1
        gaze: -1 (baayein) .. +1 (daayein) nazar ; micro: (kone, bhaunh, hoth-dabana) chhote bhaav -0.3..0.3"""
        ec, eb, ebi, eo, emin = self.EMO.get(emotion or "neutral", self.EMO["neutral"])
        o = max(o, emin * k)
        mc, mb, mp = micro if micro is not None else (0.0, 0.0, 0.0)
        quiet = abs(gaze) < 0.02 and abs(mc) + abs(mb) + abs(mp) < 0.01
        if not self.ok or (o < 0.02 and blink < 0.02 and brow < 0.02 and quiet and (emotion in (None, "neutral") or k == 0)):
            return img
        x0, y0, x1, y1 = self.box
        roi = img[y0:y1, x0:x1]
        d = o * self.fh * 0.12
        mapy = self.yy - d * self.gm
        if blink > 0.02:
            se = 1 - 0.88 * blink * self.ge
            mapy = np.where(self.ge > 0.02, self.eye_y + (mapy - self.eye_y) / np.maximum(se, 0.1), mapy)
        mapy = mapy + brow * self.eye_d * 0.06 * self.gb  # bhaunh upar
        if emotion not in (None, "neutral") and k > 0:
            fh = self.fh
            mapy = mapy + k * ec * fh * 0.035 * self.gc            # muskaan/udaasi: munh ke kone
            mapy = mapy + k * eb * self.eye_d * 0.09 * self.gb      # bhaunh upar/neeche
            mapy = mapy + k * ebi * self.eye_d * 0.08 * self.gbi    # andar ki bhaunh (dukh/darr)
            sc = 1 + k * (eo - 1)                                   # aankh chaudi/sikudi
            mapy = np.where(self.ge > 0.05, self.eye_y + (mapy - self.eye_y) / (1 + (sc - 1) * self.ge), mapy)
        # chhote bhaav (micro-expression): halki muskaan/kone, bhaunh, hoth dabana
        if not quiet:
            mapy = mapy + mc * self.fh * 0.03 * self.gc + mb * self.eye_d * 0.07 * self.gb
            mapy = mapy - mp * self.fh * 0.02 * self.gm  # hoth upar dabe
        # nazar (eye gaze): aankh ke andar ka hissa daayein/baayein (palak ke beech putli)
        mapx = self.xx
        if abs(gaze) > 0.02:
            iris = np.clip(self.ge * 1.4, 0, 1) ** 2
            mapx = self.xx - gaze * self.eye_d * 0.09 * iris
        out = cv2.remap(roi, (mapx - x0).astype(np.float32), (mapy - y0).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        if d > 1.0:
            m = np.zeros(out.shape[:2], np.float32)
            cx, cy = int(self.mx - x0), int(self.my - y0 + d * 0.5)
            ax, ay = int(self.mw * 0.30 * min(1, 0.6 + o)), max(1, int(d * 0.5))
            cv2.ellipse(m, (cx, cy), (ax, ay), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
            m = cv2.GaussianBlur(m, (0, 0), max(1.0, d * 0.12))[..., None] * 0.92
            out = out * (1 - m) + self.inner * m
            if o > 0.5:  # upar ke daant ki halki patti
                t = np.zeros(out.shape[:2], np.float32)
                cv2.ellipse(t, (cx, int(self.my - y0 + d * 0.18)), (int(ax * 0.8), max(1, int(d * 0.16))), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
                t = cv2.GaussianBlur(t, (0, 0), max(1.0, d * 0.08))[..., None] * 0.3 * min(1, (o - 0.5) * 3)
                out = out * (1 - t) + self.teeth * t
        if blink > 0.3:
            lid = (self.ge * blink)[..., None] * 0.22
            out = out * (1 - lid) + np.array([70, 90, 120], np.float32) * lid
        res = img.copy()
        res[y0:y1, x0:x1] = np.clip(out, 0, 255).astype(np.uint8)
        return res


def blink_track(n, fps=FPS, seed=3):
    rng = np.random.default_rng(seed)
    b = np.zeros(n, np.float32); t = rng.uniform(0.5, 1.5)
    while t * fps < n:
        k = int(t * fps)
        for j in range(6):
            if k + j < n:
                b[k + j] = np.sin(np.pi * (j + 0.5) / 6)
        t += rng.uniform(2.4, 4.8)
    return b


# ------------------------------------------------------------------ VFX particles
class FX:
    def __init__(self, kinds, w, h, n, seed=5):
        self.kinds, self.w, self.h = kinds or [], w, h
        r = np.random.default_rng(seed)
        self.r = r
        s = w / 1920
        self.rain = r.uniform([0, -h], [w * 1.3, h], (int(420 * s) + 60, 2)) if "rain" in self.kinds else None
        self.leaves = [dict(x=r.uniform(0, w), y=r.uniform(-h, h), v=r.uniform(40, 90) * s, ph=r.uniform(0, 6.3),
                            amp=r.uniform(20, 60) * s, sz=r.uniform(6, 13) * s, col=r.choice([0, 1, 2]))
                       for _ in range(28)] if "leaves" in self.kinds else []
        self.dust = r.uniform([0, 0], [w, h], (70, 2)) if ("dust" in self.kinds or "rays" in self.kinds) else None
        self.flies = r.uniform([0, h * 0.35], [w, h], (40, 2)) if "fireflies" in self.kinds else None
        self.birds = [dict(x=-r.uniform(0, w * 0.6), y=r.uniform(h * 0.08, h * 0.35), v=r.uniform(120, 200) * s,
                           sz=r.uniform(10, 18) * s, ph=r.uniform(0, 6)) for _ in range(5)] if "birds" in self.kinds else []
        self.s = s

    def apply(self, fr, i, fps=FPS):
        if not self.kinds:
            return fr
        t = i / fps; w, h, s = self.w, self.h, self.s
        out = fr.astype(np.float32)
        if "rays" in self.kinds:
            yy, xx = np.mgrid[0:h:8, 0:w:8].astype(np.float32)
            ang = np.arctan2(yy + h * 0.3, xx - w * 0.85)
            ray = (0.5 + 0.5 * np.sin(ang * 22 + t * 0.6)) ** 6 * np.clip(1 - yy / h, 0, 1)
            ray = cv2.resize(ray, (w, h))[..., None]
            out += ray * np.array([60, 140, 200], np.float32) * 0.35
        if self.rain is not None:
            out *= 0.86
            layer = np.zeros((h, w), np.float32)
            dy = 1400 * s / fps
            self.rain[:, 1] += dy; self.rain[:, 0] -= dy * 0.25
            wrap = self.rain[:, 1] > h
            self.rain[wrap, 1] -= h * 1.2; self.rain[wrap, 0] = self.r.uniform(0, w * 1.3, wrap.sum())
            for x, y in self.rain.astype(int):
                cv2.line(layer, (x, y), (int(x + 9 * s), int(y - 36 * s)), 0.55, max(1, int(1.5 * s)), cv2.LINE_AA)
            out += cv2.GaussianBlur(layer, (0, 0), 0.8)[..., None] * 180
        if "lightning" in self.kinds:
            fl = 1 if (t % 4.3) > 4.1 or 1.9 < (t % 4.3) < 1.97 else 0
            out += fl * 90
        for L in self.leaves:
            L["y"] += L["v"] / fps; L["x"] += np.sin(t * 1.7 + L["ph"]) * L["amp"] / fps * 2
            if L["y"] > h: L["y"] = -20; L["x"] = self.r.uniform(0, w)
            col = [(40, 160, 90), (30, 170, 200), (40, 120, 170)][L["col"]]
            ang = (t * 90 + L["ph"] * 57) % 360
            cv2.ellipse(out, (int(L["x"]), int(L["y"])), (int(L["sz"]), int(L["sz"] * 0.45)), ang, 0, 360, col, -1, cv2.LINE_AA)
        if self.dust is not None:
            layer = np.zeros((h, w), np.float32)
            for k, (x, y) in enumerate(self.dust):
                xx_ = (x + 12 * s * np.sin(t * 0.4 + k)) % w; yy_ = (y - 8 * s * t) % h
                cv2.circle(layer, (int(xx_), int(yy_)), max(1, int((2 + k % 3) * s)), 1.0, -1, cv2.LINE_AA)
            out += cv2.GaussianBlur(layer, (0, 0), 2 * s)[..., None] * np.array([120, 200, 255], np.float32) * 0.5
        if self.flies is not None:
            layer = np.zeros((h, w), np.float32)
            for k, (x, y) in enumerate(self.flies):
                a = 0.5 + 0.5 * np.sin(t * 2.3 + k * 1.7)
                cv2.circle(layer, (int(x + 30 * s * np.sin(t * 0.5 + k)), int(y + 20 * s * np.cos(t * 0.7 + k))), int(3 * s) + 1, a, -1)
            out += cv2.GaussianBlur(layer, (0, 0), 4 * s)[..., None] * np.array([80, 255, 200], np.float32)
        for B in self.birds:
            B["x"] += B["v"] / fps
            if B["x"] > w + 50: B["x"] = -50
            flap = np.sin(t * 9 + B["ph"]) * B["sz"] * 0.6
            x, y, z = int(B["x"]), int(B["y"] + 6 * s * np.sin(t + B["ph"])), B["sz"]
            pts = np.array([[x - z, y - flap], [x, y], [x + z, y - flap]], np.int32)
            cv2.polylines(out, [pts], False, (40, 40, 40), max(2, int(2.5 * s)), cv2.LINE_AA)
        return np.clip(out, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ camera
def cam_params(cam, u):
    """u = 0..1 scene progress -> (zoom, pan_x, pan_y) ; pan -1..1"""
    e = u * u * (3 - 2 * u)  # smooth
    return {"in": (1.05 + 0.10 * e, 0, 0), "out": (1.15 - 0.10 * e, 0, 0), "fastin": (1.05 + 0.25 * e, 0, 0),
            "left": (1.12, -0.8 + 1.6 * e, 0), "right": (1.12, 0.8 - 1.6 * e, 0),
            "shake": (1.12, 0, 0), "up": (1.12, 0, 0.7 - 1.4 * e), "static": (1.06, 0, 0)}.get(cam, (1.05 + 0.10 * e, 0, 0))


def warp(img, z, px, py, W, H, extra_rot=0.0, pivot=None):
    h, w = img.shape[:2]
    base = max(W / w, H / h) * z
    cx, cy = w / 2, h / 2
    M = cv2.getRotationMatrix2D((cx, cy) if pivot is None else pivot, extra_rot, base)
    M[0, 2] += W / 2 - cx + (-px) * (w * base - W) / 2 if pivot is None else W / 2 - cx
    M[1, 2] += H / 2 - cy + (-py) * (h * base - H) / 2 if pivot is None else H / 2 - cy
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def render_scene(img_path, n_frames, W, H, cam="in", mouth=None, vfx=None, crop=None, seed=1, write=None, people=None,
                 emotion="neutral", actors=None, mouths=None):
    """har frame banakar write(frame_bgr) ko deta hai"""
    img = cv2.imread(img_path)
    h0, w0 = img.shape[:2]
    img = img[int(h0 * .02):int(h0 * .94), int(w0 * .02):int(w0 * .94)]  # watermark kona
    if crop:
        x, y, cw, ch = crop; h1, w1 = img.shape[:2]
        img = img[int(h1 * y):int(h1 * (y + ch)), int(w1 * x):int(w1 * (x + cw))]
    # kaam ki resolution: output se thodi badi
    sc = max(W * 1.25 / img.shape[1], H * 1.25 / img.shape[0])
    img = cv2.resize(img, (int(img.shape[1] * sc), int(img.shape[0] * sc)), interpolation=cv2.INTER_CUBIC)
    if people == 0:  # script mein koi insaan nahi -> layer/bolna nahi (galat pakad se bachao)
        mask, area = np.zeros(img.shape[:2], np.float32), 0.0
    else:
        mask, area = person_mask(img)
    layered = 0.02 < area < 0.55
    plate = clean_plate(img, mask) if layered else img
    talker = Talker(img)
    if people == 0:
        talker.ok = False
    mouth = np.zeros(n_frames, np.float32) if mouth is None else mouth
    blinks = blink_track(n_frames, seed=seed)
    fx = FX(vfx, W, H, n_frames, seed=seed)
    m3 = mask[..., None]
    stage = None
    for i in range(n_frames):
        u = i / max(1, n_frames - 1); t = i / FPS
        z, px, py = cam_params(cam, u)
        o = float(mouth[i]) if i < len(mouth) else 0.0
        brow = 0.6 * o if o > 0.5 else 0.0
        actor = talker.apply(img, o, float(blinks[i]), brow, emotion, min(1.0, 0.3 + i / 20)) if talker.ok else img
        if actors:  # Human Motion Core: chaal, IK, baatcheet, bhaav, nazar, cheez pakadna (motion_core.py)
            if stage is None:
                import motion_core
                stage = motion_core.Stage(actors, actor.shape[0], actor.shape[1], mouths, FPS)
            actor = stage.draw(actor, i)
        rot = 0.0
        if cam == "shake":
            px += 0.04 * np.sin(t * 23); py += 0.03 * np.sin(t * 31)
        if layered:
            bg = warp(plate, z, px * 0.8, py * 0.8, W, H)
            # kirdaar: thoda zyada zoom/pan (parallax) + saans + bolte waqt sir ki halki chaal
            breathe = 1 + 0.006 * np.sin(2 * np.pi * t / 3.4)
            rot = 0.6 * np.sin(2 * np.pi * t / 3.9) + 1.2 * o * np.sin(t * 7.0)
            fz = z * 1.025 * breathe
            fg = warp(actor, fz, px * 1.2, py * 1.2, W, H)
            fm = warp(m3.repeat(3, 2), fz, px * 1.2, py * 1.2, W, H)[..., :1]
            if abs(rot) > 0.01:
                R = cv2.getRotationMatrix2D((W / 2, H * 0.9), rot * 0.5, 1.0)
                fg = cv2.warpAffine(fg, R, (W, H), borderMode=cv2.BORDER_REFLECT)
                fm = cv2.warpAffine(fm, R, (W, H))[..., None]
            fr = (bg * (1 - fm) + fg * fm).astype(np.uint8)
        else:
            fr = warp(actor, z, px, py, W, H)
        fr = fx.apply(fr, i)
        write(fr)
    info = {"layered": bool(layered), "talk": bool(talker.ok), "person_area": round(float(area), 3)}
    if stage is not None:
        info["motion_check"] = stage.report()
    return info


if __name__ == "__main__":
    ensure_models()
    a = sys.argv[1:]
    W, H, dur = 1280, 720, 6.0
    voice = a[2] if len(a) > 2 else None
    n = int(dur * FPS)
    mc = normalise_mouth(mouth_curve(voice, n, 0.5)) if voice else None
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                          "-pix_fmt", "yuv420p", a[1]], stdin=subprocess.PIPE)
    info = render_scene(a[0], n, W, H, cam="in", mouth=mc, vfx=["dust"], write=lambda f: p.stdin.write(f.tobytes()))
    p.stdin.close(); p.wait(); print(info)
