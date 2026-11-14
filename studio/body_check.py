"""Poori body aur haath ki tracking (free, offline: OpenCV + MediaPipe ONNX models, opencv_zoo se).
check_images.py isse apne aap bulata hai. Akela chalana: python body_check.py image.jpg out.jpg
Har insaan: 33 body points (sir, kandhe, kohni, kalaai, kamar, ghutne, takhne) -> anupaat jaanch.
Har haath: 21 points -> ungliyon ki lambai ka anupaat jaanch."""
import os, sys
import numpy as np, cv2

M = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
sys.path.insert(0, M)
from mp_persondet import MPPersonDet  # noqa: E402
from mp_pose import MPPose  # noqa: E402
from mp_palmdet import MPPalmDet  # noqa: E402
from mp_handpose import MPHandPose  # noqa: E402

_pd = _pose = _palm = _hand = None


def _load():
    global _pd, _pose, _palm, _hand
    if _pd is None:
        _pd = MPPersonDet(os.path.join(M, "person_mp.onnx"), nmsThreshold=0.3, scoreThreshold=0.5, topK=50)
        _pose = MPPose(os.path.join(M, "pose_mp.onnx"), confThreshold=0.6)
        _palm = MPPalmDet(os.path.join(M, "palm_mp.onnx"), nmsThreshold=0.3, scoreThreshold=0.6, topK=20)
        _hand = MPHandPose(os.path.join(M, "hand_mp.onnx"), confThreshold=0.6)


BONES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24),
         (23, 25), (25, 27), (24, 26), (26, 28), (0, 11), (0, 12)]
HAND_BONES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11), (11, 12),
              (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)]


def _d(a, b): return float(np.linalg.norm(a[:2] - b[:2]))


def analyse(img):
    """returns dict(people=[...], hands=[...], issues=[], warnings=[])"""
    _load()
    H, W = img.shape[:2]
    out = {"people": [], "hands": [], "issues": [], "warnings": []}
    persons = _pd.infer(img)
    persons = [] if persons is None else persons
    for p in persons:
        r = _pose.infer(img, p)
        if r is None:
            continue
        lm = r[1][:33]  # x, y, z, visibility, presence
        # sirf woh point jo saaf dikh rahe (visibility + presence) aur frame ke andar hain
        inside = (lm[:, 0] > W * .03) & (lm[:, 0] < W * .97) & (lm[:, 1] > H * .03) & (lm[:, 1] < H * .97)
        vis = (lm[:, 4] > 0.9) & (lm[:, 3] > 0.8) & inside
        person = {"pts": lm[:, :2].tolist(), "vis": vis.tolist(), "conf": float(r[5])}
        out["people"].append(person)
        pres = (lm[:, 4] > 0.9) & inside
        size = max(np.ptp(lm[pres, 1]) if pres.sum() > 2 else 0, 1)
        if size < H * 0.2:  # door ka chhota insaan: anupaat bharosemand nahi
            continue

        def ratio(a, b, c, d_, lo, hi, msg, hard=True):
            if vis[a] and vis[b] and vis[c] and vis[d_]:
                x, y = _d(lm[a], lm[b]), _d(lm[c], lm[d_])
                if y > 2 and x > 2:
                    q = x / y
                    if not (lo <= q <= hi):
                        (out["issues"] if hard else out["warnings"]).append(f"{msg} (anupaat {q:.2f})")
        # frame ke andar, model ko yakeen hai hissa hai, par "dikh" nahi raha = dhaka hua ya bigda
        weak = [n for n, i in (("baayi kohni", 13), ("daayi kohni", 14), ("baaya ghutna", 25), ("daaya ghutna", 26),
                               ("baaya takhna", 27), ("daaya takhna", 28)) if inside[i] and lm[i, 4] > 0.9 and lm[i, 3] < 0.6]
        if weak and size > H * 0.4:
            out["warnings"].append("ye hisse saaf/sahi nahi lag rahe (dhake ya bigde): " + ", ".join(weak) + " -> aankh se dekho")
        # baanh: upar wala hissa vs neeche wala
        ratio(11, 13, 13, 15, 0.55, 1.8, "baayi baanh ajeeb lambi/chhoti")
        ratio(12, 14, 14, 16, 0.55, 1.8, "daayi baanh ajeeb lambi/chhoti")
        # taang: jaangh vs pindli
        ratio(23, 25, 25, 27, 0.6, 1.65, "baayi taang ajeeb")
        ratio(24, 26, 26, 28, 0.6, 1.65, "daayi taang ajeeb")
        # dono baanh / dono taang barabar (perspective ke liye dheel)
        ratio(11, 15, 12, 16, 0.45, 2.2, "dono baanh ki lambai bahut alag", hard=False)
        ratio(23, 27, 24, 28, 0.45, 2.2, "dono taang ki lambai bahut alag", hard=False)
        # kandhe vs kamar ki chaudai
        ratio(11, 12, 23, 24, 0.6, 3.2, "kandhe/kamar ka anupaat ajeeb", hard=False)
        # torso vs taang (jaangh)
        ratio(11, 23, 23, 25, 0.6, 2.8, "dhad aur taang ka anupaat ajeeb", hard=False)
        # sir: naak se kandhe ka beech vs kandhe ki chaudai
        if vis[0] and vis[11] and vis[12]:
            sw = _d(lm[11], lm[12]); nk = _d(lm[0], (lm[11] + lm[12]) / 2)
            if sw > 5 and not (0.25 <= nk / sw <= 2.2):
                out["warnings"].append(f"gardan/sir ka anupaat ajeeb ({nk / sw:.2f})")
    # haath
    palms = _palm.infer(img)
    palms = [] if palms is None else palms
    for pm in palms:
        h = _hand.infer(img, pm)
        if h is None:
            out["warnings"].append("haath mila par uske points saaf nahi (haath bigda ho sakta: aankh se dekho)")
            continue
        pts = h[4:67].reshape(21, 3); conf = float(h[131])
        out["hands"].append({"pts": pts[:, :2].tolist(), "conf": conf})
        palm = _d(pts[0], pts[9]) + 1e-6
        if palm < 12:  # bahut chhota haath: jaanch bharosemand nahi
            continue
        for name, (a, tip) in {"tarjani": (5, 8), "beech wali": (9, 12), "anamika": (13, 16), "chhoti": (17, 20)}.items():
            q = _d(pts[a], pts[tip]) / palm
            if q < 0.25 or q > 1.6:
                out["issues"].append(f"{name} ungli ki lambai ajeeb ({q:.2f})")
        if conf < 0.75:
            out["warnings"].append(f"haath ka bharosa kam ({conf:.2f}): ungliyan aankh se gino")
    return out


def draw(img, res):
    for p in res["people"]:
        pts = np.array(p["pts"]).astype(int); vis = p["vis"]
        for a, b in BONES:
            if vis[a] and vis[b]:
                cv2.line(img, tuple(pts[a]), tuple(pts[b]), (255, 200, 0), 3)
        for i in (0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28):
            if vis[i]:
                cv2.circle(img, tuple(pts[i]), 5, (0, 120, 255), -1)
    for hnd in res["hands"]:
        pts = np.array(hnd["pts"]).astype(int)
        for a, b in HAND_BONES:
            cv2.line(img, tuple(pts[a]), tuple(pts[b]), (255, 0, 255), 2)
    return img


if __name__ == "__main__":
    im = cv2.imread(sys.argv[1]); r = analyse(im)
    print("log:", len(r["people"]), "haath:", len(r["hands"]))
    for x in r["issues"]: print("FIX:", x)
    for x in r["warnings"]: print("CHECK:", x)
    if len(sys.argv) > 2: cv2.imwrite(sys.argv[2], draw(im, r))
