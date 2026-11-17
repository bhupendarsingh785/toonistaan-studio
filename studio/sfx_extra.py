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


ALL = {"coins": coins, "phone": phone_ring, "gate_open": gate_open, "gate_close": gate_close,
       "footsteps": footsteps, "heartbeat": heartbeat, "paper": paper, "crowd": crowd,
       "bell": bell, "switch": switch, "car": car_pass, "water": water, "whoosh": whoosh}

KEYWORDS = [
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
