#!/usr/bin/env python3
"""
Toonistaan AWAAZ tool — likha hua → awaaz (insan jaisi, smooth).

Awaaz ke raste (jo mile wahi pehle):
  0) Sarvam bulbul      — key: SARVAM_API_KEY   (Hindi storytelling)
  1) ElevenLabs         — key: ELEVENLABS_API_KEY
  2) edge-tts           — free, hamesha (key nahi chahiye)

Chalao:
  python3 tools/awaaz.py bolo "दादी! बचाओ!" --kirdaar swara_bachcha --bhaav scared -o out.mp3
  python3 tools/awaaz.py bolo "..." --kirdaar madhur --natural -o out.mp3   # hisson me, chhote chup
  python3 tools/awaaz.py saaf recording.m4a -o saaf.mp3
  python3 tools/awaaz.py kirdaar
"""
import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "studio"))
sys.path.insert(0, HERE)

try:
    from direction import detect_emotion, prosody, PROSODY
except ImportError:
    PROSODY = {"neutral": (0, 0, 0), "happy": (6, 8, 5), "sad": (-16, -10, -12), "angry": (8, -2, 15),
               "scared": (12, 16, -4), "surprised": (4, 20, 10), "calm": (-8, -3, -5), "excited": (12, 14, 10),
               "whisper": (-10, -4, -40)}

    def detect_emotion(t):
        return "neutral"

    def prosody(e, br=0, bp=0):
        r, p, v = PROSODY.get(e, (0, 0, 0))
        return f"{max(-28, min(25, br + r)):+d}%", f"{max(-40, min(45, bp + p)):+d}Hz", f"{v:+d}%"

try:
    import voice_provider
except Exception:
    voice_provider = None

# kirdaar: (Microsoft awaaz, pitch Hz, raftaar %)
KIRDAAR = {
    "madhur": ("hi-IN-MadhurNeural", 0, -6, "Narrator / aadmi"),
    "swara": ("hi-IN-SwaraNeural", 0, -6, "Aurat / maa"),
    "swara_bachcha": ("hi-IN-SwaraNeural", 28, 0, "Bachcha / bachchi"),
    "madhur_bachcha": ("hi-IN-MadhurNeural", 30, 2, "Ladka (patli awaaz)"),
    "swara_dadi": ("hi-IN-SwaraNeural", -22, -20, "Dadi / Nani"),
    "madhur_dada": ("hi-IN-MadhurNeural", -15, -18, "Dada / Nana"),
    # naye kirdaar (kahani ke liye)
    "arjun": ("hi-IN-MadhurNeural", 6, 0, "Jawan ladka (hero)"),
    "meera": ("hi-IN-SwaraNeural", 4, 0, "Jawan ladki (heroine)"),
    "chacha": ("hi-IN-MadhurNeural", -8, -10, "Chacha (bhaari)"),
    "chachi": ("hi-IN-SwaraNeural", -4, -4, "Chachi"),
    "dadi": ("hi-IN-SwaraNeural", -20, -18, "Dadi"),
    "pandit": ("hi-IN-MadhurNeural", -6, -12, "Pandit ji"),
    "constable": ("hi-IN-MadhurNeural", 2, -4, "Constable"),
    "doctor": ("hi-IN-MadhurNeural", 4, -2, "Doctor"),
    "bachcha": ("hi-IN-SwaraNeural", 32, 6, "Chhota bachcha"),
    "sunita": ("hi-IN-SwaraNeural", 2, 0, "Gaon ki aurat"),
    "driver": ("hi-IN-MadhurNeural", 8, 4, "Driver"),
    "bhoot": ("hi-IN-MadhurNeural", -26, -22, "Bhoot (daravani)"),
    "chudail": ("hi-IN-SwaraNeural", -12, -16, "Chudail"),
    "mukhiya": ("hi-IN-MadhurNeural", -10, -14, "Gaon ka mukhiya"),
    "kaka": ("hi-IN-MadhurNeural", -2, -6, "Dukan wala kaka"),
    "bhabhi": ("hi-IN-SwaraNeural", 6, 2, "Bhabhi"),
    "ramesh": ("hi-IN-MadhurNeural", 2, -4, "Mazdoor (hero)"),
    "salim": ("hi-IN-MadhurNeural", 8, 0, "Dost"),
    "chaiwala": ("hi-IN-MadhurNeural", 14, 6, "Chai wala"),
    "announce": ("hi-IN-SwaraNeural", -2, -8, "Station announcement"),
    "aurat": ("hi-IN-SwaraNeural", 2, 0, "Aurat (co-passenger)"),
    "maa": ("hi-IN-SwaraNeural", -14, -14, "Maa"),
    "behen": ("hi-IN-SwaraNeural", 20, 8, "Chhoti behen"),
}

BODY = ("equalizer=f=220:t=q:w=1.0:g=-2,equalizer=f=3200:t=q:w=1.2:g=3.5,equalizer=f=9000:t=q:w=1.0:g=1.5,"
        "deesser=i=0.35,acompressor=threshold=0.09:ratio=3.2:attack=4:release=140:makeup=1.6,alimiter=limit=0.95,"
        "loudnorm=I=-16:TP=-1.5:LRA=11")


def clean_af(shor=24):
    return (f"afftdn=nr={shor}:nf=-40:tn=1,highpass=f=80,loudnorm=I=-20:TP=-2:LRA=15,"
            "agate=threshold=0.03:ratio=4:range=0.08:attack=5:release=180," + BODY)


TTS_AF = "highpass=f=80," + BODY


def ffmpeg(src, dst, af):
    codec = ["-c:a", "libmp3lame", "-b:a", "192k"] if dst.lower().endswith(".mp3") else []
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-af", af, "-ar", "44100", "-ac", "1",
                    *codec, dst], check=True)


# ---------------------------------------------------------------- provider chain
# ASTRA_VOICE_ENGINE=auto|sarvam|eleven|edge   (edge = 0 kharch, key nahi)
ENGINE = (os.environ.get("ASTRA_VOICE_ENGINE") or "auto").strip().lower()
CACHE_DIR = os.environ.get("ASTRA_TTS_CACHE") or os.path.join(tempfile.gettempdir(), "astra_tts_cache")
USED = {"sarvam": 0, "eleven": 0, "piper": 0, "edge": 0, "cache": 0}


def _cache_path(text, kirdaar, engine):
    import hashlib
    key = f"{engine}|{kirdaar}|{text.strip()}"
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:24]
    return os.path.join(CACHE_DIR, f"{h}.mp3")


def _providers(text, kirdaar, out):
    """Ek line ko provider se banao. Jo chala wahi naam lauta."""
    # cache: ye line pehle ban chuki hai to API call hi nahi
    try:
        cp = _cache_path(text, kirdaar, ENGINE)
        if os.path.exists(cp) and os.path.getsize(cp) > 1500:
            import shutil
            shutil.copy(cp, out)
            USED["cache"] += 1
            return "cache"
    except Exception:
        cp = None

    who = None
    if ENGINE in ("auto", "sarvam") and voice_provider is not None:
        if voice_provider.have_sarvam() and voice_provider.sarvam_tts(text, kirdaar, out):
            who = "sarvam"
    if who is None and ENGINE in ("auto", "eleven") and voice_provider is not None:
        if voice_provider.have_eleven() and voice_provider.eleven_tts(text, kirdaar, out):
            who = "eleven"
    if who is None and ENGINE in ("auto", "piper") and voice_provider is not None:
        if getattr(voice_provider, "have_piper", lambda: False)() and \
                voice_provider.piper_tts(text, kirdaar, out):
            who = "piper"

    if who and cp:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            import shutil
            shutil.copy(out, cp)
        except Exception:
            pass
    if who:
        USED[who] = USED.get(who, 0) + 1
    return who


def engine_report():
    total = sum(v for k, v in USED.items())
    print("VOICE_ENGINE " + " ".join(f"{k}={v}" for k, v in USED.items() if v),
          f"| total={total} | mode={ENGINE}", flush=True)


def _edge(text, kirdaar, bhaav, out, jitter=(0, 0)):
    name, pitch, rate, _ = KIRDAAR[kirdaar]
    bhaav = bhaav or detect_emotion(text)
    r, p, v = prosody(bhaav, rate, pitch)
    rp = int(str(r).rstrip("%")) + jitter[0]
    pp = int(str(p).replace("Hz", "")) + jitter[1]
    res = subprocess.run([sys.executable, "-m", "edge_tts", "--text", text, "--voice", name,
                          f"--rate={rp:+d}%", f"--pitch={pp:+d}Hz", f"--volume={v}",
                          "--write-media", out], capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(out):
        sys.exit("edge-tts nahi chala:\n" + (res.stderr or "")[-400:])
    return True


# ---------------------------------------------------------------- smooth (hisson me)
SMOOTH = True


def _chunks(text, max_words=18):
    """Line ko insan wale saans ke hisson me todo."""
    import re
    t = str(text).replace("\n", " ").strip()
    parts = [x.strip() for x in re.split(r"(?<=[।,.!?;:—…])\s+", t) if x.strip()]
    out = []
    for p in parts:
        w = p.split()
        if len(w) <= max_words:
            out.append(p)
            continue
        buf = []
        for word in w:
            buf.append(word)
            if len(buf) >= max_words:
                out.append(" ".join(buf))
                buf = []
        if buf:
            out.append(" ".join(buf))
    return out or [t]


def _pause_for(chunk):
    """Punctuation ke hisaab se chup (smooth = chhote)."""
    c = chunk.strip()
    scale = 0.30 if SMOOTH else 0.75
    if c.endswith(("?", "?")):
        base = 0.30
    elif c.endswith(("!", "!")):
        base = 0.26
    elif c.endswith(("।", ".", "…")):
        base = 0.22
    elif c.endswith((",", ";", ":", "—")):
        base = 0.14
    else:
        base = 0.10
    return round(base * scale, 3)


def bolo(text, kirdaar, bhaav, out, kaccha=False):
    if kirdaar not in KIRDAAR:
        sys.exit(f"kirdaar '{kirdaar}' nahi pata. Ye hain: {', '.join(KIRDAAR)}")
    tmp = tempfile.mktemp(suffix=".mp3")
    who = _providers(text, kirdaar, tmp)
    if who is None:
        _edge(text, kirdaar, bhaav, tmp)
        who = "edge"
    if kaccha:
        os.replace(tmp, out)
    else:
        ffmpeg(tmp, out, TTS_AF)
        os.remove(tmp)
    print(f"ban gaya ({who}): {out}  (kirdaar={kirdaar}, bhaav={bhaav or 'auto'})")


def bolo_natural(text, kirdaar, bhaav, out, kaccha=False):
    """Insan jaisa: chhote hisse, halka chup, har hisse par thoda utar-chadhav."""
    if kirdaar not in KIRDAAR:
        sys.exit(f"kirdaar '{kirdaar}' nahi pata")
    import random
    tmpdir = tempfile.mkdtemp()
    pieces = []
    used = set()
    for i, chunk in enumerate(_chunks(text)):
        f = os.path.join(tmpdir, f"c{i}.mp3")
        who = _providers(chunk, kirdaar, f)
        if who is None:
            _edge(chunk, kirdaar, bhaav, f, jitter=(random.choice([-2, -1, 0, 1, 2]),
                                                    random.choice([-3, -1, 0, 1, 3])))
            who = "edge"
            USED["edge"] += 1
        used.add(who)
        pieces.append((f, _pause_for(chunk)))

    listf = os.path.join(tmpdir, "list.txt")
    with open(listf, "w") as lf:
        for idx, (f, gap) in enumerate(pieces):
            # har hisse ke kinare par 25ms fade
            fp = os.path.join(tmpdir, f"fade_{idx}.mp3")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", f,
                            "-filter:a", "afade=t=in:st=0:d=0.025,areverse,afade=t=in:st=0:d=0.025,areverse",
                            fp], capture_output=True)
            if os.path.exists(fp) and os.path.getsize(fp) > 1000:
                f = fp
            lf.write(f"file '{f}'\n")
            sil = os.path.join(tmpdir, f"sil_{idx}.wav")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                            "anullsrc=r=24000:cl=mono", "-t", f"{min(gap, 0.32):.2f}", sil], capture_output=True)
            lf.write(f"file '{sil}'\n")
    joined = os.path.join(tmpdir, "joined.mp3")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", listf, "-c:a", "libmp3lame", "-b:a", "192k", joined], check=True)
    if kaccha:
        os.replace(joined, out)
    else:
        ffmpeg(joined, out, TTS_AF)
    print(f"ban gaya ({'+'.join(sorted(used))}): {out} (kirdaar={kirdaar}, {len(pieces)} hisse)")


def main():
    ap = argparse.ArgumentParser(description="Toonistaan awaaz tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bolo", help="likha hua -> awaaz")
    b.add_argument("text")
    b.add_argument("--kirdaar", default="madhur")
    b.add_argument("--bhaav", choices=list(PROSODY), help="na do to apne aap")
    b.add_argument("-o", "--out", default="awaaz.mp3")
    b.add_argument("--kaccha", action="store_true", help="bina saaf kiye")
    b.add_argument("--natural", action="store_true", help="hisson me, chhote chup (smooth)")
    c = sub.add_parser("saaf", help="apni recording saaf karo")
    c.add_argument("file")
    c.add_argument("-o", "--out", default=None)
    c.add_argument("--shor", type=int, default=24)
    sub.add_parser("kirdaar", help="saare kirdaar")
    a = ap.parse_args()
    if a.cmd == "kirdaar":
        for k, (n, p, r, d) in KIRDAAR.items():
            print(f"{k:16s} {d:22s} ({n}, pitch {p:+d}Hz, raftaar {r:+d}%)")
        print("bhaav:", ", ".join(PROSODY))
        if voice_provider:
            print("sarvam:", voice_provider.have_sarvam(), "| eleven:", voice_provider.have_eleven())
    elif a.cmd == "bolo":
        if getattr(a, "natural", False):
            bolo_natural(a.text, a.kirdaar, a.bhaav, a.out, kaccha=a.kaccha)
        else:
            bolo(a.text, a.kirdaar, a.bhaav, a.out, a.kaccha)
    else:
        out = a.out or os.path.splitext(a.file)[0] + "_saaf.mp3"
        ffmpeg(a.file, out, clean_af(max(1, min(40, a.shor))))
        print("saaf awaaz:", out)


if __name__ == "__main__":
    main()
