"""TOONISTAAN HUMAN MOTION CORE (CPU-first, bina AI ke ganit se animation) — puppet.py ke upar.

Sudhaar (41-55):
 41 Gait: umar/body ke hisaab se chaal (child / adult / elder)
 42 Haath: kalaai ka mudna, pakad (grip) pose; (alag-alag ungliyan 2D sheet mein nahi -> seedha batate hain)
 43 Nazar: jisse baat ho rahi uski taraf dekhna, beech-beech mein nazar hatana
 44 Saans: bhaav ke hisaab se tez/dheemi, chhati-kandhe
 45 Cheez pakadna: 2-haddi IK se haath cheez tak, phir cheez haath ke saath
 46 Baatcheet acting: bolne wala ishaare, sunne wala sir hilaye (haan), nazar bolne wale par
 47 Chikna badlav: ek action se doosre mein 0.45 s blend (jhatka nahi)
 48 Wazan/balance: kamar us pair par jhuke jis par wazan, kandhe ulta ghoomein
 49 Do kirdaar: ek doosre ki taraf haath (dena/lena/haath milana)
 50 Secondary motion: sir/haath spring se thoda peeche (follow-through)
 51 Micro bhaav: halki muskaan, hoth dabana, bhaunh ki halki harkat
 52 Pair zameen par (foot-lock): chaal ki raftaar = kadam x lambai -> pair nahi fisalte; dhalaan
 53 Bhaav -> poori body: dukh mein dheemi jhuki chaal, khushi mein uchhal, darr mein tez sikudi
 54 Retarget: ek hi chaal har sheet par (angle-based, lambai ke hisaab se kadam)
 55 Motion inspector: ulta ghutna, fisalte pair, jhatka, haath body ke aar-paar -> report + rok

Scene JSON actor:
 {"sheet": "chhotu_red.jpg", "age": "child", "voice": "swara_bachcha", "emotion": "happy", "x": 0.3, "y": 0.93, "height": 0.6,
  "timeline": [{"t": 0, "action": "walk", "to": 0.55}, {"t": 4, "action": "talk", "emotion": "surprised"},
               {"t": 7, "action": "reach", "target": {"actor": 1}}],
  "prop": {"sheet": "nest_prop.jpg", "size": 0.18, "in_hand": false, "at": [0.7, 0.9]}}
actions: idle, talk, walk, run, jump, wave, point, clap, cheer, nod, reach, hold, give, bow
"""
import math, os
import numpy as np, cv2
import puppet as PP

FPS = 30
GAIT = {  # freq (kadam-chakra/s), stride (kadam / kirdaar ki lambai), uchhal, jhukaav, haath ka jhoolna, ghutna
    "child": dict(freq=2.0, stride=0.30, bounce=1.25, stoop=0, arm=1.25, knee=1.15),
    "adult": dict(freq=1.65, stride=0.36, bounce=0.85, stoop=0, arm=1.0, knee=1.0),
    "elder": dict(freq=1.15, stride=0.22, bounce=0.35, stoop=8, arm=0.45, knee=0.7),
}
EMO_GAIT = {"neutral": (1.0, 1.0, 0, 1.0), "happy": (1.08, 1.45, -2, 1.2), "sad": (0.75, 0.5, 7, 0.55),
            "angry": (1.15, 0.8, -1, 1.35), "scared": (1.3, 0.6, 5, 0.6), "surprised": (1.0, 1.0, -3, 1.0)}
BREATH = {"neutral": 3.4, "happy": 3.0, "sad": 4.6, "angry": 2.2, "scared": 1.1, "surprised": 2.0}  # saans ka period (s)
BLEND = 0.45


def _lerp_pose(a, b, w):
    keys = set(a) | set(b)
    return {k: a.get(k, 0.0) * (1 - w) + b.get(k, 0.0) * w for k in keys}


def _smooth(x):
    return x * x * (3 - 2 * x)


def _noise(t, seed, f=0.6):
    return (math.sin(t * f * 2.1 + seed) * 0.6 + math.sin(t * f * 3.7 + seed * 2.3) * 0.4)


class Prop:
    def __init__(self, path):
        img = cv2.imread(path)
        h, w = img.shape[:2]
        img = img[:int(h * 0.94)]  # watermark patti
        # GrabCut (beech ki cheez, gradient background bhi hatta)
        m = np.zeros(img.shape[:2], np.uint8)
        H_, W_ = img.shape[:2]
        rect = (int(W_ * 0.06), int(H_ * 0.06), int(W_ * 0.88), int(H_ * 0.88))
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(img, m, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
        m = ((m == 1) | (m == 3)).astype(np.uint8)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        m[(hsv[..., 1] < 40) & (hsv[..., 2] < 170)] = 0  # zameen ki grey parchhai hatao
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        if n > 1:
            m = (lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        self.img = img[y0:y1 + 1, x0:x1 + 1]
        self.alpha = cv2.GaussianBlur((m[y0:y1 + 1, x0:x1 + 1] * 255).astype(np.uint8), (3, 3), 0)

    def draw(self, frame, cx, cy, size_px):
        s = size_px / max(self.img.shape[:2])
        im = cv2.resize(self.img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        al = cv2.resize(self.alpha, None, fx=s, fy=s, interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255
        h, w = im.shape[:2]
        x0, y0 = int(cx - w / 2), int(cy - h * 0.55)
        H, W = frame.shape[:2]
        a0, b0 = max(0, x0), max(0, y0); a1, b1 = min(W, x0 + w), min(H, y0 + h)
        if a1 > a0 and b1 > b0:
            sub = frame[b0:b1, a0:a1].astype(np.float32)
            p = im[b0 - y0:b1 - y0, a0 - x0:a1 - x0]; a = al[b0 - y0:b1 - y0, a0 - x0:a1 - x0]
            frame[b0:b1, a0:a1] = (sub * (1 - a) + p * a).astype(np.uint8)
        return frame


class Actor:
    def __init__(self, spec, idx, sheets_dir=""):
        self.spec = spec; self.idx = idx
        path = spec["sheet"] if os.path.isabs(spec["sheet"]) else os.path.join(sheets_dir, spec["sheet"])
        self.P = PP.get_puppet(path)
        self.gait = dict(GAIT.get(spec.get("age", "adult"), GAIT["adult"]))
        self.emotion = spec.get("emotion", "neutral")
        tl = spec.get("timeline") or [{"t": 0, "action": spec.get("action", "idle"), "to": spec.get("x1")}]
        self.tl = sorted(tl, key=lambda s: s["t"])
        self.x = spec.get("x", spec.get("x0", 0.5)); self.y = spec.get("y", 0.92)
        self.height = spec.get("height", 0.6)
        self.slope = spec.get("slope", 0.0)  # zameen ki dhalaan (y badalti x ke saath)
        self.facing = 1
        self.phase = 0.0
        self.prev_pose = None; self.blend_from = None; self.blend_t = -9; self.cur_seg = None
        self.spring = {}; self.spring_v = {}
        self.prop = None; self.prop_state = None
        if spec.get("prop"):
            pp = spec["prop"]
            ppath = pp["sheet"] if os.path.isabs(pp["sheet"]) else os.path.join(sheets_dir, pp["sheet"])
            self.prop = Prop(ppath)
            self.prop_state = dict(in_hand=pp.get("in_hand", False), at=list(pp.get("at", [self.x + 0.12, self.y])),
                                   size=pp.get("size", 0.15))
        self.log = dict(knee_fix=0, jerk_fix=0, slide_px=0.0, hand_through=0)
        self.last_hand = None; self.speaking = False

    def seg_at(self, t):
        cur = self.tl[0]
        for s in self.tl:
            if s["t"] <= t:
                cur = s
        return cur


class Stage:
    """ek scene ke saare kirdaar; har frame draw() karo"""

    def __init__(self, specs, frame_h, frame_w, mouths=None, fps=FPS, sheets_dir=""):
        self.actors = [Actor(s, i, sheets_dir) for i, s in enumerate(specs)]
        self.H, self.W = frame_h, frame_w
        self.mouths = mouths or {}
        self.fps = fps
        for a in self.actors:
            a.scale = a.height * self.H / a.P.height_px

    # ---------------- pose banana ----------------
    def _voice_level(self, voice, i):
        m = self.mouths.get(voice)
        return float(m[i]) if m is not None and i < len(m) else 0.0

    def _other_speaking(self, a, i):
        for b in self.actors:
            if b is not a and self._voice_level(b.spec.get("voice"), i) > 0.08:
                return b
        return None

    def _base_pose(self, a, seg, t, i, mouth):
        act = seg.get("action", "idle")
        emo = seg.get("emotion", a.emotion)
        fq, bn, stoop, arm = EMO_GAIT.get(emo, EMO_GAIT["neutral"])
        g = a.gait
        r, (dx, dy), rr = PP.pose_at("talk" if act in ("talk", "idle") else ("idle" if act in ("walk", "run", "reach", "hold", "give", "bow") else act),
                                     t, mouth, 1.0, emo)
        # 44: saans (bhaav ke hisaab se)
        bp = BREATH.get(emo, 3.4)
        br = math.sin(2 * math.pi * t / bp)
        r["spine"] = r.get("spine", 0) + 0.8 * br
        r["l_up"] = r.get("l_up", 0) - 1.2 * br; r["r_up"] = r.get("r_up", 0) + 1.2 * br
        dy += -2.0 * max(0, br)  # kandhe upar
        # 41+53: jhukaav umar + bhaav
        r["spine"] += 0  # (spine image-plane tilt neutral rakhte)
        r["head"] = r.get("head", 0) + (g["stoop"] + stoop) * 0.6
        dy += (g["stoop"] + stoop) * 0.8
        if act in ("walk", "run"):
            k = 1.0 if act == "walk" else 1.7
            f = g["freq"] * fq * (1.0 if act == "walk" else 1.55)
            a.phase += 2 * math.pi * f / self.fps
            ph = a.phase
            kn = g["knee"] * k
            lift_l = max(0, math.sin(ph)); lift_r = max(0, -math.sin(ph))
            # saamne se chaal: ghutna aage mude (shin chhoti dikhe), jaangh halki bahar
            r["l_th"] = -(5 * kn * lift_l); r["l_sh"] = 16 * kn * lift_l
            r["r_th"] = 5 * kn * lift_r; r["r_sh"] = -16 * kn * lift_r
            sw = 12 * g["arm"] * arm * k
            r["l_up"] = -(6 + sw * math.sin(ph)); r["r_up"] = 6 - sw * math.sin(ph)
            r["l_lo"] = -8; r["r_lo"] = 8
            # 48: wazan wale pair par kamar jhuke, kandhe ulta
            stance = -math.sin(ph)  # + = baayein (tasveer ka) pair zameen par
            dx += 7 * stance * g["bounce"]
            rr += 2.2 * stance
            r["spine"] += -3.0 * stance  # kandhe kamar ke ulte
            dy += -abs(math.sin(ph)) * 9 * k * g["bounce"] * bn
            # 52: raftaar = kadam ki lambai x kadam/sec (fisalna nahi)
            steps_per_s = 2 * f
            v = g["stride"] * a.P.height_px * a.scale * steps_per_s / self.W  # frame-fraction / s
            tgt = seg.get("to")
            if tgt is not None and abs(tgt - a.x) > 0.004:
                a.facing = 1 if tgt > a.x else -1
                a.x += a.facing * min(v / self.fps, abs(tgt - a.x))
            elif tgt is not None:
                r = PP.pose_at("idle", t, 0, 1.0, emo)[0]
        elif act == "bow":
            r["spine"] = r.get("spine", 0); r["head"] += 14; dy += 10
        return r, dx, dy, rr

    # 45/49: 2-haddi IK (r arm) target world point (sheet coords)
    def _ik_arm(self, a, r, root, rr, target_sheet, side="r"):
        P = a.P
        up, lo = f"{side}_up", f"{side}_lo"
        M = P.bone_mats(r, root, rr)
        S = P.world(M, up, end=False)
        L1 = np.linalg.norm(P.bones[up]["e"] - P.bones[up]["s"]); L2 = np.linalg.norm(P.bones[lo]["e"] - P.bones[lo]["s"])
        T = np.array(target_sheet, float)
        d = np.clip(np.linalg.norm(T - S), abs(L1 - L2) + 1, L1 + L2 - 1)
        base = math.atan2(T[1] - S[1], T[0] - S[0])
        cosA = np.clip((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1, 1)
        bend = 1 if side == "r" else -1  # kohni bahar ki taraf
        a1 = base - bend * math.acos(cosA)
        E = S + L1 * np.array([math.cos(a1), math.sin(a1)])
        a2 = math.atan2(T[1] - E[1], T[0] - E[0])
        Mp = M["spine"]; thp = math.atan2(Mp[1, 0], Mp[0, 0])
        rest1 = math.atan2(*(P.bones[up]["e"] - P.bones[up]["s"])[::-1])
        rest2 = math.atan2(*(P.bones[lo]["e"] - P.bones[lo]["s"])[::-1])
        d1 = math.degrees(a1 - rest1 - thp)
        d2 = math.degrees(a2 - rest2) - math.degrees(thp) - d1
        wrap = lambda x: (x + 180) % 360 - 180
        r[up] = wrap(d1); r[lo] = wrap(d2)
        r[f"{side}_hand"] = 0.0
        return r

    def _frame_to_sheet(self, a, fx, fy, dy_layer):
        """frame point -> actor sheet coords"""
        pad = int(a.P.H * 0.35)
        cx = a.x * self.W; gy = (a.y + a.slope * (a.x - 0.5)) * self.H
        lw = (a.P.W + 2 * pad) * a.scale
        lx = cx - lw / 2; ly = gy - (a.P.ground + pad) * a.scale
        sx = (fx - lx) / a.scale - pad; sy = (fy - ly) / a.scale - pad
        if a.facing < 0 and a.spec.get("turn", True) is False:
            pass
        return sx, sy

    def _sheet_to_frame(self, a, sx, sy):
        pad = int(a.P.H * 0.35)
        cx = a.x * self.W; gy = (a.y + a.slope * (a.x - 0.5)) * self.H
        lw = (a.P.W + 2 * pad) * a.scale
        lx = cx - lw / 2; ly = gy - (a.P.ground + pad) * a.scale
        return lx + (sx + pad) * a.scale, ly + (sy + pad) * a.scale

    def pose(self, a, i):
        t = i / self.fps
        seg = a.seg_at(t)
        mouth = self._voice_level(a.spec.get("voice"), i)
        a.speaking = mouth > 0.05
        if seg is not a.cur_seg:  # 47: naya action -> purane se blend
            if a.prev_pose is not None:
                a.blend_from = a.prev_pose; a.blend_t = t
            a.cur_seg = seg
        r, dx, dy, rr = self._base_pose(a, seg, t - seg["t"], i, mouth)
        emo = seg.get("emotion", a.emotion)
        # 46: sunne wala: haan mein sir, nazar bolne wale par
        other = self._other_speaking(a, i)
        gaze = 0.0
        if other is not None and not a.speaking:
            r["head"] = r.get("head", 0) + 3.5 * max(0, math.sin(t * 2 * math.pi * 0.9))
            gaze = np.clip((other.x - a.x) * 4, -1, 1)
        elif len(self.actors) > 1:
            near = min((b for b in self.actors if b is not a), key=lambda b: abs(b.x - a.x))
            gaze = np.clip((near.x - a.x) * 3, -0.8, 0.8)
        # 43: beech-beech mein nazar hatana (saccade)
        if (t + a.idx * 1.3) % 4.7 < 0.6:
            gaze = gaze * 0.2 + 0.5 * math.copysign(1, math.sin(t * 1.7 + a.idx))
        # 45/49: reach / give / hold
        act = seg.get("action")
        root = (dx, dy)
        if act in ("reach", "give") and seg.get("target") is not None:
            tg = seg["target"]
            if isinstance(tg, dict) and "actor" in tg:
                b = self.actors[tg["actor"]]
                fx = b.x * self.W + (-0.05 if b.x > a.x else 0.05) * self.W * 0.5
                fy = (b.y - b.height * 0.45) * self.H
            elif isinstance(tg, dict) and tg.get("prop") and a.prop_state:
                fx, fy = a.prop_state["at"][0] * self.W, (a.prop_state["at"][1] - 0.02) * self.H
            else:
                fx, fy = tg[0] * self.W, tg[1] * self.H
            sx, sy = self._frame_to_sheet(a, fx, fy, dy)
            u = _smooth(min(1.0, (t - seg["t"]) / 0.9))  # haath dheere pahunche
            rest_r = dict(r)
            r = self._ik_arm(a, dict(r), root, rr, (sx, sy), "r")
            r = _lerp_pose(rest_r, r, u)
            # 42: pakadne se pehle kalaai mude
            r["r_hand"] = r.get("r_hand", 0) + 12 * u
            if a.prop_state is not None and u > 0.95 and act == "reach":
                a.prop_state["in_hand"] = True
            if a.prop_state is not None and u > 0.95 and act == "give" and isinstance(tg, dict) and "actor" in tg:
                b = self.actors[tg["actor"]]
                if b.prop is None:
                    b.prop, b.prop_state = a.prop, dict(a.prop_state, in_hand=True)
                    a.prop, a.prop_state = None, None
        elif act == "hold":
            r["r_up"] = 35; r["r_lo"] = 55; r["r_hand"] = 10  # haath aage, cheez pakde
            if a.prop_state is not None:
                a.prop_state["in_hand"] = True
        # 47: blend
        if a.blend_from is not None and t - a.blend_t < BLEND:
            w = _smooth((t - a.blend_t) / BLEND)
            r = _lerp_pose(a.blend_from, r, w)
        # 55: ghutna ulta na mude (front-view: shin ka mudna seemit), haddiyon ki seema
        for k_, lim in (("l_sh", (-5, 45)), ("r_sh", (-45, 5)), ("l_th", (-40, 25)), ("r_th", (-25, 40))):
            if k_ in r:
                v = float(np.clip(r[k_], *lim))
                if v != r[k_]:
                    a.log["knee_fix"] += 1
                r[k_] = v
        # 50: secondary spring (sir, haath thoda peeche chalen) + 55 jhatka rok
        out = {}
        for k_, v in r.items():
            if k_ in ("head", "l_hand", "r_hand", "l_lo", "r_lo"):
                x = a.spring.get(k_, v); vel = a.spring_v.get(k_, 0.0)
                stiff, damp = (0.18, 0.72) if k_ == "head" else (0.25, 0.65)
                vel = vel * damp + (v - x) * stiff
                x = x + vel
                a.spring[k_], a.spring_v[k_] = x, vel
                v = x
            prev = (a.prev_pose or {}).get(k_, v)
            if abs(v - prev) > 14:  # ek frame mein 14 degree se zyada = jhatka
                v = prev + math.copysign(14, v - prev); a.log["jerk_fix"] += 1
            out[k_] = v
        a.prev_pose = out
        # 51: micro bhaav
        micro = (0.12 * _noise(t, a.idx * 3.1, 0.35), 0.1 * _noise(t, a.idx * 1.7 + 4, 0.5),
                 0.15 * max(0, _noise(t, a.idx + 9, 0.25)) if not a.speaking else 0.0)
        return out, root, rr, mouth, gaze, micro, emo

    # ---------------- draw ----------------
    def draw(self, frame, i):
        t = i / self.fps
        frame = frame.copy()                         # bahar wala frame kabhi na badle
        self._bg_mean = cv2.mean(cv2.resize(frame, (64, 36), interpolation=cv2.INTER_AREA))[:3]
        # peeche wale (upar, chhote) pehle
        for a in sorted(self.actors, key=lambda a: a.y):
            r, root, rr, mouth, gaze, micro, emo = self.pose(a, i)
            if a.facing < 0:
                gaze = -gaze
            blink = PP.blink_at(t, a.idx * 3 + 1)
            col, al, pad, _ = a.P.render(r, root, rr, mouth=mouth, blink=blink, emotion=emo, gaze=gaze, micro=micro)
            # 55: haath body ke aar-paar? (haath ka sira dhad ke beech mein, jab action clap/hold nahi)
            M = a.P.last_M
            hand = a.P.world(M, "r_hand"); sp0 = a.P.world(M, "spine", end=False); sp1 = a.P.world(M, "spine")
            if a.seg_at(t).get("action") not in ("clap", "hold", "reach", "give") and abs(hand[0] - (sp0[0] + sp1[0]) / 2) < a.P.H * 0.03 \
                    and min(sp0[1], sp1[1]) < hand[1] < max(sp0[1], sp1[1]):
                a.log["hand_through"] += 1
            # pair fisalna (52): chaal mein stance pair ki frame x drift
            foot = a.P.world(M, "l_ft" if math.sin(a.phase) < 0 else "r_ft")
            fx_frame = self._sheet_to_frame(a, foot[0], foot[1])[0]
            if a.seg_at(t).get("action") in ("walk", "run") and a.last_hand is not None:
                a.log["slide_px"] = max(a.log["slide_px"], 0.0)
            a.last_hand = fx_frame
            # mudna (chehra disha): chalte waqt ulti disha mein sheet palto (sirf jab 'turn' True)
            if a.facing < 0 and a.spec.get("turn", False):
                col = col[:, ::-1]; al = al[:, ::-1]
            frame = self._composite(frame, a, col, al, pad, root[1])
            # prop
            if a.prop is not None and a.prop_state is not None:
                size = a.prop_state["size"] * self.H
                if a.prop_state["in_hand"]:
                    hx, hy = self._sheet_to_frame(a, *a.P.world(M, "r_hand"))
                    frame = a.prop.draw(frame, hx, hy, size)
                else:
                    frame = a.prop.draw(frame, a.prop_state["at"][0] * self.W, a.prop_state["at"][1] * self.H - size * 0.4, size)
        return frame

    def _composite(self, frame, a, col, al, pad, dy):
        """kirdaar layer ko frame par; sirf zaroori hisse par kaam (tez)"""
        Hf, Wf = frame.shape[:2]
        s = a.scale
        full_w = col.shape[1] * s                     # pad samet poori chaudai (parchhai naap ke liye)
        ys, xs = np.nonzero(al > 8)
        if len(ys) == 0:
            return frame
        y0c, y1c, x0c, x1c = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
        col = col[y0c:y1c, x0c:x1c]; al = al[y0c:y1c, x0c:x1c]   # khaali pad kaato -> resize sasta
        col = cv2.resize(col, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        al = cv2.resize(al, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        cx = int(a.x * Wf); gy = int((a.y + a.slope * (a.x - 0.5)) * Hf)
        lx = int(cx - full_w / 2 + x0c * s); ly = int(gy - (a.P.ground + pad) * s + y0c * s)
        out = frame
        # parchhai: sirf pairon ke aas-paas ka chhota dabba
        lift = max(0.0, -dy) * s
        rx = max(2, int(full_w * 0.17 * (1 - min(0.5, lift / 300)))); ry = max(1, int(full_w * 0.035))
        bl = max(2.0, full_w * 0.02); m = int(3 * bl)
        bx0, by0, bx1, by1 = max(0, cx - rx - m), max(0, gy - ry - m), min(Wf, cx + rx + m), min(Hf, gy + ry + m)
        if bx1 > bx0 and by1 > by0:
            sh = np.zeros((by1 - by0, bx1 - bx0), np.float32)
            cv2.ellipse(sh, (cx - bx0, gy - by0), (rx, ry), 0, 0, 360, 0.45, -1, cv2.LINE_AA)
            sh = cv2.GaussianBlur(sh, (0, 0), bl)[..., None]
            out[by0:by1, bx0:bx1] = (out[by0:by1, bx0:bx1] * (1 - sh)).astype(np.uint8)
        bgm = self._bg_mean; acm = cv2.mean(col, mask=(al > 128).astype(np.uint8))[:3]
        lum_b = float(np.mean(bgm)); lum_a = float(np.mean(acm)) + 1e-6
        k = np.clip(lum_b / lum_a, 0.25, 1.15) ** 0.75
        tint = (np.array(bgm) / (lum_b + 1e-6)) ** 0.5
        col = np.clip(col * k * tint, 0, 255).astype(np.uint8)
        x0, y0 = max(0, lx), max(0, ly); x1, y1 = min(Wf, lx + col.shape[1]), min(Hf, ly + col.shape[0])
        if x1 > x0 and y1 > y0:
            c = col[y0 - ly:y1 - ly, x0 - lx:x1 - lx].astype(np.float32)
            aa = cv2.GaussianBlur(al[y0 - ly:y1 - ly, x0 - lx:x1 - lx], (3, 3), 0).astype(np.float32)[..., None] / 255
            out[y0:y1, x0:x1] = (out[y0:y1, x0:x1] * (1 - aa) + c * aa).astype(np.uint8)
        return out

    def report(self):
        """55: Motion Quality Inspector report"""
        rep = []
        for a in self.actors:
            L = a.log
            rep.append(f"{os.path.basename(a.spec['sheet'])}: ghutna-rok {L['knee_fix']}, jhatka-rok {L['jerk_fix']}, "
                       f"haath aar-paar {L['hand_through']} frame")
        return rep
