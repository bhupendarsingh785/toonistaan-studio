"""
Harkat (motion) + Bhaav (emotion) — kirdaar aur duniya ki har harkat ki awaaz. 100% local, procedural.

FX bus alag hai: yeh awaazein background ke saath normalize NAHI hoti, awaaz (voice) ke mukable
apne fixed level par rehti hain — isliye kadam, patton ki charmar, garaj, bhediya saaf sunai dete hain.

Harkat (script ke shabd -> awaaz, kirdaar ke pan par):
  walk  चल/कदम/गुज़र        -> kadam (surface: sookhe patte / mitti / patthar / paani)
  run   दौड़/भाग             -> tez kadam + haanfna
  stop  रुक/ठहर             -> aakhri kadam ki ghisat
  fall  गिर                 -> dhamm + patton ka bikharna
  jump  कूद                 -> uchhal + zameen par girna
  twig  टहनी/चटक/कड़क        -> sookhi lakdi tootna
  splash पानी में/छपाक       -> chhapaak
  wolf  भेड़िया              -> 4 panjon ki chaal (patton par) + door ki "hu-aa" ya gurrahat
  growl गुर्रा               -> gurrahat
  howl  हुआँ/चीख़ (भेड़िया)    -> lambi hu-aa
  thunder गरज/बिजली          -> paas ki kadak + lambi gadgadahat
  heart dar wala bhaav       -> dhak-dhak (halki)
Bhaav (duniya ki pratikriya):
  dar   : chidiyan chup, hawa tez, dhadkan; khushi: chidiyan zyada; dukh: hawa dheemi
"""
from __future__ import annotations
import math
import numpy as np
from scipy import signal as ss

SR = 44100   # sutradhar/voice ke saath ek hi SR (warna stems misalign)

def _bp(lo, hi, o=2): return ss.butter(o, [lo / (SR / 2), min(hi, SR / 2 - 200) / (SR / 2)], "band", output="sos")
def _lp(f, o=2): return ss.butter(o, min(f, SR / 2 - 200) / (SR / 2), "low", output="sos")
def _hp(f, o=2): return ss.butter(o, f / (SR / 2), "high", output="sos")
def F(sos, x): return ss.sosfilt(sos, x)
def norm(x): return x / (np.max(np.abs(x)) + 1e-9)


# ---------------------------------------------------------------- kadam
def crackle(n, rng, density, lo, hi, decay_s):
    """Sookhe patton ki charmar: hazaaron chhote 'chatak' — har ek ki apni chamak."""
    t = np.arange(n) / SR
    p = density * np.exp(-t / decay_s)
    imp = (rng.random(n) < p) * rng.standard_normal(n) * rng.lognormal(0, 0.7, n)
    x = F(_bp(lo, hi), imp)
    # kuch bade 'chatak' (patta mudna)
    for _ in range(rng.integers(2, 6)):
        i = int(rng.uniform(0, min(n - 200, decay_s * 2.5 * SR)))
        m = int(rng.uniform(0.004, 0.012) * SR); tt = np.arange(m) / SR
        x[i:i + m] += F(_bp(1500, 9000), rng.standard_normal(m)) * np.exp(-tt / 0.003) * rng.uniform(1.5, 3)
    return x

def step(rng, surface="leaves", force=1.0):
    """Ek kadam. force>1 = daudna (bhaari, tez)."""
    if surface == "water":
        n = int(0.45 * SR); t = np.arange(n) / SR
        x = F(_bp(250, 4000), rng.standard_normal(n)) * np.exp(-t / 0.11)
        bub = np.zeros(n)
        for _ in range(25):
            f0 = rng.uniform(500, 2000); m = int(0.02 * SR); tt = np.arange(m) / SR
            i = rng.integers(0, n - m); bub[i:i + m] += np.sin(2 * np.pi * np.cumsum(f0 * (1 + tt * 30)) / SR) * np.exp(-tt / 0.006)
        return norm(x + 0.3 * bub + F(_lp(200), rng.standard_normal(n)) * np.exp(-t / 0.04) * 0.8) * force
    cfg = {  # dur, crackle density, band, decay, thud
        "leaves": (0.42, 0.06, (700, 10000), 0.09, 0.7),
        "soil":   (0.18, 0.012, (300, 3000), 0.03, 1.4),
        "stone":  (0.12, 0.008, (1800, 8000), 0.015, 0.9),
        "grass":  (0.30, 0.03, (900, 7000), 0.07, 0.6),
    }.get(surface, (0.35, 0.04, (800, 9000), 0.08, 0.8))
    dur, dens, band, dec, th = cfg
    n = int(dur * SR); t = np.arange(n) / SR
    thud = F(_lp(150), rng.standard_normal(n)) * np.exp(-t / 0.028) * th * force
    heel = crackle(n, rng, dens * force, *band, dec)
    toe = np.zeros(n); k = int(rng.uniform(0.05, 0.08) * SR)       # edi, phir panja
    toe[k:] = crackle(n - k, rng, dens * 0.7 * force, *band, dec * 0.8)
    return norm(thud + heel + 0.8 * toe) * (0.85 + 0.15 * rng.random()) * min(force, 1.4)

def scuff(rng, surface="leaves"):
    n = int(0.35 * SR); t = np.arange(n) / SR
    e = np.sin(np.pi * np.clip(t / 0.35, 0, 1)) ** 1.5
    return norm(F(_bp(600, 8000), rng.standard_normal(n)) * e + crackle(n, rng, 0.02, 800, 9000, 0.12) * 0.8)

def paw_cycle(rng, surface="leaves"):
    """Bhediye/jaanwar ki chaal: chaar halke panje (gait), insaan se naram aur tez."""
    n = int(0.48 * SR); out = np.zeros(n)
    for off in (0.0, 0.11, 0.24, 0.35):
        m = int(0.12 * SR); tt = np.arange(m) / SR
        p = F(_lp(220), rng.standard_normal(m)) * np.exp(-tt / 0.015) * 0.5 + crackle(m, rng, 0.03, 900, 9000, 0.03)
        i = max(0, int((off + rng.uniform(0, 0.012)) * SR)); k = min(m, n - i)
        out[i:i + k] += p[:k] * rng.uniform(0.6, 1.0)
    return norm(out)

def twig(rng):
    n = int(0.25 * SR); t = np.arange(n) / SR
    snap = F(_bp(1200, 9000), rng.standard_normal(n)) * np.exp(-t / 0.006) * 2
    for f in rng.uniform(1500, 3500, 3):
        snap += np.sin(2 * np.pi * f * t) * np.exp(-t / 0.02) * 0.5
    snap += crackle(n, rng, 0.01, 1000, 8000, 0.05)
    return norm(snap)

def fall(rng):
    n = int(1.2 * SR); t = np.arange(n) / SR
    body = F(_lp(120), rng.standard_normal(n)) * np.exp(-t / 0.08) * 1.5
    return norm(body + crackle(n, rng, 0.12, 600, 10000, 0.25) * 0.9)

def jump(rng):
    up = scuff(rng) * 0.4
    land = fall(rng) * 0.7
    out = np.zeros(int(1.0 * SR) + len(land)); out[: len(up)] += up; out[int(0.55 * SR):int(0.55 * SR) + len(land)] += land
    return norm(out)

def splash(rng):
    n = int(1.0 * SR); t = np.arange(n) / SR
    x = F(_bp(200, 6000), rng.standard_normal(n)) * (np.exp(-t / 0.18) * np.minimum(1, t / 0.01))
    drops = (rng.random(n) < 0.004 * np.exp(-t / 0.4)) * rng.standard_normal(n)
    return norm(x + F(_bp(1000, 5000), drops) * 2)


# ---------------------------------------------------------------- jaanwar
def wolf_howl(rng):
    """Bhediye ki lambi 'hu-aa': neeche se upar sur, kaanpta (vibrato), saans ka shor."""
    d = rng.uniform(2.8, 4.2); n = int(d * SR); x = np.linspace(0, 1, n)
    f0 = rng.uniform(330, 400)
    f = f0 * (1 + 0.9 * np.clip(x / 0.25, 0, 1) - 0.25 * np.clip((x - 0.6) / 0.4, 0, 1))
    f *= 1 + 0.012 * np.sin(2 * np.pi * 5.2 * x * d) * np.clip(x / 0.3, 0, 1)
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph) + 0.05 * np.sin(4 * ph)
    breath = F(_bp(400, 3000), rng.standard_normal(n)) * 0.05
    e = np.clip(x / 0.12, 0, 1) ** 1.5 * np.clip((1 - x) / 0.25, 0, 1) ** 1.2
    return norm((tone + breath) * e)

def growl(rng, d=None):
    d = d or rng.uniform(1.2, 2.2); n = int(d * SR); t = np.arange(n) / SR
    am = 0.55 + 0.45 * np.sin(2 * np.pi * rng.uniform(22, 32) * t) ** 2
    src = F(_bp(70, 900), rng.standard_normal(n)) * am
    src = F(_bp(250, 700, 1), src) * 1.5 + F(_lp(160), src)
    e = np.minimum(1, t / 0.2) * np.minimum(1, (d - t) / 0.3)
    return norm(src * e)


# ---------------------------------------------------------------- mausam
def thunder(rng, near=True):
    d = rng.uniform(4.5, 7); n = int(d * SR); t = np.arange(n) / SR
    rnd = np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) / np.sqrt(np.arange(n // 2 + 1) + 1), n)
    roll = F(_lp(380), rnd); roll /= np.std(roll) + 1e-9
    roll *= np.exp(-t / (d / 3.2)) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * rng.uniform(1.5, 3) * t)))
    x = roll * 1.0
    if near:   # paas ki bijli: tez 'kadak' pehle
        crack = F(_bp(300, 9000), rng.standard_normal(n)) * np.exp(-t / 0.05) * 1.3
        x += crack
        x += F(_lp(90), rng.standard_normal(n)) * np.exp(-t / 0.5) * np.minimum(1, t / 0.03) * 0.8
    return norm(x * np.minimum(1, t / 0.005))


# ---------------------------------------------------------------- shareer / bhaav
def heartbeat(rng, dur, bpm=96):
    n = int(dur * SR); out = np.zeros(n); per = 60 / bpm; t0 = 0.0
    while t0 < dur:
        for off, a in ((0.0, 1.0), (0.24, 0.7)):
            m = int(0.12 * SR); tt = np.arange(m) / SR
            b = np.sin(2 * np.pi * 52 * tt) * np.exp(-tt / 0.035) * a
            i = int((t0 + off) * SR)
            if i + m < n: out[i:i + m] += b
        t0 += per * rng.uniform(0.97, 1.03)
    return norm(F(_lp(140), out))

def panting(rng, dur):
    n = int(dur * SR); out = np.zeros(n); t0 = 0.0
    while t0 < dur:
        for k, (L, lo, hi) in enumerate(((0.22, 500, 3500), (0.18, 700, 4500))):
            m = int(L * SR); tt = np.linspace(0, 1, m)
            b = F(_bp(lo, hi), rng.standard_normal(m)) * np.sin(np.pi * tt) ** 2 * (0.8 if k else 1)
            i = int(t0 * SR)
            if i + m < n: out[i:i + m] += b
            t0 += L + 0.04
        t0 += rng.uniform(0.05, 0.12)
    return norm(out)


# ---------------------------------------------------------------- script -> harkat events
ACTIONS = {
    "run":    ["दौड़", "दौड़ा", "दौड़ी", "भाग", "भागा", "भागी", "भागने", "daud", "bhaag"],
    "walk":   ["चल", "चला", "चली", "चलते", "चलने", "कदम", "गुज़र", "गुजर", "आगे बढ़", "पास आ", "chal", "kadam", "guzar"],
    "stop":   ["रुक", "रुका", "रुकी", "ठहर", "ruk", "thahar"],
    "fall":   ["गिर", "गिरा", "गिरी", "फिसल", "gir", "phisal"],
    "jump":   ["कूद", "छलाँग", "kood", "chhalaang"],
    "twig":   ["टहनी", "चटक", "चरमरा", "टूटी", "tahni", "chatak"],
    "splash": ["छपाक", "पानी में", "नदी में कूद", "chhapaak", "paani me"],
    "wolf":   ["भेड़िया", "भेड़िये", "भेड़ियों", "bhediya", "bhediye", "wolf"],
    "growl":  ["गुर्रा", "गुर्राया", "gurra"],
    "howl":   ["हुआँ", "हुआं", "हू-हू", "howl"],
    "thunder":["गरज", "बिजली", "कड़क", "garaj", "bijli"],
}
EMO_WORDS = {
    "dar":    ["डर", "डरा", "डरी", "काँप", "कांप", "सहम", "घबरा", "dar", "kaanp", "ghabra"],
    "khushi": ["खुश", "हँस", "हंस", "वाह", "khush", "hans"],
    "dukh":   ["दुख", "रो", "आँसू", "उदास", "dukh", "udaas"],
}

import re as _re
_L = "\u0900-\u0963\u0966-\u097Fa-zA-Z0-9"   # \u0964/\u0965 = । ॥ (viraam) shabd ka hissa nahi
_RX = {}
def _pos(text, w):
    """Shabd ki shuruaat se milao (jad/stem chalega: 'चल' -> 'चलते'), beech se nahi ('आग' != 'भाग')."""
    if w not in _RX: _RX[w] = _re.compile(f"(?<![{_L}]){_re.escape(w.lower())}")
    m = _RX[w].search(text.lower()); return m.start() if m else -1

def has(text, words):
    return any(w and _pos(text, w) >= 0 for w in words)

# Context: "हवा चलने लगी" kisi ka chalna nahi; "बारिश रुकी" kadam rukna nahi.
NOT_CTX = {
    "walk": ["हवा चल", "आँधी चल", "आंधी चल", "घड़ी चल", "गाड़ी चल", "बस चल", "पंखा चल", "काम चल", "पता चल", "चलो ठीक", "hawa chal", "pata chal"],
    "run":  ["गाड़ी भाग", "समय भाग", "नदी भाग"],
    "stop": ["बारिश रुक", "बरसात रुक", "हवा रुक", "आँधी रुक", "गाड़ी रुक", "बस रुक", "आवाज़ रुक", "आवाज रुक", "साँस रुक", "baarish ruk", "hawa ruk"],
    "fall": ["बारिश गिर", "बूँदें गिर", "बूंदें गिर", "पत्ते गिर", "ओले गिर", "बिजली गिर"],
}
def act(text, kind):
    return has(text, ACTIONS[kind]) and not has(text, NOT_CTX.get(kind, []))

def word_time(line, words, after=0.0):
    """Shabd line me kahan hai -> uska andaaze ka samay (akshar ke hisaab se). ASR marks ho to woh use karo."""
    txt = line.get("text", ""); low = txt.lower()
    for w in line.get("words", []):                      # ASR word timestamps (agar hain)
        if any(k.lower() in w.get("w", "").lower() for k in words): return w["start"] + after
    ps = [_pos(txt, k) for k in words]; ps = [x for x in ps if x >= 0]
    idx = min(ps) if ps else len(low)
    frac = (idx + 1) / max(1, len(low))
    return line["start"] + (line["end"] - line["start"]) * frac + after

def emotion_of(line):
    b = (line.get("bhaav") or "").lower()
    if b in ("dar", "khushi", "dukh", "gussa", "cheekh"): return b
    for e, w in EMO_WORDS.items():
        if has(line.get("text", ""), w): return e
    return "neutral"

def surface_of(text, surfaces, default="leaves"):
    s = default
    for k, words in surfaces.items():
        if not k.startswith("_") and has(text, words): s = k
    return s

def plan_actions(lines, total, wmap):
    """Har line se: kaun si harkat, kab, kahan (pan), kaunsa bhaav. Returns events + emotion spans."""
    ev, emo = [], []
    surf_mem = "leaves"; wolf_on = False
    for i, ln in enumerate(lines):
        txt = ln.get("text", ""); a, b = ln["start"], ln["end"]
        nxt = lines[i + 1]["start"] if i + 1 < len(lines) else min(total, b + 2.5)
        pan = ln.get("pan", 0.0)
        surf_mem = surface_of(txt, wmap.get("surfaces", {}), surf_mem)
        e = emotion_of(ln)
        if e != "neutral": emo.append((a, nxt, e))
        stop_t = word_time(ln, ACTIONS["stop"], 0.25) if act(txt, "stop") else None
        if act(txt, "run"):
            t0 = word_time(ln, ACTIONS["run"], 0.1)
            ev.append(dict(kind="run", t0=t0, t1=stop_t if stop_t and stop_t > t0 else nxt + 0.6, pan=pan, surface=surf_mem))
        elif act(txt, "walk"):
            t0 = a + 0.15                                    # "chal raha tha" = pehle se chal raha
            ev.append(dict(kind="walk", t0=t0, t1=stop_t if stop_t and stop_t > t0 else nxt + 0.3, pan=pan, surface=surf_mem))
        if stop_t: ev.append(dict(kind="stop", t0=stop_t, pan=pan, surface=surf_mem))
        if act(txt, "fall"): ev.append(dict(kind="fall", t0=word_time(ln, ACTIONS["fall"], 0.15), pan=pan))
        if has(txt, ACTIONS["jump"]): ev.append(dict(kind="jump", t0=word_time(ln, ACTIONS["jump"], 0.05), pan=pan))
        if has(txt, ACTIONS["twig"]): ev.append(dict(kind="twig", t0=word_time(ln, ACTIONS["twig"], 0.05), pan=pan + 0.3))
        if has(txt, ACTIONS["splash"]): ev.append(dict(kind="splash", t0=word_time(ln, ACTIONS["splash"], 0.1), pan=pan))
        if has(txt, ACTIONS["thunder"]): ev.append(dict(kind="thunder", t0=word_time(ln, ACTIONS["thunder"], 0.0), pan=0.2, near=True))
        if has(txt, ACTIONS["wolf"]):
            side = -0.6 if not wolf_on else 0.5
            if not wolf_on:   # pehli baar: door se hu-aa
                ev.append(dict(kind="howl", t0=b + 0.2, pan=side, dist=5.0))
            ev.append(dict(kind="wolf_walk", t0=a, t1=nxt + 1.0, pan0=side, pan1=-side * 0.3, surface=surf_mem))
            wolf_on = True
        if has(txt, ACTIONS["growl"]): ev.append(dict(kind="growl", t0=b + 0.1, pan=ln.get("wolf_pan", 0.35), dist=1.6))
        if has(txt, ACTIONS["howl"]): ev.append(dict(kind="howl", t0=b + 0.2, pan=-0.5, dist=4.0))
    return ev, emo
