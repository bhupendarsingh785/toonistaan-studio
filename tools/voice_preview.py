#!/usr/bin/env python3
"""ASTRA — awaaz ka preview (edge-tts, free, koi API key nahi).

GitHub Actions runner par chalta hai (wahan internet khula hai).
Har kirdaar ki ek line banata hai, phir umar/kism ke filters lagata hai
(astra/voices.json ke hisaab se) — aur ek hi file me jod deta hai.

Chalane ka tareeka:
    python tools/voice_preview.py out_dir
"""
import os
import sys
import subprocess
import asyncio
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import voice_provider as vp  # noqa: E402

# edge-tts ki Hindi awaazein (free)
EDGE_BY_KISM = {
    "narrator": "hi-IN-MadhurNeural",
    "male_young": "hi-IN-MadhurNeural",
    "male_mid": "hi-IN-MadhurNeural",
    "male_old": "hi-IN-MadhurNeural",
    "female_young": "hi-IN-SwaraNeural",
    "female_mid": "hi-IN-SwaraNeural",
    "female_old": "hi-IN-SwaraNeural",
    "child": "hi-IN-SwaraNeural",
    "creature": "hi-IN-MadhurNeural",
    "announce": "hi-IN-SwaraNeural",
}

LINES = {
    "sutradhar": "एक गाँव था, जहाँ हर शाम कोई न कोई कहानी जन्म लेती थी।",
    "dadi": "बेटा, आ जा पास। दादी तेरे को ही ढूँढ रही थी।",
    "behen": "भैया! तुम आ गए? मैं तो सोच ही रही थी, तुम कब आओगे।",
    "bachcha": "दादी, दादी! देखो, मुझे कितनी बड़ी तितली मिली!",
    "bhoot": "तू... यहाँ क्यों आया? ये रास्ता बंद है।",
    "madhur": "डरो मत, मैं तुम्हारे साथ हूँ। चलो, घर चलें।",
}

FF = shutil.which("ffmpeg") or "ffmpeg"


def _ff():
    global FF
    if shutil.which("ffmpeg"):
        FF = shutil.which("ffmpeg")
        return FF
    try:
        import imageio_ffmpeg
        FF = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    return FF


async def _say(text, voice, out):
    import edge_tts
    c = edge_tts.Communicate(text, voice)
    await c.save(out)


def make(kirdaar, text, outdir):
    kism = vp._kism(kirdaar) or "narrator"
    voice = EDGE_BY_KISM.get(kism, "hi-IN-MadhurNeural")
    raw = os.path.join(outdir, f"{kirdaar}_raw.mp3")
    out = os.path.join(outdir, f"{kirdaar}.mp3")
    asyncio.run(_say(text, voice, raw))

    pitch = vp.SARVAM_PITCH.get(kirdaar, 1.0)
    flt = []
    if abs(pitch - 1.0) > 0.02:
        flt += [f"asetrate=44100*{pitch:.4f}", "aresample=44100", f"atempo={1/pitch:.4f}"]
    flt += vp.age_filters(kirdaar)
    flt.append("highpass=f=60")
    r = subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", raw, "-filter:a", ",".join(flt),
                        "-ac", "1", "-ar", "44100", "-b:a", "128k", out], capture_output=True)
    if r.returncode != 0:
        shutil.copy(raw, out)
    try:
        os.remove(raw)
    except Exception:
        pass
    hz = 0
    try:
        hz = round(vp._measure_pitch(out) or 0)
    except Exception:
        pass
    print(f"{kirdaar:12s} {kism:14s} {voice:22s} {hz} Hz", flush=True)
    return out


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "preview_out"
    os.makedirs(outdir, exist_ok=True)
    parts = []
    for k, text in LINES.items():
        try:
            parts.append(make(k, text, outdir))
        except Exception as e:
            print("FAIL", k, str(e)[:100], flush=True)

    gap = os.path.join(outdir, "gap.mp3")
    subprocess.run([_ff(), "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "anullsrc=r=44100:cl=mono", "-t", "0.6", "-b:a", "128k", gap],
                   capture_output=True)
    lst = os.path.join(outdir, "list.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.basename(p)}'\n")
            f.write(f"file '{os.path.basename(gap)}'\n")
    final = os.path.join(outdir, "voice-cast-preview.mp3")
    subprocess.run([_ff(), "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c:a", "libmp3lame", "-b:a", "128k", final], check=False)
    print("BAN GAYA:", final, os.path.getsize(final) if os.path.exists(final) else 0, flush=True)


if __name__ == "__main__":
    main()
