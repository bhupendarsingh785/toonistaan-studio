#!/usr/bin/env python3
"""
ASTRA — Music Maker: maujooda tracks ko tod-marod kar NAYA music banao.

Kya kar sakta hai:
  layer   — 2-3 track ek saath (jaise piano + halki baarish + dhol door)
  chain   — do track ke beech crossfade (ek bhaav se doosre me jaana)
  slow    — tempo dheema (dukh bhaav), bina sur bigaade
  cut     — beech ka hissa nikaal kar loop banao
  mood    — ready-made "recipe": sad / tension / epic / calm / romantic / horror

Har naya track library ke `music/` me jaata hai aur report deta hai.

Chalao:
  python3 astra/music_maker.py mood sad --out naya_sad
  python3 astra/music_maker.py layer music/forest_lofi_piano.mp3 music/rain_gentle_1.mp3 --gains 1.0 0.25 --out piano_rain
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library")
OUTDIR = os.path.join(LIB, "music")


def ff():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _abs(name):
    if os.path.isabs(name):
        return name
    p = os.path.join(LIB, name)
    if os.path.exists(p):
        return p
    p2 = os.path.join(OUTDIR, name)
    return p2


def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or b"").decode("utf-8", "ignore")[-300:])
    return r


def dur(path):
    r = subprocess.run([ff(), "-i", path], capture_output=True)
    txt = (r.stderr or b"").decode("utf-8", "ignore")
    for line in txt.splitlines():
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def layer(paths, gains=None, seconds=None, out="layered.mp3", fade=2.0):
    """2-3 track ek saath — halka mix, aakhir me master."""
    paths = [_abs(p) for p in paths]
    for p in paths:
        if not os.path.exists(p):
            raise FileNotFoundError(p)
    gains = gains or [1.0] * len(paths)
    if seconds is None:
        seconds = min(dur(p) for p in paths) or 60.0
    seconds = float(seconds)

    cmd = [ff(), "-loglevel", "error", "-y"]
    for p in paths:
        cmd += ["-i", p]
    fc = []
    for i, g in enumerate(gains):
        fc.append(f"[{i}:a]volume={g},atrim=0:{seconds:.2f},asetpts=N/SR/TB[a{i}]")
    fc.append("".join(f"[a{i}]" for i in range(len(paths))) + f"amix=inputs={len(paths)}:normalize=0[m]")
    fc.append(f"[m]afade=t=in:st=0:d={fade},afade=t=out:st={max(0, seconds - fade):.2f}:d={fade},"
              f"alimiter=limit=0.95,loudnorm=I=-18:TP=-2:LRA=9[o]")
    dst = os.path.join(OUTDIR, out if out.endswith(".mp3") else out + ".mp3")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[o]", "-ac", "1", "-ar", "44100", "-b:a", "64k", dst]
    run(cmd)
    return dst


def chain(a, b, seconds_each=20.0, out="chain.mp3", fade=3.0):
    """Pehla track se doosre me dheere se badlo (bhaav ka badlav)."""
    a, b = _abs(a), _abs(b)
    dst = os.path.join(OUTDIR, out if out.endswith(".mp3") else out + ".mp3")
    fc = (f"[0:a]atrim=0:{seconds_each:.2f},asetpts=N/SR/TB,afade=t=out:st={max(0, seconds_each - fade):.2f}:d={fade}[x];"
          f"[1:a]atrim=0:{seconds_each:.2f},asetpts=N/SR/TB,afade=t=in:st=0:d={fade}[y];"
          f"[x][y]acrossfade=d={fade}:c1=tri:c2=tri,loudnorm=I=-18:TP=-2:LRA=9[o]")
    run([ff(), "-loglevel", "error", "-y", "-i", a, "-i", b, "-filter_complex", fc,
         "-map", "[o]", "-ac", "1", "-ar", "44100", "-b:a", "64k", dst])
    return dst


def slow(src, factor=0.85, out="slow.mp3", seconds=45.0):
    """Tempo dheema — sur nahi bigadta (asetrate + atempo)."""
    src = _abs(src)
    dst = os.path.join(OUTDIR, out if out.endswith(".mp3") else out + ".mp3")
    # pitch same rakhne ke liye asetrate + atempo ka jodaa
    af = (f"atrim=0:{seconds:.2f},asetrate=44100*{factor:.3f},aresample=44100,"
          f"atempo={1/factor:.4f},afade=t=in:st=0:d=2,afade=t=out:st={max(0, seconds-2):.2f}:d=2,"
          f"loudnorm=I=-18:TP=-2:LRA=9")
    run([ff(), "-loglevel", "error", "-y", "-i", src, "-filter:a", af,
         "-ac", "1", "-ar", "44100", "-b:a", "64k", dst])
    return dst


# ready-made recipes — jo bhaav chahiye, seedha ban jaye
RECIPES = {
    "sad":     (["music/forest_spirits_piano.mp3", "ambience/rain_gentle_1.mp3"], [1.0, 0.22], 0.9),
    "tension": (["music/forest_hiding_place.mp3", "ambience/wind_howl_window.mp3"], [1.0, 0.20], 1.0),
    "epic":    (["music/forest_tales_orchestral.mp3", "music/dhol_1.mp3"], [1.0, 0.30], 1.0),
    "calm":    (["music/forest_relax.mp3", "ambience/birds_chirp_1.mp3"], [1.0, 0.18], 1.0),
    "romantic": ([ "music/romantic_guitar.mp3", "ambience/rain_window.mp3"], [1.0, 0.15], 0.95),
    "horror":  (["music/halloween_scary.mp3", "horror/wind_eerie.mp3"], [1.0, 0.25], 0.92),
    "devotional": (["music/bhajan_maithili.mp3", "temple/shankh.mp3"], [1.0, 0.18], 1.0),
    "village": (["music/forest_folk_song.mp3", "ambience/birds_forest_1.mp3"], [1.0, 0.20], 1.0),
}


def make_mood(mood, out=None, seconds=None, slow_factor=None):
    if mood not in RECIPES:
        raise SystemExit(f"mood '{mood}' nahi hai. ye hain: {', '.join(RECIPES)}")
    paths, gains, sf = RECIPES[mood]
    missing = [p for p in paths if not os.path.exists(_abs(p))]
    if missing:
        raise SystemExit("file nahi mili: " + ", ".join(missing))
    out = out or f"made_{mood}"
    slow_factor = sf if slow_factor is None else slow_factor
    base = os.path.join(OUTDIR, f"_{out}_raw.mp3")
    d = layer(paths, gains, seconds=seconds, out=os.path.basename(base))
    if slow_factor:
        final = slow(d, factor=slow_factor, out=out, seconds=seconds or 45.0)
        try:
            os.remove(d)
        except Exception:
            pass
        return final
    return d


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("mood"); m.add_argument("mood"); m.add_argument("--out", default="")
    m.add_argument("--seconds", type=float, default=None); m.add_argument("--slow", type=float, default=None)

    l = sub.add_parser("layer"); l.add_argument("files", nargs="+")
    l.add_argument("--gains", nargs="*", type=float); l.add_argument("--seconds", type=float, default=None)
    l.add_argument("--out", default="layered")

    c = sub.add_parser("chain"); c.add_argument("a"); c.add_argument("b")
    c.add_argument("--seconds", type=float, default=20.0); c.add_argument("--out", default="chain")

    s = sub.add_parser("slow"); s.add_argument("src")
    s.add_argument("--factor", type=float, default=0.85); s.add_argument("--out", default="slow")
    s.add_argument("--seconds", type=float, default=45.0)

    a = ap.parse_args()
    if a.cmd == "mood":
        p = make_mood(a.mood, out=a.out or None, seconds=a.seconds, slow_factor=a.slow)
    elif a.cmd == "layer":
        p = layer(a.files, a.gains, a.seconds, a.out)
    elif a.cmd == "chain":
        p = chain(a.a, a.b, a.seconds, a.out)
    else:
        p = slow(a.src, a.factor, a.out, a.seconds)
    print(json.dumps({"ok": True, "file": os.path.relpath(p, LIB), "duration": round(dur(p), 1)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
