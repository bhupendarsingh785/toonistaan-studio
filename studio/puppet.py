"""Toonistaan 2D Puppet engine (free, CPU): ek poori-body kirdaar tasveer ko haddiyon par baandh kar chalana.
Engine 2 (rig), 3 (chalna/daudna/haath), 5 (haath ishaare), 8 (pair zameen par / IK), 9 (saans/sway), 11 (har scene same kirdaar).
Kirdaar sheet: saada background, poori body, A-pose (haath body se thoda door, pair thode khule).

python puppet.py sheet.jpg out.mp4 [action] [voice.mp3]   # akela test (saada background par)
actions: idle, talk, wave, point, walk, run, jump, nod, clap"""
import os, sys, math, subprocess
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models")
sys.path.insert(0, MODELS); sys.path.insert(0, HERE)
FPS = 30

# MediaPipe index (kirdaar ka LEFT = tasveer mein DAAYI taraf)
NOSE, LSH, RSH, LEL, REL, LWR, RWR, LHIP, RHIP, LKN, RKN, LAN, RAN = 0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28
LIDX, RIDX, LFOOT, RFOOT = 19, 20, 31, 32


def _seg_dist(p, a, b):
    ab = b - a; L2 = float(ab @ ab) + 1e-9
    t = np.clip(((p - a) @ ab) / L2, 0, 1)
    return np.linalg.norm(p - (a + np.outer(t, ab)), axis=1), t


def _rot_about(c, deg):
    a = math.radians(deg); ca, sa = math.cos(a), math.sin(a)
    return np.array([[ca, -sa, c[0] - ca * c[0] + sa * c[1]], [sa, ca, c[1] - sa * c[0] - ca * c[1]], [0, 0, 1]])


class Puppet:
    def __init__(self, sheet_path, cache=True):
        img = cv2.imread(sheet_path)
        if img is None:
            raise FileNotFoundError(sheet_path)
        # kaam ki size (kirdaar ki lambai ~900 px)
        s = 860 / img.shape[0]  # 860 px: video mein kirdaar isse bada nahi dikhta (tez render)
        img = cv2.resize(img, (int(img.shape[1] * s), 860), interpolation=cv2.INTER_AREA)
        h0, w0 = img.shape[:2]
        img = img[:int(h0 * 0.95)]  # neeche ka watermark patti hatao (pair upar rehte)
        self.img = img
        self.H, self.W = img.shape[:2]
        self.joints, self.conf = self._pose(img)
        self.mask = self._cutout(img)
        self._build_bones()
        self._build_mesh()
        self._weights()
        from motion import Talker
        self.talker = Talker(img)

    # ---------- background hatao (saada sheet) ----------
    def _cutout(self, img):
        """GrabCut: joint ke dabbe se kirdaar alag (gradient/grey background aur zameen ki parchhai hatti hai)"""
        h, w = img.shape[:2]
        J = self.joints
        x0, x1 = J[:, 0].min(), J[:, 0].max(); y0, y1 = J[:, 1].min(), J[:, 1].max()
        bw, bh = x1 - x0, y1 - y0
        x0 = max(1, x0 - bw * 0.35); x1 = min(w - 2, x1 + bw * 0.35)
        y0 = max(1, y0 - bh * 0.22); y1 = min(h - 2, y1 + bh * 0.04)
        s = 520 / h
        small = cv2.resize(img, (int(w * s), 520))
        m = np.zeros(small.shape[:2], np.uint8)
        rect = (int(x0 * s), int(y0 * s), int((x1 - x0) * s), int((y1 - y0) * s))
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(small, m, rect, bgd, fgd, 6, cv2.GC_INIT_WITH_RECT)
        # haddiyon ki line pakka kirdaar
        for a, b in [(11, 13), (13, 15), (12, 14), (14, 16), (23, 25), (25, 27), (24, 26), (26, 28), (11, 24), (12, 23), (11, 12), (23, 24)]:
            cv2.line(m, tuple((J[a] * s).astype(int)), tuple((J[b] * s).astype(int)), cv2.GC_FGD, 3)
        cv2.grabCut(small, m, None, bgd, fgd, 3, cv2.GC_INIT_WITH_MASK)
        fg = ((m == 1) | (m == 3)).astype(np.uint8)
        fg = cv2.resize(fg, (w, h), interpolation=cv2.INTER_LINEAR)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(fg)
        if n < 2:
            raise ValueError("kirdaar alag nahi hua")
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        fg = (lab == big).astype(np.uint8)
        ff = fg.copy(); cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 1)
        fg[ff == 0] = 1
        return fg

    # ---------- 33 joint ----------
    def _pose(self, img):
        from mp_persondet import MPPersonDet
        from mp_pose import MPPose
        pd = MPPersonDet(os.path.join(MODELS, "person_mp.onnx"), nmsThreshold=0.3, scoreThreshold=0.5, topK=5)
        po = MPPose(os.path.join(MODELS, "pose_mp.onnx"), confThreshold=0.5)
        # pose model ko thoda khula frame chahiye: padding do
        pad = int(self.H * 0.15)
        big = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
        dets = pd.infer(big)
        if dets is None or len(dets) == 0:
            raise ValueError("kirdaar ki body pehchaani nahi gayi")
        r = po.infer(big, dets[0])
        if r is None:
            raise ValueError("body ke joint nahi mile")
        lm = r[1][:33, :2] - pad
        conf = r[1][:33, 4]
        return lm.astype(np.float64), conf

    def _snap_arms(self):
        """pose model cartoon par baanh ko andar (kameez par) rakh deta: kohni/kalaai/haath ko asli baanh ke beech mein khiskao"""
        J = self.joints; m = self.mask; h, w = m.shape
        cx = (J[LSH, 0] + J[RSH, 0]) / 2
        for el, wr, idx, side in ((LEL, LWR, LIDX, 1 if J[LSH, 0] > cx else -1), (REL, RWR, RIDX, 1 if J[RSH, 0] > cx else -1)):
            for k in (el, wr, idx):
                y = int(np.clip(J[k, 1], 0, h - 1))
                row = m[y]
                runs, x = [], 0
                while x < w:
                    if row[x]:
                        x0 = x
                        while x < w and row[x]: x += 1
                        runs.append((x0, x - 1))
                    x += 1
                if len(runs) < 2:
                    continue  # baanh body se chipki: chhodo
                outer = max(runs, key=lambda r: side * (r[0] + r[1]) / 2)
                c = (outer[0] + outer[1]) / 2
                if abs(c - J[k, 0]) < self.H * 0.12 and (outer[1] - outer[0]) < self.H * 0.12:
                    J[k, 0] = c
        # kandha: baanh ke upar wale hisse ki seedh mein
        for sh, el in ((LSH, LEL), (RSH, REL)):
            J[sh, 0] = J[sh, 0] * 0.5 + J[el, 0] * 0.5

    # ---------- haddiyan ----------
    def _build_bones(self):
        self._snap_arms()
        J = self.joints
        pelvis = (J[LHIP] + J[RHIP]) / 2
        neck = (J[LSH] + J[RSH]) / 2
        head_top = J[NOSE] + (J[NOSE] - neck) * 1.1
        lhand = J[LIDX] if self.conf[LIDX] > 0.3 else J[LWR] + (J[LWR] - J[LEL]) * 0.35
        rhand = J[RIDX] if self.conf[RIDX] > 0.3 else J[RWR] + (J[RWR] - J[REL]) * 0.35
        lfoot = J[LFOOT] if self.conf[LFOOT] > 0.3 else J[LAN] + np.array([0, 20.0])
        rfoot = J[RFOOT] if self.conf[RFOOT] > 0.3 else J[RAN] + np.array([0, 20.0])
        # (naam, start, end, parent)
        B = [("spine", pelvis, neck, None), ("head", neck, head_top, "spine"),
             ("l_up", J[LSH], J[LEL], "spine"), ("l_lo", J[LEL], J[LWR], "l_up"), ("l_hand", J[LWR], lhand, "l_lo"),
             ("r_up", J[RSH], J[REL], "spine"), ("r_lo", J[REL], J[RWR], "r_up"), ("r_hand", J[RWR], rhand, "r_lo"),
             ("l_th", J[LHIP], J[LKN], None), ("l_sh", J[LKN], J[LAN], "l_th"), ("l_ft", J[LAN], lfoot, "l_sh"),
             ("r_th", J[RHIP], J[RKN], None), ("r_sh", J[RKN], J[RAN], "r_th"), ("r_ft", J[RAN], rfoot, "r_sh")]
        self.bones = {n: dict(s=np.array(s, float), e=np.array(e, float), p=p) for n, s, e, p in B}
        self.names = [b[0] for b in B]
        self.pelvis = pelvis
        # zameen = kirdaar ka sabse neeche dikhne wala pixel (pair kate hon to joint tasveer ke bahar ho sakte)
        self.ground = float(np.nonzero(self.mask.any(1))[0].max())
        self.height_px = self.ground - float(np.nonzero(self.mask.any(1))[0].min())
        # parde ka kram: peeche se aage (saamne khade kirdaar ke liye)
        self.order = ["l_th", "l_sh", "l_ft", "r_th", "r_sh", "r_ft", "spine", "head",
                      "l_up", "l_lo", "l_hand", "r_up", "r_lo", "r_hand"]

    # ---------- mesh ----------
    def _build_mesh(self):
        m = self.mask
        h, w = m.shape
        step = max(8, int(self.H / 56))  # kam triangle = tez (quality jaanch ke baad)
        ys, xs = np.mgrid[step // 2:h:step, step // 2:w:step]
        pts = np.stack([xs.ravel(), ys.ravel()], 1)
        inside = m[pts[:, 1], pts[:, 0]] > 0
        pts = pts[inside]
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        c = max(cnts, key=cv2.contourArea)[:, 0, :]
        c = c[:: max(1, step // 2)]
        # joint ke paas zyada points (mudne par chikna)
        extra = []
        for b in self.bones.values():
            for t in np.linspace(0, 1, 6):
                extra.append(b["s"] * (1 - t) + b["e"] * t)
        pts = np.concatenate([pts, c, np.array(extra)]).astype(np.float32)
        pts[:, 0] = np.clip(pts[:, 0], 0, w - 1); pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
        pts = np.unique(np.round(pts, 1), axis=0)
        sub = cv2.Subdiv2D((0, 0, w, h))
        for p in pts:
            sub.insert((float(p[0]), float(p[1])))
        tris = sub.getTriangleList().reshape(-1, 3, 2)
        keep = []
        for t in tris:
            if (t < 0).any() or (t[:, 0] >= w).any() or (t[:, 1] >= h).any():
                continue
            cx, cy = t.mean(0).astype(int)
            mids = [(t[i] + t[(i + 1) % 3]) / 2 for i in range(3)]
            if m[cy, cx] and all(m[int(q[1]), int(q[0])] for q in mids):
                keep.append(t)
        tris = np.array(keep, np.float32)
        # vertex index
        V, idx = {}, []
        for t in tris:
            row = []
            for p in t:
                k = (round(float(p[0]), 1), round(float(p[1]), 1))
                if k not in V:
                    V[k] = len(V)
                row.append(V[k])
            idx.append(row)
        self.verts = np.array(list(V.keys()), np.float64)
        self.tris = np.array(idx, np.int32)

    # ---------- weights (har point kis haddi se hile) ----------
    def _weights(self):
        V = self.verts; nb = len(self.names)
        D = np.zeros((len(V), nb)); T = np.zeros((len(V), nb))
        for j, n in enumerate(self.names):
            b = self.bones[n]
            D[:, j], T[:, j] = _seg_dist(V, b["s"], b["e"])
        # har haddi ki motai: baanh patli, dhad mota -> haath ke paas wale shorts ke pixel baanh ke saath na chalein
        Hh = self.height_px if hasattr(self, "height_px") else self.H
        rad = {"spine": 0.16, "head": 0.13, "l_up": 0.05, "l_lo": 0.045, "l_hand": 0.04, "r_up": 0.05, "r_lo": 0.045,
               "r_hand": 0.04, "l_th": 0.065, "l_sh": 0.055, "l_ft": 0.05, "r_th": 0.065, "r_sh": 0.055, "r_ft": 0.05}
        R = np.array([rad[n] * Hh for n in self.names])
        hd = self.names.index("head")
        neck_y = self.bones["head"]["s"][1]
        W = np.zeros_like(D)
        near = np.argmin(D - R, 1)  # jis haddi ki 'motai' ke sabse andar ho
        for i in range(len(V)):
            j = near[i]
            if V[i, 1] < neck_y - self.H * 0.01 and abs(V[i, 0] - self.bones["head"]["s"][0]) < self.H * 0.12:
                j = hd
            W[i, j] = 1.0
            n = self.names[j]; par = self.bones[n]["p"]
            t = T[i, j]
            if par is not None and t < 0.25:  # jod ke paas parent ke saath mila do (chikna mudna)
                a = 0.5 + 0.5 * (t / 0.25)
                W[i, j] = a; W[i, self.names.index(par)] = 1 - a
        self.Wts = W
        # har triangle ka hissa (sabse zyada weight)
        part = np.argmax(W[self.tris].sum(1), 1)
        self.tri_part = np.array([self.names[p] for p in part])
        # alag-alag ang ko jodne wale triangle hatao (jaise haath<->jaangh): warna khinch kar lambi lakeer banti
        own = np.array([self.names[j] for j in np.argmax(W, 1)])
        def linked(a, b):
            return a == b or self.bones[a]["p"] == b or self.bones[b]["p"] == a or \
                {a, b} <= {"spine", "head", "l_up", "r_up", "l_th", "r_th"} and "spine" in (a, b)
        good = [all(linked(own[t[i]], own[t[j]]) for i, j in ((0, 1), (1, 2), (0, 2))) for t in self.tris]
        good = np.array(good)
        self.tris, self.tri_part = self.tris[good], self.tri_part[good]

    # ---------- pose -> vertex ----------
    def deform(self, rot, root=(0.0, 0.0), root_rot=0.0):
        """rot: {bone: degrees} (apne parent ke hisaab se); root: pelvis kitna khiske (px)"""
        R0 = _rot_about(self.pelvis, root_rot)
        R0[0, 2] += root[0]; R0[1, 2] += root[1]
        M = {}
        for n in self.names:
            b = self.bones[n]
            P = M[b["p"]] if b["p"] else R0
            M[n] = P @ _rot_about(b["s"], rot.get(n, 0.0))
        Vh = np.c_[self.verts, np.ones(len(self.verts))]
        out = np.zeros((len(self.verts), 2))
        for j, n in enumerate(self.names):
            w = self.Wts[:, j]
            if w.any():
                out += w[:, None] * (Vh @ M[n].T)[:, :2]
        return out, M

    def bone_mats(self, rot, root=(0.0, 0.0), root_rot=0.0):
        """sirf haddiyon ke world matrix (IK ke liye, tez)"""
        R0 = _rot_about(self.pelvis, root_rot)
        R0[0, 2] += root[0]; R0[1, 2] += root[1]
        M = {}
        for n in self.names:
            b = self.bones[n]
            M[n] = (M[b["p"]] if b["p"] else R0) @ _rot_about(b["s"], rot.get(n, 0.0))
        return M

    def world(self, M, bone, end=True):
        p = self.bones[bone]["e" if end else "s"]
        return (M[bone] @ np.array([p[0], p[1], 1.0]))[:2]

    def render(self, rot, root=(0.0, 0.0), root_rot=0.0, mouth=0.0, blink=0.0, pad=None, emotion="neutral",
               gaze=0.0, micro=None, emo_k=1.0):
        """RGBA layer (kirdaar ki size + pad), aur pairon ki zameen wali y"""
        pad = pad or int(self.H * 0.35)
        tex = self.talker.apply(self.img, mouth, blink, 0.5 * mouth, emotion, emo_k, gaze, micro) if self.talker.ok else self.img
        Vd, M = self.deform(rot, root, root_rot)
        self.last_M, self.last_pad = M, pad
        Vd = Vd + pad
        Hh, Ww = self.H + 2 * pad, self.W + 2 * pad
        col = np.zeros((Hh, Ww, 3), np.uint8); al = np.zeros((Hh, Ww), np.uint8)
        alpha_src = (self.mask * 255).astype(np.uint8)
        for part in self.order:
            for k in np.nonzero(self.tri_part == part)[0]:
                src = self.verts[self.tris[k]].astype(np.float32)
                dst = Vd[self.tris[k]].astype(np.float32)
                x, y, w, h = cv2.boundingRect(dst)
                if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w >= Ww or y + h >= Hh:
                    continue
                sx, sy, sw, sh = cv2.boundingRect(src)
                sx = max(0, sx - 1); sy = max(0, sy - 1)
                sw = min(self.W - sx, sw + 2); sh = min(self.H - sy, sh + 2)
                A = cv2.getAffineTransform((src - [sx, sy]).astype(np.float32), (dst - [x, y]).astype(np.float32))
                patch = cv2.warpAffine(tex[sy:sy + sh, sx:sx + sw], A, (w + 1, h + 1), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                apatch = cv2.warpAffine(alpha_src[sy:sy + sh, sx:sx + sw], A, (w + 1, h + 1), flags=cv2.INTER_LINEAR)
                tm = np.zeros((h + 1, w + 1), np.uint8)
                cv2.fillConvexPoly(tm, np.round(dst - [x, y]).astype(np.int32), 255, cv2.LINE_AA)
                cv2.polylines(tm, [np.round(dst - [x, y]).astype(np.int32)], True, 255, 1, cv2.LINE_AA)  # daraar band
                tm = cv2.min(tm, apatch)
                roi_c = col[y:y + h + 1, x:x + w + 1]; roi_a = al[y:y + h + 1, x:x + w + 1]
                sel = tm > 0
                a = (tm[sel].astype(np.float32) / 255)[:, None]
                roi_c[sel] = (patch[sel] * a + roi_c[sel] * (1 - a)).astype(np.uint8)
                roi_a[sel] = np.maximum(roi_a[sel], tm[sel])
        # bache-khuche chhote tukde hatao (jod par chhoote pixel)
        n, lab, st, _ = cv2.connectedComponentsWithStats((al > 60).astype(np.uint8))
        if n > 2:
            big = st[1:, cv2.CC_STAT_AREA].max()
            for k in range(1, n):
                if st[k, cv2.CC_STAT_AREA] < big * 0.02:
                    al[lab == k] = 0
        feet_y = float(max(Vd[:, 1].max(), 0))
        return col, al, pad, feet_y


# ---------------------------------------------------------------- chaal (motion library)
# Sign: "bahar ki taraf" (body se door) = + ; r_* tasveer ke baayi taraf (+ = clockwise), l_* daayi taraf (ulta)
def _signed(r):
    out = {}
    for k, v in r.items():
        out[k] = -v if k.startswith("l_") else v
    return out


EMO_BODY = {  # bhaav -> body language (darja)
    "neutral": dict(head=0, spine=0, arms=0, bounce=0, tremble=0),
    "happy": dict(head=-3, spine=0, arms=6, bounce=1.0, tremble=0),
    "sad": dict(head=10, spine=4, arms=-4, bounce=0, tremble=0),
    "angry": dict(head=-2, spine=-2, arms=14, bounce=0, tremble=0.3),
    "scared": dict(head=6, spine=5, arms=-8, bounce=0, tremble=1.0),
    "surprised": dict(head=-6, spine=-2, arms=18, bounce=0, tremble=0),
}


def pose_at(action, t, energy=0.0, speed=1.0, emotion="neutral"):
    """returns (rot dict, root (dx, dy), root_rot) ; t seconds ; energy = bolne ki taakat 0..1 ; emotion = bhaav"""
    E = EMO_BODY.get(emotion, EMO_BODY["neutral"])
    r = {}; dx = dy = rr = 0.0
    br = math.sin(2 * math.pi * t / 3.4)
    r["spine"] = 1.2 * br + E["spine"] + E["tremble"] * 1.2 * math.sin(t * 40)
    r["head"] = 2.0 * math.sin(2 * math.pi * t / 4.1) + E["head"]
    r["l_up"] = r["r_up"] = 5 + 2 * br + E["arms"]
    r["l_lo"] = r["r_lo"] = 4
    dy = -E["bounce"] * 8 * abs(math.sin(t * 4.0))
    if action in ("talk", "idle"):
        g = energy
        r["head"] += 4 * g * math.sin(t * 6.5)
        r["r_up"] += 20 * g; r["r_lo"] += 40 * g * (0.6 + 0.4 * math.sin(t * 3.1))
        r["l_up"] += 8 * g * (0.5 + 0.5 * math.sin(t * 2.3))
    elif action == "wave":
        r["r_up"] = 150 + 6 * math.sin(t * 2)
        r["r_lo"] = 20 + 28 * math.sin(t * 2 * math.pi * 1.6)
        r["r_hand"] = 10 * math.sin(t * 2 * math.pi * 1.6)
    elif action == "point":
        r["r_up"] = 95; r["r_lo"] = 8; r["r_hand"] = 5
    elif action == "clap":
        c = 0.5 + 0.5 * math.sin(t * 2 * math.pi * 2.2)
        r["l_up"] = r["r_up"] = -(55 + 10 * c); r["l_lo"] = r["r_lo"] = -(70 + 15 * c)
    elif action == "nod":
        r["head"] += 7 * math.sin(t * 2 * math.pi * 1.4)
    elif action == "cheer":
        r["l_up"] = r["r_up"] = 150 + 8 * math.sin(t * 6); r["l_lo"] = r["r_lo"] = 10
        dy = -14 * abs(math.sin(t * 5))
    elif action in ("walk", "run"):
        f = (1.6 if action == "walk" else 2.6) * speed
        ph = 2 * math.pi * f * t
        k = 1.0 if action == "walk" else 1.6
        lift_l = max(0, math.sin(ph)); lift_r = max(0, -math.sin(ph))
        r["l_th"] = 6 * k * lift_l; r["l_sh"] = -18 * k * lift_l
        r["r_th"] = 6 * k * lift_r; r["r_sh"] = -18 * k * lift_r
        r["l_up"] = 6 + 12 * k * math.sin(ph); r["r_up"] = 6 - 12 * k * math.sin(ph)
        r["l_lo"] = r["r_lo"] = 10 * k
        r["spine"] += 2.5 * k * math.sin(ph)
        dy += -abs(math.sin(ph)) * 10 * k
        rr = 1.5 * k * math.sin(ph)
    elif action == "jump":
        c = (t * 0.9) % 1.0
        if c < 0.25:
            q = c / 0.25; dy = 30 * q
            r["l_th"] = r["r_th"] = 14 * q; r["l_sh"] = r["r_sh"] = -30 * q
        elif c < 0.65:
            q = (c - 0.25) / 0.4; dy = -140 * math.sin(math.pi * q)
            r["l_up"] = r["r_up"] = 150
        else:
            q = 1 - (c - 0.65) / 0.35; dy = 20 * q
            r["l_th"] = r["r_th"] = 10 * q; r["l_sh"] = r["r_sh"] = -22 * q
    return _signed(r), (dx, dy), rr


def blink_at(t, seed=1):
    period = 3.3 + (seed % 5) * 0.4
    d = (t + seed * 0.7) % period
    return math.sin(math.pi * d / 0.18) if d < 0.18 else 0.0


# ---------------------------------------------------------------- scene mein jodna
_cache = {}


def get_puppet(path):
    if path not in _cache:
        _cache[path] = Puppet(path)
    return _cache[path]


def composite_actor(frame, actor, t, mouth=0.0):
    """frame: BGR scene (in-place se naya) ; actor: dict(sheet, action, x0,x1 (0-1), y (pairon ki line 0-1), height (0-1), flip, speed, dur)"""
    P = get_puppet(actor["sheet"])
    Hf, Wf = frame.shape[:2]
    u = min(1.0, t / max(0.01, actor.get("dur", 1.0)))
    act = actor.get("action", "idle")
    emo = actor.get("emotion", "neutral")
    rot, (dx, dy), rr = pose_at(act, t, mouth, actor.get("speed", 1.0), emo)
    col, al, pad, _ = P.render(rot, (0, dy), rr, mouth=mouth, blink=blink_at(t, sum(map(ord, actor["sheet"])) % 7), emotion=emo)
    if actor.get("flip"):
        col = col[:, ::-1]; al = al[:, ::-1]
    scale = actor.get("height", 0.6) * Hf / P.height_px
    col = cv2.resize(col, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    al = cv2.resize(al, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    # zameen: rest pose ke pair (pad ke saath) frame ki y line par (IK-style: pair zameen par tike)
    ground_in_layer = (P.ground + pad) * scale
    x = actor.get("x0", 0.5) + (actor.get("x1", actor.get("x0", 0.5)) - actor.get("x0", 0.5)) * (u * u * (3 - 2 * u) if act not in ("walk", "run") else u)
    cx = int(x * Wf); gy = int(actor.get("y", 0.92) * Hf)
    lx = cx - col.shape[1] // 2; ly = gy - int(ground_in_layer)
    out = frame.copy()
    # parchhai (zameen par)
    sh = np.zeros((Hf, Wf), np.float32)
    lift = max(0.0, -dy) * scale
    cv2.ellipse(sh, (cx, gy), (int(col.shape[1] * 0.18 * (1 - min(0.5, lift / 300))), int(col.shape[1] * 0.04)), 0, 0, 360, 0.45, -1, cv2.LINE_AA)
    sh = cv2.GaussianBlur(sh, (0, 0), max(2, col.shape[1] * 0.02))[..., None]
    out = (out * (1 - sh)).astype(np.uint8)
    # rang milao: kirdaar ki roshni scene jaisi
    bgm = cv2.mean(frame)[:3]; acm = cv2.mean(col, mask=(al > 128).astype(np.uint8))[:3]
    # roshni milao: scene andhera ho to kirdaar bhi andhera + scene ka rang (raat neeli, shaam narangi)
    lum_b = float(np.mean(bgm)); lum_a = float(np.mean(acm)) + 1e-6
    k = np.clip(lum_b / lum_a, 0.25, 1.15) ** 0.75
    tint = (np.array(bgm) / (lum_b + 1e-6)) ** 0.5
    col = np.clip(col * k * tint, 0, 255).astype(np.uint8)
    # chipkao (frame ke bahar wala hissa kaato)
    x0, y0 = max(0, lx), max(0, ly); x1, y1 = min(Wf, lx + col.shape[1]), min(Hf, ly + col.shape[0])
    if x1 > x0 and y1 > y0:
        c = col[y0 - ly:y1 - ly, x0 - lx:x1 - lx].astype(np.float32)
        a = cv2.GaussianBlur(al[y0 - ly:y1 - ly, x0 - lx:x1 - lx], (3, 3), 0).astype(np.float32)[..., None] / 255
        out[y0:y1, x0:x1] = (out[y0:y1, x0:x1] * (1 - a) + c * a).astype(np.uint8)
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    sheet, outp = a[0], a[1]
    action = a[2] if len(a) > 2 else "wave"
    emotion = a[3] if len(a) > 3 else "neutral"
    W, H, dur = 960, 720, 4.0
    P = get_puppet(sheet)
    print("bones ok, verts", len(P.verts), "tris", len(P.tris), "talk", P.talker.ok, "height", int(P.height_px))
    enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", outp],
                           stdin=subprocess.PIPE)
    bg = np.full((H, W, 3), (210, 225, 235), np.uint8)
    cv2.rectangle(bg, (0, int(H * 0.8)), (W, H), (120, 170, 140), -1)
    for i in range(int(dur * FPS)):
        t = i / FPS
        m = 0.5 + 0.5 * math.sin(t * 9) if action == "talk" else 0.0
        actor = dict(sheet=sheet, action=action, x0=0.3 if action in ("walk", "run") else 0.5, x1=0.7 if action in ("walk", "run") else 0.5,
                     y=0.9, height=0.8, dur=dur, emotion=emotion)
        enc.stdin.write(composite_actor(bg, actor, t, m).tobytes())
    enc.stdin.close(); enc.wait(); print("DONE", outp)
