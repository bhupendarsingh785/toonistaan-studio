#!/usr/bin/env python3
"""ASTRA — Hindi ko bolne ke kabil banana (Sarvam se seekha hua).

Sarvam ki natural awaaz ka raaz sirf model nahi hai. Unke apne blog ke
mutabik teen cheezein hain:
  1. Text normalisation — "Dr. Sharma ka appointment 18 Jan ko 7:30 AM pe hai"
     ko bolne wale roop me badalna ("डॉक्टर शर्मा का अपॉइंटमेंट अठारह जनवरी को
     साढ़े सात बजे सुबह है") — yahi robotic aur insaan ka farq hai.
  2. Language ka apna G2P / uchchaaran — English niyam Hindi par lagane se
     awaaz "sahi par parayi" lagti hai.
  3. Prosody — kahan rukna, kahan zor dena, kitni der rukna.

Yeh file wahi teen cheezein karti hai — bina kisi API ke. Isse koi bhi
TTS (edge, piper, sarvam) zyada insaani lagega.

Istemal:
    from astra.hindi_natural import naturalize
    chunks = naturalize("Dr. Sharma ka appointment 18 Jan ko 7:30 AM pe hai.")
    # -> [{'text': 'डॉक्टर शर्मा का अपॉइंटमेंट अठारह जनवरी को साढ़े सात बजे सुबह है',
    #      'pause_after': 0.35}]
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- ank (numbers)
_HIN_DIGITS = ["शून्य", "एक", "दो", "तीन", "चार", "पाँच", "छह", "सात", "आठ", "नौ",
               "दस", "ग्यारह", "बारह", "तेरह", "चौदह", "पंद्रह", "सोलह", "सत्रह",
               "अठारह", "उन्नीस"]
_TENS = {20: "बीस", 30: "तीस", 40: "चालीस", 50: "पचास", 60: "साठ", 70: "सत्तर",
         80: "अस्सी", 90: "नब्बे"}

# 21-99 ke irregular shabd (Hindi me har dashak ke apne roop hote hain)
_IRREG = {
    21: "इक्कीस", 22: "बाईस", 23: "तेईस", 24: "चौबीस", 25: "पच्चीस", 26: "छब्बीस",
    27: "सत्ताईस", 28: "अट्ठाईस", 29: "उनतीस", 31: "इकतीस", 32: "बत्तीस", 33: "तैंतीस",
    34: "चौंतीस", 35: "पैंतीस", 36: "छत्तीस", 37: "सैंतीस", 38: "अड़तीस", 39: "उनतालीस",
    41: "इकतालीस", 42: "बयालीस", 43: "तैंतालीस", 44: "चवालीस", 45: "पैंतालीस",
    46: "छियालीस", 47: "सैंतालीस", 48: "अड़तालीस", 49: "उनचास", 51: "इक्यावन",
    52: "बावन", 53: "तिरपन", 54: "चौवन", 55: "पचपन", 56: "छप्पन", 57: "सत्तावन",
    58: "अट्ठावन", 59: "उनसठ", 61: "इकसठ", 62: "बासठ", 63: "तिरसठ", 64: "चौंसठ",
    65: "पैंसठ", 66: "छियासठ", 67: "सड़सठ", 68: "अड़सठ", 69: "उनहत्तर", 71: "इकहत्तर",
    72: "बहत्तर", 73: "तिहत्तर", 74: "चौहत्तर", 75: "पचहत्तर", 76: "छिहत्तर",
    77: "सतहत्तर", 78: "अठहत्तर", 79: "उनासी", 81: "इक्यासी", 82: "बयासी",
    83: "तिरासी", 84: "चौरासी", 85: "पचासी", 86: "छियासी", 87: "सत्तासी",
    88: "अट्ठासी", 89: "नवासी", 91: "इक्यानवे", 92: "बानवे", 93: "तिरानवे",
    94: "चौरानवे", 95: "पचानवे", 96: "छियानवे", 97: "सत्तानवे", 98: "अट्ठानवे",
    99: "निन्यानवे",
}


def _two(n: int) -> str:
    if n < 20:
        return _HIN_DIGITS[n]
    if n in _IRREG:
        return _IRREG[n]
    return _TENS.get((n // 10) * 10, _HIN_DIGITS[n % 10])


def _hundreds(n: int) -> str:
    h, r = n // 100, n % 100
    out = ""
    if h:
        out = ("एक" if h == 1 else _HIN_DIGITS[h]) + " सौ"
    if r:
        out = (out + " " + _two(r)).strip()
    return out


def number_to_hindi(n: int) -> str:
    """0 se karor tak — Hindi shabdon me (lakh/crore ke saath)."""
    n = int(n)
    if n < 0:
        return "माइनस " + number_to_hindi(-n)
    if n < 100:
        return _two(n)
    if n < 1000:
        return _hundreds(n)
    parts = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1000)
    if crore:
        parts.append(number_to_hindi(crore) + " करोड़")
    if lakh:
        parts.append(number_to_hindi(lakh) + " लाख")
    if thousand:
        parts.append(number_to_hindi(thousand) + " हज़ार")
    if n:
        parts.append(_hundreds(n))
    return " ".join(parts)


def _decimal_to_hindi(s: str) -> str:
    if "." not in s:
        return number_to_hindi(int(s))
    a, b = s.split(".", 1)
    left = number_to_hindi(int(a)) if a else "शून्य"
    right = " ".join(_HIN_DIGITS[int(d)] for d in b if d.isdigit())
    return f"{left} दशमलव {right}"


# ---------------------------------------------------------------- mahine / din
MONTHS = {
    "jan": "जनवरी", "january": "जनवरी", "feb": "फ़रवरी", "february": "फ़रवरी",
    "mar": "मार्च", "march": "मार्च", "apr": "अप्रैल", "april": "अप्रैल",
    "may": "मई", "jun": "जून", "june": "जून", "jul": "जुलाई", "july": "जुलाई",
    "aug": "अगस्त", "august": "अगस्त", "sep": "सितंबर", "sept": "सितंबर",
    "september": "सितंबर", "oct": "अक्टूबर", "october": "अक्टूबर",
    "nov": "नवंबर", "november": "नवंबर", "dec": "दिसंबर", "december": "दिसंबर",
}

ORDINAL_DAY = {1: "पहली", 2: "दूसरी", 3: "तीसरी", 4: "चौथी", 5: "पाँचवीं",
               6: "छठी", 7: "सातवीं", 8: "आठवीं", 9: "नौवीं", 10: "दसवीं",
               11: "ग्यारहवीं", 12: "बारहवीं", 13: "तेरहवीं", 14: "चौदहवीं",
               15: "पंद्रहवीं", 16: "सोलहवीं", 17: "सत्रहवीं", 18: "अठारहवीं",
               19: "उन्नीसवीं", 20: "बीसवीं", 21: "इक्कीसवीं", 22: "बाईसवीं",
               23: "तेईसवीं", 24: "चौबीसवीं", 25: "पच्चीसवीं", 26: "छब्बीसवीं",
               27: "सत्ताईसवीं", 28: "अट्ठाईसवीं", 29: "उनतीसवीं", 30: "तीसवीं",
               31: "इकतीसवीं"}

# ---------------------------------------------------------------- chhote roop
ABBR = {
    r"\bDr\.?(?=\s)": "डॉक्टर", r"\bMr\.?(?=\s)": "मिस्टर", r"\bMrs\.?(?=\s)": "मिसेज़",
    r"\bShri\.?(?=\s)": "श्री", r"\bSmt\.?(?=\s)": "श्रीमती", r"\bEr\.?(?=\s)": "इंजीनियर",
    r"\bAdv\.?(?=\s)": "एडवोकेट", r"\bProf\.?(?=\s)": "प्रोफ़ेसर",
    r"\bGovt\.?(?=\s)": "सरकार", r"\bNo\.\b": "नंबर", r"\bRs\.?\b": "रुपये",
    r"\bkm\b": "किलोमीटर", r"\bkg\b": "किलो", r"\bAM\b": "सुबह", r"\bPM\b": "शाम",
    r"\betc\.?(?=\s|$)": "वगैरह", r"\bi\.e\.\b": "यानी", r"\be\.g\.\b": "जैसे",
}

# ---------------------------------------------------------------- time
def _time_words(h: int, m: int, marker: str = "") -> str:
    marker = (marker or "").upper()
    part = "सुबह" if marker == "AM" else ("शाम" if marker == "PM" else "")
    if h > 12:
        h -= 12
    if h == 12:
        h = 12
    if m == 0:
        core = f"{number_to_hindi(h)} बजे"
    elif m == 15:
        core = f"सवा {number_to_hindi(h)} बजे"
    elif m == 30:
        core = f"साढ़े {number_to_hindi(h)} बजे"
    elif m == 45:
        core = f"पौने {number_to_hindi(h + 1)} बजे"
    else:
        core = f"{number_to_hindi(h)} बजकर {number_to_hindi(m)} मिनट"
    return f"{core} {part}".strip()


# ---------------------------------------------------------------- asli kaam
def normalize_text(text: str) -> str:
    """Text ko bolne wale roop me badlo (Sarvam jaisa normaliser)."""
    s = " " + str(text).strip() + " "

    # 1) paisa  ₹1,25,000  /  Rs 500
    def _money(m):
        raw = m.group(1).replace(",", "")
        try:
            return _decimal_to_hindi(raw) + " रुपये"
        except Exception:
            return m.group(0)

    s = re.sub(r"(?:₹|Rs\.?|INR)\s?([0-9][0-9,]*(?:\.[0-9]+)?)", _money, s)

    # 2) time — 7:30 AM / 7.30 pm / 19:45
    def _time(m):
        h, mi, mk = int(m.group(1)), int(m.group(2)), (m.group(3) or "")
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return " " + _time_words(h, mi, mk) + " "
        return m.group(0)

    s = re.sub(r"\b([0-9]{1,2})[:.]([0-9]{2})\s?(AM|PM|am|pm)?\b", _time, s)

    # 3) tareekh — 18 Jan / 18 January / 18-01-2026
    def _date(m):
        d = int(m.group(1))
        mon = MONTHS.get(m.group(2).lower())
        if not mon or not (1 <= d <= 31):
            return m.group(0)
        day = number_to_hindi(d)
        return f" {day} {mon} "

    s = re.sub(r"\b([0-9]{1,2})(?:st|nd|rd|th)?[\s\-/]([A-Za-z]{3,9})\b", _date, s)

    # 4) chhote roop
    for pat, rep in ABBR.items():
        s = re.sub(pat, rep, s)

    # 5) percentage / degree
    s = re.sub(r"\b([0-9]+(?:\.[0-9]+)?)\s?%", lambda m: _decimal_to_hindi(m.group(1)) + " प्रतिशत", s)
    s = re.sub(r"\b([0-9]+)\s?°C\b", lambda m: number_to_hindi(int(m.group(1))) + " डिग्री", s)

    # 6) bache hue ank
    s = re.sub(r"\b([0-9]{1,7}(?:\.[0-9]+)?)\b", lambda m: _decimal_to_hindi(m.group(1)), s)

    # 7) Hinglish ke aam shabd — Devanagari me (sirf jo pakke hain)
    s = dehinglish(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------- Hinglish ke aam shabd
# Sarvam code-mix model se karta hai. Hamare paas model nahi, isliye jo shabd
# pakke hain unki spelling Devanagari me de dete hain — uchchaaran Hindi jaisa ho.
HINGLISH = {
    "ka": "का", "ki": "की", "ke": "के", "ko": "को", "se": "से", "me": "में",
    "mein": "में", "pe": "पे", "par": "पर", "aur": "और", "ya": "या", "bhi": "भी",
    "nahi": "नहीं", "nahin": "नहीं", "hai": "है", "hain": "हैं", "tha": "था",
    "thi": "थी", "the": "थे", "hoga": "होगा", "hogi": "होगी", "kya": "क्या",
    "kaise": "कैसे", "kyun": "क्यों", "kyu": "क्यों", "kab": "कब", "kahan": "कहाँ",
    "kaun": "कौन", "kitna": "कितना", "kitni": "कितनी", "abhi": "अभी", "phir": "फिर",
    "aaj": "आज", "kal": "कल", "parso": "परसों", "subah": "सुबह", "shaam": "शाम",
    "raat": "रात", "din": "दिन", "ghar": "घर", "gaon": "गाँव", "shehar": "शहर",
    "bhai": "भाई", "behen": "बहन", "maa": "माँ", "papa": "पापा", "dadi": "दादी",
    "dada": "दादा", "beta": "बेटा", "beti": "बेटी", "bachcha": "बच्चा",
    "aadmi": "आदमी", "aurat": "औरत", "ladka": "लड़का", "ladki": "लड़की",
    "paani": "पानी", "khana": "खाना", "chai": "चाय", "doodh": "दूध", "roti": "रोटी",
    "paisa": "पैसा", "paise": "पैसे", "kaam": "काम", "baat": "बात", "cheez": "चीज़",
    "train": "ट्रेन", "ticket": "टिकट", "platform": "प्लेटफ़ॉर्म", "station": "स्टेशन",
    "gaadi": "गाड़ी", "sadak": "सड़क", "raasta": "रास्ता", "darwaza": "दरवाज़ा",
    "kamra": "कमरा", "school": "स्कूल", "doctor": "डॉक्टर", "dawai": "दवाई",
    "appointment": "अपॉइंटमेंट", "time": "टाइम", "price": "दाम", "tax": "टैक्स",
    "phone": "फ़ोन", "mobile": "मोबाइल", "photo": "फ़ोटो", "video": "वीडियो",
    "accha": "अच्छा", "achha": "अच्छा", "bura": "बुरा", "bahut": "बहुत",
    "thoda": "थोड़ा", "zyada": "ज़्यादा", "kam": "कम", "sab": "सब", "kuch": "कुछ",
    "koi": "कोई", "log": "लोग", "dost": "दोस्त", "pyaar": "प्यार", "khushi": "खुशी",
    "dar": "डर", "darr": "डर", "raat": "रात", "sapna": "सपना", "kahani": "कहानी",
    "chalo": "चलो", "aao": "आओ", "jao": "जाओ", "dekho": "देखो", "suno": "सुनो",
    "ruko": "रुको", "chalo": "चलो", "batao": "बताओ", "bolo": "बोलो",
}


def dehinglish(text: str) -> str:
    """Latin shabdon ko Devanagari me — sirf jo list me hain."""
    def rep(m):
        w = m.group(0)
        return HINGLISH.get(w.lower(), w)
    return re.sub(r"\b[A-Za-z]{2,}\b", rep, text)


# ---------------------------------------------------------------- prosody
# Sarvam prosody seekhta hai; hamare paas model nahi, isliye niyam:
#   - lamba vakya chhote saans-bhar hisson me
#   - "aur", "lekin", "phir" par chhota pause
#   - sawal ke ant me pause + thoda upar
PAUSE_SOFT = 0.18
PAUSE_MID = 0.35
PAUSE_LONG = 0.6

_BREAKERS = ("लेकिन", "मगर", "पर ", "फिर", "इसलिए", "क्योंकि", "और ", "तो ",
             "जब ", "जैसे ", "यानी", "वगैरह")


def prosody_chunks(text: str, max_words: int = 10):
    """Vakya ko bolne ke hisson me todo — har hisse ke saath pause."""
    t = normalize_text(text)
    out = []
    for sent in re.split(r"(?<=[।!?])\s*", t):
        sent = sent.strip()
        if not sent:
            continue
        is_q = sent.endswith("?")
        # comma par clauses
        clauses = [c.strip() for c in re.split(r"[,;:]\s*", sent) if c.strip()]
        bits = []
        for ci, cl in enumerate(clauses):
            words = cl.split()
            if len(words) <= max_words:
                bits.append((cl, PAUSE_SOFT if ci < len(clauses) - 1 else PAUSE_MID))
                continue
            cur = []
            for w in words:
                cur.append(w)
                hit = any(w.startswith(b.strip()) for b in _BREAKERS)
                if (hit and len(cur) >= 4) or len(cur) >= max_words:
                    bits.append((" ".join(cur), PAUSE_SOFT))
                    cur = []
            if cur:
                bits.append((" ".join(cur), PAUSE_MID))
        for i, (b, pause) in enumerate(bits):
            last = (i == len(bits) - 1)
            out.append({"text": b,
                        "pause_after": PAUSE_LONG if last else pause,
                        "question": bool(is_q and last)})
    return out


def naturalize(text: str):
    """Ek line -> bolne ke liye taiyaar chunks."""
    return prosody_chunks(text)


if __name__ == "__main__":
    tests = [
        "Dr. Sharma ka appointment 18 Jan ko 7:30 AM pe hai.",
        "Ticket ka price ₹1,25,000 hai, aur 15% tax alag.",
        "Train 19:45 pe aayegi, lekin platform abhi bataya nahi.",
        "Aaj 5 बजे मिलते हैं, ठीक है?",
    ]
    for t in tests:
        print("IN :", t)
        print("OUT:", normalize_text(t))
        for c in naturalize(t):
            print(f"   [{c['pause_after']:.2f}s] {c['text']}")
        print()
