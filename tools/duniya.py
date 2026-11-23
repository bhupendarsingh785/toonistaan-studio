#!/usr/bin/env python3
"""
Duniya engine (world sound) — Seetal / ASTRA ke liye, 100% local.

Kya karta hai:
  1. Script ke shabd padh kar scene banata hai (nadi, hawa, patte, chidiya, kadam...).
  2. Har awaaz ko stereo me jagah deta hai: baayein/daayein (pan) + door/paas (distance).
     Nadi "paas se guzarti" hai (pan + distance automation), kadam kirdaar ke saath chalte hain.
  3. Bed kabhi band nahi hota (asli duniya chup nahi hoti). Bolte waqt halka duck, ruke me wapas.
  4. Kahani me insaan jaise ruke daalta hai (comma / vakya / sawaal / scene badalna).
  5. Pehle aapki library (astra/library) ki asli recording dhundhta hai; na mile to
     khud procedural awaaz banata hai (river, wind, leaves, rain, birds, koel, crickets, kadam, thunder).

Koi cloud nahi, koi API nahi. Sirf numpy + scipy + ffmpeg.

Use:
  python tools/world/duniya.py --voice voice.wav --marks story_local.json --out out.mp3
  python tools/world/duniya.py --voice mix.mp3 --auto-pauses --scene scene.json --out out.mp3
"""
from __future__ import annotations
import argparse, fnmatch, json, math, os, re, subprocess, sys
from pathlib import Path
import numpy as np
from scipy import signal as ss
sys.path.insert(0, str(Path(__file__).resolve().parent))
import harkat as H
import awaazein as AW
import spotting as S
import rachna as RC

SR = 44100   # sutradhar/voice ke saath ek hi SR (warna stems misalign)
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MAP_PATH = ROOT / "knowledge" / "world-map.json"


# ----------------------------------------------------------------- basics
def db2a(db): return 10.0 ** (np.asarray(db, dtype=np.float64) / 20.0)
def a2db(a): return 20.0 * np.log10(np.maximum(np.abs(a), 1e-12))

def sos_bp(lo, hi, order=2): return ss.butter(order, [lo / (SR / 2), min(hi, SR / 2 - 100) / (SR / 2)], "band", output="sos")
def sos_lp(f, order=2): return ss.butter(order, min(f, SR / 2 - 100) / (SR / 2), "low", output="sos")
def sos_hp(f, order=2): return ss.butter(order, f / (SR / 2), "high", output="sos")
def filt(sos, x): return ss.sosfilt(sos, x, axis=-1)

def pink(n, rng):
    """1/f noise (kudrati shor) — white noise se zyada asli."""
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.arange(len(X)); f[0] = 1
    y = np.fft.irfft(X / np.sqrt(f), n)
    return y / (np.std(y) + 1e-12)

def smooth_rand(n, rate_hz, rng, lo=0.0, hi=1.0):
    """Dheere badalne wali random lehar (hawa ke jhonke, nadi ka utar-chadhav)."""
    k = max(2, int(n / SR * rate_hz) + 2)
    pts = rng.uniform(lo, hi, k)
    x = np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)
    w = int(SR / max(rate_hz, 0.05) / 2) | 1
    if 3 < w < n:
        h = np.hanning(w); x = ss.fftconvolve(np.pad(x, w // 2, mode="edge"), h / h.sum(), mode="valid")[:n]
    return x

def env_ar(n, a_s, d_s):
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(a_s, 1e-4)) * np.exp(-np.maximum(0, t - a_s) / max(d_s, 1e-4))
    return e

def add_at(buf, sig, t0):
    """buf: (2,N) ya (N,), sig ko t0 second par jodo."""
    i = int(t0 * SR)
    if i >= buf.shape[-1] or i + sig.shape[-1] <= 0: return
    s0 = max(0, -i); i = max(0, i)
    m = min(buf.shape[-1] - i, sig.shape[-1] - s0)
    buf[..., i:i + m] += sig[..., s0:s0 + m]


# ----------------------------------------------------------------- spatial
def pan_mono(x, pan):
    """Equal-power pan. pan: -1 (baayein) .. +1 (daayein); scalar ya array."""
    p = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    return np.vstack([x * np.cos(p), x * np.sin(p)])

def place(x, pan=0.0, dist=1.0):
    """Mono awaaz ko jagah do: door = dheemi + upar ki frequency kam + zyada goonj (send)."""
    d = np.maximum(np.asarray(dist, dtype=np.float64), 0.3)
    dm = float(np.mean(d))
    cut = 16000.0 / (1 + 0.45 * (dm - 1)) if dm > 1 else 18000.0
    y = filt(sos_lp(cut), x)
    y = y * (1.0 / d)                           # inverse distance
    dry = pan_mono(y, pan)
    send = np.clip(0.12 + 0.07 * dm, 0.1, 0.55)  # door wali cheez me goonj zyada
    return dry, dry * send

def place_wide(l, r, pan, width, dist=1.0):
    """Chaudi awaaz (nadi, hawa): do alag stream, beech ka centre pan hota hai."""
    m, s = (l + r) / 2, (l - r) / 2 * width
    d = np.maximum(np.asarray(dist, dtype=np.float64), 0.3)
    dm = float(np.mean(d))
    cut = 16000.0 / (1 + 0.45 * (dm - 1)) if dm > 1 else 18000.0
    m, s = filt(sos_lp(cut), m) / d, filt(sos_lp(cut), s) / d
    st = pan_mono(m, pan)
    st[0] += s; st[1] -= s
    send = np.clip(0.10 + 0.06 * dm, 0.08, 0.5)
    return st, st * send

_IR_CACHE = {}
def outdoor_reverb(x, rt=0.9, seed=7):
    """Khuli jagah ki halki goonj: decorrelated decaying noise IR (comb filter NAHI — metallic echo se bachav)."""
    key = (rt, seed)
    if key not in _IR_CACHE:
        rng = np.random.default_rng(seed)
        n = int(SR * rt); t = np.arange(n) / SR
        dec = np.exp(-6.9 * t / rt)
        irs = []
        for ch in range(2):
            ir = rng.standard_normal(n) * dec
            ir = filt(sos_lp(5500), ir)
            ir[: int(0.012 * SR)] = 0                         # 12 ms pre-delay
            # kuch early reflections (zameen, ped)
            for dt, g in [(0.017, 0.5), (0.029, 0.35), (0.043, 0.28), (0.061, 0.2)]:
                ir[int((dt + 0.003 * ch) * SR)] += g * (1 if rng.random() > .5 else -1)
            irs.append(ir / np.sqrt(np.sum(ir ** 2)))
        _IR_CACHE[key] = irs
    irs = _IR_CACHE[key]
    return np.vstack([ss.oaconvolve(x[0], irs[0])[: x.shape[1]], ss.oaconvolve(x[1], irs[1])[: x.shape[1]]])


# ----------------------------------------------------------------- procedural synths
def syn_river(n, rng, flow=1.0):
    """Bahti nadi: neeche ka shor + hazaaron chhote bulbule (Farnell 'babbling brook' tarika)."""
    out = []
    for ch in range(2):
        bed = filt(sos_bp(150, 1800), pink(n, rng)) * 0.30
        bed *= 0.75 + 0.25 * smooth_rand(n, 0.25, rng)
        hiss = filt(sos_bp(1800, 7000), rng.standard_normal(n)) * 0.05
        bub = np.zeros(n)
        count = int(n / SR * 110 * flow)
        for _ in range(count):
            f0 = math.exp(rng.uniform(math.log(320), math.log(1900)))
            dur = rng.uniform(0.010, 0.045)
            m = int(dur * SR); t = np.arange(m) / SR
            f = f0 * (1 + rng.uniform(0.4, 1.6) * t / dur)        # bulbula upar jaata sur
            ph = 2 * np.pi * np.cumsum(f) / SR
            a = rng.lognormal(-1.2, 0.6) * np.exp(-t / (dur / 3.5)) * np.minimum(1, t / 0.0015)
            i = rng.integers(0, max(1, n - m))
            bub[i:i + m] += a * np.sin(ph)
        bub = filt(sos_bp(250, 4000), bub) * 0.16
        out.append(bed + hiss + bub)
    return out

def syn_wind(n, rng):
    g = 0.25 + 0.75 * smooth_rand(n, 0.12, rng) ** 1.5
    return [filt(sos_bp(220, 1600), pink(n, rng)) * g * 0.5 for _ in range(2)]

def syn_leaves(n, rng):
    """Patton ki sarsarahat: jhonke ke saath tez band ka shor + chhoti khadkhad."""
    gust = 0.2 + 0.8 * smooth_rand(n, 0.15, rng) ** 2
    out = []
    for ch in range(2):
        flutter = 0.5 + 0.5 * smooth_rand(n, 14, rng)
        x = filt(sos_bp(1200, 9000), rng.standard_normal(n)) * gust * flutter * 0.28
        crack = (rng.random(n) < 0.0009 * gust) * rng.standard_normal(n) * 1.2
        x += filt(sos_bp(2000, 8000), crack) * 0.4
        out.append(x)
    return out

def syn_rain(n, rng):
    out = []
    for ch in range(2):
        x = filt(sos_bp(400, 9000), pink(n, rng)) * 0.4
        drops = (rng.random(n) < 0.004) * rng.standard_normal(n)
        x += filt(sos_bp(1500, 7000), drops) * 0.8
        out.append(x * (0.85 + 0.15 * smooth_rand(n, 0.2, rng)))
    return out

def syn_crickets(n, rng):
    out = []
    for ch in range(2):
        x = np.zeros(n); t = np.arange(n) / SR
        for k in range(3):
            f = rng.uniform(4200, 5200); rate = rng.uniform(14, 22)
            chirp = (np.sin(2 * np.pi * rate * t + rng.uniform(0, 6)) > 0.55).astype(float)
            chirp *= (np.sin(2 * np.pi * rng.uniform(0.3, 0.6) * t + rng.uniform(0, 6)) > -0.2)
            chirp = ss.fftconvolve(chirp, np.hanning(120) / 60, "same")
            x += np.sin(2 * np.pi * f * t) * chirp * rng.uniform(0.3, 1.0) / (1 + k)
        out.append(x * 0.15)
    return out

def _tone(freq_track, amps=(1.0, 0.18, 0.05)):
    ph = 2 * np.pi * np.cumsum(freq_track) / SR
    return sum(a * np.sin((h + 1) * ph) for h, a in enumerate(amps))

def syn_bird(rng):
    """Ek chidiya ki aawaz — kai prakar ki, har baar thodi alag."""
    kind = rng.choice(["seeti", "trill", "chirp2", "chatter"], p=[0.3, 0.3, 0.25, 0.15])
    if kind == "seeti":
        d = rng.uniform(0.15, 0.3); m = int(d * SR); x = np.linspace(0, 1, m)
        f = rng.uniform(2600, 3400) + rng.uniform(800, 1500) * np.sin(np.pi * x) - 400 * x
        return _tone(f) * np.sin(np.pi * x) ** 0.7
    if kind == "trill":
        notes = rng.integers(6, 14); f0 = rng.uniform(3800, 5200); parts = []
        for k in range(notes):
            d = rng.uniform(0.025, 0.045); m = int(d * SR); x = np.linspace(0, 1, m)
            f = f0 * (1.15 - 0.3 * x) * (1 - 0.01 * k)
            parts += [_tone(f, (1, .1)) * np.sin(np.pi * x), np.zeros(int(rng.uniform(.01, .025) * SR))]
        return np.concatenate(parts) * 0.8
    if kind == "chirp2":
        parts = []
        for k in range(2):
            d = rng.uniform(0.08, 0.14); m = int(d * SR); x = np.linspace(0, 1, m)
            f = rng.uniform(2200, 3000) + (900 if k else -300) * x
            parts += [_tone(f) * np.sin(np.pi * x), np.zeros(int(0.07 * SR))]
        return np.concatenate(parts)
    parts = []
    for k in range(rng.integers(4, 9)):
        d = rng.uniform(0.015, 0.04); m = int(d * SR); x = np.linspace(0, 1, m)
        f = rng.uniform(5000, 7000) - rng.uniform(500, 1500) * x
        parts += [_tone(f, (1,)) * np.sin(np.pi * x) * rng.uniform(.4, 1), np.zeros(int(rng.uniform(.02, .09) * SR))]
    return np.concatenate(parts) * 0.6

def syn_koel(rng):
    """Koel ki 'ku-oo' — do sur, har baar thoda upar."""
    parts = []; base = rng.uniform(700, 820)
    for k in range(rng.integers(2, 5)):
        d = 0.42; m = int(d * SR); x = np.linspace(0, 1, m)
        f = base * (1 + 0.04 * k) * (1 + 0.35 * np.clip(x * 2.2 - 0.4, 0, 1)) * (1 + 0.006 * np.sin(2 * np.pi * 6 * x * d))
        e = np.sin(np.pi * x) ** 0.5 * np.minimum(1, (1 - x) * 4)
        parts += [_tone(f, (1, .25, .08)) * e, np.zeros(int(0.32 * SR))]
    return np.concatenate(parts)

def syn_thunder(rng):
    d = rng.uniform(3, 5.5); n = int(d * SR); t = np.arange(n) / SR
    x = filt(sos_lp(420), pink(n, rng)) * np.exp(-t / (d / 3)) * np.minimum(1, t / 0.08)
    x += filt(sos_bp(60, 900), rng.standard_normal(n)) * np.exp(-t / 0.35) * 0.6
    return x * (0.6 + 0.4 * smooth_rand(n, 3, rng))

def syn_step(rng, surface="leaves"):
    """Ek kadam: zameen ki 'thap' + surface ki khadkhad (patte / mitti / patthar / paani)."""
    if surface == "water":
        n = int(0.35 * SR); t = np.arange(n) / SR
        x = filt(sos_bp(300, 3500), rng.standard_normal(n)) * np.exp(-t / 0.09) * 0.8
        return x + filt(sos_lp(180), rng.standard_normal(n)) * np.exp(-t / 0.05) * 0.6
    dur = {"leaves": 0.24, "soil": 0.14, "stone": 0.10}.get(surface, 0.2)
    n = int(dur * SR); t = np.arange(n) / SR
    thud = filt(sos_lp(160), rng.standard_normal(n)) * np.exp(-t / 0.03) * (1.4 if surface == "soil" else 0.9)
    dens = {"leaves": 0.035, "soil": 0.012, "stone": 0.006}.get(surface, 0.02)
    grains = (rng.random(n) < dens * np.exp(-t / (dur / 2.5))) * rng.standard_normal(n)
    band = {"leaves": (900, 8500), "soil": (300, 2500), "stone": (1800, 7000)}.get(surface, (800, 6000))
    crunch = filt(sos_bp(*band), grains) * {"leaves": 2.2, "soil": 1.2, "stone": 2.6}.get(surface, 1.5)
    # heel -> toe: do hisse
    second = np.zeros(n); k = int(0.045 * SR)
    second[k:] = crunch[: n - k] * 0.6
    return (thud + crunch + second) * rng.uniform(0.75, 1.1)

BED_SYNTH = {"river": syn_river, "wind": syn_wind, "leaves": syn_leaves, "rain": syn_rain, "crickets": syn_crickets}
EVENT_SYNTH = {"birds": syn_bird, "koel": syn_koel, "thunder": syn_thunder}


# ----------------------------------------------------------------- library (asli recordings)
def decode(path, sr=SR):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"],
                       capture_output=True, check=True)
    a = np.frombuffer(p.stdout, dtype=np.float32).reshape(-1, 2).T.astype(np.float64)
    return a

class Library:
    """astra/library me naam se file dhundho. Mile to asli recording, warna synth."""
    def __init__(self, root):
        self.files = []
        if root and Path(root).exists():
            for p in Path(root).rglob("*"):
                if p.suffix.lower() in (".wav", ".mp3", ".flac", ".ogg", ".m4a"):
                    self.files.append(p)
    def find(self, patterns, rng):
        hits = [p for p in self.files if any(fnmatch.fnmatch(p.name.lower(), pat) for pat in patterns)]
        return hits[rng.integers(len(hits))] if hits else None

def loop_to(a, n, rng, xf_s=2.0):
    """Recording ko lamba karo: random jagah se shuru, 2s crossfade par loop (jhatka nahi)."""
    L = a.shape[1]
    if L >= n:
        s = rng.integers(0, L - n + 1); return a[:, s:s + n].copy()
    xf = min(int(xf_s * SR), L // 3)
    fin, fout = np.sqrt(np.linspace(0, 1, xf)), np.sqrt(np.linspace(1, 0, xf))
    out = np.zeros((2, n + L)); pos = 0
    while pos < n:
        st = rng.integers(0, max(1, L // 3)) if pos == 0 else 0   # sirf pehli baar random jagah
        piece = a[:, st:].copy(); Lp = piece.shape[1]
        piece[:, :xf] *= fin; piece[:, -xf:] *= fout
        out[:, pos:pos + Lp] += piece
        pos += Lp - xf
    return out[:, :n]


# ----------------------------------------------------------------- scene planning
def load_map(path=MAP_PATH):
    with open(path, encoding="utf-8") as f: return json.load(f)

def detect(text, words):
    """Poora shabd milao (spotting.has): 'आग' != 'आगे', 'बह' != 'बहुत'. Jad ke liye shabd ke ant me '*'."""
    return S.has(text, words)

def plan_scene(lines, total, wmap, overrides=None):
    """
    lines: [{who, text, start, end}] (naye timeline par).
    Return: {layer: gain-envelope (N,)}, walks, river_pan, events_extra
    """
    n = int(total * SR)
    kw = wmap["keywords"]; layers = wmap["layers"]
    env = {k: np.zeros(n) for k, v in layers.items() if v["kind"] in ("bed", "event")}
    present = {k: False for k in env}
    walks = []
    ramp = int(1.2 * SR)  # 1.2 s smooth fade (aapke system ka niyam)
    for i, ln in enumerate(lines):
        nxt = lines[i + 1]["start"] if i + 1 < len(lines) else total
        a, b = int(max(0, ln["start"] - 0.6) * SR), int(min(total, nxt + 1.5) * SR)
        for k in env:
            if k in kw and detect(ln["text"], kw[k]):
                present[k] = True
                env[k][a:b] = np.maximum(env[k][a:b], 1.0)       # zikr par ubhro (+6 dB tak)
        if detect(ln["text"], kw.get("footsteps", [])):
            surf = "leaves"
            for s, words in wmap["surfaces"].items():
                if s.startswith("_"): continue
                if detect(ln["text"], words): surf = s
            walks.append({"t0": ln["start"] + 0.2, "t1": nxt + 0.4, "surface": surf, "pan": ln.get("pan", 0.0)})
    # yaad: ek baar zikr hua to scene me rehta hai (base 0.5 = -6 dB)
    for k in env:
        first = next((int(max(0, l["start"] - 0.6) * SR) for l in lines if k in kw and detect(l["text"], kw[k])), None)
        if first is not None and layers[k]["kind"] == "bed":
            env[k][first:] = np.maximum(env[k][first:], 0.5)
        if first is not None and layers[k]["kind"] == "event":
            env[k][first:] = np.maximum(env[k][first:], 0.6)
    if overrides:
        for o in overrides.get("objects", []):
            k = o["sound"]; env.setdefault(k, np.zeros(n)); present[k] = True
            a, b = int(o.get("t0", 0) * SR), int(min(total, o.get("t1", total)) * SR)
            env[k][a:b] = np.maximum(env[k][a:b], o.get("level", 0.6))
        walks += overrides.get("walks", [])
    win = np.hanning(2 * ramp + 1); win /= win.sum()
    for k in env:
        if not isinstance(env[k], np.ndarray): continue
        if env[k].any():
            env[k] = ss.fftconvolve(np.pad(env[k], ramp, mode="edge"), win, "valid")[:n]
    env["_mentioned"] = {k for k, v in present.items() if v}
    return env, walks


# ----------------------------------------------------------------- render world
def render_world(total, env, walks, wmap, lib, rng, tod="day", river_pass=True):
    n = int(total * SR)
    dry = np.zeros((2, n)); wet = np.zeros((2, n))
    layers = wmap["layers"]; todm = wmap["time_of_day"].get(tod, {})
    used = {}
    mentioned = env.get("_mentioned", set())
    for k, e in env.items():
        if k.startswith("_") or not e.any(): continue
        L = layers[k]; mult = todm.get(k, 1.0)
        if k in mentioned: mult = max(mult, 1.0)        # script me likha hai to din/raat se band mat karo
        if mult <= 0: continue
        g = db2a(L["base_db"]) * mult
        f = lib.find(L.get("lib", []), rng)
        if L["kind"] == "bed":
            if f is not None:
                a = loop_to(decode(f), n, rng); l, r = a[0], a[1]; used[k] = f.name
            elif L.get("synth", True) and k in BED_SYNTH:
                l, r = BED_SYNTH[k](n, rng); used[k] = "synth"
            else:
                used[k] = "MISSING (library me file daalo)"; continue
            l = l / (np.sqrt(np.mean(l ** 2)) + 1e-9) * 0.1; r = r / (np.sqrt(np.mean(r ** 2)) + 1e-9) * 0.1
            pan, dist = 0.0, L.get("dist", 1.5)
            if k == "river" and river_pass and walks:
                # nadi paas se guzarti hai: baayein door -> paas -> daayein door
                on = np.flatnonzero(e > 0.05)
                a0, a1 = (on[0], on[-1]) if len(on) else (0, n - 1)
                x = np.clip((np.arange(n) - a0) / max(1, a1 - a0) * 2 - 1, -1, 1)
                pan = 0.7 * x                       # baayein -> daayein
                dist = 1.0 + 1.6 * x ** 2           # beech me sabse paas
            st, sd = place_wide(l, r, pan, L.get("width", 0.8), dist if np.isscalar(dist) else 1.0)
            if not np.isscalar(dist):
                st, sd = st / dist, sd / dist
            dry += st * g * e; wet += sd * g * e
        elif L["kind"] == "event":
            rate = L.get("rate_per_min", 6) * mult / 60.0
            t = rng.exponential(1 / max(rate, 1e-3))
            cnt = 0
            while t < total:
                lvl = e[min(int(t * SR), n - 1)]
                if lvl > 0.05 and rng.random() < lvl:
                    if f is not None:
                        a = decode(f).mean(0); m = min(a.shape[0], int(rng.uniform(2, 6) * SR))
                        x = a[:m] * np.minimum(1, np.linspace(0, m / SR, m) / 0.05) * np.minimum(1, np.linspace(m / SR, 0, m) / 0.3)
                        x /= (np.max(np.abs(x)) + 1e-9)
                    elif L.get("synth", True) and k in EVENT_SYNTH:
                        x = EVENT_SYNTH[k](rng); x /= (np.max(np.abs(x)) + 1e-9)
                    else:
                        break
                    d = rng.uniform(*L["dist"]); p = rng.uniform(-0.9, 0.9)
                    a1, a2 = place(x * 0.35, p, d)
                    add_at(dry, a1 * g * lvl, t); add_at(wet, a2 * g * lvl, t)
                    cnt += 1
                    if k == "birds" and rng.random() < 0.35:       # jawab deti doosri chidiya
                        x2 = EVENT_SYNTH["birds"](rng) if f is None else x
                        x2 /= (np.max(np.abs(x2)) + 1e-9)
                        b1, b2 = place(x2 * 0.3, -p * rng.uniform(.5, 1), rng.uniform(*L["dist"]))
                        tt = t + rng.uniform(0.4, 1.5); add_at(dry, b1 * g * lvl, tt); add_at(wet, b2 * g * lvl, tt)
                t += rng.exponential(1 / max(rate, 1e-3))
            used[k] = (f.name if f is not None else "synth") + f" x{cnt}"
    # hamesha: halki "air" (recording jaisi zindagi)
    air = np.vstack([filt(sos_bp(60, 6000), pink(n, rng)) for _ in range(2)]) * db2a(-58)
    dry += air
    world = dry + outdoor_reverb(wet, rt=0.9)
    world = filt(sos_hp(45), world)
    return world, used


# ----------------------------------------------------------------- FX bus (harkat) + bhaav
# Peak dBFS jab awaaz (voice) ka RMS -20 dBFS ho. Yeh normalize nahi hote — isliye dabte nahi.
FX_PEAK_DB = {"walk": -7, "run": -5, "stop": -10, "fall": -3, "jump": -5, "twig": -7,
              "splash": -5, "wolf_walk": -9, "howl": -22, "growl": -9, "thunder": -2,
              "heart": -14, "pant": -16}

def apply_emotion(env, emo, total):
    """Bhaav ke hisaab se duniya badle: dar -> chidiyan chup, hawa tez; khushi -> chidiyan zyada."""
    n = int(total * SR)
    rules = {"dar": {"birds": 0.08, "koel": 0.0, "wind": 1.7, "crickets": 0.4},
             "khushi": {"birds": 1.5, "koel": 1.3},
             "dukh": {"birds": 0.5, "wind": 0.7}}
    for a, b, e in emo:
        for k, m in rules.get(e, {}).items():
            if k not in env or not isinstance(env[k], np.ndarray): continue
            i, j = int(max(0, a - 0.4) * SR), int(min(total, b + 1.5) * SR)
            w = np.ones(n); w[i:j] = m
            r = int(1.0 * SR); h = np.hanning(2 * r + 1); h /= h.sum()
            w = ss.fftconvolve(np.pad(w, r, mode="edge"), h, "valid")[:n]
            env[k] = env[k] * w
            if m > 1 and not env[k].any(): pass
    return env

def render_fx(total, events, emo, rng):
    n = int(total * SR); dry = np.zeros((2, n)); wet = np.zeros((2, n)); log = {}
    def put(x, t, pan, dist, kind):
        x = H.norm(x) * db2a(FX_PEAK_DB[kind])
        d1, d2 = place(x, pan, dist)
        add_at(dry, d1 * dist, t); add_at(wet, d2 * dist, t)   # place() dheema karta hai; peak ko pas ke hisaab rakho
        log[kind] = log.get(kind, 0) + 1
    for e in events:
        k = e["kind"]
        if k in ("walk", "run"):
            t, side, step_s = e["t0"], 1, (0.52 if k == "walk" else 0.31)
            force = 1.0 if k == "walk" else 1.35
            while t < e["t1"]:
                put(H.step(rng, e.get("surface", "leaves"), force), t, e.get("pan", 0) + side * 0.05, 1.0, k)
                t += step_s * rng.uniform(0.93, 1.07); side = -side
            if k == "run":
                put(H.panting(rng, e["t1"] - e["t0"] + 1.5), e["t0"] + 0.5, e.get("pan", 0), 1.0, "pant")
        elif k == "stop":   put(H.scuff(rng, e.get("surface", "leaves")), e["t0"], e.get("pan", 0), 1.0, k)
        elif k == "fall":   put(H.fall(rng), e["t0"], e.get("pan", 0), 1.0, k)
        elif k == "jump":   put(H.jump(rng), e["t0"], e.get("pan", 0), 1.0, k)
        elif k == "twig":   put(H.twig(rng), e["t0"], e.get("pan", 0.3), 1.3, k)
        elif k == "splash": put(H.splash(rng), e["t0"], e.get("pan", 0), 1.0, k)
        elif k == "howl":   put(H.wolf_howl(rng), e["t0"], e.get("pan", -0.5), e.get("dist", 4.0) ** 0.5, k)
        elif k == "growl":  put(H.growl(rng), e["t0"], e.get("pan", 0.3), 1.0, k)
        elif k == "thunder":put(H.thunder(rng, e.get("near", True)), e["t0"], e.get("pan", 0.2), 1.0, k)
        elif k == "wolf_walk":
            t = e["t0"]; T = max(e["t1"] - e["t0"], 0.5)
            while t < e["t1"]:
                x = (t - e["t0"]) / T
                pan = e["pan0"] + (e["pan1"] - e["pan0"]) * x
                dist = 3.5 - 2.3 * math.sin(math.pi * min(1, x * 1.4) / 2)   # door se paas aata
                cyc = H.paw_cycle(rng, e.get("surface", "leaves")) * db2a(FX_PEAK_DB["wolf_walk"]) / dist
                d1, d2 = place(cyc, pan, 1.0); add_at(dry, d1, t); add_at(wet, d2 * (1 + 0.3 * dist), t)
                log["wolf_walk"] = log.get("wolf_walk", 0) + 1
                t += 0.48 * rng.uniform(0.95, 1.08)
    for a, b, e in emo:
        if e == "dar":
            put(H.heartbeat(rng, b - a + 1.0, bpm=rng.uniform(92, 108)), a, 0.0, 1.0, "heart")
    fx = dry + outdoor_reverb(wet * 1.6, rt=1.1, seed=5)
    return filt(sos_hp(35), fx), log


# ----------------------------------------------------------------- cue sheet: rozmarra, aawa-jaahi, mausam, andar/bahar
def smooth_env(x, sec):
    r = max(1, int(sec * SR)); h = np.hanning(2 * r + 1); h /= h.sum()
    return ss.fftconvolve(np.pad(x, r, mode="edge"), h, "valid")[: len(x)]

def place_env(places, total):
    """1 = andar (ghar/kamra), 0 = bahar. 0.5 s me badalta hai."""
    n = int(total * SR); ind = np.zeros(n)
    for p in places:
        if p["place"] == "indoor": ind[int(p["t0"] * SR):int(p["t1"] * SR)] = 1.0
    return smooth_env(ind, 0.5)

def indoor_muffle(world, ind):
    """Andar ho to bahar ki duniya deewar ke peeche: 900 Hz se upar kam, 8 dB dheemi."""
    if not ind.any(): return world
    m = filt(sos_lp(900, 2), world) * db2a(-8)
    return world * (1 - ind) + m * ind

def apply_weather(env, spans, kb, total, events, cues, rng):
    W = kb["weather"]["states"]; n = int(total * SR)
    for sp in spans:
        d = W.get(sp["state"], {}); i, j = int(sp["t0"] * SR), int(min(total, sp["t1"]) * SR)
        if j <= i: continue
        for bed, lvl in d.get("beds", {}).items():
            if bed in env and isinstance(env[bed], np.ndarray):
                w = np.zeros(n); w[i:j] = lvl; env[bed] = np.maximum(env[bed], smooth_env(w, 1.2))
        if "birds" in d and "birds" in env:
            w = np.ones(n); w[i:j] = d["birds"]; env["birds"] = env["birds"] * smooth_env(w, 1.2)
            if d["birds"] > 1 and not env["birds"][i:j].any():
                w2 = np.zeros(n); w2[i:j] = 0.8; env["birds"] = np.maximum(env["birds"], smooth_env(w2, 1.0))
        if d.get("thunder_every_s"):
            t = sp["t0"] + rng.uniform(1, 4)
            while t < sp["t1"]:
                events.append(dict(kind="thunder", t0=t, pan=rng.uniform(-0.6, 0.6), near=rng.random() < 0.4))
                t += rng.uniform(*d["thunder_every_s"])
        for name in d.get("events", []):
            cues.append(dict(event=name, t=sp["t0"] + 0.5, t_end=sp["t1"], pan=-0.3, dist=2.0, level=kb["events"][name]["level"], source="weather"))
        for name in d.get("events_once", []):
            cues.append(dict(event=name, t=sp["t0"] + rng.uniform(1, 3), pan=0.6, dist=5.0, level=kb["events"][name]["level"], source="weather"))
    return env

def sound_for(name, kb, lib, rng, dur=None, sit=None):
    """Event ki awaaz — kram: (1) seekhi hui awaaz se naya roop (rachna, halat ke hisaab se),
    (2) library ki recording, (3) awaazein.py ka synth."""
    e = kb["events"].get(name, {})
    if RC.is_learned(name):
        y, info = RC.variant(name, sit or {}, rng, dur)
        if y is not None:
            return y, f"seekha:{info['similarity']}/{'ok' if info['passed'] else 'x'}"
    f = lib.find(e.get("lib", []), rng) if e.get("lib") else None
    if f is not None:
        x = decode(f).mean(0)
        if dur and len(x) < dur * SR:
            reps = int(dur * SR / len(x)) + 1; x = np.tile(x, reps)
        return x[: int(dur * SR)] if dur else x, f.name
    syn = e.get("synth") or name
    if syn in AW.REGISTRY:
        x = AW.REGISTRY[syn](rng)
        if dur:                                   # halat (state): jab tak chale tab tak dohraao
            while len(x) < dur * SR: x = np.concatenate([x, AW.REGISTRY[syn](rng)])
            x = x[: int(dur * SR)]; k = min(len(x) // 4, int(0.3 * SR)); x[-k:] *= np.linspace(1, 0, k)
        return x, "synth"
    return None, "MISSING"

def situation_at(t, line_text, sheet):
    sit = RC.situation_from_text(line_text or "")
    for em in sheet.get("emotions", []):
        if em["t0"] - 0.5 <= t <= em["t1"] + 0.5: sit["emotion"] = em["e"]
    return sit

def render_sheet(total, sheet, kb, lib, rng, ind, lines=None):
    n = int(total * SR); dry = np.zeros((2, n)); wet = np.zeros((2, n)); log = {}
    def put(x, t, pan, dist, peak_db, key):
        x = H.norm(x) * db2a(peak_db)
        d1, d2 = place(x, pan, dist)
        k = ind[min(int(t * SR), n - 1)] if len(ind) else 0
        add_at(dry, d1 * dist, t); add_at(wet, d2 * dist * (1 + 0.6 * k), t)
        log[key] = log.get(key, 0) + 1
    for c in sheet["cues"]:
        dur = (c["t_end"] - c["t"]) if c.get("t_end") else None
        txt = lines[c["line"]]["text"] if lines and c.get("line") is not None and c["line"] < len(lines) else ""
        x, src = sound_for(c["event"], kb, lib, rng, dur, situation_at(c["t"], txt, sheet))
        if src.startswith("seekha"): log["roop:" + c["event"]] = src
        if x is None: log[c["event"] + " (MISSING)"] = log.get(c["event"] + " (MISSING)", 0) + 1; continue
        reps = c.get("repeat", [1, 0])
        for r in range(int(reps[0])):
            put(x, c["t"] + r * reps[1], c["pan"], c["dist"], c["level"], c["event"])
    for m in sheet["motion"]:
        k = m["kind"]
        if k in ("approach", "leave"):
            t, side = m["t0"], 1; T = max(0.5, m["t1"] - m["t0"])
            surf = "tile" if ind[min(int(t * SR), n - 1)] > 0.5 else "leaves"
            while t < m["t1"]:
                x = (t - m["t0"]) / T
                pan = m["pan0"] + (m["pan1"] - m["pan0"]) * x
                dist = (3.5 - 2.5 * x) if k == "approach" else (1.0 + 2.5 * x)
                st = H.step(rng, "stone" if surf == "tile" else surf) if surf == "tile" else H.step(rng, surf)
                put(st, t, pan + side * 0.04, max(1.0, dist), FX_PEAK_DB["walk"] - 3 * (dist - 1), "motion:" + k)
                t += 0.55 * rng.uniform(0.93, 1.07); side = -side
        elif k == "door":       put(AW.door_open(rng), m["t"], -0.5, 2.0, -12, "motion:door")
        elif k == "door_close": put(AW.door_close(rng), m["t"], 0.6, 2.5, -10, "motion:door_close")
        elif k == "sit":
            put(AW.cloth_rustle(rng), m["t"], m.get("pan", 0), 1.0, -19, "motion:sit")
            if ind[min(int(m["t"] * SR), n - 1)] > 0.5: put(AW.chair_drag(rng), m["t"] - 0.3, m.get("pan", 0), 1.0, -17, "motion:sit")
        elif k == "stand":      put(AW.cloth_rustle(rng, 0.6), m["t"], m.get("pan", 0), 1.0, -20, "motion:stand")
    room = outdoor_reverb(wet, rt=0.45, seed=9); out = outdoor_reverb(wet, rt=1.0, seed=6)
    k = ind[None, :] if len(ind) else 0
    fx = dry + room * k + out * (1 - k)
    return filt(sos_hp(35), fx), log

def phone_voice(v):
    """Phone ke us paar ki awaaz: 300–3400 Hz, halki ghis (codec), patli."""
    y = filt(sos_bp(320, 3300, 3), v)
    y = np.tanh(y * 3) / 3
    return y * 1.1


# ----------------------------------------------------------------- pacing (insaan jaise ruke)
def pause_after(text, next_who, who, scene_break, wmap, rng):
    P = wmap["pauses_s"]
    t = text.strip()
    if scene_break: lo, hi = P["scene_change"]
    elif t.endswith(("?", "!")): lo, hi = P["question_exclaim"]
    elif t.endswith(("।", ".", "|")): lo, hi = P["sentence"]
    elif t.endswith((",", "—", "-")): lo, hi = P["comma"]
    else: lo, hi = P["sentence"]
    p = rng.uniform(lo, hi)
    if next_who is not None and next_who != who: p = max(p, rng.uniform(*P["speaker_change"]))
    return p

SCENE_WORDS = ["सुबह", "दोपहर", "शाम", "रात", "थोड़ी देर बाद", "कुछ देर बाद", "अगले दिन", "उस दिन", "कई दिन", "फिर एक दिन",
               "एक दिन", "उधर", "इधर", "subah", "dopahar", "shaam", "raat", "thodi der baad", "agle din", "ek din"]
def is_scene_start(text):
    """Line samay-badalne wale shabd se shuru ho ('शाम को...', 'थोड़ी देर बाद...') to pehle lamba ruka."""
    t = text.strip()
    return any(t.startswith(w) for w in SCENE_WORDS)

def repace_lines(voice, line_marks, lines, wmap, rng):
    """Har line ki wav ko naye ruke ke saath dobara jodo. line_marks: [(start,end)] purane voice me."""
    out = []; new = []; t = 0.25
    out.append(np.zeros(int(0.25 * SR)))
    for i, ((s, e), ln) in enumerate(zip(line_marks, lines)):
        seg = voice[int(s * SR):int(e * SR)]
        fade = min(len(seg) // 4, int(0.012 * SR))
        if fade > 0:
            seg = seg.copy(); seg[:fade] *= np.linspace(0, 1, fade); seg[-fade:] *= np.linspace(1, 0, fade)
        new.append(dict(ln, start=t, end=t + len(seg) / SR)); out.append(seg); t += len(seg) / SR
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        brk = ln.get("scene_break", False) or (nxt is not None and is_scene_start(nxt["text"]))
        p = pause_after(ln["text"], nxt.get("who") if nxt else None, ln.get("who"), brk, wmap, rng)
        out.append(np.zeros(int(p * SR))); t += p
    return np.concatenate(out), new

def auto_repace(voice, wmap, rng, thr_db=-45.0):
    """Bina script ke: chup jagah dhundho aur unhe insaan jaise lamba karo.
    Lambe gap = vakya ka ant (0.45–0.7 s), chhote = comma (0.16–0.26 s), har ~5 vakya par saans (1.2 s)."""
    hop = 240
    fr = np.lib.stride_tricks.sliding_window_view(np.pad(voice, (0, 480)), 480)[::hop]
    d = a2db(np.sqrt(np.mean(fr ** 2, axis=1)))
    quiet = d < thr_db
    runs = []; i = 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]: j += 1
            if (j - i) * hop / SR >= 0.12: runs.append((i * hop, j * hop))
            i = j
        else: i += 1
    if not runs: return voice, []
    lens = np.array([(b - a) / SR for a, b in runs])
    cut = np.quantile(lens, 0.6)
    P = wmap["pauses_s"]
    pieces = []; last = 0; breaths = []; t_new = 0.0; sent = 0
    for (a, b), L in zip(runs, lens):
        mid = (a + b) // 2
        pieces.append(voice[last:mid]); t_new += (mid - last) / SR
        if L >= cut:
            sent += 1
            target = rng.uniform(*P["sentence"])
            if sent % 4 == 0:
                target = rng.uniform(1.2, 1.8); breaths.append((t_new + 0.15, t_new + target - 0.1))
        else:
            target = max(L, rng.uniform(*P["comma"]))
        add = max(0.0, target - L)
        pieces.append(np.zeros(int(add * SR))); t_new += add
        last = mid
    pieces.append(voice[last:])
    return np.concatenate(pieces), breaths


# ----------------------------------------------------------------- mix
def voice_chain(v):
    """Awaaz: 90 Hz se neeche ka gol-mol hatao, 220 Hz par halka kam (bhaaripan), bas. Zyada processing nahi."""
    v = filt(sos_hp(100, 2), v)
    b, a = _peaking(230, -3.5, 0.9)
    return ss.lfilter(b, a, v)

def _peaking(f0, gain_db, q):
    A = 10 ** (gain_db / 40); w = 2 * np.pi * f0 / SR; al = np.sin(w) / (2 * q)
    b = np.array([1 + al * A, -2 * np.cos(w), 1 - al * A]); a = np.array([1 + al / A, -2 * np.cos(w), 1 - al / A])
    return b / a[0], a / a[0]

def follow(x, att_ms, rel_ms):
    """One-pole attack/release envelope (gain smoothing)."""
    out = np.empty_like(x); aa = math.exp(-1 / (att_ms * SR / 1000)); ar = math.exp(-1 / (rel_ms * SR / 1000))
    y = x[0]
    # vectorised in blocks for speed
    step = 48
    xs = x[::step]; ys = np.empty_like(xs); y = xs[0]
    aa, ar = aa ** step, ar ** step
    for i, v in enumerate(xs):
        y = aa * y + (1 - aa) * v if v < y else ar * y + (1 - ar) * v   # gain neeche jaldi, upar dheere
        ys[i] = y
    return np.interp(np.arange(len(x)), np.arange(len(xs)) * step, ys)

def mix(voice, world, wmap, voice_pan=0.0, lines=None, fx=None, ind=None, phone_lines=()):
    Lv = wmap["levels_db"]
    n = max(len(voice), world.shape[1])
    v = np.pad(voice, (0, n - len(voice))); w = np.pad(world, ((0, 0), (0, n - world.shape[1])))
    v = voice_chain(v)
    v = v / (np.sqrt(np.mean(v[np.abs(v) > 1e-4] ** 2)) + 1e-9) * db2a(-20)      # bolti awaaz ~ -20 dBFS RMS
    ph = np.zeros(n)
    for i in phone_lines or ():
        ln = lines[i]; ph[int(ln["start"] * SR):int(ln["end"] * SR)] = 1.0
    if ph.any():
        k = int(0.01 * SR); ph = np.convolve(ph, np.ones(k) / k, "same")
        v = v * (1 - ph) + phone_voice(v) * ph
    pan = np.full(n, float(voice_pan))
    for ln in (lines or []):
        if "pan" in ln: pan[int(ln["start"] * SR):int(ln["end"] * SR)] = ln["pan"]
    if lines:
        k = int(0.05 * SR); pan = ss.fftconvolve(np.pad(pan, k, mode="edge"), np.hanning(2 * k + 1) / np.hanning(2 * k + 1).sum(), "valid")[:n]
    vst = pan_mono(v, pan) * math.sqrt(2)
    dry_part = vst * (1 - ph)[None, :] if ph.any() else vst                        # phone ki awaaz par goonj nahi
    if ind is not None and len(ind) and ind.any():
        I = np.pad(ind, (0, max(0, n - len(ind))))[:n][None, :]
        vst = vst + outdoor_reverb(dry_part * 0.06, rt=0.7, seed=3) * (1 - I) + outdoor_reverb(dry_part * 0.09, rt=0.4, seed=8) * I
    else:
        vst = vst + outdoor_reverb(dry_part * 0.06, rt=0.7, seed=3)                # bahar khade hone ka ehsaas
    # world level: bolte waqt awaaz se bed_under_speech dB neeche
    wr = np.sqrt(np.mean(w ** 2)) + 1e-12
    w = w / wr * db2a(-20 + Lv["bed_under_speech"] + Lv["duck_db"])
    # ducking: awaaz chal rahi ho to duck_db tak neeche, ruke me wapas (kabhi band nahi)
    c = np.concatenate([[0], np.cumsum(v ** 2)]); k = 2400
    ve = np.sqrt(np.maximum(0, (c[np.minimum(np.arange(n) + k // 2, n)] - c[np.maximum(np.arange(n) - k // 2, 0)]) / k))
    act = np.clip((a2db(ve) + 45) / 15, 0, 1)                                    # 0 = chup, 1 = bol raha
    gain_db = -Lv["duck_db"] * act
    gain = db2a(follow(gain_db, Lv["duck_attack_ms"], Lv["duck_release_ms"]))
    m = vst + w * gain
    # zameen (floor): duniya kabhi -55 dB se neeche nahi — bahar halki hawa, andar kamre ki 'room tone'
    rng0 = np.random.default_rng(99)
    air = np.vstack([filt(sos_bp(80, 3000), pink(n, rng0)) for _ in range(2)])
    room = np.vstack([filt(sos_bp(40, 450), pink(n, rng0)) for _ in range(2)])
    I = np.pad(ind, (0, max(0, n - len(ind))))[:n][None, :] if ind is not None and len(ind) else 0
    m = m + air / np.sqrt(np.mean(air ** 2)) * db2a(-52) * (1 - I) + room / np.sqrt(np.mean(room ** 2)) * db2a(-49) * I
    if fx is not None:
        f = np.pad(fx, ((0, 0), (0, max(0, n - fx.shape[1]))))[:, :n]
        m = m + f * db2a(follow(-2.0 * act, 80, 500))          # FX sirf 2 dB duck — saaf sunai de
    return m

def master(st, out_path, lufs=-16.0, tp=-1.5):
    tmp = Path(out_path).with_suffix(".pre.wav")
    import wave
    x = np.clip(st.T, -1, 1); pcm = (x * 32767).astype("<i2")
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(pcm.tobytes())
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(tmp), "-af", f"loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    j = json.loads(m[m.rfind("{"):m.rfind("}") + 1])
    af = (f"loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
          f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']},"
          f"alimiter=limit={10 ** (tp / 20):.3f}:level=false")
    args = ["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-af", af, "-ar", str(SR), "-ac", "2"]
    args += (["-c:a", "libmp3lame", "-b:a", "192k"] if str(out_path).endswith(".mp3") else [])
    subprocess.run(args + [str(out_path)], check=True)
    tmp.unlink(missing_ok=True)


# ----------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="Duniya engine — realistic world sound, 100% local")
    ap.add_argument("--voice", required=True, help="awaaz ki wav/mp3 (sirf dialogue ho to best)")
    ap.add_argument("--marks", help="story_local.json: lines [{who,text,start,end,bhaav,pan?,scene_break?}]")
    ap.add_argument("--scene", help="scene.json: {time_of_day, objects:[...], walks:[...], lines:[...]}")
    ap.add_argument("--auto-pauses", action="store_true", help="script nahi hai to chup jagah lamba karo")
    ap.add_argument("--library", default=os.environ.get("ASTRA_LIBRARY", str(ROOT / "astra" / "library")))
    ap.add_argument("--tod", default=None, help="morning/day/evening/night")
    ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--llm", default=None, help="local Ollama model (optional), jaise qwen2.5:7b")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    wmap = load_map()
    lib = Library(a.library)
    voice = decode(a.voice).mean(0)
    scene = json.load(open(a.scene, encoding="utf-8")) if a.scene else {}
    tod = a.tod or scene.get("time_of_day", "day")

    lines = []
    if a.marks:
        mk = json.load(open(a.marks, encoding="utf-8"))
        mk = mk.get("lines", mk) if isinstance(mk, dict) else mk
        old = [(m["start"], m["end"]) for m in mk]
        voice, lines = repace_lines(voice, old, mk, wmap, rng)
        breaths = []
    elif a.auto_pauses:
        voice, breaths = auto_repace(voice, wmap, rng)
    else:
        breaths = []
    total = len(voice) / SR + 1.5
    # scene me "breath": i likha ho to us cheez ka samay i-ve saans-ruke se gina jaata hai
    def resolve(o):
        o = dict(o)
        if "breath" in o and breaths:
            b0 = breaths[min(o["breath"], len(breaths)) - 1][0]
            for k in ("t0", "t1"):
                if k in o: o[k] += b0
            o.setdefault("t0", b0)
        if "until_breath" in o and breaths:
            o["t1"] = breaths[min(o["until_breath"], len(breaths)) - 1][0] + o.get("tail", 0.5)
        return o
    for key in ("events", "objects", "walks"):
        scene[key] = [resolve(o) for o in scene.get(key, [])]
    scene["emotions"] = [(r["t0"], r["t1"], r["e"]) for r in (resolve(e) for e in scene.get("emotions_at", []))] + scene.get("emotions", [])
    if not lines and scene.get("lines"):
        lines = scene["lines"]
    if not lines:
        lines = [{"who": "narrator", "text": " ".join(scene.get("keywords", [])), "start": 0.0, "end": total}]
    env, walks = plan_scene(lines, total, wmap, scene)
    kb = S.load_events(); sheet = None
    if a.marks:
        sheet = S.spot(lines, total, kb, wmap, a.llm, Path(a.marks).stem)
        events, emo = list(sheet["actions"]), [(e["t0"], e["t1"], e["e"]) for e in sheet["emotions"]]
    elif scene.get("auto_actions"):
        events, emo = H.plan_actions(lines, total, wmap)
    else:
        events, emo = [], []
    events += [dict(w, kind=w.get("kind", "walk")) for w in walks if a.marks is None or w in scene.get("walks", [])]
    events += scene.get("events", [])
    emo += [tuple(x) for x in scene.get("emotions", [])]
    if scene.get("walk_in_breaths", True):
        events += [{"kind": "walk", "t0": s, "t1": e, "surface": scene.get("surface", "leaves"), "pan": 0.0} for s, e in breaths]
    env = apply_emotion(env, emo, total)
    ind = np.zeros(int(total * SR))
    if sheet:
        env = apply_weather(env, sheet["weather"], kb, total, events, sheet["cues"], rng)
        ind = place_env(sheet["places"], total)
    world, used = render_world(total, env, events, wmap, lib, rng, tod)
    world = indoor_muffle(world, ind)
    fx, fxlog = render_fx(total, events, emo, rng)
    used.update({"fx:" + k: v for k, v in fxlog.items()})
    if sheet:
        fx2, log2 = render_sheet(total, sheet, kb, lib, rng, ind, lines)
        fx = fx + fx2; used.update({"cue:" + k: v for k, v in log2.items()})
    st = mix(voice, world, wmap, lines=lines if a.marks else None, fx=fx, ind=ind,
             phone_lines=sheet["phone_lines"] if sheet else ())
    master(st, a.out, lufs=a.lufs)
    # QA ke liye: ruke sirf awaaz (voice stem) se gino - FX ruke ko bharte hain, par ruka phir bhi ruka hai
    hop = 240; fr = np.lib.stride_tricks.sliding_window_view(np.pad(voice, (0, 480)), 480)[::hop]
    dv = a2db(np.sqrt(np.mean(fr ** 2, 1))); sp = dv > np.percentile(dv, 90) - 14
    gaps, i = [], 0
    while i < len(sp):
        if not sp[i]:
            j = i
            while j < len(sp) and not sp[j]: j += 1
            gaps.append(round((j - i) * hop / SR, 3)); i = j
        else: i += 1
    Path(a.out).with_suffix(".pauses.json").write_text(json.dumps({"voice_gaps_s": [g for g in gaps if g >= 0.1], "duration_s": len(voice) / SR}), encoding="utf-8")
    report = {"out": a.out, "duration_s": round(total, 2), "time_of_day": tod, "layers": used,
              "events": len(events), "emotions": len(emo), "missing": len(sheet["missing"]) if sheet else 0, "breaths": len(breaths), "library_files": len(lib.files)}
    if lines and a.marks:
        Path(a.out).with_suffix(".cues.json").write_text(json.dumps({"lines": lines, "events": events, "sheet": sheet}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
