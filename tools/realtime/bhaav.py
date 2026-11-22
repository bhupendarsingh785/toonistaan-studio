"""
Bhaav — line me kaun sa bhaav CHAHIYE, kitna AAYA, aur kis SHABD par kitna zor/lambai/sur/ruka — phir sudhaar aur seekhna.

1. Lakshya (text se): bhaav + kitna (0–100%) + zor wale shabd aur unka lakshya
     srot: line ka 'emotion' field, bhaav-shabd, vismayadi (अरे, वाह, हाय), tez-karne-wale (बहुत, बिल्कुल), ! ? …
2. Maap (audio se), kirdaar ki SAAMANYA awaaz ke mukable:
     sur (f0), sur ka phailav (range), raftaar, zor, chamak, aakhri sur (utaar/chadhav), ruke
   -> har bhaav ki signature se milaan -> "mila: dukh 35%"  (cosine = kism sahi?, projection = kitna)
3. Shabd-war: har shabd ki lambai (apni ummeed se guna), sur-shikhar, zor, pehle/baad ka ruka
   (ASR ke word timestamps ho to unse; warna laghu-guru matra se baant kar, awaaz ke gaddhon par set)
4. Sudhaar: line par (sur, raftaar, zor, chamak) + shabd par "tarashna" (lamba, ooncha, tez) -> phir naapo
5. Seekhna (knowledge/bhaav-yaad.json): is engine/awaaz/bhaav ke liye kaunse param kaam aaye ->
   agli baar render se PEHLE wahi; kaun sa bhaav baar-baar kam padta hai; insaan ki raay (sahi/kam/zyada) se calibration.
"""
from __future__ import annotations
import json, math, re, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
KN = HERE.parent.parent / "knowledge"
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import akshar as A

_R = {}
def rules():
    if "r" not in _R: _R["r"] = json.load(open(KN / "bhaav-rules.json", encoding="utf-8"))
    return _R["r"]

_L = "\u0900-\u0963\u0966-\u097F"   # Devanagari akshar (। ॥ shabd ka hissa nahi)
def _has(text, w):
    """Poora shabd ('रो' != 'रोज़'); jad ke liye ant me '*' ('हँस*' = हँसा, हँसते...)."""
    stem = w.endswith("*"); w = w.rstrip("*")
    return re.search(rf"(?<![{_L}]){re.escape(w)}" + ("" if stem else rf"(?![{_L}])"), text) is not None

# ---------------------------------------------------------------- 1. lakshya (text)
def target(line, context=None):
    """Lakshya bhaav — gehri samajh (v2).

    Kaise: (1) shabd ka wazan (vismayadi > bhaav-shabd > tez-karne-wala > punctuation),
           (2) line ka 'emotion' field (sabse bada wazan),
           (3) punh-raavriti (ek hi bhaav-shabd do baar = zyada),
           (4) sawaal/chidev (! ? …), (5) pichhli line ka bhaav (context),
           (6) kirdaar ka swabhav (dadi -> pyaar, bachcha -> hairani).
    Lautata hai: emotion, intensity (0–1), mixed (top-2 hissa), emphasis (shabd-war target), arc.
    """
    R = rules(); text = line.get("text", "")
    W = {"interjection": 2.0, "bhaav": 1.5, "intensifier": 0.5, "punct": 0.3}
    score = {e: 0.0 for e in R["signature"]}
    hit = {e: [] for e in R["signature"]}

    for e, ws in R["words"].items():
        for w in ws:
            w2 = w.rstrip("!").rstrip("*")
            if not w2:
                continue
            n = len(re.findall(rf"(?<![{_L}]){re.escape(w2)}", text))
            if n:
                score[e] += W["bhaav"] * min(2, n)          # punh-raavriti par zyada
                hit[e].append(w2)

    for w in R["interjections"]:
        if _has(text, w):
            for e, ws in R["words"].items():
                if w in ws:
                    score[e] += W["interjection"]
    for w in R["intensifiers"]:
        if _has(text, w.split()[0]):
            for e in score:
                score[e] += W["intensifier"] * 0.25
    # chidev
    score["gussa"] += W["punct"] * text.count("!")
    score["hairani"] += W["punct"] * (text.count("?") * 1.5)
    score["dukh"] += W["punct"] * text.count("…")

    # line ka field
    emo = line.get("emotion") or line.get("bhaav")
    if emo in score:
        score[emo] += 3.0

    # kirdaar ka swabhav (halka)
    who = (line.get("who") or "").lower()
    bias = {"dadi": {"pyaar": 0.9}, "maa": {"pyaar": 0.8}, "sonu": {"hairani": 0.7, "khushi": 0.4}}
    for e, b in bias.get(who, {}).items():
        if e in score:
            score[e] += b

    # pichhli line ka bhaav (context) — thoda sa
    if context:
        prev = context.get("emotion")
        if prev in score and score.get(prev, 0) > 0:
            score[prev] += 0.4

    tot = sum(score.values())
    best = max(score, key=score.get) if tot > 0 else "neutral"
    if score.get(best, 0) <= 0:
        best = "neutral"

    # intensity: saturating (0.25 se 1.0), punctuation/emphasis se boost
    if best == "neutral":
        inten = 0.0
    else:
        raw = score[best]
        inten = 1.0 - math.exp(-0.55 * raw)
        inten += 0.10 * min(2, text.count("!")) + 0.04 * min(3, text.count("?"))
        if "…" in text or "..." in text:
            inten += 0.05 if best in ("dukh", "dar") else 0
        inten = max(0.25, min(1.0, line.get("intensity", inten)))

    # mixed (top-2 hissa) — "pyaar 60% + khushi 40%" jaisa sach
    ranked = sorted(((e, v) for e, v in score.items() if v > 0), key=lambda kv: -kv[1])[:2]
    s2 = sum(v for _, v in ranked) or 1.0
    mixed = [{"emotion": e, "share": round(v / s2, 2)} for e, v in ranked]

    # shabd-war zor
    emph = []
    raw_words = [w.strip("।,.!?\"'…") for w in text.split()]
    for wi, w in enumerate(raw_words):
        why = None
        if not w:
            continue
        if any(_has(w, x.rstrip("!")) for x in R["interjections"]):
            why = "interjection"
        elif any(_has(w, x.split()[0]) for x in R["intensifiers"]):
            why = "intensifier"
        elif best != "neutral" and w in hit.get(best, []):
            why = "bhaav-shabd"
        elif wi + 1 < len(raw_words) and wi < len(text.split()) and text.split()[wi].endswith("!") and best != "neutral":
            why = "! se pehle"
        if why:
            T = dict(R["word_target"].get("interjection" if why == "interjection" else best, R["word_target"]["default"]))
            k = max(inten, 0.5)
            emph.append({"word": w, "i": wi, "why": why,
                         "len": round(1 + (T.get("len", 1) - 1) * k, 2),
                         "f0": round(T.get("f0", 0) * k, 1),
                         "energy": round(T.get("energy", 0) * k, 1),
                         "pause_ms": int(T.get("pause_ms", 0) * k),
                         "pause_after_ms": int(T.get("pause_after_ms", 0) * k)})
    # arc: line ke andar bhaav ka utaar-chadhav (! end me = chadhav)
    arc = "chadhav" if text.rstrip().endswith(("!", "?")) else ("utar" if best in ("dukh", "pyaar") else "flat")
    return {"emotion": best, "intensity": round(inten, 2), "mixed": mixed,
            "emphasis": emph, "arc": arc, "score": {k: round(v, 2) for k, v in score.items() if v}}


# ---------------------------------------------------------------- 2. maap (audio)
def prosody(y, sr):
    import librosa
    yt, idx = librosa.effects.trim(y, top_db=35)
    if len(yt) < 2048: yt = np.pad(yt, (0, 2048 - len(yt)))
    hop = 256
    f0 = librosa.yin(yt, fmin=70, fmax=500, sr=sr, frame_length=1024, hop_length=hop)
    rms = librosa.feature.rms(y=yt, frame_length=1024, hop_length=hop)[0]
    n = min(len(f0), len(rms)); f0, rms = f0[:n], rms[:n]
    speech = rms > rms.max() * 0.1
    voiced = speech & (f0 > 70) & (f0 < 500)
    st = 12 * np.log2(np.maximum(f0, 1) / 100.0)
    if voiced.sum() > 5:                   # poore shabd ki octave-galti: line ke beech se 9 st door = ek octave sudhaar
        gm = np.median(st[voiced])
        st = np.where(voiced & (st - gm > 9), st - 12, st); st = np.where(voiced & (gm - st > 9), st + 12, st)
    vs = st[voiced] if voiced.any() else np.array([0.0])
    if len(vs) > 9:                        # octave-galti hatao: median filter, achaanak >5 st chhalaang wale frame chhodo
        from scipy.signal import medfilt
        med = medfilt(vs, 9); good = np.abs(vs - med) < 5
        idx_v = np.flatnonzero(voiced); bad = idx_v[~good]; voiced = voiced.copy(); voiced[bad] = False
        st = st.copy(); st[bad] = -99.0        # shabd-naap me bhi yeh frame na gine jaayein
        vs = vs[good] if good.sum() > 5 else vs
    k = max(1, int(len(vs) * 0.3))
    end = float(np.median(vs[-k:]) - np.median(vs[:-k])) if len(vs) > 3 else 0.0
    cen = librosa.feature.spectral_centroid(y=yt, sr=sr, hop_length=hop)[0][:n]
    loud = 20 * np.log10(np.sqrt(np.mean(yt[np.abs(yt) > 1e-4] ** 2)) + 1e-9)
    st[~voiced] = -99.0
    return {"f0": float(np.median(vs)), "range": float(np.percentile(vs, 85) - np.percentile(vs, 15)),
            "energy": float(loud), "bright": float(np.mean(cen[speech]) if speech.any() else np.mean(cen)),
            "end": end, "pause": float(1 - speech.mean()), "speech_s": float(speech.sum() * hop / sr),
            "_f0_st": st.tolist(), "_rms": rms.tolist(), "_hop": hop, "_trim0": int(idx[0])}

def deviation(p, base, units):
    """Saamanya (neutral) se fark — rules ke dims me."""
    rate = units / max(p["speech_s"], 0.2)
    return {"f0": p["f0"] - base["f0"], "range": p["range"] - base["range"], "rate": math.log(rate / base["rate"]),
            "energy": p["energy"] - base["energy"], "bright": math.log(p["bright"] / base["bright"]),
            "end": p["end"] - base["end"], "pause": p["pause"] - base["pause"]}

def estimate(dev, calib=None, noise=None):
    """Kaun sa bhaav (kism = cosine, sabse milti disha), kitna (projection: signature ka kitna %).
    noise: saamanya awaaz ka apna utaar-chadhav (std) — usse kam fark ko bhaav mat samjho."""
    R = rules(); dims = R["dims"]; calib = calib or {}
    S = {k: max(R["scale"][k], 1.5 * (noise or {}).get(k, 0.0)) for k in dims}
    d = np.clip(np.array([dev[k] / S[k] for k in dims]), -3, 3); out = {}   # ek naap poora nateeja na bigaade
    for e, sig in R["signature"].items():
        s = np.array([sig[k] / S[k] for k in dims])
        cos = float(d @ s / (np.linalg.norm(d) * np.linalg.norm(s) + 1e-9))
        frac = float(d @ s / (s @ s)) * calib.get(e, 1.0)
        out[e] = {"cos": round(cos, 3), "frac": round(frac, 3)}
    mag = float(np.linalg.norm(d))
    cand = [(v["cos"], e) for e, v in out.items() if v["cos"] > R["tolerance"]["min_cos"] and v["frac"] > 0.2]
    top = max(cand)[1] if cand and mag > 1.0 else "neutral"
    return {"top": top, "top_frac": out[top]["frac"] if top != "neutral" else 0.0, "all": out, "magnitude": round(mag, 2)}

# ---------------------------------------------------------------- 3. shabd-war
def word_spans(y, sr, text, pros, asr_words=None):
    """Shabdon ki seema: ASR timestamps ho to woh; warna laghu-guru matra se baant kar awaaz ke gaddhon par khiska do."""
    raw = [w.strip("।,.!?\"'…") for w in text.split()]; raw = [w for w in raw if w]
    if asr_words and len(asr_words) == len(raw) and all(w.get("end", 0) > 0 for w in asr_words):
        return [(w, a["start"], a["end"]) for w, a in zip(raw, asr_words)]
    hop = pros["_hop"]; rms = np.array(pros["_rms"]); t0 = pros["_trim0"] / sr
    sp = np.flatnonzero(rms > rms.max() * 0.1)
    if not len(sp): return []
    a, b = sp[0], sp[-1] + 1
    units = [max(1, A.matra_units(w)) + 0.5 for w in raw]       # +0.5 = shabd ke beech ka halka ruka
    cum = np.cumsum([0] + units) / sum(units)
    edges = [a + int(c * (b - a)) for c in cum]
    win = max(2, int(0.08 * sr / hop))
    for k in range(1, len(edges) - 1):                           # najdeeki gaddha (energy dip)
        lo, hi = max(edges[k - 1] + 2, edges[k] - win), min(edges[k + 1] - 2, edges[k] + win)
        if hi > lo: edges[k] = lo + int(np.argmin(rms[lo:hi]))
    return [(w, t0 + edges[k] * hop / sr, t0 + edges[k + 1] * hop / sr) for k, w in enumerate(raw)]

def word_measure(y, sr, text, pros, spans, rate_base, emph=None):
    """Har shabd: lambai (apni matra-ummeed se guna), sur-shikhar aur zor — BAAKI SHABDON ke beech (median) se."""
    st = np.array(pros["_f0_st"]); rms = np.array(pros["_rms"]); hop = pros["_hop"]; t0 = pros["_trim0"] / sr
    thr = rms.max() * 0.1; raw = []; prev_end = None
    for w, s, e in spans:
        i0 = int((s - t0) * sr / hop); i1 = max(i0 + 1, int((e - t0) * sr / hop))
        seg_st, seg_rms = st[i0:i1], rms[i0:i1]
        voiced = seg_st[(seg_rms > thr) & (seg_st > -20) & (seg_st < 40)]
        loud = seg_rms[seg_rms > thr]
        raw.append({"word": w, "start": round(s, 3), "end": round(e, 3),
                    "len": round((e - s) / (max(1, A.matra_units(w)) / rate_base), 2),
                    "_f0": float(np.percentile(voiced, 90)) if len(voiced) else None,
                    "_db": float(20 * np.log10(np.percentile(loud, 90) + 1e-9)) if len(loud) else None,
                    "gap_before_ms": int(max(0, (s - prev_end)) * 1000) if prev_end is not None else 0})
        prev_end = e
    emph = emph or set(); ref = [r for r in raw if r["word"] not in emph] or raw   # saadharan shabd hi pemaana
    f_med = np.median([r["_f0"] for r in ref if r["_f0"] is not None] or [0])
    d_med = np.median([r["_db"] for r in ref if r["_db"] is not None] or [0])
    for r in raw:
        r["f0"] = round(r.pop("_f0") - f_med, 1) if r["_f0"] is not None else (r.pop("_f0") or 0.0)
        r["energy"] = round(r.pop("_db") - d_med, 1) if r["_db"] is not None else (r.pop("_db") or 0.0)
    return raw

def judge_words(targets, measured):
    """Zor wale shabdon ka lakshya vs mila. Returns list with kami (shortfall)."""
    R = rules(); res = []
    for t in targets:
        m = next((x for x in measured if x["word"] == t["word"]), None)
        if not m: continue
        need = {"len": t["len"] - 1, "f0": t["f0"], "energy": t["energy"]}
        got = {"len": m["len"] - 1, "f0": m["f0"], "energy": m["energy"]}
        fr = {k: (got[k] / need[k] if abs(need[k]) > 0.05 else 1.0) for k in need}
        ok = all(v >= R["tolerance"]["word_min_frac"] for v in fr.values())
        res.append({"word": t["word"], "why": t["why"], "need": t, "got": m, "frac": {k: round(v, 2) for k, v in fr.items()}, "ok": ok})
    return res

# ---------------------------------------------------------------- 4. sudhaar
def correction(tgt, est, dev, damp=0.8):
    """Lakshya signature x kitna  -  jo mila  ->  param badlaav (line par)."""
    R = rules()
    if tgt["emotion"] == "neutral":
        want = {k: 0.0 for k in R["dims"]}
    else:
        sig = R["signature"][tgt["emotion"]]; want = {k: sig[k] * tgt["intensity"] for k in R["dims"]}
    miss = {k: want[k] - dev[k] for k in R["dims"]}
    k = damp                               # pehli koshish 0.8, baad me 0.5 (jhoolna band)
    return {"pitch_st": round(k * miss["f0"], 2), "rate": round(math.exp(k * miss["rate"]), 3),
            "gain_db": round(k * miss["energy"], 2), "presence_db": round(k * miss["bright"] * 25, 2),
            "range_boost": round(0.75 * k * miss["range"], 2), "end_st": round(0.75 * k * miss["end"], 2)}, miss

def sculpt(y, sr, spans, plan):
    """Shabd tarashna: [(start,end,len_x,f0_st,gain_db,pause_ms)] — chuna hua shabd lamba/ooncha/tez, 15 ms crossfade."""
    import librosa
    out, last, fade = [], 0, int(0.015 * sr)
    for (s, e, lx, st, g, pms) in sorted(plan):
        i0, i1 = int(s * sr), int(e * sr)
        if i1 - i0 < int(0.06 * sr) or i0 < last: continue
        out.append(y[last:i0])
        if pms > 0: out.append(np.zeros(int(pms / 1000 * sr)))
        seg = y[i0:i1].astype(np.float32); r0 = np.sqrt(np.mean(seg ** 2)) + 1e-12
        if abs(lx - 1) > 0.03: seg = librosa.effects.time_stretch(seg, rate=1 / lx)
        if abs(st) > 0.1: seg = librosa.effects.pitch_shift(seg, sr=sr, n_steps=st)
        seg = seg.astype(np.float64); seg *= r0 / (np.sqrt(np.mean(seg ** 2)) + 1e-12)   # level wapas, phir zor
        seg = seg * 10 ** (g / 20)
        k = min(fade, len(seg) // 4)
        if k: seg[:k] *= np.linspace(0, 1, k); seg[-k:] *= np.linspace(1, 0, k)
        out.append(seg); last = i1
    out.append(y[last:])
    return np.concatenate(out)

def end_contour(y, sr, spans, st):
    """Aakhri shabd ka sur badlo (sawaal/hairani = upar, dukh/gussa = neeche)."""
    if not spans or abs(st) < 0.2: return y
    w, s, e = spans[-1]
    return sculpt(y, sr, spans, [(s, e, 1.0, st, 0.0, 0)])

# ---------------------------------------------------------------- 5. yaad (seekhna)
class BhaavYaad:
    def __init__(self, path=KN / "bhaav-yaad.json"):
        self.path = Path(path)
        self.d = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"voices": {}, "neutral": {}, "calib": {}}
    def ev(self, ev): return self.d["voices"].setdefault(ev, {})
    def start_params(self, ev, emo, inten):
        """Pehle-se-bhaav: is awaaz/bhaav ke liye jo param pehle kaam aaye (intensity ke anupaat me)."""
        m = self.ev(ev).get(emo)
        if not m or m.get("n", 0) < 1: return {}          # sirf 'kam pada' darj hai, koi jeeta hua param nahi
        k = inten / max(m["inten"], 0.1)
        return {"pitch_st": round(m["pitch_st"] * k, 2), "rate": round(math.exp(math.log(m["rate"]) * k), 3),
                "gain_db": round(m["gain_db"] * k, 2), "presence_db": round(m["presence_db"] * k, 2),
                "range_boost": round(m.get("range_boost", 0) * k, 2), "end_st": round(m.get("end_st", 0) * k, 2)}
    def learn(self, ev, emo, inten, params, achieved):
        M = self.ev(ev).setdefault(emo, {"n": 0, "inten": inten, "pitch_st": 0, "rate": 1.0, "gain_db": 0, "presence_db": 0,
                                         "range_boost": 0, "end_st": 0, "achieved": [], "short": 0})
        a = 1 / (M["n"] + 1)
        scale = M["inten"] / max(inten, 0.1)                 # sab ko seekhi hui intensity par laao
        for k in ("pitch_st", "gain_db", "presence_db", "range_boost", "end_st"):
            M[k] = round((1 - a) * M.get(k, 0.0) + a * params.get(k, 0) * scale, 3)
        M["rate"] = round(math.exp((1 - a) * math.log(M["rate"]) + a * math.log(params.get("rate", 1.0)) * scale), 3)
        M["n"] += 1; M["achieved"] = (M["achieved"] + [round(achieved, 2)])[-30:]
    def note_short(self, ev, emo):
        M = self.ev(ev).setdefault(emo, {"n": 0, "inten": 0.7, "pitch_st": 0, "rate": 1.0, "gain_db": 0, "presence_db": 0,
                                         "range_boost": 0, "end_st": 0, "achieved": [], "short": 0})
        M["short"] = M.get("short", 0) + 1
    def neutral(self, ev): return self.d["neutral"].get(ev)
    def update_neutral(self, ev, p, units):
        rate = units / max(p["speech_s"], 0.2); N = self.d["neutral"].get(ev)
        cur = {"f0": p["f0"], "range": p["range"], "rate": rate, "energy": p["energy"], "bright": p["bright"], "end": p["end"], "pause": p["pause"], "n": 1}
        if not N: cur["var"] = {k: 0.0 for k in ("f0", "range", "rate", "energy", "bright", "end", "pause")}; self.d["neutral"][ev] = cur; return
        a = 1 / min(N["n"] + 1, 20); V = N.setdefault("var", {})
        for k in ("f0", "range", "rate", "energy", "bright", "end", "pause"):
            old = N[k]; N[k] = (1 - a) * N[k] + a * cur[k]
            dv = (cur[k] - old) if k != "rate" else math.log(cur[k] / old)
            if k == "bright": dv = math.log(cur[k] / old)
            V[k] = (1 - a) * V.get(k, 0.0) + a * dv * dv      # saamanya utaar-chadhav (variance)
        N["n"] += 1
    def noise(self, ev):
        N = self.d["neutral"].get(ev)
        return {k: math.sqrt(v) for k, v in (N or {}).get("var", {}).items()} if N and N.get("n", 0) >= 4 else {}
    def feedback(self, ev, emo, verdict):
        """Insaan ki raay: 'kam' = system zyada bata raha tha -> calibration ghatao; 'zyada' = ulta."""
        C = self.d["calib"].setdefault(ev, {}); c = C.get(emo, 1.0)
        C[emo] = round(c * (0.9 if verdict == "kam" else 1.1 if verdict == "zyada" else 1.0), 3)
    def calib(self, ev): return self.d["calib"].get(ev, {})
    def save(self): self.path.write_text(json.dumps(self.d, ensure_ascii=False, indent=1), encoding="utf-8")

def analyse(y, sr, line, base, calib=None, asr_words=None, noise=None):
    """Poori bhaav jaanch ek line ki."""
    R = rules(); tgt = target(line); units = A.matra_units(line["text"])
    p = prosody(y, sr)
    if not base: return {"target": tgt, "ready": False, "pros": p}
    dev = deviation(p, base, units); est = estimate(dev, calib, noise)
    T = R["tolerance"]
    if tgt["emotion"] == "neutral":
        frac = 1.0; ok = est["top"] == "neutral" or est["top_frac"] < 0.45
    else:
        e = est["all"][tgt["emotion"]]; frac = e["frac"] / max(tgt["intensity"], 0.1)
        ok = (T["min_frac"] <= frac <= T["max_frac"]) and e["cos"] >= T["min_cos"]
    rate_base = base["rate"] * math.exp(dev["rate"])
    spans = word_spans(y, sr, line["text"], p, asr_words)
    wm = word_measure(y, sr, line["text"], p, spans, rate_base, {e["word"] for e in tgt["emphasis"]}) if spans else []
    wj = judge_words(tgt["emphasis"], wm)
    return {"target": tgt, "ready": True, "dev": {k: round(v, 3) for k, v in dev.items()}, "est": est,
            "frac": round(frac, 2), "ok": bool(ok), "words": wm, "word_judge": wj, "spans": spans, "pros": p,
            "words_ok": all(w["ok"] for w in wj)}

def describe(b):
    """Insaan ke padhne layak ek line."""
    R = rules(); N = R["names"]; t = b["target"]
    if not b.get("ready"): return f"chahiye {N.get(t['emotion'])} {int(t['intensity'] * 100)}% · (saamanya awaaz abhi seekh raha)"
    e = b["est"]
    s = f"chahiye {N.get(t['emotion'])} {int(t['intensity'] * 100)}% · mila {N.get(e['top'])} {int(e['top_frac'] * 100)}%"
    if t["emotion"] != "neutral":
        te = e["all"][t["emotion"]]
        if e["top"] != t["emotion"]: s += f", {N.get(t['emotion'])} {int(te['frac'] * 100)}%"
        s += f" → lakshya ka {int(b['frac'] * 100)}%{' (kam)' if b['frac'] < R['tolerance']['min_frac'] else ' (zyada)' if b['frac'] > R['tolerance']['max_frac'] else ''}"
    return s

# ---------------------------------------------------------------- insaan ki raay (CLI)
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Bhaav par apni raay do — system usse apna naap theek karta hai")
    ap.add_argument("--report", required=True, help="live.py ka out .json")
    ap.add_argument("--line", type=int, required=True, help="line number (1 se)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--kam", action="store_true", help="sunne me bhaav KAM laga (system zyada bata raha tha)")
    g.add_argument("--zyada", action="store_true", help="sunne me bhaav ZYADA laga")
    g.add_argument("--sahi", action="store_true", help="bilkul sahi laga")
    ap.add_argument("--engine", default=None)
    a = ap.parse_args()
    rep = json.load(open(a.report, encoding="utf-8")); r = next(x for x in rep["lines"] if x["i"] == a.line - 1)
    eng = a.engine or rep["summary"]["engine"]; ev = f"{eng}/{r['who']}"
    emo = (r.get("bhaav_final") or r.get("bhaav_first") or {}).get("target", {}).get("emotion", "neutral")
    Y = BhaavYaad(); verdict = "kam" if a.kam else "zyada" if a.zyada else "sahi"
    Y.feedback(ev, emo, verdict)
    if verdict == "kam":                   # agli baar shuruaati param thode tez
        m = Y.ev(ev).get(emo)
        if m: m["inten"] = round(m["inten"] * 0.9, 3)
    elif verdict == "zyada":
        m = Y.ev(ev).get(emo)
        if m: m["inten"] = round(m["inten"] * 1.1, 3)
    Y.save()
    print(f"raay darj: {ev} · {rules()['names'].get(emo)} · '{verdict}' → calibration {Y.calib(ev).get(emo, 1.0)}")
