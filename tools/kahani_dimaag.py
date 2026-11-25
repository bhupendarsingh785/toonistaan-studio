#!/usr/bin/env python3
"""kahani_dimaag.py — ASTRA ka FAISLA lene wala dimaag + duniya ki asli awaaz.

cast_build.py (zero pipeline) har kirdaar ki awaaz banata hai. Ye uske upar baith kar
kahani padhta hai aur KHUD tay karta hai:
  • kaun bol raha hai (har kirdaar alag; naya kirdaar aaye to khud nayi awaaz, aur yaad rakhta hai)
  • kis bhaav me (gussa / dar / dheere / chillana / udaas / khushi / thakan)
  • kahan se (paas / door / bahut door / jhadi ke peeche / deewar ke peeche / phone / mann me, baayein/daayein)
  • peeche kya chale (raat, din, jungle, gaon, shahar, ghar, barish, nadi) + beech-beech me door ki awaazein
  • kaun si harkat ki awaaz (seedhi, kadam, darwaza, gaadi, jeev-jantu ...) — sirf vaachak ki baat se

  python tools/kahani_dimaag.py seekho                    library_awaaz/ ko scan karo
  python tools/kahani_dimaag.py library-badao 6           Freesound se asli recordings (free key)
  python tools/kahani_dimaag.py jaanch kahani.txt         faisle dikhao (awaaz nahi banti)
  python tools/kahani_dimaag.py kahani.txt out.mp3        poori audio-drama

Script: [दृश्य: जंगल, रात] | नाम (दूर से, चिल्लाकर): baat | ( आवाज़: दरवाज़ा बंद ) | bina naam = वाचक
Zero guard: sirf awaaz ka stem (out_voice.wav) alag likha jaata hai aur zero_baseline se naapa jaata hai.
Sikhana: knowledge/kahani_rules.json (shabd), knowledge/cast_auto.json (naye kirdaar) — code chhedna nahi.
"""
from __future__ import annotations
import json, os, random, re, sys, unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal as ss

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
RULES = ROOT / "knowledge" / "kahani_rules.json"
import astra_paths as _AP                                   # noqa: E402
CAST_AUTO = ROOT / "knowledge" / "cast_auto.json"
LIB = ROOT / "library_awaaz"
SR = 44100
AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac", ".aiff", ".aif", ".m4a"}
NARRATOR = "वाचक"
NARRATOR_NAMES = {"वाचक", "सूत्रधार", "कथावाचक", "narrator", "vachak"}


# ============================================================================ shabd pehchaan
def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = s.replace("़", "").replace("ँ", "ं").replace("‍", "").replace("‌", "")
    return unicodedata.normalize("NFC", s)


SUFFIXES = {"", "ा", "ी", "े", "ो", "ों", "ें", "ीं", "ं", "ई", "ए", "ओ", "ाई", "ाए", "ाया", "ायी", "ाने", "ाना",
            "ाती", "ाता", "ाते", "ाकर", "कर", "के", "की", "का", "ने", "ना", "नी", "ते", "ता", "ती", "ियां", "ियों",
            "ाएं", "ाओं", "a", "e", "i", "o", "s", "ne", "kar"}


def tokens(text: str):
    return [t for t in re.split(r"[\s,।\.!?\"'“”‘’:;\-–—()\[\]{}…]+", norm(text)) if t]


def has_word(toks, kw: str) -> bool:
    kt = tokens(kw)
    if not kt:
        return False
    for i in range(len(toks) - len(kt) + 1):
        if all(toks[i + j] == k or (toks[i + j].startswith(k) and toks[i + j][len(k):] in SUFFIXES)
               for j, k in enumerate(kt)):
            return True
    return False


def best_match(text, table, exclude=()):
    toks, best, bl = tokens(text), None, 0
    for name, spec in table.items():
        if name.startswith("_") or name in exclude:
            continue
        for w in spec.get("words", []):
            if len(w) > bl and has_word(toks, w):
                best, bl = name, len(w)
    return best


def all_matches(text, table):
    toks = tokens(text)
    return [n for n, s in table.items() if not n.startswith("_") and any(has_word(toks, w) for w in s.get("words", []))]


# ============================================================================ script
DIALOG_RE = re.compile(r"^\s*([^\s:()\[\]{}][^:()\[\]{}]{0,30}?)\s*(?:\(([^)]*)\))?\s*[:：]\s*(.+)$")
SFX_RE = re.compile(r"^\s*(?:\(\s*(?:sfx|आवाज़|आवाज|awaaz|awaz)\s*[:：]\s*(.+?)\s*\)|\{\s*(.+?)\s*\})\s*$", re.I)
SCENE_RE = re.compile(r"^\s*\[\s*(?:(?:दृश्य|scene|jagah|जगह)\s*[:：]?\s*)?(.+?)\s*\]\s*$", re.I)
SPEECH_VERBS = ("कहा", "बोला", "बोली", "पूछा", "पूछी", "बताया")


def parse_script(text):
    items = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = SCENE_RE.match(line)
        if m:
            items.append({"type": "scene", "text": m.group(1)}); continue
        m = SFX_RE.match(line)
        if m:
            items.append({"type": "sfx", "text": m.group(1) or m.group(2)}); continue
        m = DIALOG_RE.match(line)
        if m:
            name = m.group(1).strip()
            if len(name.split()) <= 3 and not any(v in name for v in SPEECH_VERBS):
                who = NARRATOR if norm(name) in {norm(n) for n in NARRATOR_NAMES} else name
                items.append({"type": "line", "who": who, "note": (m.group(2) or "").strip(), "text": m.group(3).strip()})
                continue
        items.append({"type": "line", "who": NARRATOR, "note": "", "text": line})
    return items


# ============================================================================ kirdaar (cast_build ke saath)
FEMALE_W = ["माँ", "मां", "बहन", "दीदी", "रानी", "चाची", "मौसी", "बुआ", "काकी", "लड़की", "औरत", "बेटी", "भाभी", "ताई", "राजकुमारी"]
OLD_F_W = ["दादी", "नानी", "बूढ़ी", "अम्मा"]
OLD_M_W = ["दादा", "नाना", "बाबा", "बूढ़ा", "काका", "ताऊ", "पंडित", "पुजारी"]
CHILD_W = ["बच्चा", "बच्ची", "मुन्ना", "मुन्नी", "छोटू", "गुड़िया", "चिंटू", "पिंकी"]
ANIMAL_W = ["भेड़िया", "शेर", "बंदर", "कौआ", "लोमड़ी", "भालू", "हाथी", "चूहा", "बिल्ली", "कुत्ता", "सियार", "तोता", "राक्षस", "भूत"]

# piper priyamvada (f, 207 Hz) / pratham (m, 97 Hz) par — zero ki 'mana' list ke andar (pitch < 1.5x)
POOL = {
    "stri":    [dict(engine="piper-f", pitch=1.06, tempo=1.02, tilt=0.5, breath=0.011, vib=0.16, form="preserved"),
                dict(engine="piper-f", pitch=0.90, tempo=0.95, tilt=-1.5, breath=0.013, vib=0.18, form="preserved"),
                dict(engine="piper-f", pitch=1.12, tempo=1.05, tilt=1.5, breath=0.010, vib=0.12, form="preserved")],
    "purush":  [dict(engine="piper-m", pitch=1.08, tempo=1.02, tilt=0.5, breath=0.012, vib=0.14, form="preserved"),
                dict(engine="piper-m", pitch=1.25, tempo=1.04, tilt=1.0, breath=0.012, vib=0.12, form="preserved"),
                dict(engine="piper-m", pitch=0.98, tempo=0.95, tilt=-1.5, breath=0.015, vib=0.16, form="preserved")],
    "bachcha": [dict(engine="piper-f", pitch=1.24, tempo=1.06, tilt=2.0, breath=0.012, vib=0.10, form="shifted"),
                dict(engine="piper-f", pitch=1.36, tempo=1.08, tilt=2.5, breath=0.012, vib=0.10, form="shifted")],
    "budha":   [dict(engine="piper-m", pitch=1.10, tempo=0.88, tilt=-2.5, breath=0.018, vib=0.24, form="preserved")],
    "budhi":   [dict(engine="piper-f", pitch=0.86, tempo=0.88, tilt=-2.5, breath=0.018, vib=0.26, form="preserved")],
    "janwar":  [dict(engine="piper-m", pitch=0.90, tempo=0.88, tilt=-3.0, breath=0.030, vib=0.30, form="preserved")],
}


def guess_ling(name):
    toks = tokens(name)
    has = lambda ws: any(has_word(toks, w) for w in ws)
    if has(ANIMAL_W): return "janwar"
    if has(OLD_F_W): return "budhi"
    if has(OLD_M_W): return "budha"
    if has(CHILD_W): return "bachcha"
    if has(FEMALE_W): return "stri"
    return "stri" if norm(name.split()[0]).endswith(("ी", "ा", "i", "a")) else "purush"


def load_cast():
    """cast_build.CAST + knowledge/cast_auto.json (pichli kahaniyon ke naye kirdaar)."""
    import cast_build as CB
    auto = _AP.read_json(CAST_AUTO)
    try:                                                   # asli awaazein (voices/bank) Piper se pehle
        import awaaz_bank as AB
        BANKV = AB.cast_entries()
    except Exception:
        BANKV = {}
    CB.CAST.update(BANKV)
    for k, v in auto.items():
        if k.startswith("_") or k in BANKV:
            continue
        if v.get("bank") in BANKV:
            CB.CAST[k] = dict(BANKV[v["bank"]])
        elif k not in CB.CAST:
            CB.CAST[k] = {x: v[x] for x in ("engine", "pitch", "tempo", "tilt", "breath", "vib", "form") if x in v}
    CB._BANK = BANKV
    return CB, auto


def ensure_character(CB, auto, who):
    if who in CB.CAST:
        return False
    ling = guess_ling(who)
    bank = getattr(CB, "_BANK", {})                        # pehle bank ki koi khaali asli awaaz (usi ling ki)
    used = {v.get("bank") for k, v in auto.items() if not k.startswith("_") and isinstance(v, dict)}
    used |= {c.get("bank") for k, c in CB.CAST.items() if k not in bank}      # doosre kirdaar ko mil chuki
    used |= getattr(CB, "_STORY_NAMES", set())                                # is kahani ka apna kirdaar hai
    ix = {}
    try:
        import awaaz_bank as AB
        ix = AB._index()
    except Exception:
        pass
    # pehle usi ling ki; na ho to sabse kareeb (bachcha -> kishor, budha -> aadmi, budhi -> aurat)
    tiers = [lambda k, v: v.get("ling") == ling]
    if ling == "bachcha":
        tiers.append(lambda k, v: ix.get(k, {}).get("umar", "").startswith("kishor"))
    tiers.append(lambda k, v: v.get("ling") == {"budha": "purush", "budhi": "stri", "janwar": "budha"}.get(ling))
    for ok in tiers:
        for bk, bv in bank.items():
            if bk not in used and ok(bk, bv):
                CB.CAST[who] = dict(bv)
                auto[who] = {"bank": bk, "ling": ling, "_note": f"asli awaaz '{bk}' (voices/bank) — badal sakte ho"}
                return True
    used = {(c["engine"], round(c["pitch"], 3), round(c["tempo"], 3)) for c in CB.CAST.values()}
    pool = POOL[ling]
    pick = next((dict(p) for p in pool if (p["engine"], round(p["pitch"], 3), round(p["tempo"], 3)) not in used), None)
    if pick is None:                                     # sab le liye: thoda alag sur
        pick = dict(pool[len(used) % len(pool)])
        pick["pitch"] = round(min(1.45, pick["pitch"] * (1.04 + 0.03 * (len(used) % 3))), 3)
    CB.CAST[who] = pick
    auto[who] = dict(pick, ling=ling, _note="system ne diya — badal sakte ho")
    return True


def save_cast(auto):
    auto.setdefault("_samjho", "Naye kirdaar jo kahani_dimaag ne khud banaye. 'ling' ya settings badal sakte ho; "
                               "pakka karna ho to tools/cast_build.py CAST me daal do.")
    CAST_AUTO.write_text(json.dumps(auto, ensure_ascii=False, indent=1), encoding="utf-8")


# ============================================================================ dimaag (faisle)
def plan(items, rules, CB, auto):
    scenes, sfx_t, pos_t, emo_t = rules["scenes"], rules["sfx"], rules["positions"], rules["emotions"]
    pan_only = {k for k, v in pos_t.items() if set(v) <= {"words", "pan"}}
    out, cur, prev_narr, new_chars = [], None, "", []
    CB._STORY_NAMES = {it["who"] for it in items if it["type"] == "line"}
    for it in items:
        if it["type"] == "scene":
            cur = all_matches(it["text"], scenes) or ["ghar"]
            out.append({"type": "scene", "scenes": cur, "text": it["text"]}); continue
        if it["type"] == "sfx":
            t = it["text"].strip()
            out.append({"type": "sfx", "tag": t if t in sfx_t else best_match(t, sfx_t), "text": t}); continue
        who, note, text = it["who"], it["note"], it["text"]
        if who != NARRATOR and ensure_character(CB, auto, who):
            new_chars.append(who)
        hint = note
        if who != NARRATOR and prev_narr and has_word(tokens(prev_narr), who):
            hint += " " + prev_narr                       # "तभी दूर से कमला ने पुकारा।" -> कमला door se
        if cur is None:
            g = all_matches(text, scenes)
            if g:
                cur = g; out.append({"type": "scene", "scenes": g, "text": "(kahani se khud samjha)"})
        if cur and (who == NARRATOR or _is_narration(text)):     # "रात हो गई थी" -> wahi jagah, naya samay
            tod = [x for x in all_matches(text, scenes) if x in ("raat", "din")]
            if tod and tod[0] not in cur and (has_word(tokens(text), "हो") or has_word(tokens(text), "हुई")):
                cur = [x for x in cur if x not in ("raat", "din")] + [tod[0]]
                out.append({"type": "scene", "scenes": cur, "text": f"(samay badla: {tod[0]})"})
        pos_name = best_match(hint, pos_t, exclude=pan_only) or "paas"
        pos = dict(pos_t[pos_name])
        for p in pan_only:
            if any(has_word(tokens(hint), w) for w in pos_t[p]["words"]):
                pos["pan"] = pos_t[p]["pan"]
        emos = [] if who == NARRATOR else all_matches(hint, emo_t)
        r = sum(emo_t[e]["rate"] for e in emos); ph = sum(emo_t[e]["pitch"] for e in emos)
        vol = sum(emo_t[e]["volume"] for e in emos)
        if who != NARRATOR and not emos:                  # likha nahi -> ASTRA ka apna bhaav-pehchaan (realtime/bhaav)
            e, k = _text_bhaav(text)
            if e in emo_t:
                emos = [f"{e}~{int(k * 100)}%"]
                r, ph, vol = (emo_t[e][x] * k * 0.6 for x in ("rate", "pitch", "volume"))
        extra = {"tempo": round(max(0.8, min(1.2, 1 + r / 100)), 3),
                 "pitch": round(max(0.9, min(1.12, 1 + ph / 200)), 3),       # chhota badlav — zero ki seema ke andar
                 "bhaav": [e.split("~")[0] for e in emos]}                  # asli awaaz: is bhaav ki recording
        auto_sfx = all_matches(text, sfx_t) if who == NARRATOR or (cur and not note and _is_narration(text)) else []
        prev_narr = text if who == NARRATOR or _is_narration(text) else ""
        out.append({"type": "line", "who": who, "text": text, "extra": extra, "gain_db": 20 * np.log10(max(0.3, 1 + vol / 100)),
                    "pos_name": pos_name, "pos": pos, "emos": emos, "auto_sfx": auto_sfx})
    if not any(p["type"] == "scene" for p in out):
        out.insert(0, {"type": "scene", "scenes": ["ghar"], "text": "(jagah nahi mili — ghar maana)"})
    elif out[0]["type"] != "scene":
        first = next(p for p in out if p["type"] == "scene"); out.remove(first); out.insert(0, first)
    return out, new_chars


_BHAAV_MAP = {"dar": "dar", "khushi": "khushi", "dukh": "udaas", "gussa": "gussa", "krodh": "gussa",
              "hairani": "hairani", "udaasi": "udaas", "pyaar": "pyaar"}


def _text_bhaav(text):
    """Line ke shabdon se bhaav (ASTRA realtime/bhaav.target). 'डरो मत' jaise inkaar par bhaav nahi."""
    try:
        sys.path.insert(0, str(ROOT / "tools" / "realtime"))
        import bhaav as B
        t = B.target({"text": text})
    except Exception:
        return None, 0
    e, k = _BHAAV_MAP.get(t.get("emotion")), float(t.get("intensity", 0))
    if k < 0.5 or (e and has_word(tokens(text), "मत")):
        return None, 0
    return e, min(1.0, k)


def _chunks(text, n=200):
    """Bina danda wali lambi line ko shabd ki seema par todo (TTS lambi line me bigadta hai)."""
    if len(text) <= n:
        return [text]
    out, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + 1 > n and cur:
            out.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    return out + ([cur] if cur else [])


def _is_narration(text):
    """ASTRA script me kirdaar bhi kahani sunata hai ('गौरी: उस शाम जंगल शांत था।').
    Bina sambodhan/sawaal ke, teesre purush me likhi line = varnan."""
    t = tokens(text)
    first_person = {"मैं", "मैंने", "मुझे", "हम", "हमने", "तुम", "तुम्हें", "आप", "तू", "देखो", "चलो"}
    return (not ("?" in text or "!" in text) and not (set(t) & first_person)
            and any(has_word(t, w) for w in ("था", "थी", "थे", "गया", "गई", "गए")))


# ============================================================================ audio
def _ff():
    import ffbin
    return ffbin.ensure() or "ffmpeg"


def load(path):
    try:
        y, sr = sf.read(str(path), always_2d=True)
    except Exception:
        import subprocess, tempfile
        tmp = Path(tempfile.mkdtemp()) / "d.wav"
        subprocess.run([_ff(), "-v", "error", "-y", "-i", str(path), "-ar", str(SR), str(tmp)], capture_output=True)
        y, sr = sf.read(str(tmp), always_2d=True)
    y = y.T.astype(np.float64)
    if y.shape[0] == 1:
        y = np.vstack([y, y])
    y = y[:2]
    if sr != SR:
        from math import gcd
        g = gcd(int(sr), SR)
        y = ss.resample_poly(y, SR // g, sr // g, axis=1)
    return y


def db(x): return 10 ** (x / 20)


def trim(a, thr=-48, keep=0.04):
    m = np.abs(a).max(axis=0); idx = np.flatnonzero(m > db(thr))
    if not len(idx): return a
    k = int(keep * SR)
    return a[:, max(0, idx[0] - k): idx[-1] + k]


def fade(a, fi=0.01, fo=0.01):
    n = a.shape[1]; i, o = min(n, int(fi * SR)), min(n, int(fo * SR))
    if i: a[:, :i] *= np.linspace(0, 1, i)
    if o: a[:, n - o:] *= np.linspace(1, 0, o)
    return a


def pan(a, p):
    p = max(-1.0, min(1.0, p)); ang = (p + 1) * np.pi / 4; m = a.mean(axis=0)
    return np.vstack([m * np.cos(ang), m * np.sin(ang)]) * 1.414


def lowpass(a, hz):
    return ss.sosfilt(ss.butter(4, min(0.99, hz / (SR / 2)), btype="low", output="sos"), a, axis=1)


def bandpass(a, lo, hi):
    return ss.sosfilt(ss.butter(4, [lo / (SR / 2), min(0.99, hi / (SR / 2))], btype="band", output="sos"), a, axis=1)


_IR = {}


def reverb(a, wet, size=0.6):
    """Goonj: stereo, dheere marti hui IR (aage chhota pre-delay), bina kisi plugin ke."""
    if wet <= 0.005: return a
    key = round(size, 2)
    if key not in _IR:
        rt = 0.35 + 1.3 * size; n = int(rt * SR); t = np.arange(n) / SR
        rng = np.random.default_rng(5)
        ir = rng.normal(0, 1, (2, n)) * np.exp(-6.9 * t / rt)
        ir = lowpass(ir, 6500 - 3000 * size); ir[:, :int(0.012 * SR)] = 0
        _IR[key] = ir / np.sqrt((ir ** 2).sum(axis=1, keepdims=True))
    ir = _IR[key]
    pad = np.concatenate([a, np.zeros((2, ir.shape[1]))], axis=1)
    w = np.vstack([ss.fftconvolve(pad[c], ir[c])[:pad.shape[1]] for c in range(2)])
    return trim(pad * (1 - wet * 0.5) + w * wet * 1.6, -62, 0.05)


def place(a, pos, extra_wet=0.0):
    a = a * db(pos.get("gain", 0))
    if pos.get("lowpass"): a = lowpass(a, pos["lowpass"])
    if pos.get("bandpass"): a = bandpass(a, *pos["bandpass"])
    wet = min(0.7, pos.get("reverb", 0) + extra_wet)
    a = reverb(a, wet, 0.35 + wet)
    return pan(a, pos["pan"]) if pos.get("pan") else a


def loop_to(a, n, xf=1.0):
    if a.shape[1] >= n:
        s = random.randint(0, a.shape[1] - n); return a[:, s:s + n].copy()
    x = int(min(xf * SR, a.shape[1] // 3)); r = np.linspace(0, 1, x); out = a.copy()
    while out.shape[1] < n:
        out = np.concatenate([out[:, :-x], out[:, -x:] * r[::-1] + a[:, :x] * r, a[:, x:]], axis=1)
    return out[:, :n]


class Bus:
    def __init__(self): self.c = []
    def add(self, t, a): self.c.append((max(0, int(t * SR)), a))
    def render(self, n):
        o = np.zeros((2, n))
        for s, a in self.c:
            e = min(n, s + a.shape[1])
            if e > s: o[:, s:e] += a[:, :e - s]
        return o


def duck(voice, amt=-6, blk=2048):
    m = np.abs(voice).mean(axis=0); nb = int(np.ceil(len(m) / blk))
    rms = np.array([np.sqrt(np.mean(m[i * blk:(i + 1) * blk] ** 2) + 1e-12) for i in range(nb)])
    g, cur = np.ones(nb), 1.0
    for i, t in enumerate(np.where(rms > db(-42), db(amt), 1.0)):
        cur += (t - cur) * (0.5 if t < cur else 0.08); g[i] = cur
    return np.interp(np.arange(len(m)), np.arange(nb) * blk + blk / 2, g)


# ============================================================================ library
def all_tags(rules):
    tags = set(rules["library_find"]) | set(rules["sfx"])
    for s in rules["scenes"].values():
        tags |= set(s["beds"]) | set(s["events"])
    return tags


def scan(rules, verbose=True):
    LIB.mkdir(exist_ok=True)
    tags = all_tags(rules)
    for t in tags: (LIB / t).mkdir(exist_ok=True)
    idx, uns = {t: [] for t in tags}, []
    finds = {t: [norm(w) for w in ws] for t, ws in rules["library_find"].items()}
    for f in sorted(LIB.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in AUDIO_EXT: continue
        rel = str(f.relative_to(ROOT))
        if f.parent.name in tags:
            idx[f.parent.name].append(rel); continue
        nm = " " + re.sub(r"[_\-\.\d]+", " ", norm(f.stem)) + " "
        best, bl = None, 0
        for t, ws in finds.items():
            for w in ws:
                if (f" {w} " in nm or (len(w) > 4 and w in nm)) and len(w) > bl: best, bl = t, len(w)
        (idx[best].append(rel) if best else uns.append(rel))
    (ROOT / "knowledge" / "library_awaaz_index.json").write_text(
        json.dumps({"index": idx, "unsorted": uns}, ensure_ascii=False, indent=1), encoding="utf-8")
    missing = sorted(t for t in tags if not idx[t])
    with open(LIB / "download_list.txt", "w", encoding="utf-8") as fh:
        fh.write("Khaali khaane. Freesound/Pixabay se file lo, library_awaaz/<khaana>/ me daalo, phir: seekho\n"
                 "Ya khud: python tools/kahani_dimaag.py library-badao 6\n\n")
        for t in missing:
            fh.write(f"library_awaaz/{t}/   search: {', '.join(rules['library_find'].get(t, [t]))}\n")
    if verbose:
        print(f"library_awaaz: {sum(map(len, idx.values()))} file, {sum(1 for t in tags if idx[t])}/{len(tags)} khaane bhare"
              + (f", {len(uns)} pehchaan nahi" if uns else "") + ("  (khaali: library_awaaz/download_list.txt)" if missing else ""))
    return idx


def grow(rules, per_tag=4, allow_by=False):
    import urllib.request, urllib.parse, urllib.error, time
    kf = ROOT / "freesound_key.txt"
    key = os.environ.get("FREESOUND_API_KEY") or (kf.read_text().strip() if kf.exists() else "")
    if not key:
        raise SystemExit("Freesound key chahiye (free): freesound.org/apiv2/apply — key ko freesound_key.txt me daalo.")
    beds = {b for s in rules["scenes"].values() for b in s["beds"]}
    evs = {e for s in rules["scenes"].values() for e in s["events"]}
    idx = scan(rules, verbose=False)
    lic = '"Creative Commons 0"' if not allow_by else '("Creative Commons 0" OR "Attribution")'
    got = 0
    with open(LIB / "CREDITS.txt", "a", encoding="utf-8") as cr:
        for tag in sorted(all_tags(rules)):
            terms = rules["library_find"].get(tag, [tag.replace("_", " ")])
            have = len(idx.get(tag, []))
            if have >= per_tag: continue
            dur = "[20 TO 600]" if tag in beds else ("[0.5 TO 12]" if tag in evs else "[0.5 TO 20]")
            folder = LIB / tag; need = per_tag - have
            seen = {p.name.split("_")[0] for p in folder.glob("*")}
            for term in terms:
                if need <= 0: break
                q = {"query": term, "filter": f"license:{lic} duration:{dur}", "page_size": "15",
                     "fields": "id,name,previews,license,username", "sort": "rating_desc", "token": key}
                data = None
                for ep in ("search/", "search/text/"):
                    try:
                        with urllib.request.urlopen(f"https://freesound.org/apiv2/{ep}?" + urllib.parse.urlencode(q), timeout=30) as r:
                            data = json.loads(r.read()); break
                    except urllib.error.HTTPError as e:
                        if e.code in (401, 403): raise SystemExit("Freesound key galat hai.")
                    except Exception:
                        continue
                for res in (data or {}).get("results", []):
                    if need <= 0: break
                    sid = str(res["id"]); url = res.get("previews", {}).get("preview-hq-mp3")
                    if sid in seen or not url: continue
                    dest = folder / f"{sid}_{re.sub(r'[^\w-]+', '_', res['name'])[:40]}.mp3"
                    try:
                        urllib.request.urlretrieve(url, dest)
                    except Exception:
                        continue
                    seen.add(sid); need -= 1; got += 1
                    cr.write(f"{tag}\t{dest.name}\t{res['username']}\t{res['license']}\thttps://freesound.org/s/{sid}/\n")
                    time.sleep(0.3)
            print(f"  {tag:<18} {per_tag - need}/{per_tag}")
    print(f"Nayi {got} awaazein. Kiski hai: library_awaaz/CREDITS.txt")
    scan(rules)


# ============================================================================ banana
def build(pl, rules, idx, CB, out, cue):
    import clarity as CL
    rng = random.Random(7); random.seed(7)
    vb, fb, ab = Bus(), Bus(), Bus()
    last, missing, last_t = {}, set(), {}
    t, spans, cur, room = 1.5, [], None, 0.0

    try:
        import awaaz_khoj as AK
        W = AK.weight
    except Exception:
        W = lambda rel: 1.0

    def pick(tag):
        fs = [x for x in (idx.get(tag) or []) if W(x) > 0]          # 'galat' bataayi file kabhi nahi
        if not fs: return None
        pool = [x for x in fs if x != last.get(tag)] or fs
        f = random.choices(pool, weights=[W(x) for x in pool])[0]; last[tag] = f   # 'sahi' wali zyada baar
        return ROOT / f

    def sfx(tag, when, gain, maxlen):
        if not tag or when - last_t.get(tag, -99) < 1.5: return 0
        f = pick(tag)
        if f is None:
            missing.add(tag); cue.append((when, "KHAALI", f"{tag} (library_awaaz me nahi)")); return 0
        a = fade(trim(load(f), -50)[:, :int(maxlen * SR)], 0.01, 0.4) * db(gain)
        fb.add(when, place(a, {"reverb": 0.06 + room})); last_t[tag] = when
        cue.append((when, "AWAAZ", f"{tag} <- {f.name}"))
        return a.shape[1] / SR

    prev_who, dry = None, []          # dry = bina doori/goonj, zero ke gap ke saath — zero guard isi ko naapta hai
    for p in pl:
        if p["type"] == "scene":
            if cur: cur["end"] = t; t += 0.8
            cur = {"start": 0.0 if not spans else t, "scenes": p["scenes"], "end": None}; spans.append(cur)
            room = 0.08 if "ghar" in p["scenes"] else 0.03
            cue.append((t, "JAGAH", f"{' + '.join(p['scenes'])}  [{p['text']}]")); continue
        if p["type"] == "sfx":
            if not p["tag"]:
                cue.append((t, "?", f"'{p['text']}' samajh nahi aaya — knowledge/kahani_rules.json -> sfx")); continue
            t += min(sfx(p["tag"], t, rules["sfx"][p["tag"]].get("gain", -8), 6), 2.5) * 0.8; continue
        parts = [c.strip() for c in re.split(r"(?<=[।!?])\s*", p["text"].replace(",", " ")) if c.strip()]
        parts = [x for c in parts for x in _chunks(c)]          # bahut lambi line -> 200 akshar ke tukde
        ys = []
        for k, part in enumerate(parts):
            y, sr0 = sf.read(str(CB.line_audio(p["who"], part, p["extra"])))
            ys.append(CB._trim((y.mean(1) if y.ndim > 1 else y).astype(np.float64), sr0))
            if k < len(parts) - 1: ys.append(np.zeros(int(0.11 * sr0)))
        y = CL.clarity(np.concatenate(ys), sr0)
        y = y / (np.sqrt(np.mean(y ** 2)) + 1e-9) * db(-20)                  # har kirdaar barabar zor par
        from math import gcd
        g = gcd(sr0, SR); y = ss.resample_poly(y, SR // g, sr0 // g)
        dry += [y.copy(), np.zeros(int((0.34 if prev_who not in (None, p["who"]) else 0.12) * SR))]
        a = fade(np.vstack([y, y]) * db(p["gain_db"]), 0.006, 0.03)
        a = place(a, p["pos"], room if p["pos_name"] == "paas" else 0)
        vb.add(t, a); d = a.shape[1] / SR
        cue.append((t, p["who"], f"[{p['pos_name']}]" + (f" bhaav:{','.join(p['emos'])}" if p["emos"] else "") + f"  {p['text'][:48]}"))
        st = t + 0.2
        for tag in p["auto_sfx"]:
            st += min(sfx(tag, st, rules["sfx"][tag].get("gain", -9), max(3, min(7, d + 1))), 2.5)
        t += d + (0.34 if prev_who != p["who"] else 0.14)
        prev_who = p["who"]
    if cur: cur["end"] = t + 1.5
    total = int((t + 2.5) * SR)

    for sp in spans:
        s0, s1 = sp["start"], sp["end"] + 1.0; n = int((s1 - s0) * SR)
        indoor = "ghar" in sp["scenes"]
        outdoor = {b for sc in sp["scenes"] if sc != "ghar" for b in rules["scenes"][sc]["beds"]}
        beds = list(dict.fromkeys(b for sc in sp["scenes"] for b in rules["scenes"][sc]["beds"]))
        for k, b in enumerate(beds):
            f = pick(b)
            if f is None: missing.add(b); continue
            a = loop_to(load(f), n) * db(-21 if k == 0 else -27)
            if indoor and b in outdoor:
                a = lowpass(a, 1400) * db(-7)                 # kamre ke andar: bahar ki awaaz deewar ke paar
            ab.add(s0, fade(a, 1.2, 1.2)); cue.append((s0, "MAHAUL", f"{b} <- {f.name}"))
        evs = sorted({e for sc in sp["scenes"] for e in rules["scenes"][sc]["events"]})
        missing.update(e for e in evs if not idx.get(e)); evs = [e for e in evs if idx.get(e)]
        lo = min(rules["scenes"][sc]["event_every"][0] for sc in sp["scenes"])
        hi = max(rules["scenes"][sc]["event_every"][1] for sc in sp["scenes"])
        et = s0 + rng.uniform(3, lo + 2)
        while evs and et < s1 - 2:
            tag = rng.choice(evs); f = pick(tag)
            a = fade(trim(load(f), -50)[:, :int(5 * SR)], 0.05, 0.6)
            far = {"gain": rng.uniform(-22, -16) - (6 if indoor else 0),
                   "lowpass": 1400 if indoor else rng.choice([2800, 3800, 5000]), "reverb": 0.3, "pan": rng.uniform(-0.75, 0.75)}
            ab.add(et, place(a, far)); cue.append((et, "DOOR", f"{tag} <- {f.name}"))
            et += rng.uniform(lo, hi)

    voice = vb.render(total)
    mix = voice + fb.render(total) + ab.render(total) * duck(voice)
    try:
        import pyloudnorm as ln
        mix = ln.normalize.loudness(mix.T, ln.Meter(SR).integrated_loudness(mix.T), -16.0).T
    except Exception:
        mix = mix / (np.sqrt(np.mean(mix ** 2)) + 1e-9) * db(-18)
    th = 0.8                                               # naram limiter (chot na lage)
    over = np.abs(mix) > th
    mix[over] = np.sign(mix[over]) * (th + (1 - th) * np.tanh((np.abs(mix[over]) - th) / (1 - th)))
    mix *= min(1.0, 0.95 / (np.abs(mix).max() + 1e-9))
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.with_suffix(".wav"); sf.write(str(wav), mix.T.astype("float32"), SR)
    vstem = out.with_name(out.stem + "_voice.wav")
    sf.write(str(vstem), (voice.mean(axis=0) / (np.abs(voice).max() + 1e-9) * 0.9).astype("float32"), SR)
    dz = np.concatenate(dry) if dry else np.zeros(SR)
    dstem = out.with_name(out.stem + "_voice_dry.wav")
    sf.write(str(dstem), (dz / (np.abs(dz).max() + 1e-9) * 0.9).astype("float32"), SR)
    if out.suffix.lower() == ".mp3":
        import subprocess
        subprocess.run([_ff(), "-v", "error", "-y", "-i", str(wav), "-b:a", "192k", str(out)], capture_output=True)
    return total / SR, missing, dstem


def auto_khoj(pl, rules, idx):
    """Jo awaaz chahiye par library me nahi — khud web se (key ho to). ASTRA_AUTO_KHOJ=0 se band."""
    if os.environ.get("ASTRA_AUTO_KHOJ") == "0":
        return idx
    try:
        import awaaz_khoj as AK
        AK._key()
    except (SystemExit, Exception):
        return idx
    need = set()
    for p in pl:
        if p["type"] == "sfx":
            if not p["tag"]:
                tag, _, _ = AK.samjho(p["text"])                 # naya shabd: khud samjho aur rules me jodo
                p["tag"] = tag
            if p["tag"]: need.add(p["tag"])
        elif p["type"] == "line":
            need |= set(p["auto_sfx"])
        elif p["type"] == "scene":
            for sc in p["scenes"]:
                need |= set(rules["scenes"][sc]["beds"]) | set(rules["scenes"][sc]["events"])
    for t in sorted(x for x in need if not idx.get(x)):
        print(f"[khoj] {t} library me nahi — web se dhoondh raha hoon")
        AK.khoj(t, quiet=True)
    rules.clear(); rules.update(json.loads(RULES.read_text(encoding="utf-8")))
    return scan(rules, verbose=False)


def write_cue(cue, path):
    with open(path, "w", encoding="utf-8") as fh:
        for tm, k, w in sorted(cue, key=lambda x: x[0]):
            fh.write(f"{int(tm // 60):02d}:{tm % 60:05.2f}  {k:<8} {w}\n")


def main():
    rules = _AP.read_json(RULES, apni=True)
    a = sys.argv[1:]
    if not a:
        print(__doc__); return 0
    if a[0] == "seekho":
        scan(rules); return 0
    if a[0] == "library-badao":
        grow(rules, int(a[1]) if len(a) > 1 and a[1].isdigit() else 4, "--sab" in a); return 0
    dry = a[0] == "jaanch"
    if dry: a = a[1:]
    story = Path(a[0])
    CB, auto = load_cast()
    if not story.exists():
        raise SystemExit(f"Kahani ki file nahi mili: {story}")
    items = parse_script(story.read_text(encoding="utf-8-sig"))
    if not any(i["type"] == "line" for i in items):
        raise SystemExit("Kahani khaali hai — koi bolne wali line nahi mili.")
    pl, new = plan(items, rules, CB, auto)
    if new:
        save_cast(auto); print(f"Naye kirdaar ko apni awaaz di (knowledge/cast_auto.json): {', '.join(new)}")
    if dry:
        for p in pl:
            if p["type"] == "scene": print(f"\n== JAGAH: {' + '.join(p['scenes'])}   {p['text']}")
            elif p["type"] == "sfx": print(f"   (awaaz) {p['tag'] or '?? ' + p['text']}")
            else:
                c = CB.CAST.get(p["who"], {})
                print(f"   {p['who']:<9} [{p['pos_name']}] {','.join(p['emos']) or '-':<14} {c.get('engine','?')} "
                      f"sur x{c.get('pitch',1)*p['extra']['pitch']:.2f}  {p['text'][:38]}"
                      + (f"   + {', '.join(p['auto_sfx'])}" if p["auto_sfx"] else ""))
        return 0
    out = Path(a[1]) if len(a) > 1 else ROOT / "out" / (story.stem + ".mp3")
    idx = scan(rules, verbose=False); cue = []
    idx = auto_khoj(pl, rules, idx)
    dur, missing, vstem = build(pl, rules, idx, CB, out, cue)
    write_cue(cue, out.with_suffix(".cue.txt"))
    print(json.dumps({"out": str(out), "dur": round(dur, 1), "cue": str(out.with_suffix('.cue.txt'))}, ensure_ascii=False))
    if missing:
        print(f"library_awaaz me nahi ({len(missing)}): {', '.join(sorted(missing))}")
    try:
        import zero_baseline as ZB
        print("zero guard (kirdaaron ki saaf awaaz, bina mahaul/doori):"); ZB.check(str(vstem))
    except SystemExit:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
