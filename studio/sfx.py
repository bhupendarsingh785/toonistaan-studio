#!/usr/bin/env python3
"""Free sound effects + music bed, sirf numpy se (internet ki zarurat nahi).
python sfx.py all            -> audio/library/ mein saare SFX
python sfx.py music happy 20 -> 20 second ka khushi wala music"""
import sys, os, wave, numpy as np
SR = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio", "library")

def save(name, x):
    os.makedirs(OUT, exist_ok=True)
    x = np.clip(x / (np.max(np.abs(x)) + 1e-9) * 0.9, -1, 1)
    p = os.path.join(OUT, name + ".wav")
    with wave.open(p, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    return p

def t(d): return np.linspace(0, d, int(SR * d), False)
def env(n, a=0.01, r=0.3):
    e = np.ones(n); A = max(1, min(int(SR*a), n // 2)); R = max(1, min(int(SR*r), n // 2))
    e[:A] = np.linspace(0, 1, A); e[-R:] *= np.linspace(1, 0, R); return e
def noise(d): return np.random.randn(int(SR*d))
def lowpass(x, k):
    return np.convolve(x, np.ones(k)/k, mode="same")

def whoosh(d=0.8):
    n = noise(d); f = np.linspace(40, 4, len(n)).astype(int)
    out = np.array([n[max(0,i-f[i]):i+1].mean() for i in range(len(n))])
    return out * np.sin(np.pi * np.linspace(0, 1, len(n)))**2
def footstep():
    x = lowpass(noise(0.12), 30) * np.exp(-t(0.12)*40)
    return x + 0.5*np.sin(2*np.pi*90*t(0.12))*np.exp(-t(0.12)*50)
def footsteps(n=4, gap=0.4):
    out = np.zeros(int(SR*(gap*n+0.2)))
    for i in range(n):
        s = footstep(); k = int(SR*gap*i); out[k:k+len(s)] += s*(0.8+0.2*np.random.rand())
    return out
def chime():
    tt = t(1.5); return sum(np.sin(2*np.pi*f*tt)*np.exp(-tt*(3+i)) for i, f in enumerate([1318, 1760, 2093, 2637]))
def sparkle():
    out = np.zeros(int(SR*1.2))
    for _ in range(14):
        f = np.random.uniform(2000, 5000); tt = t(0.15); k = np.random.randint(0, len(out)-len(tt))
        out[k:k+len(tt)] += np.sin(2*np.pi*f*tt)*np.exp(-tt*30)
    return out
def boom():
    tt = t(2.0); return (lowpass(noise(2.0), 80)*3 + np.sin(2*np.pi*45*tt)) * np.exp(-tt*2.5)
def thunder():
    tt = t(3.0); x = lowpass(noise(3.0), 120)*np.exp(-tt*1.2)
    x[:int(SR*.08)] += noise(.08)*2; return x
def wind(d=5):
    n = lowpass(noise(d), 200); return n*(0.6+0.4*np.sin(2*np.pi*0.3*t(d)))
def leaves(d=3):
    return (noise(d) - lowpass(noise(d), 8)) * (0.5+0.5*np.abs(np.sin(2*np.pi*0.7*t(d)))) * 0.4
def door_creak():
    tt = t(1.4); f = 180 + 60*np.sin(2*np.pi*1.3*tt)
    saw = 2*((np.cumsum(f)/SR) % 1) - 1
    return saw*env(len(tt), .05, .3)*0.6 + lowpass(noise(1.4), 20)*0.1
def takeoff():
    return np.concatenate([boom()[:int(SR*.4)]*0.7, whoosh(1.0)])
def land():
    x = boom(); x[:int(SR*.03)] += noise(.03)*3; return x
def beam(d=1.5):
    tt = t(d); f = 300 + 200*np.sin(2*np.pi*8*tt)
    return np.sin(2*np.pi*np.cumsum(f)/SR)*env(len(tt), .05, .3) + 0.2*noise(d)*env(len(tt))
def fear(d=6):
    tt = t(d); return (np.sin(2*np.pi*55*tt) + 0.5*np.sin(2*np.pi*58.3*tt) + 0.2*lowpass(noise(d), 300)) * env(len(tt), 1, 1)

NOTE = lambda n: 440 * 2 ** ((n - 69) / 12)
MOODS = {  # (bpm, chord roots, scale type)
    "happy": (112, [60, 67, 69, 65], [0, 4, 7]),
    "sad": (70, [57, 53, 60, 55], [0, 3, 7]),
    "action": (140, [50, 50, 53, 48], [0, 3, 7]),
    "mystery": (80, [57, 58, 57, 56], [0, 3, 6]),
    "comedy": (128, [60, 65, 67, 60], [0, 4, 7]),
    # --- naye mood (video editor / story ke liye) ---
    "calm": (72, [57, 60, 64, 53], [0, 4, 7]),
    "romance": (76, [60, 65, 69, 67], [0, 4, 7]),
    "epic": (92, [50, 57, 62, 46], [0, 7, 12]),
    "lofi": (78, [62, 67, 72, 57], [0, 4, 7]),
    "suspense": (60, [45, 48, 52, 41], [0, 3, 7]),
    "horror": (54, [40, 43, 46, 38], [0, 1, 6]),
    "emotional": (66, [57, 60, 64, 50], [0, 3, 7]),
}
MOOD_ALIAS = {  # galat/alternate naam bhi chalein
    "darr": "horror", "fear": "horror", "dark": "horror",
    "pyaar": "romance", "love": "romance", "romantic": "romance",
    "dukh": "sad", "emotional": "sad", "alone": "sad",
    "khushi": "happy", "fun": "comedy", "masti": "comedy",
    "shant": "calm", "soft": "calm", "peace": "calm",
    "josh": "epic", "hero": "epic", "motivation": "epic",
    "chill": "lofi", "lo-fi": "lofi",
    "raaz": "mystery", "secret": "mystery", "detective": "suspense",
}
def music(mood="happy", d=20):
    """Mood ka music. Koi bhi galat mood aaye to 'happy' par gir jata hai (crash nahi)."""
    if not isinstance(mood, str):
        mood = "happy"
    key = mood.strip().lower()
    key = MOOD_ALIAS.get(key, key)
    if key not in MOODS:
        key = "happy"
    bpm, roots, tri = MOODS[key]; beat = 60 / bpm
    d = max(0.2, float(d))
    out = np.zeros(int(SR*d))
    N = len(out)
    i = 0; pos = 0.0
    while pos < d - 1e-6:
        root = roots[i % len(roots)]; bar = beat * 4
        seg = min(bar, d - pos)
        tt = t(seg); k = int(SR*pos)
        pad = sum(np.sin(2*np.pi*NOTE(root+iv-12)*tt) for iv in tri) * 0.15
        seg_len = min(len(tt), N - k)
        if seg_len > 0:
            out[k:k+seg_len] += (pad * env(len(tt), .2, .3))[:seg_len]
        for b in range(4):
            note = root + tri[(b + i) % 3] + 12
            nt = t(beat*0.9); kk = k + int(SR*beat*b)
            if kk >= N:
                break
            add = np.sin(2*np.pi*NOTE(note)*nt) * np.exp(-nt*4) * 0.35
            n_len = min(len(add), N - kk)
            if n_len > 0:
                out[kk:kk+n_len] += add[:n_len]
            if key in ("action", "happy", "comedy", "epic"):
                kt = t(.1); kick = np.sin(2*np.pi*60*kt) * np.exp(-kt*30) * 0.6
                k_len = min(len(kick), N - kk)
                if k_len > 0:
                    out[kk:kk+k_len] += kick[:k_len]
        pos += bar; i += 1
    fade = min(int(SR*1.5), N // 3)
    if fade > 1:
        out[-fade:] *= np.linspace(1, 0, fade)
    peak = float(np.max(np.abs(out))) if N else 0.0
    if peak > 0.98:
        out *= 0.98 / peak
    return out

ALL = {"whoosh": whoosh, "footsteps": footsteps, "chime": chime, "sparkle": sparkle, "boom": boom,
       "thunder": thunder, "wind": wind, "leaves": leaves, "door_creak": door_creak,
       "takeoff": takeoff, "land": land, "beam": beam, "fear": fear}

if __name__ == "__main__":
    a = sys.argv[1:] or ["all"]
    if a[0] == "all":
        for k, f in ALL.items(): print(save(k, f()))
    elif a[0] == "music":
        mood = a[1] if len(a) > 1 else "happy"; d = float(a[2]) if len(a) > 2 else 20
        print(save(f"music_{mood}", music(mood, d)))
    elif a[0] in ALL:
        print(save(a[0], ALL[a[0]]()))
