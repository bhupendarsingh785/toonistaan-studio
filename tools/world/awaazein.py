"""
Awaazein — rozmarra ki duniya ki procedural awaazein (100% local, koi recording nahi).
Har function ek mono numpy array (48 kHz) lautata hai. Library me asli recording ho to woh pehle chalegi;
yeh tab ke liye hai jab na ho — aur system kabhi chup na rahe.

Naya sound jodna: ek function likho `def naam(rng, **kw) -> np.ndarray`, phir REGISTRY me daalo,
aur knowledge/sound-events.json me uske shabd likho. Bas.
"""
from __future__ import annotations
import math
import numpy as np
from scipy import signal as ss

SR = 48000

def _bp(lo, hi, o=2): return ss.butter(o, [max(lo, 20) / (SR / 2), min(hi, SR / 2 - 200) / (SR / 2)], "band", output="sos")
def _lp(f, o=2): return ss.butter(o, min(f, SR / 2 - 200) / (SR / 2), "low", output="sos")
def _hp(f, o=2): return ss.butter(o, f / (SR / 2), "high", output="sos")
def F(sos, x): return ss.sosfilt(sos, x)
def norm(x): return x / (np.max(np.abs(x)) + 1e-9)
def T(d): return np.arange(int(d * SR)) / SR
def sil(d): return np.zeros(int(d * SR))
def modal(freqs, decays, amps, d, rng=None):
    """Thos cheez ki 'tan' awaaz: kai resonant mode (ghanti, bartan, lakdi)."""
    t = T(d); x = np.zeros_like(t)
    for f, dc, a in zip(freqs, decays, amps):
        x += a * np.sin(2 * np.pi * f * t + (rng.uniform(0, 6) if rng is not None else 0)) * np.exp(-t / dc)
    return x

# ---------------------------------------------------------------- phone
def phone_ring_old(rng, rings=4):
    """Purane landline ki ghanti: 2 ghantiyon par hathoda ~20 Hz, 'tring-tring'."""
    parts = []
    for _ in range(rings):
        for burst in range(2):
            t = T(0.4)
            strike = (np.sin(2 * np.pi * 20 * t) > 0).astype(float)
            bell = modal([1150, 1620, 2830, 4100], [0.05, 0.04, 0.03, 0.02], [1, .6, .3, .15], 0.4, rng)
            parts += [bell * (0.6 + 0.4 * strike), sil(0.2)]
        parts.append(sil(1.6))
    return norm(np.concatenate(parts))

def mobile_ring(rng, rings=4):
    """Mobile ringtone: chhoti madhur dhun (marimba jaisi), har ring par repeat."""
    notes = [72, 76, 79, 76, 81, 79]  # MIDI
    parts = []
    for _ in range(rings):
        for m in notes:
            f = 440 * 2 ** ((m - 69) / 12)
            parts.append(modal([f, 4 * f, 9.8 * f], [0.18, 0.04, 0.015], [1, .25, .08], 0.16, rng))
        parts.append(sil(0.9))
    x = np.concatenate(parts)
    return norm(F(_bp(300, 6000), x))          # chhote speaker jaisi

def phone_vibrate(rng, pulses=4):
    parts = []
    for _ in range(pulses):
        t = T(0.7)
        buzz = np.sin(2 * np.pi * 150 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 300 * t))
        rattle = F(_bp(1500, 6000), rng.standard_normal(len(t))) * (np.sin(2 * np.pi * 150 * t) > 0.9) * 0.4
        parts += [(buzz * 0.5 + rattle) * np.minimum(1, t / 0.02) * np.minimum(1, (0.7 - t) / 0.02), sil(0.5)]
    return norm(np.concatenate(parts))

def phone_pickup(rng):
    t = T(0.25)
    click = F(_bp(800, 6000), rng.standard_normal(len(t))) * np.exp(-t / 0.006)
    clack = F(_bp(200, 2000), rng.standard_normal(len(t))) * np.exp(-np.maximum(0, t - 0.08) / 0.01) * (t > 0.08) * 0.7
    return norm(click + clack)

def phone_hangup(rng):
    x = np.concatenate([phone_pickup(rng) * 0.7, sil(0.3)])
    for _ in range(3):
        t = T(0.25); x = np.concatenate([x, np.sin(2 * np.pi * 425 * t) * 0.3, sil(0.25)])
    return norm(x)

def message_tone(rng):
    return norm(np.concatenate([modal([1568, 6272], [0.12, 0.03], [1, .2], 0.14, rng), modal([2093, 8372], [0.2, 0.04], [1, .2], 0.3, rng)]))

# ---------------------------------------------------------------- darwaza / ghar
def door_knock(rng, n=3):
    parts = []
    for i in range(n):
        t = T(0.18)
        hit = F(_bp(90, 1400), rng.standard_normal(len(t))) * np.exp(-t / 0.018)
        body = modal([110, 240, 410], [0.06, 0.04, 0.03], [1, .5, .3], 0.18, rng)
        parts += [hit * 0.8 + body * 0.6, sil(rng.uniform(0.12, 0.2))]
    return norm(np.concatenate(parts))

def door_creak(rng, d=None):
    """Kabze ki charr-charr: stick-slip friction — tez pulse train jiska sur badalta hai."""
    d = d or rng.uniform(1.0, 1.8); t = T(d); n = len(t)
    f = 18 + 30 * np.abs(np.sin(np.pi * t / d * rng.uniform(0.8, 1.6))) + 6 * np.cumsum(rng.standard_normal(n)) / np.sqrt(SR)
    ph = np.cumsum(f) / SR
    pulses = (np.diff(np.floor(ph), prepend=0) > 0).astype(float)
    exc = pulses * (0.6 + 0.4 * rng.random(n))
    x = F(_bp(400, 900, 1), exc) * 1.0 + F(_bp(1200, 2600, 1), exc) * 0.7 + F(_bp(2800, 4200, 1), exc) * 0.35
    return norm(x * np.sin(np.pi * t / d) ** 0.5)

def door_close(rng):
    t = T(0.9)
    thud = F(_lp(180), rng.standard_normal(len(t))) * np.exp(-t / 0.06) * 1.5
    latch = F(_bp(1500, 7000), rng.standard_normal(len(t))) * np.exp(-np.maximum(0, t - 0.03) / 0.008) * (t > 0.03)
    ring = modal([95, 180, 330], [0.15, 0.1, 0.06], [1, .4, .2], 0.9, rng) * 0.4
    return norm(thud + latch * 0.5 + ring)

def door_open(rng):
    t = T(0.3)
    latch = F(_bp(1500, 7000), rng.standard_normal(len(t))) * np.exp(-t / 0.008)
    return norm(np.concatenate([latch, door_creak(rng, rng.uniform(0.6, 1.0)) * 0.7]))

def clock_tick(rng, d=8.0):
    t0, out = 0.0, sil(d)
    while t0 < d - 0.1:
        m = int(0.03 * SR); tt = np.arange(m) / SR
        tick = F(_bp(2000, 7000), rng.standard_normal(m)) * np.exp(-tt / 0.003) + modal([3200], [0.01], [0.4], 0.03)
        i = int(t0 * SR); out[i:i + m] += tick * (1.0 if int(t0) % 2 == 0 else 0.75)
        t0 += 1.0
    return norm(out)

def wall_clock_chime(rng, strikes=3):
    parts = []
    for _ in range(strikes):
        parts += [modal([523, 1046, 1320, 2093], [1.2, 0.6, 0.4, 0.2], [1, .5, .3, .15], 1.4, rng)]
    return norm(np.concatenate(parts))

def utensils(rng, n=None):
    """Bartan: steel ki tan-tan (rasoi)."""
    n = n or rng.integers(3, 7); parts = []
    for _ in range(n):
        f0 = rng.uniform(900, 2400)
        parts += [modal([f0, f0 * 2.76, f0 * 5.4], [0.25, 0.12, 0.05], [1, .5, .25], 0.4, rng) * rng.uniform(.4, 1),
                  sil(rng.uniform(0.15, 0.6))]
    return norm(np.concatenate(parts))

def pressure_cooker(rng):
    t = T(3.0)
    hiss = F(_bp(2500, 9000), rng.standard_normal(len(t))) * np.minimum(1, t / 0.4) * np.minimum(1, (3 - t) / 0.6)
    whistle = np.sin(2 * np.pi * (2200 + 150 * np.sin(2 * np.pi * 6 * t)) * t) * 0.35 * np.minimum(1, np.maximum(0, t - 0.5) / 0.3) * np.minimum(1, (3 - t) / 0.5)
    return norm(hiss + whistle)

def water_pour(rng, d=2.5):
    t = T(d); n = len(t)
    stream = F(_bp(300, 5000), rng.standard_normal(n)) * 0.4
    fill = 300 + 900 * t / d                         # bartan bharte hue sur upar
    x = np.zeros(n)
    for _ in range(int(d * 140)):
        i = rng.integers(0, n - 600); m = 500; tt = np.arange(m) / SR
        f = fill[i] * rng.uniform(0.8, 1.3)
        x[i:i + m] += np.sin(2 * np.pi * f * tt * (1 + 20 * tt)) * np.exp(-tt / 0.004) * rng.uniform(.2, 1)
    return norm((stream + x * 0.5) * np.minimum(1, t / 0.1) * np.minimum(1, (d - t) / 0.2))

def tap_water(rng, d=3.0):
    t = T(d)
    return norm(F(_bp(400, 7000), rng.standard_normal(len(t))) * (0.85 + 0.15 * np.sin(2 * np.pi * 3 * t)) * np.minimum(1, t / 0.15) * np.minimum(1, (d - t) / 0.2))

def drip(rng, d=6.0):
    """Barish ke baad tapakti boondein."""
    out = sil(d); t0 = rng.uniform(0, .5)
    while t0 < d - 0.1:
        m = int(0.05 * SR); tt = np.arange(m) / SR
        f = rng.uniform(900, 1800)
        out[int(t0 * SR):int(t0 * SR) + m] += np.sin(2 * np.pi * f * tt * (1 + 12 * tt)) * np.exp(-tt / 0.012) * rng.uniform(.4, 1)
        t0 += rng.uniform(0.3, 1.2)
    return norm(out)

def paper_page(rng):
    t = T(0.55)
    e = np.sin(np.pi * t / 0.55) ** 2
    x = F(_bp(1500, 9000), rng.standard_normal(len(t))) * e * (0.6 + 0.4 * (rng.random(len(t)) > 0.7))
    return norm(x)

def cloth_rustle(rng, d=0.8):
    t = T(d)
    return norm(F(_bp(600, 5000), rng.standard_normal(len(t))) * np.sin(np.pi * t / d) ** 1.5 * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 7 * t))))

def typing(rng, d=3.0):
    out = sil(d); t0 = 0.1
    while t0 < d - 0.05:
        m = int(0.03 * SR); tt = np.arange(m) / SR
        out[int(t0 * SR):int(t0 * SR) + m] += F(_bp(1500, 7000), rng.standard_normal(m)) * np.exp(-tt / 0.004) * rng.uniform(.5, 1)
        t0 += rng.uniform(0.07, 0.22) + (0.4 if rng.random() < 0.06 else 0)
    return norm(out)

def glass_break(rng):
    t = T(1.4)
    crash = F(_bp(1500, 12000), rng.standard_normal(len(t))) * np.exp(-t / 0.08)
    shards = np.zeros(len(t))
    for _ in range(40):
        f = rng.uniform(2500, 9000); i = int(rng.uniform(0.02, 1.0) * SR); m = int(0.08 * SR); tt = np.arange(m) / SR
        if i + m < len(t): shards[i:i + m] += np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.02) * rng.uniform(.2, .8)
    return norm(crash + shards * 0.5)

def fire_crackle(rng, d=8.0):
    t = T(d); n = len(t)
    roar = F(_bp(80, 900), rng.standard_normal(n)) * 0.25
    pops = (rng.random(n) < 0.0007) * rng.standard_normal(n) * rng.lognormal(0, 0.8, n)
    return norm(roar + F(_bp(800, 9000), pops) * 1.5)

def wood_chop(rng):
    t = T(0.6)
    return norm(F(_bp(150, 3000), rng.standard_normal(len(t))) * np.exp(-t / 0.03) + modal([180, 420, 760], [0.08, 0.05, 0.03], [1, .5, .3], 0.6, rng) * 0.6)

def chair_drag(rng):
    c = door_creak(rng, 0.8); n = len(c)
    return norm(c * 0.5 + F(_bp(200, 1500), rng.standard_normal(n)) * np.sin(np.pi * np.arange(n) / n) * 0.5)

def clap(rng, n=None):
    n = n or rng.integers(3, 8); parts = []
    for _ in range(n):
        t = T(0.12); parts += [F(_bp(600, 6000), rng.standard_normal(len(t))) * np.exp(-t / 0.012), sil(rng.uniform(.12, .25))]
    return norm(np.concatenate(parts))

# ---------------------------------------------------------------- ghantiyan / gaadi
def temple_bell(rng):
    return norm(modal([440, 1060, 1720, 2510, 3460], [2.5, 1.4, 0.9, 0.6, 0.4], [1, .6, .4, .25, .12], 4.0, rng))

def school_bell(rng, d=2.5):
    t = T(d); strike = (np.sin(2 * np.pi * 22 * t) > 0)
    return norm(modal([1900, 3800, 5300], [0.08] * 3, [1, .4, .2], d, rng) * strike * np.minimum(1, (d - t) / 0.1))

def cycle_bell(rng):
    return norm(np.concatenate([modal([2700, 5900], [0.25, 0.1], [1, .3], 0.3, rng) for _ in range(2)]))

def car_horn(rng, d=0.6):
    t = T(d); f = rng.uniform(380, 450)
    x = sum(np.sign(np.sin(2 * np.pi * f * h * t)) / h for h in (1, 1.26))
    return norm(F(_bp(300, 4000), x) * np.minimum(1, t / 0.01) * np.minimum(1, (d - t) / 0.02))

def vehicle_pass(rng, d=6.0, kind="car"):
    """Gaadi paas se guzarti: engine + tyre ka shor, doppler (sur upar->neeche), dheere aati/jaati."""
    t = T(d); x = (t - d / 2) / (d / 2)
    fe = (38 if kind == "car" else 70) * (1 + 0.08 * -np.tanh(3 * x))      # doppler
    ph = 2 * np.pi * np.cumsum(fe) / SR
    eng = np.sign(np.sin(ph)) * 0.3 + np.sin(2 * ph) * 0.3
    tyre = F(_bp(300, 3000), np.random.default_rng(int(rng.integers(1e9))).standard_normal(len(t))) * 0.6
    amp = 1 / (0.15 + x ** 2)
    return norm((F(_lp(1800), eng) + tyre) * amp)

def bike_engine(rng, d=4.0):
    return vehicle_pass(rng, d, "bike")

# ---------------------------------------------------------------- jaanwar (sasta synth — library behtar)
def dog_bark(rng, n=None):
    n = n or rng.integers(1, 4); parts = []
    for _ in range(n):
        d = rng.uniform(0.18, 0.28); t = T(d); x = np.linspace(0, 1, len(t))
        f = rng.uniform(380, 520) * (1 + 0.5 * np.sin(np.pi * x))
        ph = 2 * np.pi * np.cumsum(f) / SR
        src = (np.sign(np.sin(ph)) + 0.4 * F(_bp(400, 3000), rng.standard_normal(len(t))))
        y = F(_bp(500, 1400, 1), src) + F(_bp(1800, 3200, 1), src) * 0.6
        parts += [y * np.exp(-x * 2.5) * np.minimum(1, t / 0.008), sil(rng.uniform(0.15, 0.4))]
    return norm(np.concatenate(parts))

def rooster(rng):
    d = 1.6; t = T(d); x = t / d
    f = 600 * (1 + 0.6 * np.interp(x, [0, .1, .25, .5, .8, 1], [0, .6, .5, .9, .7, .3]))
    ph = 2 * np.pi * np.cumsum(f) / SR
    src = np.sign(np.sin(ph)) * 0.5 + np.sin(2 * ph) * 0.4
    y = F(_bp(700, 2500, 1), src) + F(_bp(2600, 4500, 1), src) * 0.4
    return norm(y * np.interp(x, [0, .05, .15, .2, .9, 1], [0, 1, 1, .6, .8, 0]))

def frog(rng, d=6.0):
    out = sil(d); t0 = 0.2
    while t0 < d - 0.3:
        t = T(0.12); f = rng.uniform(300, 500)
        out[int(t0 * SR):int(t0 * SR) + len(t)] += np.sin(2 * np.pi * f * t) * (np.sin(2 * np.pi * 45 * t) > 0) * np.sin(np.pi * t / 0.12)
        t0 += rng.uniform(0.35, 1.2)
    return norm(F(_bp(200, 1500), out))

REGISTRY = {
    "phone_ring_old": phone_ring_old, "mobile_ring": mobile_ring, "phone_vibrate": phone_vibrate,
    "phone_pickup": phone_pickup, "phone_hangup": phone_hangup, "message_tone": message_tone,
    "door_knock": door_knock, "door_creak": door_creak, "door_close": door_close, "door_open": door_open,
    "clock_tick": clock_tick, "wall_clock_chime": wall_clock_chime, "utensils": utensils,
    "pressure_cooker": pressure_cooker, "water_pour": water_pour, "tap_water": tap_water, "drip": drip,
    "paper_page": paper_page, "cloth_rustle": cloth_rustle, "typing": typing, "glass_break": glass_break,
    "fire_crackle": fire_crackle, "wood_chop": wood_chop, "chair_drag": chair_drag, "clap": clap,
    "temple_bell": temple_bell, "school_bell": school_bell, "cycle_bell": cycle_bell, "car_horn": car_horn,
    "vehicle_pass": vehicle_pass, "bike_engine": bike_engine,
    "dog_bark": dog_bark, "rooster": rooster, "frog": frog,
}
