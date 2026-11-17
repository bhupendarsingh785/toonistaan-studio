#!/usr/bin/env python3
"""
ASTRA — Universal Sound Creation Engine (offline, bina internet, bina API key)

Kisi bhi cheez ki awaaz banao: kadam (mitti/patthar/lakdi/barf/geela), patte, baaris,
hawa, aag, paani, darwaza, kaanch, dhatu, gaadi, train, helicopter, machine, jaanwar,
pakshi, jhoote/monster, magic, dhamaka — aur sab par processing: doori, reverb,
pan (baayein/daayein), EQ, normalize.

Chalao:
  python3 astra/astra.py banao "sukha patta pair ke neeche dheere kuchal raha hai" -o out.wav
  python3 astra/astra.py banao "mitti par bhaari kadam, paas se" -o out.wav --pan -0.4
  python3 astra/astra.py list
  python3 astra/astra.py pack -o pack/            # demo pack (12 awaazein)

Har awaaz ka metadata memory/index.json me jata hai (dobara kaam aata hai).
"""
import argparse
import json
import os
import sys
import hashlib
from dataclasses import dataclass, asdict, field
from typing import Optional

import numpy as np

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
MEM = os.path.join(HERE, "memory")
os.makedirs(MEM, exist_ok=True)
INDEX = os.path.join(MEM, "index.json")


# ============================================================ helpers
def T(d):
    return np.linspace(0, d, max(1, int(SR * d)), False)


def noise(d):
    return np.random.randn(max(1, int(SR * d))).astype(np.float32)


def lp(x, hz):
    k = max(1, int(SR / max(hz, 20)))
    return np.convolve(x, np.ones(k) / k, "same").astype(np.float32)


def hp(x, hz):
    return (x - lp(x, hz)).astype(np.float32)


def bp(x, lo, hi):
    return hp(lp(x, hi), lo)


def env_ad(n, a=0.005, d=0.25, curve=8.0):
    """attack + decay envelope"""
    e = np.ones(n, np.float32)
    A = max(1, min(int(SR * a), n // 2))
    e[:A] = np.linspace(0, 1, A)
    tail = np.linspace(0, 1, max(1, n - A))
    e[A:] = np.exp(-tail * curve)
    return e


def norm(x, peak=0.9):
    p = float(np.abs(x).max()) if len(x) else 0.0
    return (x / p * peak).astype(np.float32) if p > 0 else x.astype(np.float32)


def reverb(x, room=0.35, damp=3000, tail=1.2):
    """Simple Schroeder-ish reverb (free, numpy)."""
    if room <= 0:
        return x
    n_tail = int(SR * tail)
    out = np.concatenate([x, np.zeros(n_tail, np.float32)])
    for delay_ms, g in ((29, 0.7), (37, 0.6), (41, 0.55), (53, 0.5), (67, 0.45)):
        d = int(SR * delay_ms / 1000)
        y = np.zeros_like(out)
        y[d:] = out[:-d] * g * room
        out += y
    return lp(out, damp).astype(np.float32)


def distance(x, meters=1.0):
    """Doori: awaaz dheemi + garam (high freq kam)."""
    if meters <= 1.0:
        return x
    g = 1.0 / (1.0 + meters * 0.35)
    cutoff = max(600, 12000 / (1 + meters * 0.6))
    return (lp(x, cutoff) * g).astype(np.float32)


def stereo(x, pan=0.0, width=1.0):
    """pan: -1 baayein, 0 beech, +1 daayein."""
    if x.ndim == 1:
        l = x * (1 - max(0.0, pan))
        r = x * (1 + min(0.0, pan))
        if width != 1.0:
            d = int(SR * 0.012 * width)
            l2 = np.concatenate([np.zeros(d, np.float32), l[:-d]]) if d else l
            r2 = np.concatenate([np.zeros(d, np.float32), r[:-d]]) if d else r
            l, r = l2, r2
        return np.stack([l, r], 1).astype(np.float32)
    return x


# ============================================================ generators
# har generator: (params) -> mono float32
MATERIALS = {
    "soil": {"low": 200, "high": 2500, "crunch": 0.35, "thump": 70},
    "gravel": {"low": 900, "high": 7000, "crunch": 0.8, "thump": 110},
    "stone": {"low": 400, "high": 5000, "crunch": 0.55, "thump": 90},
    "wood": {"low": 120, "high": 2200, "crunch": 0.3, "thump": 80},
    "snow": {"low": 150, "high": 3500, "crunch": 0.9, "thump": 55},
    "wet": {"low": 180, "high": 3000, "crunch": 0.5, "thump": 65},
    "leaves": {"low": 800, "high": 9000, "crunch": 1.0, "thump": 40},
    "concrete": {"low": 300, "high": 4200, "crunch": 0.4, "thump": 95},
}


def footstep(material="soil", weight=0.5, speed=1.0, d=0.35):
    m = MATERIALS.get(material, MATERIALS["soil"])
    n = int(SR * d)
    tt = T(d)[:n]
    # thump (body weight)
    thump = np.sin(2 * np.pi * m["thump"] * tt) * np.exp(-tt * 28) * (0.4 + weight * 0.6)
    # crunch (surface)
    cr = bp(noise(d), m["low"], m["high"]) * np.exp(-tt * (18 + speed * 8)) * m["crunch"]
    x = thump * 0.9 + cr * 0.8
    return norm(x, 0.85)


def footsteps(material="soil", steps=4, bpm=105, weight=0.5):
    step = 60.0 / bpm
    total = step * steps + 0.3
    out = np.zeros(int(SR * total), np.float32)
    for i in range(steps):
        s = footstep(material, weight, 1.0)
        k = int(SR * (i * step + np.random.uniform(-0.01, 0.01)))
        g = 0.9 if i % 2 == 0 else 0.75      # left/right foot
        k = max(0, min(int(k), max(0, len(out) - 1)))
        m = min(len(s), len(out) - k)
        if m <= 0:
            continue
        out[k:k + m] += s[:m] * g
    return norm(out, 0.9)


def leaves_rustle(d=2.5, intensity=0.6):
    x = bp(noise(d), 1200, 9000)
    mod = (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * (0.8 + intensity) * T(d))))
    return norm(x * mod * env_ad(len(x), 0.05, d, 2.5), 0.7)


def leaf_crush(d=0.8):
    x = bp(noise(d), 1500, 10000) * np.exp(-T(d) * 9)
    crack = np.zeros_like(x)
    for _ in range(7):
        k = np.random.randint(0, max(1, len(x) - int(SR * 0.02)))
        crack[k:k + int(SR * 0.012)] += noise(0.012) * np.random.uniform(0.4, 1.0)
    return norm(x * 0.7 + crack, 0.8)


def rain(d=4.0, intensity=0.6):
    hiss = hp(noise(d), 2500) * 0.5
    drops = np.zeros(int(SR * d), np.float32)
    n_drops = int(60 * d * intensity)
    for _ in range(n_drops):
        k = np.random.randint(0, max(1, len(drops) - int(SR * 0.03)))
        f = np.random.uniform(900, 4000)
        tt = T(0.03)
        drops[k:k + len(tt)] += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 90)).astype(np.float32) * np.random.uniform(0.2, 0.7)
    return norm(hiss * 0.5 + drops * 0.6, 0.8)


def wind(d=5.0, strength=0.5):
    base = lp(noise(d), 200 + strength * 400)
    mod = 0.6 + 0.4 * np.sin(2 * np.pi * (0.2 + strength * 0.4) * T(d))
    whistle = np.sin(2 * np.pi * (400 + 200 * strength) * T(d)) * 0.05 * mod
    return norm(base * mod + whistle, 0.75)


def water_flow(d=4.0):
    x = bp(noise(d), 400, 4000)
    mod = 0.7 + 0.3 * np.sin(2 * np.pi * 2.3 * T(d))
    return norm(x * mod, 0.75)


def water_drop(d=0.5, n=1):
    out = np.zeros(int(SR * (d * n + 0.4)), np.float32)
    for i in range(n):
        f0 = np.random.uniform(700, 1400)
        tt = T(0.12)
        f = f0 * (1 + 1.6 * tt / 0.12)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 30)
        k = int(SR * (i * d))
        out[k:k + len(s)] += s.astype(np.float32)
    return norm(out, 0.8)


def fire(d=4.0, intensity=0.6):
    roar = lp(noise(d), 900) * 0.5
    crackle = np.zeros(int(SR * d), np.float32)
    for _ in range(int(40 * d * intensity)):
        k = np.random.randint(0, max(1, len(crackle) - int(SR * 0.03)))
        s = hp(noise(0.02), 2000) * np.exp(-T(0.02) * 60)
        crackle[k:k + len(s)] += s[:len(crackle) - k] * np.random.uniform(0.3, 1.0)
    return norm(roar + crackle * 0.7, 0.85)


def door(kind="wood", d=1.6):
    tt = T(d)
    if kind == "metal":
        f = 300 + 120 * np.sin(2 * np.pi * 1.1 * tt)
        creak = 2 * ((np.cumsum(f) / SR) % 1) - 1
        creak = bp(creak, 400, 5000) * env_ad(len(tt), 0.05, d, 3) * 0.5
    else:
        f = 120 + 70 * np.sin(2 * np.pi * 0.8 * tt)
        creak = 2 * ((np.cumsum(f) / SR) % 1) - 1
        creak = lp(creak, 1500) * env_ad(len(tt), 0.05, d, 3) * 0.5
    thud = np.zeros_like(tt)
    thud[:int(SR * 0.12)] = np.sin(2 * np.pi * 65 * T(0.12)) * np.exp(-T(0.12) * 16) * 0.8
    return norm(creak + thud, 0.85)


def glass(d=0.9):
    out = np.zeros(int(SR * d), np.float32)
    for f, g in ((2600, 0.5), (3900, 0.35), (5200, 0.25), (7400, 0.15)):
        tt = T(d)
        out += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 9) * g).astype(np.float32)
    hit = hp(noise(0.05), 3000) * np.exp(-T(0.05) * 50)
    out[:len(hit)] += hit * 0.8
    return norm(out, 0.85)


def metal_hit(d=1.4):
    out = np.zeros(int(SR * d), np.float32)
    for f, g in ((520, 0.6), (1180, 0.4), (1970, 0.3), (3100, 0.2), (4600, 0.12)):
        tt = T(d)
        out += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 5) * g).astype(np.float32)
    return norm(out, 0.85)


def wood_hit(d=0.6):
    tt = T(d)
    body = np.sin(2 * np.pi * 180 * tt) * np.exp(-tt * 18)
    knock = lp(noise(d), 1200) * np.exp(-tt * 40)
    return norm(body * 0.8 + knock * 0.6, 0.85)


def paper(d=0.9):
    x = hp(noise(d), 1800)
    mod = 0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 7 * T(d)))
    return norm(x * mod * env_ad(len(x), 0.02, d, 2), 0.7)


def coins(d=0.9):
    out = np.zeros(int(SR * d), np.float32)
    for _ in range(9):
        f = np.random.uniform(2600, 5200)
        tt = T(0.16)
        k = np.random.randint(0, max(1, len(out) - len(tt)))
        out[k:k + len(tt)] += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 26) * 0.5).astype(np.float32)
    return norm(out, 0.8)


def engine(d=5.0, rpm=0.5):
    tt = T(d)
    f = 40 + rpm * 70 + 6 * np.sin(2 * np.pi * 1.5 * tt)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    x += 0.4 * np.sin(2 * np.pi * np.cumsum(f * 2) / SR)
    x += 0.2 * lp(noise(d), 400)
    return norm(x * env_ad(len(x), 0.2, d, 1.2), 0.8)


def train(d=6.0):
    x = engine(d, 0.3)
    clack = np.zeros(int(SR * d), np.float32)
    k = 0.0
    while k < d - 0.3:
        tt = T(0.12)
        s = (np.sin(2 * np.pi * 140 * tt) * np.exp(-tt * 30)).astype(np.float32)
        i = int(SR * k)
        clack[i:i + len(s)] += s[:len(clack) - i]
        k += 0.55
    horn = np.sin(2 * np.pi * 320 * T(d)) * 0.15 * (np.sin(np.pi * T(d) / d) ** 2)
    return norm(x * 0.7 + clack * 0.6 + horn, 0.85)


def helicopter(d=4.0):
    tt = T(d)
    blade = (np.sin(2 * np.pi * 18 * tt) > 0).astype(np.float32)
    rotor = lp(noise(d), 600) * blade * 0.8
    whine = np.sin(2 * np.pi * 900 * tt) * 0.12
    return norm(rotor + whine, 0.8)


def machine_hum(d=4.0):
    tt = T(d)
    x = np.sin(2 * np.pi * 100 * tt) * 0.4 + np.sin(2 * np.pi * 150 * tt) * 0.2
    x += bp(noise(d), 300, 2500) * 0.3
    return norm(x * env_ad(len(x), 0.2, d, 1), 0.7)


def dog_bark(d=1.6, n=2):
    out = np.zeros(int(SR * d), np.float32)
    for i in range(n):
        tt = T(0.18)
        f = 420 - 180 * tt / 0.18
        x = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * bp(noise(0.18), 300, 2200)) * np.exp(-tt * 18)
        k = int(SR * (0.15 + i * 0.45))
        out[k:k + len(x)] += x.astype(np.float32)
    return norm(out, 0.85)


def cat_meow(d=1.2):
    tt = T(d)
    f = 500 + 300 * np.sin(np.pi * tt / d)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / d)
    return norm(x, 0.75)


def bird_chirp(d=2.0, n=5):
    out = np.zeros(int(SR * d), np.float32)
    for i in range(n):
        dur = np.random.uniform(0.08, 0.16)
        tt = T(dur)
        f0 = np.random.uniform(2200, 4200)
        f = f0 * (1 + 0.6 * np.sin(np.pi * tt / dur))
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / dur)
        k = int(SR * np.random.uniform(0, d - dur))
        out[k:k + len(x)] += x.astype(np.float32)
    return norm(out, 0.7)


def cricket(d=4.0):
    tt = T(d)
    gate = (np.sin(2 * np.pi * 9 * tt) > 0.85).astype(np.float32)
    x = np.sin(2 * np.pi * 4600 * tt) * gate
    return norm(x * 0.6, 0.6)


def monster_growl(d=2.4):
    tt = T(d)
    f = 90 + 25 * np.sin(2 * np.pi * 1.7 * tt)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    x += 0.5 * lp(noise(d), 300)
    x *= (0.6 + 0.4 * np.sin(2 * np.pi * 6 * tt))
    return norm(x * env_ad(len(x), 0.15, d, 2), 0.9)


def magic_sparkle(d=2.0):
    out = np.zeros(int(SR * d), np.float32)
    for _ in range(30):
        f = np.random.uniform(1500, 7000)
        tt = T(0.25)
        s = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 12)
        k = np.random.randint(0, max(1, len(out) - len(s)))
        out[k:k + len(s)] += s.astype(np.float32) * np.random.uniform(0.2, 0.8)
    pad = np.sin(2 * np.pi * 220 * T(d)) * 0.1
    return norm(out * 0.7 + pad, 0.8)


def laser(d=1.2):
    tt = T(d)
    f = 2200 * np.exp(-tt * 3)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 4)
    return norm(x, 0.85)


def explosion(d=2.6):
    tt = T(d)
    boom = lp(noise(d), 120) * np.exp(-tt * 3) * 2.2
    boom[:int(SR * 0.05)] += noise(0.05) * 1.5
    rumble = lp(noise(d), 60) * np.exp(-tt * 1.2)
    return norm(boom + rumble, 0.95)


def thunder(d=3.0):
    tt = T(d)
    crack = hp(noise(0.15), 1200) * np.exp(-T(0.15) * 25)
    body = lp(noise(d), 140) * np.exp(-tt * 1.6)
    out = body
    out[:len(crack)] += crack * 1.2
    return norm(out, 0.9)


def laugh(d=1.8):
    out = np.zeros(int(SR * d), np.float32)
    for i in range(4):
        dur = 0.22
        tt = T(dur)
        f = 220 - 40 * tt / dur
        x = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.4 * bp(noise(dur), 400, 2000)) * np.sin(np.pi * tt / dur)
        k = int(SR * (i * 0.33))
        out[k:k + len(x)] += x.astype(np.float32) * 0.8
    return norm(out, 0.8)


def cry(d=2.5):
    tt = T(d)
    f = 300 + 60 * np.sin(2 * np.pi * 2.2 * tt)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.8 * tt))
    x += 0.2 * bp(noise(d), 500, 2500)
    return norm(x * env_ad(len(x), 0.2, d, 1.5), 0.7)


def breath_sound(d=1.2):
    x = bp(noise(d), 400, 4000) * np.sin(np.pi * T(d) / d) ** 2
    return norm(x, 0.5)


def scream(d=1.4):
    tt = T(d)
    f = 700 + 300 * np.sin(2 * np.pi * 5 * tt)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    x += 0.5 * bp(noise(d), 600, 3500)
    return norm(x * np.sin(np.pi * tt / d) * 0.9, 0.9)


GENERATORS = {
    # human
    "footsteps": footsteps, "leaf_crush": leaf_crush, "laugh": laugh, "cry": cry,
    "breath": breath_sound, "scream": scream,
    # nature
    "leaves": leaves_rustle, "rain": rain, "wind": wind, "water": water_flow,
    "water_drop": water_drop, "fire": fire, "thunder": thunder,
    # objects
    "door": door, "glass": glass, "metal": metal_hit, "wood": wood_hit,
    "paper": paper, "coins": coins,
    # machines
    "engine": engine, "train": train, "helicopter": helicopter, "machine": machine_hum,
    # animals
    "dog": dog_bark, "cat": cat_meow, "bird": bird_chirp, "cricket": cricket,
    # fictional
    "monster": monster_growl, "magic": magic_sparkle, "laser": laser, "explosion": explosion,
}

CATEGORIES = {
    "human": ["footsteps", "laugh", "cry", "breath", "scream", "leaf_crush"],
    "animal": ["dog", "cat", "bird", "cricket", "monster"],
    "nature": ["leaves", "rain", "wind", "water", "water_drop", "fire", "thunder"],
    "object": ["door", "glass", "metal", "wood", "paper", "coins"],
    "machine": ["engine", "train", "helicopter", "machine"],
    "fictional": ["magic", "laser", "explosion", "monster"],
}


# ============================================================ intent parsing
HINTS = [
    # (keywords, generator, extra)
    (["kadam", "footstep", "चलने", "कदम", "चलता", "पैर"], "footsteps", {}),
    (["patta", "patte", "leaf", "leaves", "पत्ता", "पत्ते"], "leaves", {}),
    (["kuchal", "crush", "कुचल"], "leaf_crush", {}),
    (["barish", "rain", "बारिश", "बौछार"], "rain", {}),
    (["hawa", "wind", "हवा", "आंधी"], "wind", {}),
    (["nadi", "paani", "water", "नदी", "पानी", "बहता"], "water", {}),
    (["boond", "drop", "बूंद"], "water_drop", {}),
    (["aag", "fire", "आग", "जलता", "अलाव"], "fire", {}),
    (["bijli", "thunder", "बिजली", "गरज"], "thunder", {}),
    (["darwaza", "door", "gate", "दरवाज़ा", "दरवाजा", "गेट"], "door", {}),
    (["kaanch", "glass", "कांच", "काँच"], "glass", {}),
    (["loha", "metal", "dhatu", "लोहा", "धातु", "थाली", "घंटी"], "metal", {}),
    (["lakdi", "wood", "लकड़ी", "लकडी", "थप्पी"], "wood", {}),
    (["kagaz", "paper", "कागज़", "कागज", "पन्ने", "चिट्ठी"], "paper", {}),
    (["sikke", "coins", "पैसे", "सिक्के", "गुल्लक", "रुपये"], "coins", {}),
    (["gaadi", "engine", "कार", "गाड़ी", "इंजन", "ट्रक", "स्कूटर"], "engine", {}),
    (["train", "रेल", "ट्रेन"], "train", {}),
    (["helicopter", "हेलीकॉप्टर"], "helicopter", {}),
    (["machine", "मशीन", "मोटर"], "machine", {}),
    (["kutta", "dog", "कुत्ता", "भौं"], "dog", {}),
    (["billi", "cat", "बिल्ली", "म्याऊ"], "cat", {}),
    (["chidiya", "bird", "पक्षी", "चिड़िया", "चहचह"], "bird", {}),
    (["jhingur", "cricket", "झींगुर", "टिड्डा"], "cricket", {}),
    (["monster", "rakshas", "राक्षस", "भूत", "दैत्य"], "monster", {}),
    (["magic", "जादू", "sparkle", "चमक"], "magic", {}),
    (["laser", "लेजर"], "laser", {}),
    (["dhamaka", "blast", "explosion", "धमाका", "विस्फोट"], "explosion", {}),
    (["hans", "laugh", "हंसी", "हँसी"], "laugh", {}),
    (["rona", "cry", "रोना", "रुलाई"], "cry", {}),
    (["saans", "breath", "सांस", "साँस"], "breath", {}),
    (["cheekh", "scream", "चीख", "चिल्ला"], "scream", {}),
]

MATERIAL_HINTS = [
    (["sukha", "सूखा", "सूखे", "dry"], "leaves"),
    (["geela", "गीला", "गीले", "wet", "keechad", "कीचड़"], "wet"),
    (["barf", "snow", "बर्फ"], "snow"),
    (["patthar", "gravel", "कंकड़", "पत्थर", "रोड़ी"], "gravel"),
    (["lakdi", "wood", "लकड़ी"], "wood"),
    (["concrete", "फर्श", "सीमेंट"], "concrete"),
    (["mitti", "soil", "मिट्टी", "मिटटी"], "soil"),
]


@dataclass
class SoundRequest:
    description: str
    category: str = ""
    duration: float = 3.0
    style: str = "realistic"
    environment: str = "neutral"
    intensity: float = 0.5
    distance_m: float = 1.0
    pan: float = 0.0
    reverb: float = 0.25
    seed: Optional[int] = None


@dataclass
class SoundResult:
    asset_path: str
    duration: float
    sample_rate: int
    generator: str
    success: bool
    meta: dict = field(default_factory=dict)


def parse(desc):
    """Text -> kaunsa generator + kaunse params."""
    low = str(desc or "").lower()
    gen, extra = None, {}
    for words, g, ex in HINTS:
        if any(w.lower() in low for w in words):
            gen = g
            extra.update(ex)
            break
    if gen is None:
        gen = "wind" if "hawa" in low else "rain"

    material = None
    for words, m in MATERIAL_HINTS:
        if any(w.lower() in low for w in words):
            material = m
            break

    # door: metal ya wood?
    if gen == "door":
        extra["kind"] = "metal" if any(w in low for w in ["loha", "metal", "लोहा"]) else "wood"

    # footstep material
    if gen == "footsteps":
        extra["material"] = material or "soil"
        if any(w in low for w in ["bhaari", "भारी", "heavy"]):
            extra["weight"] = 0.9
        if any(w in low for w in ["dheere", "धीरे", "slow"]):
            extra["bpm"] = 70
        if any(w in low for w in ["tez", "तेज़", "तेज", "fast", "daud", "दौड़"]):
            extra["bpm"] = 150

    dist = 1.0
    for w, m in (("paas", 1.0), ("पास", 1.0), ("door", 12.0), ("दूर", 12.0), ("bahut door", 30.0)):
        if w in low:
            dist = m
    pan = 0.0
    if any(w in low for w in ["baayein", "बाएं", "left"]):
        pan = -0.6
    if any(w in low for w in ["daayein", "दाएं", "right"]):
        pan = 0.6
    return gen, extra, dist, pan


def build(req: SoundRequest):
    """(audio_array, meta) — asli kaam."""
    if req.seed is not None:
        np.random.seed(req.seed)
    gen, extra, dist, pan = parse(req.description)
    if req.category and req.category in GENERATORS:
        gen = req.category
    fn = GENERATORS.get(gen, GENERATORS["wind"])
    sig = fn.__code__.co_varnames[: fn.__code__.co_argcount]
    kwargs = dict(extra)
    if "d" in sig:
        kwargs["d"] = max(0.2, float(req.duration))
    kwargs = {k: v for k, v in kwargs.items() if k in sig}
    x = norm(fn(**kwargs), 0.9)
    x = distance(x, req.distance_m)
    x = reverb(x, req.reverb)
    x = norm(x, 0.92)
    x = stereo(x, req.pan if req.pan else pan, width=0.6)
    meta = {"generator": gen, "params": kwargs, "distance": req.distance_m, "pan": req.pan}
    return x, meta


def generate(req: SoundRequest) -> SoundResult:
    x, meta = build(req)
    return SoundResult("", len(x) / SR, SR, meta["generator"], True, meta)


# ============================================================ QA + memory
def qa(x):
    peak = float(np.abs(x).max()) if len(x) else 0.0
    clip = int((np.abs(x) > 0.999).sum())
    rms = float(np.sqrt((x ** 2).mean())) if len(x) else 0.0
    return {"peak": round(peak, 3), "rms": round(rms, 3), "clipped_samples": clip,
            "seconds": round(len(x) / SR, 2), "ok": peak > 0.01 and clip == 0}


def save_wav(path, x):
    import wave
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    x = np.clip(x, -1, 1)
    ch = 1 if x.ndim == 1 else x.shape[1]
    with wave.open(path, "w") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(SR)
        data = (x * 32767).astype(np.int16).tobytes() if x.ndim == 1 else (x * 32767).astype(np.int16).tobytes()
        w.writeframes(data)


def remember(desc, path, meta):
    try:
        idx = json.load(open(INDEX)) if os.path.exists(INDEX) else {}
    except Exception:
        idx = {}
    key = hashlib.md5((desc + path).encode()).hexdigest()[:12]
    idx[key] = {"description": desc, "file": path, **meta}
    try:
        json.dump(idx, open(INDEX, "w"), ensure_ascii=False, indent=1)
    except Exception:
        pass


# ============================================================ CLI
def cmd_banao(a):
    req = SoundRequest(description=a.text, duration=a.dur, distance_m=a.dist,
                       pan=a.pan, reverb=a.reverb, seed=a.seed)
    arr, meta = build(req)
    save_wav(a.out, arr)
    info = qa(arr)
    remember(a.text, a.out, {"generator": meta["generator"], **info})
    print(f"TAIYAR {a.out} | {meta['generator']} | {info['seconds']}s | peak {info['peak']} | ok={info['ok']}")
    return 0


def cmd_list(a):
    print("ASTRA generators:")
    for cat, gens in CATEGORIES.items():
        print(f"  {cat:10s} " + ", ".join(gens))
    return 0


def cmd_pack(a):
    os.makedirs(a.out, exist_ok=True)
    demo = [
        ("sukha patta pair ke neeche kuchal raha hai", "leaf_crush", 1.0),
        ("mitti par bhaari kadam, paas se", "footsteps", 3.0),
        ("barish tez ho rahi hai", "rain", 4.0),
        ("hawa chal rahi hai, halki", "wind", 4.0),
        ("aag jal rahi hai, alav", "fire", 3.5),
        ("purana lakdi ka darwaza khul raha hai", "door", 1.8),
        ("kaanch ka glass gir kar toota", "glass", 1.2),
        ("sikke gir rahe hain gulllak se", "coins", 1.0),
        ("gaadi ka engine chal raha hai", "engine", 4.0),
        ("chidiya subah chahchaha rahi hai", "bird", 2.5),
        ("rakshas ki dahaad", "monster", 2.4),
        ("jaadu ki chamak", "magic", 2.0),
    ]
    made = 0
    for desc, name, dur in demo:
        gen, extra, dist, pan = parse(desc)
        fn = GENERATORS.get(gen, GENERATORS["wind"])
        sig = fn.__code__.co_varnames[: fn.__code__.co_argcount]
        kwargs = {k: v for k, v in extra.items() if k in sig}
        if "d" in sig:
            kwargs["d"] = dur
        arr = norm(fn(**kwargs), 0.9)
        arr = distance(arr, 1.0)
        arr = reverb(arr, 0.2)
        arr = stereo(norm(arr, 0.92), 0.0, 0.6)
        p = os.path.join(a.out, f"{made + 1:02d}_{name}.wav")
        save_wav(p, arr)
        info = qa(arr)
        print(f"  {p}  {info['seconds']}s peak {info['peak']} ok={info['ok']}")
        made += 1
    print(f"PACK_TAIYAR {a.out} ({made} sounds)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="ASTRA — Universal Sound Creation Engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("banao", help="text se awaaz banao")
    b.add_argument("text")
    b.add_argument("-o", "--out", default="sound.wav")
    b.add_argument("--dur", type=float, default=3.0)
    b.add_argument("--dist", type=float, default=1.0, help="doori (meter): 1 paas, 12 door")
    b.add_argument("--pan", type=float, default=0.0, help="-1 baayein, +1 daayein")
    b.add_argument("--reverb", type=float, default=0.25)
    b.add_argument("--seed", type=int, default=None)
    b.set_defaults(func=cmd_banao)

    l = sub.add_parser("list", help="saare generators")
    l.set_defaults(func=cmd_list)

    p = sub.add_parser("pack", help="demo pack banao")
    p.add_argument("-o", "--out", default="pack")
    p.set_defaults(func=cmd_pack)

    a = ap.parse_args()
    sys.exit(a.func(a))


if __name__ == "__main__":
    main()
