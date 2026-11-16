#!/usr/bin/env python3
"""Toonistaan Image Checker: tasveeron ki mashini jaanch (bina internet, OpenCV + YuNet face model).
python check_images.py <images_dir> [episode.json] [--out report.json]
Jaanch: dhundhlapan, roshni, contrast, saada/khaali background, chehre (ginti, saaf, aankh-naak-munh ki jagah),
script se logon ki ginti (scene "people": N), lagatar do scene ek jaise. Har image: PASS / FIX + kaaran.
Saath mein <dir>/_check_sheet.jpg banti hai (chehron par dabbe) taaki aankh se bhi jaancha jaa sake.
Haath/ungliyan aur kahani ka mel mashin nahi pakad sakti: woh skill ke checklist se aankh se jaancho."""
import sys, os, json, glob
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import body_check  # poori body + haath tracking
except Exception as e:  # models na hon to bhi baaki jaanch chale
    body_check = None; print("body tracking band:", e)

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
D = args[0]
EP = args[1] if len(args) > 1 and args[1].endswith(".json") else None
OUT = args[args.index("--out") + 1] if "--out" in args else os.path.join(D, "_check_report.json")
scenes = {}
if EP:
    for s in json.load(open(EP, encoding="utf-8"))["scenes"]:
        scenes[s["id"]] = s

det = cv2.FaceDetectorYN.create(os.path.join(HERE, "models", "yunet.onnx"), "", (320, 320), 0.75, 0.3, 50)

def ahash(g):
    s = cv2.resize(g, (16, 9)); return (s > s.mean()).flatten()

files = sorted(f for f in glob.glob(os.path.join(D, "*.jpg")) if not os.path.basename(f).startswith("_"))
report, prev_hash, thumbs = [], None, []
for f in files:
    name = os.path.splitext(os.path.basename(f))[0]; sid = name.split("_v")[0]
    sc = scenes.get(sid, {})
    img = cv2.imread(f); h0, w0 = img.shape[:2]
    # Pollinations kona watermark ignore (story_video crop karta hai)
    img = img[int(h0 * .02):int(h0 * .94), int(w0 * .02):int(w0 * .94)]
    im = img if img.shape[1] <= 1280 else cv2.resize(img, (1280, int(1280 * img.shape[0] / img.shape[1])))  # asli size par hi jaancho
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); H, W = g.shape
    issues, warn = [], []
    L = cv2.Laplacian(g, cv2.CV_64F)
    # sabse saaf hisse ka sharpness (90th percentile tile): aasmaan/bokeh wale smooth scene galat FIX na hon
    th, tw = H // 6, W // 8
    sharp = float(np.percentile([L[y:y + th, x:x + tw].var() for y in range(0, H - th + 1, th) for x in range(0, W - tw + 1, tw)], 90))
    bright, contrast = float(g.mean()), float(g.std())
    night = any(k in (sc.get("img", "") + name).lower() for k in ("night", "storm", "dark"))
    if w0 < 960: issues.append(f"chhoti image {w0}x{h0}")
    sk = 0.45 if night else 1.0  # raat ke scene naram hote (16 Nov calibration: ep03 sab sahi par FIX aa rahe the)
    if sharp < 25 * sk: issues.append(f"dhundhli (sharpness {sharp:.0f})")
    elif sharp < 60 * sk: warn.append(f"thodi naram (sharpness {sharp:.0f})")
    if bright < (18 if night else 40): issues.append(f"bahut andhera ({bright:.0f})")
    if bright > 225: issues.append(f"bahut ujli/safed ({bright:.0f})")
    if contrast < (14 if night else 22): issues.append(f"phiki, contrast kam ({contrast:.0f})")
    # saada background: upar ke 40% hisse mein texture
    edges = cv2.Canny(g, 60, 140)
    top = edges[: int(H * .4)].mean() / 255; sat = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)[..., 1].mean()
    if top < 0.012 and sat < 60: issues.append("background saada/khaali (studio deewar jaisa); jagah prompt mein pehle likho")
    # chehre
    det.setInputSize((W, H)); _, faces = det.detect(im)
    faces = [] if faces is None else faces
    fz = []
    for fc in faces:
        x, y, fw, fh = fc[:4].astype(int); lm = fc[4:14].reshape(5, 2); conf = float(fc[14])
        reye, leye, nose, rm, lmo = lm
        roi = g[max(0, y):y + fh, max(0, x):x + fw]
        fs = cv2.Laplacian(roi, cv2.CV_64F).var() if roi.size else 0
        eye_d = np.linalg.norm(leye - reye) + 1e-6
        tilt = abs(np.degrees(np.arctan2(leye[1] - reye[1], leye[0] - reye[0])))
        tilt = min(tilt, 180 - tilt)
        nose_mid = abs(nose[0] - (reye[0] + leye[0]) / 2) / eye_d
        order_ok = (nose[1] > min(reye[1], leye[1])) and ((rm[1] + lmo[1]) / 2 > nose[1])
        rec = {"box": [int(x), int(y), int(fw), int(fh)], "conf": round(conf, 2), "sharp": round(fs, 1)}
        big = fh > H * 0.12
        if big and fs < 20 * sk: issues.append(f"chehra dhundhla (face sharp {fs:.0f})")
        if big and not order_ok: issues.append("chehra bigda: aankh-naak-munh ki jagah galat")
        if big and nose_mid > 0.55 and tilt < 25: warn.append("naak beech mein nahi (tircha chehra ya bigda)")
        if big and tilt > 35: warn.append(f"chehra bahut tircha ({tilt:.0f} deg)")
        fz.append(rec)
    body = body_check.analyse(im) if body_check else {"people": [], "hands": [], "issues": [], "warnings": []}
    issues += body["issues"]; warn += body["warnings"]
    npeople = max(len(fz), len(body["people"]))
    need = sc.get("people")
    if need is not None:
        if need == 0 and npeople > 0: issues.append(f"script mein koi insaan nahi, par {npeople} dikh rahe")
        elif need and len(fz) < need: warn.append(f"script {need} log, saaf chehre sirf {len(fz)} (door/peeche ho sakte, aankh se dekho)")
        elif need and npeople > need + 1: issues.append(f"faltu log: script {need}, dikh rahe {npeople}")
    hsh = ahash(g)
    if prev_hash is not None and (hsh == prev_hash).mean() > 0.93: warn.append("pichhli image se lagbhag same")
    prev_hash = hsh
    verdict = "FIX" if issues else ("CHECK" if warn else "PASS")
    report.append({"image": name, "verdict": verdict, "issues": issues, "warnings": warn,
                   "sharpness": round(sharp, 1), "brightness": round(bright), "contrast": round(contrast),
                   "faces": fz, "people_tracked": len(body["people"]), "hands_tracked": len(body["hands"])})
    t = im.copy()
    if body_check: body_check.draw(t, body)
    for fc in fz:
        x, y, fw, fh = fc["box"]; cv2.rectangle(t, (x, y), (x + fw, y + fh), (0, 255, 255), 3)
    col = {"PASS": (60, 200, 60), "CHECK": (0, 200, 255), "FIX": (0, 0, 255)}[verdict]
    cv2.rectangle(t, (0, 0), (W, 46), (0, 0, 0), -1); cv2.putText(t, f"{name} {verdict}", (10, 34), 0, 1.1, col, 2)
    thumbs.append(cv2.resize(t, (480, 270)))

if thumbs:
    cols = 3; rows = (len(thumbs) + cols - 1) // cols
    sheet = np.zeros((rows * 270, cols * 480, 3), np.uint8)
    for i, t in enumerate(thumbs): sheet[(i // cols) * 270:(i // cols + 1) * 270, (i % cols) * 480:(i % cols + 1) * 480] = t
    cv2.imwrite(os.path.join(D, "_check_sheet.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
json.dump(report, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
fix = [r["image"] for r in report if r["verdict"] == "FIX"]
for r in report:
    print(f"{r['image']:8s} {r['verdict']:5s} " + "; ".join(r["issues"] + r["warnings"]))
print(f"\nPASS {sum(r['verdict']=='PASS' for r in report)} | CHECK {sum(r['verdict']=='CHECK' for r in report)} | FIX {len(fix)}")
print("FIX_LIST=" + ",".join(sorted({x.split('_v')[0] for x in fix})))
