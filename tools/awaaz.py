#!/usr/bin/env python3
"""Toonistaan AWAAZ tool: Hindi awaaz banao, ya apni recording saaf (clear) karo. Pocket FM jaisi awaaz.

1) Likha hua -> awaaz (Microsoft neural Hindi, free, internet chahiye):
   python3 awaaz.py bolo "दादाजी! बचाओ!" --kirdaar swara_bachcha --bhaav scared -o chhotu.mp3
   (bhaav na do to Hindi shabdon se apne aap: डर->darr, वाह->khushi ...)

2) Apni recording saaf karo (phone/mic ki awaaz):
   python3 awaaz.py saaf meri_recording.m4a -o saaf.mp3
   Shor hatao -> hum kaato -> chup mein gate -> awaaz saaf -> barabar karo -> YouTube star (-16 LUFS)
   Shor zyada ho to: --shor 32

3) Kirdaar dekho:  python3 awaaz.py kirdaar

Zaroorat: ffmpeg ; bolo ke liye: pip install edge-tts"""
import argparse, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "studio"))
sys.path.insert(0, HERE)
try:
    from direction import detect_emotion, prosody, PROSODY
except ImportError:  # akele file ho tab bhi chale
    PROSODY = {"neutral": (0, 0, 0), "happy": (6, 8, 5), "sad": (-16, -10, -12), "angry": (8, -2, 15),
               "scared": (12, 16, -4), "surprised": (4, 20, 10), "calm": (-8, -3, -5), "excited": (12, 14, 10),
               "whisper": (-10, -4, -40)}
    def detect_emotion(t): return "neutral"
    def prosody(e, br=0, bp=0):
        r, p, v = PROSODY.get(e, (0, 0, 0))
        return f"{max(-28, min(25, br + r)):+d}%", f"{max(-40, min(45, bp + p)):+d}Hz", f"{v:+d}%"

# kirdaar: (Microsoft awaaz, pitch Hz, raftaar %)
KIRDAAR = {
    "madhur": ("hi-IN-MadhurNeural", 0, -6, "Narrator / aadmi"),
    "swara": ("hi-IN-SwaraNeural", 0, -6, "Aurat / maa"),
    "swara_bachcha": ("hi-IN-SwaraNeural", 28, 0, "Bachcha / bachchi"),
    "madhur_bachcha": ("hi-IN-MadhurNeural", 30, 2, "Ladka (patli awaaz)"),
    "swara_dadi": ("hi-IN-SwaraNeural", -22, -20, "Dadi / Nani"),
    "madhur_dada": ("hi-IN-MadhurNeural", -15, -18, "Dada / Nana"),
}

# ---- awaaz saaf karne ki chain (ffmpeg filters, kram se) ----
#  1 afftdn     lagataar shor hatao (pankha, AC, hiss)        2 highpass   80 Hz se neeche gungunahat/bijli ki hum kaato
#  3 loudnorm   pehle ek barabar star (dheemi recording bhi)   4 agate      chup ke waqt bacha shor dabao (gate)
#  5 220 Hz -2  dabbe jaisi/bhari awaaz kam                    6 3.2k +3.5  shabd saaf, "paas" wali awaaz (Pocket FM)
#  7 9 kHz +1.5 halki chamak                                   8 deesser    "s/sh" ki seeti kam
#  9 compressor dheemi-tez awaaz barabar                      10 limiter    kabhi phate nahi
# 11 loudnorm   YouTube/Pocket FM star (-16 LUFS)
# Jaancha: shor wali recording mein awaaz/shor 11.7 dB -> ~32 dB; bolne wale hisse bache rehte hain.
BODY = ("equalizer=f=220:t=q:w=1.0:g=-2,equalizer=f=3200:t=q:w=1.2:g=3.5,equalizer=f=9000:t=q:w=1.0:g=1.5,"
        "deesser=i=0.35,acompressor=threshold=0.09:ratio=3.2:attack=4:release=140:makeup=1.6,alimiter=limit=0.95,"
        "loudnorm=I=-16:TP=-1.5:LRA=11")


def clean_af(shor=24):
    return (f"afftdn=nr={shor}:nf=-40:tn=1,highpass=f=80,loudnorm=I=-20:TP=-2:LRA=15,"
            "agate=threshold=0.03:ratio=4:range=0.08:attack=5:release=180," + BODY)


TTS_AF = "highpass=f=80," + BODY   # bani hui awaaz mein shor nahi hota: sirf saafi + star


def ffmpeg(src, dst, af):
    codec = ["-c:a", "libmp3lame", "-b:a", "192k"] if dst.lower().endswith(".mp3") else []
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-af", af, "-ar", "44100", "-ac", "1", *codec, dst], check=True)


def bolo(text, kirdaar, bhaav, out, kaccha=False):
    if kirdaar not in KIRDAAR:
        sys.exit(f"kirdaar '{kirdaar}' nahi pata. Ye hain: {', '.join(KIRDAAR)}")
    name, pitch, rate, _ = KIRDAAR[kirdaar]
    bhaav = bhaav or detect_emotion(text)
    r, p, v = prosody(bhaav, rate, pitch)
    tmp = tempfile.mktemp(suffix=".mp3")
    res = subprocess.run([sys.executable, "-m", "edge_tts", "--text", text, "--voice", name, f"--rate={r}", f"--pitch={p}",
                          f"--volume={v}", "--write-media", tmp], capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(tmp):
        sys.exit("edge-tts nahi chala (internet? 'pip install edge-tts'?):\n" + res.stderr[-400:])
    if kaccha:
        os.replace(tmp, out)
    else:
        ffmpeg(tmp, out, TTS_AF); os.remove(tmp)
    print(f"ban gaya: {out}  (kirdaar={kirdaar}, bhaav={bhaav}, raftaar={r}, pitch={p})")


def _chunks(text, max_words=7):
    """Line ko chhote hisson me todo — jahan insan saans leta hai."""
    import re
    t = str(text).replace("\n", " ")
    # pehle punctuation par todo
    parts = [x.strip() for x in re.split(r"(?<=[।,.!?;:—])\s+", t) if x.strip()]
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
                out.append(" ".join(buf)); buf = []
        if buf:
            out.append(" ".join(buf))
    return out or [t]


def _pause_for(chunk):
    """Punctuation ke hisaab se chup."""
    c = chunk.strip()
    if c.endswith(("?", "?")):
        return 0.30
    if c.endswith(("!", "!")):
        return 0.26
    if c.endswith(("।", ".", "…")):
        return 0.30
    if c.endswith((",", ";", ":", "—")):
        return 0.16
    return 0.12


def bolo_natural(text, kirdaar, bhaav, out, jitter=True, kaccha=False):
    """Insan jaisi awaaz: line chhote hisson me, beech me chhota chup, halka utar-chadhav."""
    import random
    if kirdaar not in KIRDAAR:
        sys.exit(f"kirdaar '{kirdaar}' nahi pata. Ye hain: {', '.join(KIRDAAR)}")
    name, pitch, rate, _ = KIRDAAR[kirdaar]
    bhaav = bhaav or detect_emotion(text)
    base_r, base_p, base_v = prosody(bhaav, rate, pitch)
    tmpdir = tempfile.mkdtemp()
    pieces = []
    for i, chunk in enumerate(_chunks(text)):
        rp = int(base_r.rstrip("%")) if str(base_r).endswith("%") else int(base_r)
        pp = int(str(base_p).replace("Hz", "")) if "Hz" in str(base_p) else int(base_p)
        if jitter:
            rp += random.choice([-2, -1, 0, 1, 2])
            pp += random.choice([-3, -1, 0, 1, 3])
        f = os.path.join(tmpdir, f"c{i}.mp3")
        res = subprocess.run([sys.executable, "-m", "edge_tts", "--text", chunk, "--voice", name,
                              f"--rate={rp:+d}%", f"--pitch={pp:+d}Hz", f"--volume={base_v}",
                              "--write-media", f], capture_output=True, text=True)
        if res.returncode != 0 or not os.path.exists(f):
            sys.exit("edge-tts nahi chala:\n" + res.stderr[-300:])
        pieces.append((f, _pause_for(chunk)))
    # jodo: piece + chup
    from pathlib import Path
    listf = os.path.join(tmpdir, "list.txt")
    with open(listf, "w") as lf:
        for f, gap in pieces:
            lf.write(f"file '{f}'\n")
            sil = os.path.join(tmpdir, f"sil_{len(lf.name)}.wav")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                            f"anullsrc=r=24000:cl=mono", "-t", f"{gap:.2f}", sil], capture_output=True)
            lf.write(f"file '{sil}'\n")
    joined = os.path.join(tmpdir, "joined.mp3")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", listf, "-c:a", "libmp3lame", "-b:a", "192k", joined], check=True)
    if kaccha:
        os.replace(joined, out)
    else:
        ffmpeg(joined, out, TTS_AF)
    print(f"ban gaya (natural): {out}  (kirdaar={kirdaar}, bhaav={bhaav}, {len(pieces)} hisse)")


def main():
    ap = argparse.ArgumentParser(description="Toonistaan awaaz tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bolo", help="likha hua -> awaaz")
    b.add_argument("text"); b.add_argument("--kirdaar", default="madhur")
    b.add_argument("--bhaav", choices=list(PROSODY), help="na do to apne aap")
    b.add_argument("-o", "--out", default="awaaz.mp3"); b.add_argument("--kaccha", action="store_true", help="bina saaf kiye")
    b.add_argument("--natural", action="store_true", help="insan jaisa: hisson me todo, chhote chup")
    c = sub.add_parser("saaf", help="apni recording saaf karo")
    c.add_argument("file"); c.add_argument("-o", "--out", default=None)
    c.add_argument("--shor", type=int, default=24, help="shor kitna hatana (8 halka ... 36 zyada), default 24")
    sub.add_parser("kirdaar", help="saare kirdaar")
    a = ap.parse_args()
    if a.cmd == "kirdaar":
        for k, (n, p, r, d) in KIRDAAR.items():
            print(f"{k:16s} {d:22s} ({n}, pitch {p:+d}Hz, raftaar {r:+d}%)")
        print("bhaav:", ", ".join(PROSODY))
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
