#!/usr/bin/env python3
"""hindi_text.py — bolne se pehle text ko THEEK karo (Hindi uchcharan ke liye).

Asli dikkat: TTS "21", "1990", "OK", "%" jaisi cheezein galat bolta hai, aur kuch
English shabd Hindi me toot jaate hain. Yahan sab kuch bolne layak Hindi me badalta hai.

  python tools/hindi_text.py "21 साल की गौरी, 1990 में, OK?"
"""
from __future__ import annotations
import re
import sys

HUNDRED = ['शून्य', 'एक', 'दो', 'तीन', 'चार', 'पाँच', 'छह', 'सात', 'आठ', 'नौ', 'दस', 'ग्यारह', 'बारह', 'तेरह', 'चौदह', 'पंद्रह', 'सोलह', 'सत्रह', 'अठारह', 'उन्नीस', 'बीस', 'इक्कीस', 'बाईस', 'तेईस', 'चौबीस', 'पच्चीस', 'छब्बीस', 'सत्ताईस', 'अट्ठाईस', 'उनतीस', 'तीस', 'इकतीस', 'बत्तीस', 'तैंतीस', 'चौंतीस', 'पैंतीस', 'छत्तीस', 'सैंतीस', 'अड़तीस', 'उनतालीस', 'चालीस', 'इकतालीस', 'बयालीस', 'तैंतालीस', 'चवालीस', 'पैंतालीस', 'छियालीस', 'सैंतालीस', 'अड़तालीस', 'उनचास', 'पचास', 'इक्यावन', 'बावन', 'तिरेपन', 'चौवन', 'पचपन', 'छप्पन', 'सत्तावन', 'अट्ठावन', 'उनसठ', 'साठ', 'इकसठ', 'बासठ', 'तिरसठ', 'चौंसठ', 'पैंसठ', 'छियासठ', 'सड़सठ', 'अड़सठ', 'उनहत्तर', 'सत्तर', 'इकहत्तर', 'बहत्तर', 'तिहत्तर', 'चौहत्तर', 'पचहत्तर', 'छिहत्तर', 'सतहत्तर', 'अठहत्तर', 'उन्नासी', 'अस्सी', 'इक्यासी', 'बयासी', 'तिरासी', 'चौरासी', 'पचासी', 'छियासी', 'सत्तासी', 'अट्ठासी', 'नवासी', 'नब्बे', 'इक्यानवे', 'बानवे', 'तिरानवे', 'चौरानवे', 'पचानवे', 'छियानवे', 'सत्तानवे', 'अट्ठानवे', 'निन्यानवे']

ENGLISH = {
    "ok": "ओके", "okay": "ओके", "school": "स्कूल", "police": "पुलिस", "doctor": "डॉक्टर",
    "phone": "फ़ोन", "mobile": "मोबाइल", "video": "वीडियो", "photo": "फ़ोटो", "car": "कार",
    "bus": "बस", "train": "ट्रेन", "station": "स्टेशन", "hospital": "अस्पताल", "market": "बाज़ार",
    "yes": "हाँ", "no": "नहीं", "sorry": "सॉरी", "please": "प्लीज़", "hello": "हेलो", "hi": "हाय",
    "tv": "टीवी", "computer": "कंप्यूटर", "internet": "इंटरनेट", "bank": "बैंक", "ticket": "टिकट",
}


def num_to_hindi(n: int) -> str:
    if n < 0:
        return "माइनस " + num_to_hindi(-n)
    if n < 100:
        return HUNDRED[n]
    if n < 1000:
        h, r = divmod(n, 100)
        return HUNDRED[h] + " सौ" + ("" if r == 0 else " " + num_to_hindi(r))
    if n < 100000:
        th, r = divmod(n, 1000)
        return num_to_hindi(th) + " हज़ार" + ("" if r == 0 else " " + num_to_hindi(r))
    if n < 10000000:
        l, r = divmod(n, 100000)
        return num_to_hindi(l) + " लाख" + ("" if r == 0 else " " + num_to_hindi(r))
    c, r = divmod(n, 10000000)
    return num_to_hindi(c) + " करोड़" + ("" if r == 0 else " " + num_to_hindi(r))


def _year(n: int) -> str:
    """1990 -> उन्नीस सौ नब्बे (saal jaisa)"""
    if 1000 <= n <= 1999:
        a, b = divmod(n, 100)
        return num_to_hindi(a) + " सौ" + ("" if b == 0 else " " + num_to_hindi(b))
    return num_to_hindi(n)


def normalize(text: str) -> str:
    t = str(text or "")
    t = t.replace("—", ", ").replace("–", ", ").replace("…", "...")
    t = re.sub(r"[«»\"“”]", "", t)
    t = re.sub(r"\s*\.\.\.\s*", "… ", t)
    # percent / rupees pehle
    t = re.sub(r"(\d+)\s*%", r"\1 प्रतिशत", t)
    t = re.sub(r"[₹]\s*(\d+)", r"\1 रुपये", t)
    # saal
    t = re.sub(r"\b(1[0-9]{3}|20[0-9]{2})\b", lambda m: _year(int(m.group(1))), t)
    # number (bade se chhote)
    t = re.sub(r"\b\d{6,}\b", lambda m: num_to_hindi(int(m.group(0))), t)
    t = re.sub(r"\b\d+\b", lambda m: num_to_hindi(int(m.group(0))), t)
    # percent / rupees
    t = re.sub(r"(\d+)\s*%", r"\1 प्रतिशत", t)
    t = re.sub(r"[₹]\s*(\d+)", r"\1 रुपये", t)
    # English shabd -> Devanagari (chhote list)
    def _en(m):
        w = m.group(0).lower()
        return ENGLISH.get(w, m.group(0))
    t = re.sub(r"\b[A-Za-z]{2,10}\b", _en, t)
    # bache hue akshar (English) hata do — warna TTS hadbadata hai
    t = re.sub(r"[A-Za-z]+", "", t)
    # saaf
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\s+([,।!?])", r"\1", t)
    return t.strip()


def main() -> int:
    src = " ".join(sys.argv[1:]) or "21 साल की गौरी, 1990 में, OK?"
    print(normalize(src))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
