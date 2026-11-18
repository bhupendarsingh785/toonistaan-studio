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



def _cut(src, a, b, out, fade=0.35):
    """Ek track ka hissa kaato (chhote fade ke saath)."""
    af = (f"atrim={a:.2f}:{b:.2f},asetpts=N/SR/TB,"
          f"afade=t=in:st=0:d={fade},afade=t=out:st={max(0, (b-a)-fade):.2f}:d={fade}")
    run([ff(), "-loglevel", "error", "-y", "-i", src, "-filter:a", af,
         "-ac", "1", "-ar", "44100", out])
    return out


def splice(pieces, out="splice.mp3", fade=0.5):
    """Editor jaisa: A ka tukda + B ka tukda + C ka tukda = naya music."""
    tmpd = os.path.join(OUTDIR, "_splice")
    os.makedirs(tmpd, exist_ok=True)
    parts = []
    for i, (src, a, b) in enumerate(pieces):
        srcp = _abs(src)
        if not os.path.exists(srcp):
            raise FileNotFoundError(srcp)
        parts.append(_cut(srcp, float(a), float(b), os.path.join(tmpd, f"p{i}.wav"), fade=fade))
    cur = parts[0]
    for n, nxt in enumerate(parts[1:], 1):
        o = os.path.join(tmpd, f"j{n}.wav")
        run([ff(), "-loglevel", "error", "-y", "-i", cur, "-i", nxt, "-filter_complex",
             f"[0:a][1:a]acrossfade=d={fade}:c1=tri:c2=tri[o]", "-map", "[o]",
             "-ac", "1", "-ar", "44100", o])
        cur = o
    dst = os.path.join(OUTDIR, out if out.endswith(".mp3") else out + ".mp3")
    run([ff(), "-loglevel", "error", "-y", "-i", cur, "-filter:a",
         "alimiter=limit=0.95,loudnorm=I=-18:TP=-2:LRA=9", "-ac", "1", "-ar", "44100", "-b:a", "64k", dst])
    shutil.rmtree(tmpd, ignore_errors=True)
    return dst


def build(recipe, out="built.mp3", seconds=45.0):
    """intro (A) -> body (A+B+bed layer) -> outro (C) = naya music."""
    intro = _abs(recipe["intro"])
    body = [_abs(p) for p in recipe.get("body", [])]
    bed = _abs(recipe["bed"]) if recipe.get("bed") else None
    outro = _abs(recipe["outro"]) if recipe.get("outro") else None
    part = max(6.0, seconds / 3.0)
    tmpd = os.path.join(OUTDIR, "_build")
    os.makedirs(tmpd, exist_ok=True)

    a = _cut(intro, 2.0, 2.0 + part, os.path.join(tmpd, "intro.wav"), fade=0.6)
    layers = []
    for i, bp in enumerate(body[:2]):
        layers.append(_cut(bp, 4.0, 4.0 + part, os.path.join(tmpd, f"b{i}.wav"), fade=0.6))
    if bed:
        layers.append(_cut(bed, 1.0, 1.0 + part, os.path.join(tmpd, "bed.wav"), fade=1.0))
    gains = [1.0, 0.55, 0.22][:len(layers)]
    cmd = [ff(), "-loglevel", "error", "-y"]
    for l in layers:
        cmd += ["-i", l]
    fc = [f"[{i}:a]volume={g}[v{i}]" for i, g in enumerate(gains)]
    fc.append("".join(f"[v{i}]" for i in range(len(layers))) + f"amix=inputs={len(layers)}:normalize=0[m]")
    b = os.path.join(tmpd, "body.wav")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[m]", "-ac", "1", "-ar", "44100", b]
    run(cmd)

    seq = [a, b]
    if outro:
        seq.append(_cut(outro, 2.0, 2.0 + part, os.path.join(tmpd, "outro.wav"), fade=0.8))
    cur = seq[0]
    for n, nxt in enumerate(seq[1:], 1):
        o = os.path.join(tmpd, f"j{n}.wav")
        run([ff(), "-loglevel", "error", "-y", "-i", cur, "-i", nxt, "-filter_complex",
             "[0:a][1:a]acrossfade=d=2.5:c1=tri:c2=tri[o]", "-map", "[o]",
             "-ac", "1", "-ar", "44100", o])
        cur = o
    dst = os.path.join(OUTDIR, out if out.endswith(".mp3") else out + ".mp3")
    end_fade = max(0, dur(cur) - 2)
    run([ff(), "-loglevel", "error", "-y", "-i", cur, "-filter:a",
         f"afade=t=out:st={end_fade:.2f}:d=2,alimiter=limit=0.95,loudnorm=I=-18:TP=-2:LRA=9",
         "-ac", "1", "-ar", "44100", "-b:a", "64k", dst])
    shutil.rmtree(tmpd, ignore_errors=True)
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

    sp = sub.add_parser("splice"); sp.add_argument("pieces", nargs="+",
        help="har piece: file:start:end  (jaise music/a.mp3:4:12)")
    sp.add_argument("--out", default="splice"); sp.add_argument("--fade", type=float, default=0.5)

    bd = sub.add_parser("build"); bd.add_argument("intro"); bd.add_argument("body", nargs="+")
    bd.add_argument("--bed", default=""); bd.add_argument("--outro", default="")
    bd.add_argument("--out", default="built"); bd.add_argument("--seconds", type=float, default=45.0)

    a = ap.parse_args()
    if a.cmd == "splice":
        pieces = []
        for spec in a.pieces:
            f, st, en = spec.rsplit(":", 2)
            pieces.append((f, float(st), float(en)))
        p = splice(pieces, a.out, a.fade)
    elif a.cmd == "build":
        p = build({"intro": a.intro, "body": a.body, "bed": a.bed or None,
                   "outro": a.outro or None}, a.out, a.seconds)
    elif a.cmd == "mood":
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
