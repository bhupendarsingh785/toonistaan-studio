"""Direction: har line ka bhaav (emotion) aur action. Line likhne ke 3 tareeke (sab chalte hain):
  ["swara_bachcha", "दादाजी! बचाओ!"]
  ["swara_bachcha", "दादाजी! बचाओ!", {"emotion": "scared", "action": "run"}]
  {"voice": "swara_bachcha", "text": "...", "emotion": "scared", "action": "wave", "volume": "whisper"}
Bhaav na likha ho to text se andaaza (Hindi shabd + ! ?). Bhaav se awaaz badalti hai (raftaar, pitch, zor)."""
import re

EMOTIONS = ("neutral", "happy", "sad", "angry", "scared", "surprised", "calm", "excited", "whisper")

# bhaav -> (raftaar %, pitch Hz, volume %) edge-tts mein (kirdaar ki apni awaaz ke upar jodta hai)
PROSODY = {
    "neutral": (0, 0, 0), "calm": (-8, -3, -5), "happy": (6, 8, 5), "excited": (12, 14, 10),
    "sad": (-16, -10, -12), "angry": (8, -2, 15), "scared": (12, 16, -4), "surprised": (4, 20, 10),
    "whisper": (-10, -4, -40),
}
# chehre/body ke liye (motion engine ke 6 bhaav)
FACE = {"neutral": "neutral", "calm": "neutral", "happy": "happy", "excited": "happy", "sad": "sad",
        "angry": "angry", "scared": "scared", "surprised": "surprised", "whisper": "neutral"}

_WORDS = [  # (bhaav, shabd) : pehla mila wahi
    ("scared", ["डर", "बचाओ", "भागो", "अँधेरा", "अंधेरा", "भूत", "काँप", "कांप", "मदद"]),
    ("sad", ["रो ", "रोने", "रोया", "दुख", "दुःख", "उदास", "माफ़", "माफ", "अकेला", "बेचारा", "टूट गया", "चला गया"]),
    ("angry", ["गुस्सा", "चुप", "ख़बरदार", "खबरदार", "बदमाश", "कैसे हिम्मत", "निकलो"]),
    ("happy", ["हाहा", "हा हा", "हँस", "हंस", "वाह", "मज़ा", "मजा", "शाबाश", "खुश", "धन्यवाद", "बहुत अच्छा", "जीत"]),
    ("surprised", ["अरे", "सच में", "क्या?", "ओह", "हैरान"]),
    ("calm", ["धीरे", "धीरज", "शांत", "सुनो बेटा", "चिंता मत"]),
]


def detect_emotion(text):
    t = text or ""
    for emo, words in _WORDS:
        if any(w in t for w in words):
            return emo
    if t.count("!") >= 2:
        return "excited"
    if re.search(r"[?？]\s*$", t.strip()):
        return "surprised" if "!" in t else "neutral"
    return "neutral"


def parse_line(l):
    """-> (voice, text, opts dict with emotion/action set)"""
    if isinstance(l, dict):
        voice, text = l.get("voice", "madhur"), l.get("text", "")
        opts = {k: v for k, v in l.items() if k not in ("voice", "text")}
    else:
        voice, text = l[0], l[1]
        opts = dict(l[2]) if len(l) > 2 and isinstance(l[2], dict) else {}
    emo = opts.get("emotion") or detect_emotion(text)
    if opts.get("volume") == "whisper":
        emo = "whisper"
    opts["emotion"] = emo if emo in PROSODY else "neutral"
    opts.setdefault("action", "talk")
    return voice, text, opts


def prosody(emotion, base_rate=0, base_pitch=0):
    r, p, v = PROSODY.get(emotion, PROSODY["neutral"])
    rate = max(-28, min(25, base_rate + r)); pitch = max(-40, min(45, base_pitch + p))   # hadd: awaaz ajeeb na ho
    return f"{rate:+d}%", f"{pitch:+d}Hz", f"{v:+d}%"


if __name__ == "__main__":
    for s in ["दादाजी! बचाओ! बहुत अँधेरा है!", "वाह! कितनी सुंदर पतंग है!", "मुझे माफ़ कर दो दादी...", "चुप रहो!",
              "पतंग ऊँची तभी उड़ती है बेटा, जब डोर को धीरज से छोड़ते हैं।", "तुम कहाँ जा रहे हो?"]:
        print(detect_emotion(s), "|", s)
