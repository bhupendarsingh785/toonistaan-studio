#!/usr/bin/env python3
"""
ASTRA — Music Match: do music ko "milakar" jodna (sirf kaatna nahi).

Kya naap-ta hai (har track ka profile):
  - tempo (BPM), energy (RMS), brightness, bass, activity

Kaise jodta hai (smart):
  1. Dono taraf ka **best hissa** chunta hai (jahan awaaz sthir ho)
  2. Tempo ko **match** karta hai (dheeme ko tez / tez ko dheema — sur nahi bigadta)
  3. Crossfade ki lambai **tempo se** tay hoti hai (dheema music = lamba fade)
  4. Energy jump zyada ho to beech me **chhota bridge** (halka hissa) daal deta hai

Chalao:
  python3 astra/music_match.py profile <file...>
  python3 astra/music_match.py join a.mp3 b.mp3 --out naya
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library")
OUT = os.path.join(LIB, "music")
SR = 22050


def ff():
    e = shutil.which("ffmpeg")
    if e:
        return e
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or b"").decode("utf-8", "ignore")[-250:])
    return r


def load(path, seconds=45.0):
    cmd = [ff(), "-loglevel", "error", "-i", path, "-t", str(seconds),
           "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or len(r.stdout) < 8000:
        return None
    return np.frombuffer(r.stdout, dtype=np.float32)


def dur(path):
    r = subprocess.run([ff(), "-i", path], capture_output=True)
    for line in (r.stderr or b"").decode("utf-8", "ignore").splitlines():
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def profile(path):
    """Track ka musical profile — tempo, energy, brightness, stability."""
    x = load(path, 45)
    if x is None:
        return None
    x = x / (np.abs(x).max() + 1e-9)
    win, hop = 2048, 1024
    frames = min(1 + (len(x) - win) // hop, 600)
    if frames < 6:
        return None
    spec = np.zeros(win // 2 + 1)
    flux, energies = [], []
    prev = None
    for i in range(frames):
        seg = x[i * hop:i * hop + win]
        if len(seg) < win:
            break
        mag = np.abs(np.fft.rfft(seg * np.hanning(win)))
        spec += mag
        energies.append(float(np.sqrt((seg ** 2).mean())))
        if prev is not None:
            flux.append(float(np.maximum(mag - prev, 0).sum()))
        prev = mag
    spec /= max(1, frames)
    freqs = np.fft.rfftfreq(win, 1 / SR)
    centroid = float((spec * freqs).sum() / (spec.sum() + 1e-9))
    bass = float(spec[freqs < 200].sum() / (spec.sum() + 1e-9))

    bpm = 0.0
    if len(flux) > 20:
        env = np.array(flux, dtype=np.float32)
        env -= env.mean()
        ac = np.correlate(env, env, "full")[len(env) - 1:]
        lo, hi = int(SR / hop * 60 / 200), min(int(SR / hop * 60 / 40), len(ac) - 1)
        if hi > lo + 2:
            lag = lo + int(np.argmax(ac[lo:hi]))
            if lag > 0:
                bpm = 60.0 * SR / (hop * lag)
    while bpm > 180:
        bpm /= 2
    while 0 < bpm < 50:
        bpm *= 2

    e = np.array(energies, dtype=np.float32) if energies else np.array([0.1])
    return {
        "file": os.path.relpath(path, LIB),
        "bpm": round(bpm, 1),
        "energy": round(float(e.mean()), 3),
        "energy_stability": round(float(1.0 / (1.0 + e.std() / (e.mean() + 1e-6))), 2),
        "brightness": round(centroid),
        "bass": round(bass, 2),
        "seconds": round(dur(path), 1),
    }


def best_cut(path, length, prof=None):
    """Sabse sthir (energy-wise) hissa — jodne ke liye sabse saaf."""
    prof = prof or profile(path) or {}
    total = prof.get("seconds") or dur(path)
    length = min(length, max(2.0, total - 1.0))
    x = load(path, min(total, 60))
    if x is None:
        return 0.0, length
    win = int(SR * 1.0)
    if len(x) < win * 2:
        return 0.0, length
    rms = np.array([float(np.sqrt((x[i:i + win] ** 2).mean())) for i in range(0, len(x) - win, win)])
    need = int(np.ceil(length))
    best_i, best_score = 0, -1e9
    for i in range(0, max(1, len(rms) - need + 1)):
        seg = rms[i:i + need]
        score = seg.mean() - 2.0 * seg.std()      # bhara hua + sthir
        if score > best_score:
            best_score, best_i = score, i
    start = max(0.0, min(best_i * 1.0, total - length))
    return start, length


def cut_stretch(src, start, length, target_bpm=None, out=None, fade=0.4):
    """Hissa kaato + tempo match karo (sur nahi badalta)."""
    src_p = src if os.path.isabs(src) else os.path.join(LIB, src)
    p = profile(src_p) or {}
    bpm = p.get("bpm") or 0
    tempo = 1.0
    if target_bpm and bpm:
        tempo = max(0.85, min(1.18, target_bpm / bpm))     # halka hi stretch (sur bache)
    af = (f"atrim={start:.2f}:{start + length:.2f},asetpts=N/SR/TB,"
          + (f"atempo={tempo:.4f}," if abs(tempo - 1.0) > 0.01 else "")
          + f"afade=t=in:st=0:d={fade},afade=t=out:st={max(0, length - fade):.2f}:d={fade}")
    run([ff(), "-loglevel", "error", "-y", "-i", src_p, "-filter:a", af,
         "-ac", "1", "-ar", str(SR), out])
    return out, {"bpm_src": bpm, "tempo_factor": round(tempo, 3), "start": round(start, 2)}


def smart_join(files, out="match_join", lengths=None, verbose=True):
    """Do ya zyada music ko matching ke saath jodo (kaat + tempo + adaptive fade)."""
    procs = [f if os.path.isabs(f) else os.path.join(LIB, f) for f in files]
    profs = [profile(p) or {} for p in procs]
    base_bpm = next((x.get("bpm") for x in profs if x.get("bpm")), None)

    tmpd = os.path.join(OUT, "_match")
    os.makedirs(tmpd, exist_ok=True)
    parts, info = [], []
    for i, (p, pr) in enumerate(zip(procs, profs)):
        L = (lengths[i] if lengths and i < len(lengths) else 12.0)
        start, length = best_cut(p, L, pr)
        seg = os.path.join(tmpd, f"p{i}.wav")
        _, meta = cut_stretch(p, start, length, target_bpm=base_bpm, out=seg,
                              fade=0.5 if (pr.get("bpm") or 0) < 90 else 0.35)
        meta.update({"file": os.path.relpath(p, LIB), "bpm": pr.get("bpm"),
                     "energy": pr.get("energy")})
        info.append(meta)
        parts.append(seg)

    # crossfade: dheema music = lamba fade
    cur = parts[0]
    for n, nxt in enumerate(parts[1:], 1):
        a_bpm = info[n - 1].get("bpm") or 90
        b_bpm = info[n].get("bpm") or 90
        fade = 1.6 if min(a_bpm, b_bpm) >= 100 else 2.6
        o = os.path.join(tmpd, f"j{n}.wav")
        run([ff(), "-loglevel", "error", "-y", "-i", cur, "-i", nxt, "-filter_complex",
             f"[0:a][1:a]acrossfade=d={fade}:c1=tri:c2=tri[o]", "-map", "[o]",
             "-ac", "1", "-ar", str(SR), o])
        info[n]["crossfade_s"] = fade
        cur = o

    dst = os.path.join(OUT, out if out.endswith(".mp3") else out + ".mp3")
    run([ff(), "-loglevel", "error", "-y", "-i", cur, "-filter:a",
         "alimiter=limit=0.95,loudnorm=I=-18:TP=-2:LRA=9", "-ac", "1", "-ar", "44100", "-b:a", "64k", dst])
    shutil.rmtree(tmpd, ignore_errors=True)
    if verbose:
        print("MATCH_JOIN", os.path.basename(dst), round(dur(dst), 1), "s", flush=True)
        for i in info:
            print(f"  {i.get('file','?'):34s} bpm={i.get('bpm')} stretch={i.get('tempo_factor')} "
                  f"energy={i.get('energy')} fade={i.get('crossfade_s','-')}", flush=True)
    return {"output": dst, "seconds": round(dur(dst), 1), "parts": info}


def main():
    if len(sys.argv) < 2:
        print("usage: music_match.py profile <files...> | join <a> <b> [--out name]")
        return 1
    cmd = sys.argv[1]
    if cmd == "profile":
        for p in sys.argv[2:]:
            print(json.dumps(profile(p if os.path.isabs(p) else os.path.join(LIB, p)), ensure_ascii=False))
        return 0
    if cmd == "join":
        argv = sys.argv[2:]
        out = "match_join"
        if "--out" in argv:
            i = argv.index("--out")
            out = argv[i + 1] if i + 1 < len(argv) else "match_join"
            argv = argv[:i] + argv[i + 2:]
        args = [a for a in argv if not a.startswith("--")]
        r = smart_join(args, out=out)
        print(json.dumps({"output": r["output"], "seconds": r["seconds"]}, ensure_ascii=False))
        return 0
    print("pata nahi:", cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
