"""Toonistaan extra SFX — kahani ke saath chalne wali asli awaazein (bina internet, numpy).
Sab functions numpy array (float32, SR=44100) dete hain. KEYWORDS se auto-detect.
"""
import numpy as np

SR = 44100


def t(d):
    return np.linspace(0, d, int(SR * d), False)


def env(n, a=0.01, r=0.2):
    e = np.ones(n)
    A = max(1, min(int(SR * a), n // 2))
    R = max(1, min(int(SR * r), n // 2))
    e[:A] = np.linspace(0, 1, A)
    e[-R:] *= np.linspace(1, 0, R)
    return e


def _noise(d):
    return np.random.randn(int(SR * d)).astype(np.float32)


def _lp(x, hz):
    k = max(1, int(SR / max(hz, 20)))
    return np.convolve(x, np.ones(k) / k, "same").astype(np.float32)


def _bp(x, lo, hi):
    return _hp(_lp(x, hi), lo)


def _hp(x, hz):
    return (x - _lp(x, hz)).astype(np.float32)


def coins(d=0.9):
    out = np.zeros(int(SR * d), np.float32)
    for _ in range(9):
        f = np.random.uniform(2600, 5200)
        tt = t(0.16)
        k = np.random.randint(0, max(1, len(out) - len(tt)))
        out[k:k + len(tt)] += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 26) * 0.5).astype(np.float32)
    return out * 0.7


def phone_ring(d=2.2):
    tt = t(d)
    gate = ((tt % 1.2) < 0.9).astype(np.float32)
    ring = (np.sin(2 * np.pi * 440 * tt) + 0.6 * np.sin(2 * np.pi * 480 * tt)) * gate
    return (ring * 0.25 * env(len(tt), .01, .1)).astype(np.float32)


def gate_open(d=1.6):
    tt = t(d)
    f = 140 + 90 * np.sin(2 * np.pi * 0.9 * tt)
    creak = 2 * ((np.cumsum(f) / SR) % 1) - 1
    creak = _lp(creak, 1200) * env(len(tt), .05, .4) * 0.25
    thud = np.zeros_like(tt)
    thud[:int(SR * .12)] = (np.sin(2 * np.pi * 70 * t(.12)) * np.exp(-t(.12) * 18) * 0.5)
    return (creak + thud).astype(np.float32)


def gate_close(d=0.7):
    tt = t(d)
    thud = np.sin(2 * np.pi * 60 * tt) * np.exp(-tt * 16) * 0.7
    click = np.zeros_like(tt)
    click[:int(SR * .04)] = _noise(.04) * 1.2
    return (thud + click).astype(np.float32)


def footsteps(d=2.4, bpm=110):
    out = np.zeros(int(SR * d), np.float32)
    step = 60.0 / bpm
    k = 0.0
    while k < d - 0.2:
        tt = t(0.18)
        s = (_lp(_noise(0.18), 900) * np.exp(-tt * 30) * 0.55)
        i = int(SR * k)
        out[i:i + len(s)] += s[:len(out) - i]
        k += step
    return out


def heartbeat(d=2.0):
    out = np.zeros(int(SR * d), np.float32)
    for base in (0.0, 0.35, 1.0, 1.35):
        if base >= d - 0.2:
            break
        tt = t(0.22)
        b = np.sin(2 * np.pi * 48 * tt) * np.exp(-tt * 14) * 0.9
        i = int(SR * base)
        out[i:i + len(b)] += b[:len(out) - i]
    return out * 0.6


def paper(d=0.8):
    x = _hp(_noise(d), 1800)
    mod = (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 7 * t(d))))
    return (x * mod * env(int(SR * d), .02, .25) * 0.5).astype(np.float32)


def crowd(d=3.0):
    x = _lp(_noise(d), 1400) * 0.5 + _lp(_noise(d), 400) * 0.6
    mod = 0.7 + 0.3 * np.sin(2 * np.pi * 0.7 * t(d))
    return (x * mod * 0.28).astype(np.float32)


def bell(d=2.4):
    out = np.zeros(int(SR * d), np.float32)
    for f, g in ((520, 0.5), (780, 0.3), (1040, 0.2), (1560, 0.1)):
        tt = t(d)
        out += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 2.2) * g).astype(np.float32)
    return out * 0.45


def switch(d=0.35):
    tt = t(d)
    return (_noise(d) * np.exp(-tt * 60) * 0.9).astype(np.float32)


def car_pass(d=2.6):
    tt = t(d)
    f = 90 + 60 * np.sin(np.pi * tt / d)
    eng = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25
    air = _lp(_noise(d), 900) * (0.4 * np.sin(np.pi * tt / d))
    return (eng + air).astype(np.float32)


def water(d=2.5):
    x = _hp(_noise(d), 900) * 0.4
    mod = 0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 3 * t(d)))
    return (x * mod).astype(np.float32)


def whoosh(d=0.8):
    tt = t(d)
    x = _hp(_noise(d), 400) * np.sin(np.pi * tt / d) ** 2
    return (x * 0.35).astype(np.float32)


def cooker_whistle(d=2.2):
    """प्रेशर कुकर की सीटी — Indian ghar ki sabse pehchani awaaz."""
    out = np.zeros(int(SR * d), np.float32)
    for i, start in enumerate((0.0, 0.75, 1.5)):
        dur = 0.55
        tt = t(dur)
        f = 2400 + 240 * np.sin(2 * np.pi * 7 * tt)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / dur) ** 2
        x += 0.3 * _hp(_noise(dur), 3000) * np.sin(np.pi * tt / dur) ** 2
        k = int(SR * start)
        out[k:k + len(x)] += x[:len(out) - k] * (0.9 - i * 0.15)
    return out * 0.6


def chai_boil(d=3.0):
    """चाय उबलना — halka bulbulana."""
    tt = t(d)
    base = _lp(_noise(d), 900) * 0.25
    bub = np.zeros(int(SR * d), np.float32)
    k = 0.0
    while k < d - 0.2:
        dur = np.random.uniform(0.05, 0.12)
        w = t(dur)
        f = np.random.uniform(300, 700)
        x = np.sin(2 * np.pi * f * w) * np.exp(-w * 25)
        i = int(SR * k)
        bub[i:i + len(x)] += x[:len(bub) - i] * np.random.uniform(0.3, 0.8)
        k += np.random.uniform(0.06, 0.18)
    return (base + bub * 0.5)


def keys_jingle(d=1.2):
    """चाबियों की खनखन — jeb se nikalna."""
    out = np.zeros(int(SR * d), np.float32)
    for _ in range(14):
        f = np.random.uniform(2200, 6200)
        w = t(0.12)
        k = np.random.randint(0, max(1, len(out) - len(w)))
        out[k:k + len(w)] += (np.sin(2 * np.pi * f * w) * np.exp(-w * 30) * 0.4).astype(np.float32)
    return out * 0.7


def broom(d=2.0):
    """झाड़ू — pharsh par jhaadu."""
    out = np.zeros(int(SR * d), np.float32)
    k = 0.0
    while k < d - 0.4:
        w = t(0.35)
        x = _bp(_noise(0.35), 900, 6000) * np.sin(np.pi * w / 0.35) ** 2
        i = int(SR * k)
        out[i:i + len(x)] += x[:len(out) - i] * np.random.uniform(0.4, 0.7)
        k += 0.42
    return out * 0.8


def matka_water(d=1.8):
    """मटके में पानी डालना — Indian ghar."""
    tt = t(d)
    x = _hp(_noise(d), 500) * 0.35
    mod = 0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 4.5 * tt))
    gurgle = np.sin(2 * np.pi * np.cumsum(180 + 90 * np.sin(2 * np.pi * 2.2 * tt)) / SR) * 0.25
    return (x * mod + gurgle * np.exp(-tt * 1.2)) * 0.8


def ceiling_fan(d=4.0):
    """छत का पंखा — dheemi hum."""
    tt = t(d)
    hum = np.sin(2 * np.pi * 100 * tt) * 0.12 + np.sin(2 * np.pi * 200 * tt) * 0.06
    air = _lp(_noise(d), 700) * 0.18
    wobble = 0.9 + 0.1 * np.sin(2 * np.pi * 1.1 * tt)
    return (hum + air) * wobble * 0.9


ALL = {"coins": coins, "phone": phone_ring, "gate_open": gate_open, "gate_close": gate_close,
       "footsteps": footsteps, "heartbeat": heartbeat, "paper": paper, "crowd": crowd,
       "bell": bell, "switch": switch, "car": car_pass, "water": water, "whoosh": whoosh,
       "cooker": cooker_whistle, "chai": chai_boil, "keys": keys_jingle,
       "broom": broom, "matka": matka_water, "fan": ceiling_fan}

KEYWORDS = [
    ("scream_woman", ["चीख", "चिल्ला", "cheekh", "scream", "दहाड़"]),
    ("monster_lurk", ["राक्षस", "भूत", "दैत्य", "monster", "साया", "आत्मा"]),
    ("crowd_panic", ["भगदड़", "panic", "भाग-दौड़", "शोर"]),
    ("crowd_applause", ["ताली", "वाहवाही", "applause", "खुशी की आवाज़"]),
    ("ghost", ["भूतनी", "आत्मा", "ghost", "परछाई"]),
    ("horror_hit", ["धमाका", "टकराव", "impact", "धड़ाम"]),
    ("scary_sting", ["डरावनी आवाज़", "चौंक", "sting", "अचानक"]),
    ("horror_ambience", ["माहौल", "सन्नाटा", "डरावना", "ambience"]),
    ("cooker", ["सीटी", "कुकर", "cooker", "प्रेशर"]),
    ("chai", ["चाय", "केटली", "chai", "उबल"]),
    ("keys", ["चाबी", "चाबियाँ", "चाबियों", "keys", "ताला"]),
    ("broom", ["झाड़ू", "jhaadu", "broom", "सफ़ाई"]),
    ("matka", ["मटका", "घड़ा", "matka", "पानी डाल"]),
    ("fan", ["पंखा", "fan", "छत का पंखा"]),
    ("coins", ["सिक्के", "पैसे", "गुल्लक", "रुपये", "बैंक", "खाता", "पर्स", "नोट", "कमाई", "बचत", "मुद्रा"]),
    ("phone", ["फोन", "मोबाइल", "घंटी", "कॉल", "बजा", "बजी"]),
    ("gate_open", ["गेट खुला", "दरवाज़ा खुला", "दरवाजा खुला", "खटखट", "चरचरा"]),
    ("gate_close", ["दरवाज़ा बंद", "दरवाजा बंद", "गेट बंद", "धम्म"]),
    ("footsteps", ["कदम", "चलने", "दौड़", "पैरों", "आहट"]),
    ("heartbeat", ["धड़कन", "दिल ज़ोर", "दिल जोर", "डर", "खौफ", "सन्नाटा"]),
    ("paper", ["कागज़", "कागज", "चिट्ठी", "खत", "फाइल", "किताब", "पन्ने"]),
    ("crowd", ["बाज़ार", "बाजार", "भीड़", "मेला", "स्टेशन"]),
    ("bell", ["मंदिर", "आरती", "मस्जिद", "गिरजा"]),
    ("switch", ["बत्ती", "लाइट", "स्विच"]),
    ("car", ["गाड़ी", "कार", "बस", "ट्रेन", "ट्रक", "स्कूटर"]),
    ("water", ["नदी", "पानी", "बारिश", "बौछार", "कुआँ", "कुआं"]),
]


DOOR_WORDS = ["दरवाज़ा", "दरवाजा", "गेट", "द्वार", "door", "gate"]
OPEN_WORDS = ["खुल", "खोल", "open"]
CLOSE_WORDS = ["बंद", "बन्द", "close", "shut"]


def _door_rule(low):
    """Darwaza + khulna/band hona — shabd alag-alag ho to bhi pakde."""
    if not any(w in low for w in DOOR_WORDS):
        return []
    out = []
    if any(w in low for w in CLOSE_WORDS):
        out.append("gate_close")
    if any(w in low for w in OPEN_WORDS):
        out.append("gate_open")
    return out


# Bhaav -> kaunsi awaaz lagti hai (situation ke hisaab se)
BHAV_SOUNDS = {
    "scared":    ["heartbeat", "breath"],
    "surprised": ["scary_sting"],
    "sad":       ["wind"],
    "happy":     ["crowd_applause", "birds"],
    "excited":   ["crowd_applause"],
    "angry":     ["horror_hit"],
    "whisper":   ["room"],
    "calm":      [],
    "neutral":   [],
}


def detect_bhav(bhaav, limit=1):
    """Sirf bhaav se sound (jab vaakya me koi cheez na mile)."""
    return list(BHAV_SOUNDS.get(str(bhaav or "").lower(), []))[:limit]


def detect(text):
    """Line ke shabdon se SFX chuno (max 2)."""
    out = []
    low = str(text or "")
    out.extend(_door_rule(low))
    if out:
        # darwaza mil gaya to baaki (max 2) bhi jod do
        for name, words in KEYWORDS:
            if name in ("gate_open", "gate_close"):
                continue
            if any(w in low for w in words) and name not in out:
                out.append(name)
            if len(out) >= 2:
                break
        return out[:2]
    for name, words in KEYWORDS:
        if any(w in low for w in words):
            out.append(name)
        if len(out) >= 2:
            break
    return out


# ---------------------------------------------------------------- samajh (context)
# Kaunse mahaul me kaunsi awaaz allowed hai — galat jagah galat sound na lage
ENV_ALLOW = {
    "street":  {"crowd", "car", "horn", "chai", "coins", "paper", "footsteps", "keys",
                "phone", "traffic", "rickshaw", "cycle_bell", "shop_shutter"},
    "station": {"train", "crowd", "horn", "chai", "footsteps", "announce", "coins",
                "paper", "bag", "train_horn", "station"},
    "night":   {"train", "crickets", "wind", "footsteps", "crowd", "owl", "frog",
                "train_horn", "station", "heartbeat", "rain"},
    "room":    {"clock", "paper", "water", "footsteps", "door", "knock", "coins",
                "phone", "kettle", "chai", "cooker", "switch", "fan"},
    "village": {"birds", "footsteps", "water", "chai", "cooker", "dog", "cow", "gate",
                "bell", "temple", "crowd", "cycle_bell", "rain", "wind", "goat", "kids"},
    "jungle":  {"leaves", "birds", "wind", "footsteps", "frog", "crickets", "water"},
    "hall":    {"clock", "footsteps", "door", "crowd", "paper", "bell"},
    "cave":    {"water", "wind", "footsteps", "heartbeat"},
    "neutral": set(),
}

# shabd -> (sound, sirf in mahaul me)  |  env=None = har jagah
CONTEXT_WORDS = [
    (["ट्रेन", "रेलगाड़ी", "रेल", "स्टेशन", "प्लेटफ़ॉर्म", "गाड़ी आई", "ट्रेन आई"], "train", {"station", "night"}),
    (["गाड़ी", "कार", "बस", "ट्रक"], "car", {"street", "station"}),
    (["भीड़", "लोग", "बाज़ार", "मेला"], "crowd", {"street", "station", "village"}),
    (["चाय", "केतली", "चायवाला"], "chai", {"street", "station", "room", "village"}),
    (["सिक्के", "पैसे", "रुपये", "गुल्लक"], "coins", {"street", "room", "village"}),
    (["दरवाज़ा", "दरवाजा", "गेट", "द्वार"], "gate_open", {"room", "village", "hall"}),
    (["खिड़की", "खिड़की के बाहर"], "wind", {"room", "night", "village"}),
    (["बारिश", "पानी", "बौछार"], "rain", {"village", "night", "street", "jungle"}),
    (["पत्ते", "पेड़", "जंगल"], "leaves", {"jungle", "village"}),
    (["मुर्गा", "मुर्गी", "चिड़िया", "पक्षी"], "birds", {"village", "jungle"}),
    (["कुत्ता", "कुत्ते"], "dog", {"village", "street"}),
    (["घड़ी", "टिक-टिक"], "clock", {"room", "hall"}),
    (["चूल्हा", "रसोई", "थाली", "खाना"], "cooker", {"village", "room"}),
    (["कागज़", "चिट्ठी", "पत्र", "टिकट"], "paper", {"street", "station", "room", "hall"}),
    (["पैदल", "चलते", "चलना", "कदम", "आहट", "रास्ता", "भाग", "दौड़"], "footsteps", None),
]


def detect_smart(text, env="neutral", allow_horror=False):
    """Mahaul dekh kar sound chuno — galat sound nahi lagta."""
    low = str(text or "").lower()
    allowed = ENV_ALLOW.get(env, set())
    out = []
    for words, snd, envs in CONTEXT_WORDS:
        if not any(w in low for w in words):
            continue
        if envs is not None and env not in envs:
            continue
        if allowed and not any(snd.startswith(a) or a.startswith(snd) for a in allowed):
            continue
        if snd not in out:
            out.append(snd)
        if len(out) >= 2:
            return out
    for cand in detect_action(low, env):
        if cand not in out:
            out.append(cand)
    if out:
        return out[:2]
    # kuch na mile to purana tareeka, par mahaul ke andar hi
    for cand in detect(low)[:2]:
        if allow_horror or not cand.startswith(("horror", "scary", "ghost", "monster", "scream")):
            if not allowed or any(cand.startswith(a) or a.startswith(cand) for a in allowed):
                out.append(cand)
    return out[:2]


# ---------------------------------------------------------------- kaam (action) ke shabd
ACTION_WORDS = [
    (["खुला", "खोल", "खुल गया", "खुलती"], "gate_open", {"room", "village", "hall", "station"}),
    (["बंद", "बन्द", "बंद हो"], "gate_close", {"room", "village", "hall"}),
    (["कुर्सी", "चौकी", "बैठ"], "chair", {"room", "hall", "street"}),
    (["थाली", "खाना खा", "परोस", "चम्मच"], "plate", {"room", "village"}),
    (["पलंग", "सो", "लेट", "करवट"], "bed", {"room"}),
    (["नहा", "स्नान", "बाल्टी"], "water", {"room", "village"}),
    (["सीढ़ी", "चढ़", "उतर"], "stairs", {"room", "village", "hall"}),
    (["दौड़", "भाग"], "run", {"street", "village", "jungle", "night"}),
]


def detect_action(text, env="neutral"):
    """Kaam dekh kar awaaz — khulna, band hona, baithna, khana."""
    low = str(text or "").lower()
    out = []
    for words, snd, envs in ACTION_WORDS:
        if not any(w in low for w in words):
            continue
        if envs is not None and env not in envs:
            continue
        if snd not in out:
            out.append(snd)
    return out
