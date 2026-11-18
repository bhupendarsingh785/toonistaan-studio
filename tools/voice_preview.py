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
sys.path.insert(0, os.path.dirname(HERE))
from astra.hindi_natural import naturalize  # noqa: E402

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


def _speak_natural(text, voice, out, gap=0.16):
    """Normalise + prosody chunks. Har chunk ke kinare se khamoshi kato,
    awaaz barabar (loudnorm) karo, phir chhote pause se jodo.
    Isse lambi khamoshi aur chunk-dar-chunk awaaz ka uchhalna dono kam hote hain."""
    import tempfile
    parts = []
    for ch in naturalize(text):
        tmp = tempfile.mktemp(suffix=".mp3")
        asyncio.run(_say(ch["text"], voice, tmp))
        # kinare ki khamoshi hatao + awaaz barabar
        clean = tempfile.mktemp(suffix=".mp3")
        af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,"
              "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
              "loudnorm=I=-16:TP=-1.5:LRA=11")
        r = subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", tmp, "-filter:a", af,
                            "-ac", "1", "-ar", "44100", "-b:a", "128k", clean], capture_output=True)
        parts.append((clean if r.returncode == 0 else tmp,
                      max(0.10, min(0.45, ch.get("pause_after", 0.25) * 0.6))))
    if not parts:
        asyncio.run(_say(text, voice, out))
        return out
    lst = tempfile.mktemp(suffix=".txt")
    g = tempfile.mktemp(suffix=".mp3")
    subprocess.run([_ff(), "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "anullsrc=r=44100:cl=mono", "-t", "0.01", "-b:a", "128k", g],
                   capture_output=True)
    with open(lst, "w") as f:
        for i, (tmp, pause) in enumerate(parts):
            f.write(f"file '{tmp}'\n")
            if i < len(parts) - 1:
                f.write(f"file '{g}'\n")
    joined = tempfile.mktemp(suffix=".mp3")
    subprocess.run([_ff(), "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c:a", "libmp3lame", "-b:a", "128k", joined], check=False)
    # pauses daalne ke liye beech me chhoti khamoshi — adelay wala simple tareeka
    # (concat ke baad ek hi baar loudnorm, taaki saab chunk ek hi level par aayein)
    r = subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", joined,
                        "-filter:a", "loudnorm=I=-16:TP=-1.5:LRA=11",
                        "-ac", "1", "-ar", "44100", "-b:a", "128k", out], capture_output=True)
    if r.returncode != 0:
        shutil.copy(joined, out)
    return out


def make(kirdaar, text, outdir):
    kism = vp._kism(kirdaar) or "narrator"
    voice = EDGE_BY_KISM.get(kism, "hi-IN-MadhurNeural")
    raw = os.path.join(outdir, f"{kirdaar}_raw.mp3")
    out = os.path.join(outdir, f"{kirdaar}.mp3")
    _speak_natural(text, voice, raw)

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
        vp.shape_age(out, kirdaar)          # kampan / lowpass / dheema
        vp.fit_to_target(out, kirdaar)      # target Hz par le jao
    except Exception as e:
        print("SHAPE_FAIL", kirdaar, str(e)[:60], flush=True)
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
