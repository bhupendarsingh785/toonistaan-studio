
"""Hindi text preparation and structured character/dialogue analysis.

This is deterministic preprocessing, not a generative Hindi language model.
It never claims to infer facts that are not present in the script.
"""
import re, unicodedata, hashlib
from pathlib import Path

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
DIALOGUE_PATTERNS = [
    re.compile(r"^\s*([^:：]{1,60})\s*[:：]\s*(.+)$"),
    re.compile(r"^\s*[\"“](.+?)[\"”]\s*[-—]\s*(.+)$"),
]
ROLE_HINTS = {
    "बच्चा": ("child_3_6", "unspecified"), "तीन साल": ("child_3_6", "unspecified"),
    "3 साल": ("child_3_6", "unspecified"), "चार साल": ("child_3_6", "unspecified"),
    "बच्ची": ("child_3_6", "female"), "लड़का": ("child_7_12", "male"),
    "लड़की": ("child_7_12", "female"), "किशोर": ("teen_13_17", "male"),
    "किशोरी": ("teen_13_17", "female"), "युवक": ("young_adult", "male"),
    "युवती": ("young_adult", "female"), "महिला": ("adult", "female"),
    "पुरुष": ("adult", "male"), "माँ": ("adult", "female"), "पिता": ("adult", "male"),
    "दादी": ("elderly", "female"), "नानी": ("elderly", "female"),
    "दादा": ("elderly", "male"), "नाना": ("elderly", "male"),
    "बुजुर्ग महिला": ("elderly", "female"), "बुजुर्ग आदमी": ("elderly", "male"),
}
EMOTION_HINTS = {
    "गुस्से": "angry", "क्रोधित": "angry", "नाराज़": "angry", "खुश": "happy",
    "हँस": "laughing", "हंस": "laughing", "रो ": "crying", "रोने": "crying",
    "डर": "fearful", "चौंक": "surprised", "धीरे": "soft", "फुसफुस": "whisper",
    "चिल्ला": "shout", "उदास": "sad", "दुखी": "sad", "जिज्ञासा": "curious",
}
def normalize_hindi(text: str) -> str:
    text = unicodedata.normalize("NFC", text.replace("\ufeff", "").replace("\r\n", "\n"))
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def language_diagnostics(text: str) -> dict:
    chars = [c for c in text if not c.isspace()]
    dev = sum(1 for c in chars if DEVANAGARI.match(c))
    latin = sum(1 for c in chars if c.isascii() and c.isalpha())
    return {
        "characters": len(chars), "devanagari_letters": dev, "latin_letters": latin,
        "devanagari_ratio": round(dev / max(1, len(chars)), 3),
        "likely_hindi_or_devanagari": dev > 0,
        "warning": None if dev else "देवनागरी अक्षर नहीं मिले; Roman Hindi हो सकती है।"
    }

def stable_id(name: str) -> str:
    return hashlib.sha256(name.strip().casefold().encode("utf-8")).hexdigest()[:12]

def _speaker_line(line):
    for pattern in DIALOGUE_PATTERNS:
        m = pattern.match(line)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return None, None

def scan_script(text: str) -> dict:
    text = normalize_hindi(text)
    characters, segments, warnings = {}, [], []
    for line_no, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        speaker, utterance = _speaker_line(raw)
        if speaker:
            key = speaker.strip()
            char = characters.setdefault(key, {
                "character_id": stable_id(key), "name": key,
                "age_group": "unspecified", "voice_presentation": "unspecified",
                "evidence": [], "dialogue_count": 0, "voice_profile_status": "NEEDS_REVIEW"
            })
            char["dialogue_count"] += 1
            char["evidence"].append({"line": line_no, "source": "explicit_speaker_label"})
            # 1) pehle SPEAKER ke naam se pehchano (सबसे भरोसेमंद).
            #    Pehle poora vakya dekha jata tha, isliye "आरव: माँ, ..." me
            #    आरव ko female aur "दादी" ko male (दादा match) mil raha tha.
            name_low = key.casefold()
            matched_name = False
            for hint in sorted(ROLE_HINTS, key=len, reverse=True):   # lamba hint pehle
                age, presentation = ROLE_HINTS[hint]
                if hint in name_low:
                    char["age_group"] = age
                    if presentation != "unspecified":
                        char["voice_presentation"] = presentation
                    char["evidence"].append({"line": line_no, "source": "speaker_name_keyword", "matched": hint})
                    matched_name = True
                    break
            # 2) naam se kuch na mile to hi vakya se sirf UMAR ka andaza
            #    (ling kabhi nahi — warna dusre kirdaar ke shabd se galat ho jata hai)
            if not matched_name and char["age_group"] == "unspecified":
                low = utterance.casefold()
                for hint in sorted(ROLE_HINTS, key=len, reverse=True):
                    age, _presentation = ROLE_HINTS[hint]
                    if hint in low:
                        char["age_group"] = age
                        char["evidence"].append({"line": line_no, "source": "utterance_keyword_age_only", "matched": hint})
                        break
            emotion = next((v for k, v in EMOTION_HINTS.items() if k in utterance), "neutral")
            segments.append({
                "line": line_no, "speaker": key, "character_id": char["character_id"],
                "text": utterance, "emotion_hint": emotion, "delivery": "dialogue"
            })
        else:
            segments.append({
                "line": line_no, "speaker": None, "character_id": None,
                "text": raw.strip(), "emotion_hint": "narration", "delivery": "narration"
            })
    if not characters:
        warnings.append("कोई स्पष्ट speaker label नहीं मिला। स्क्रिप्ट में 'नाम: संवाद' प्रारूप या manual character map दें।")
    warnings += [
        "आयु/लिंग के अनुमान केवल लिखित संकेतों पर आधारित हैं; अस्पष्ट मामलों में manual confirmation जरूरी है।",
        "स्क्रिप्ट स्कैनर वास्तविक उम्र या आवाज़ को प्रमाणित नहीं कर सकता।"
    ]
    return {
        "schema_version": "0.3", "language": language_diagnostics(text),
        "characters": list(characters.values()), "segments": segments, "warnings": warnings
    }

def scan_file(path):
    return scan_script(Path(path).read_text(encoding="utf-8"))
