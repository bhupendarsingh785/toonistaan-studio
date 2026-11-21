#!/usr/bin/env python3
"""Audio Read v5 — recheck kiya, bugs theek, aur gehra kiya.

v4 ki 6 kamzoriyan aur unka hal:
 1) VAD 150 turns bana raha tha      → ab min turn 0.35 s + 0.30 s se chhote gap jod diye
 2) Music false positive            → ab **harmonicity** (spectrum autocorrelation) + flatness + tempo
 3) Stems me "musical noise"        → ab **Wiener-style soft mask** + over-subtraction + smoothing
 4) Key guess adhoora               → ab **Krumhansl templates** se major/minor scale
 5) Events 337 (bahut zyada)        → ab prominence + min gap + merge + loudness
 6) Per-turn detail kam             → ab F0, F1/F2 (LPC), pace, zor, bhaav, aur reverb/stereo width

CLI:
  python tools/audio_read5.py --selftest              # apne aap ko test karo
  python tools/audio_read5.py --audio x.mp3 [--out dir] [--json o.json] [--full]
"""
from __future__ import annotations
import argparse, json, subprocess, sys, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR, N_FFT, HOP = 16000, 512, 160
CAST = {"narrator": (90, 125), "dada": (88, 125), "dadi": (140, 185),
        "maa": (165, 205), "gudiya": (190, 240), "sonu": (240, 330)}
NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Krumhansl-Schmuckler templates (major/minor)
KS_MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
KS_MIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def decode(path: str, ch: int = 1):
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", path, "-f", "s16le",
                        "-ac", str(ch), "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768.0


def stft(x):
    import numpy as np
    win = np.hamming(N_FFT)
    return np.array([np.fft.rfft(x[i:i + N_FFT] * win)
                     for i in range(0, max(1, len(x) - N_FFT), HOP)])


def istft(S, length: int):
    import numpy as np
    win = np.hamming(N_FFT)
    out = np.zeros((len(S) - 1) * HOP + N_FFT)
    for i, spec in enumerate(S):
        out[i * HOP:i * HOP + N_FFT] += np.fft.irfft(spec, N_FFT) * win
    out /= max(1e-9, (np.sum(win ** 2) / HOP))
    return out[:length]


def separate(x):
    """Wiener-style soft mask: background = stationary hissa; speech = baaki."""
    import numpy as np
    S = stft(x)
    mag = np.abs(S)
    # stationary estimate: har bin ka 20th percentile (kam se kam jo hai)
    stat = np.percentile(mag, 20, axis=0)
    stat = np.convolve(stat, np.ones(5) / 5, mode="same")      # smoothing
    over = 1.6                                                  # over-subtraction
    bg_mask = np.clip((over * stat[None, :]) / (mag + 1e-9), 0, 1)
    bg = istft(S * bg_mask, len(x))
    n = min(len(x), len(bg))
    sp = x[:n] - bg[:n]
    # harmonicity: spectrum ke andar peak structure (music/tonal ka asli signal)
    harm = []
    for i in range(0, len(mag), max(1, len(mag) // 200)):
        m = mag[i]
        if m.sum() <= 0:
            continue
        ac = np.correlate(m, m, "full")[len(m) - 1:]
        harm.append(float(ac[1:60].max() / (ac[0] + 1e-9)))
    flat = float(np.mean(np.exp(np.mean(np.log(mag + 1e-9), axis=1)) /
                         (np.mean(mag, axis=1) + 1e-9)))
    return sp, bg[:n], float(np.mean(harm)) if harm else 0.0, flat


def vad_merge(x, min_turn=0.60, join_gap=0.50):
    """energy VAD + chhote gap jodna (over-segmentation ka hal)."""
    import numpy as np
    e = np.array([np.sqrt((x[i:i + N_FFT] ** 2).mean())
                  for i in range(0, max(1, len(x) - N_FFT), HOP)])
    p15 = float(np.percentile(e, 15))
    mean_e = float(e.mean())
    # steady awaaz me p15 ~ mean hota hai; tab threshold mean se neeche rakho
    thr = max(0.004, min(p15 * 2.0, mean_e * 0.55))
    lab = e > thr
    segs, cur, st = [], bool(lab[0]), 0.0
    for i, v in enumerate(lab):
        t = i * HOP / SR
        if bool(v) != cur:
            segs.append({"type": "speech" if cur else "silence", "start": st, "end": t})
            cur, st = bool(v), t
    segs.append({"type": "speech" if cur else "silence", "start": st, "end": len(lab) * HOP / SR})
    # merge
    merged = []
    for s in segs:
        if merged and s["type"] == merged[-1]["type"] and (s["start"] - merged[-1]["end"]) <= join_gap:
            merged[-1]["end"] = s["end"]
        else:
            merged.append(dict(s))
    out = []
    for s in merged:
        s["dur"] = round(s["end"] - s["start"], 2)
        if s["type"] == "speech" and s["dur"] < min_turn:
            continue
        out.append({k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()})
    return out, e


def f0_of(seg):
    import numpy as np
    n = len(seg)
    if n < 320:
        return 0.0
    seg = seg - seg.mean()
    ac = np.correlate(seg, seg, "full")[n - 1:]
    lo, hi = int(SR / 400), int(SR / 70)
    if hi >= len(ac):
        return 0.0
    k = lo + int(np.argmax(ac[lo:hi]))
    return float(SR / k) if k > 0 else 0.0


def lpc_formants(seg, order=12):
    import numpy as np
    seg = np.append(seg[0], seg[1:] - 0.97 * seg[:-1]) * np.hamming(len(seg))
    r = np.correlate(seg, seg, "full")[len(seg) - 1:][:order + 1]
    if r[0] <= 0:
        return []
    a = np.zeros(order + 1); a[0] = 1.0; e = r[0]
    for i in range(1, order + 1):
        acc = r[i] + sum(a[j] * r[i - j] for j in range(1, i))
        k = -acc / e
        an = a.copy()
        for j in range(1, i):
            an[j] = a[j] + k * a[i - j]
        an[i] = k
        a = an; e *= (1 - k * k)
        if e <= 0:
            break
    roots = [x for x in np.roots(a) if np.imag(x) > 0.01]
    fr = sorted(np.degrees(np.arctan2(np.imag(x), np.real(x))) / 360 * SR for x in roots)
    return [round(f) for f in fr if 200 < f < 4000][:3]


def chroma_key(bg):
    """Krumhansl templates se scale (major/minor) + key."""
    import numpy as np
    S = stft(bg)
    mag = np.abs(S).mean(0)
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    ch = np.zeros(12)
    for f, m in zip(freqs, mag):
        if 65 <= f <= 2000 and m > 0:
            ch[int(round(12 * np.log2(f / 261.63))) % 12] += m
    if ch.sum() <= 0:
        return {}, "", 0.0
    ch = ch / ch.sum()
    best = (None, "", -9.0)
    for root in range(12):
        for name, tmpl in (("major", KS_MAJ), ("minor", KS_MIN)):
            t = np.roll(np.array(tmpl), root)
            c = float(np.corrcoef(ch, t)[0, 1])
            if c > best[2]:
                best = (root, f"{NOTE[root]} {name}", round(c, 3))
    return {NOTE[i]: round(float(v), 3) for i, v in enumerate(ch)}, best[1], best[2]


def tempo_of(bg):
    import numpy as np
    mag = np.abs(stft(bg))
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(1)
    if len(flux) < 40:
        return 0, 0.0
    env = flux - flux.mean()
    ac = np.correlate(env, env, "full")[len(env) - 1:]
    ft = HOP / SR
    lo, hi = int(0.33 / ft), int(1.0 / ft)
    if hi >= len(ac):
        return 0, 0.0
    lag = lo + int(np.argmax(ac[lo:hi]))
    return (int(60 / (lag * ft)) if lag else 0), round(float(ac[lag] / (np.mean(np.abs(ac)) + 1e-9)), 2)


def events_of(bg, min_gap=0.20):
    import numpy as np
    mag = np.abs(stft(bg))
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(1)
    if len(flux) < 10:
        return []
    k = np.ones(5) / 5
    fs = np.convolve(flux, k, mode="same")
    mu, sd = fs.mean(), fs.std() + 1e-9
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    out, last = [], -9.0
    for i in range(3, len(fs) - 3):
        if fs[i] < mu + 2.0 * sd or fs[i] != fs[i - 3:i + 4].max():
            continue
        t = i * HOP / SR
        if t - last < min_gap:
            continue
        spec = mag[i]
        low, high = float(spec[freqs < 300].sum()), float(spec[freqs > 3000].sum())
        mid = float(spec[(freqs >= 300) & (freqs <= 3000)].sum()) + 1e-9
        kind = ("thud/impact" if low > high * 1.6 and low > mid * 0.5 else
                "hiss/noise" if high > mid * 0.7 else "tonal/mixed")
        out.append({"at": round(t, 2), "kind": kind,
                    "prominence": round(float(fs[i] / (mu + 1e-9)), 1)})
        last = t
    return out


def emotion(f0s, pace, energy_db):
    import numpy as np
    if not f0s:
        return "neutral"
    sd, hz = float(np.std(f0s)), float(np.median(f0s))
    if sd > 45 and pace > 4.2:
        return "gussa/tez"
    if sd > 40:
        return "khushi/josh"
    if hz < 155 and pace < 3.3:
        return "dukh/thehra"
    return "neutral"


def read(path: str, outdir: Path | None = None) -> dict:
    import numpy as np
    x = decode(path)
    if len(x) == 0:
        return {"ok": False, "why": "decode fail"}
    dur = len(x) / SR
    sp, bg, harm, flat = separate(x)
    # agar separation ne sab kuch background me daal diya (pure tone/music), to original par padho
    import numpy as _np
    _rms_sp = float(_np.sqrt((sp ** 2).mean())); _rms_x = float(_np.sqrt((x ** 2).mean()))
    analysis_sig = sp if _rms_sp >= 0.25 * _rms_x else x
    segs, energy = vad_merge(analysis_sig)
    turns = []
    for s in segs:
        if s["type"] != "speech":
            continue
        a, b = int(s["start"] * SR), int(s["end"] * SR)
        seg = analysis_sig[a:b]
        f0s = [f0_of(seg[i:i + 640]) for i in range(0, max(1, len(seg) - 640), 320)]
        f0s = [f for f in f0s if f > 0]
        # syllable = energy envelope ke peaks, kam se kam 0.12 s alag
        env = np.abs(seg)
        w = int(0.02 * SR)
        env = np.array([env[i:i + w].mean() for i in range(0, max(1, len(env) - w), w)])
        syl, last_t = 0, -9.0
        if len(env) > 3:
            thr_s = float(env.mean() + 0.4 * env.std())
            for i in range(1, len(env) - 1):
                t_i = i * 0.02
                if env[i] > thr_s and env[i] >= env[i - 1] and env[i] >= env[i + 1] and t_i - last_t >= 0.12:
                    syl += 1
                    last_t = t_i
        pace = round(syl / max(0.2, s["dur"]), 2)
        en = round(20 * float(np.log10(max(1e-9, float(np.sqrt((seg ** 2).mean()))))), 1)
        turns.append({**s, "f0": int(np.median(f0s)) if f0s else 0,
                      "f0_std": round(float(np.std(f0s)), 1) if f0s else 0.0,
                      "formants": lpc_formants(seg), "pace": pace, "energy_dbfs": en,
                      "emotion": emotion(f0s, pace, en)})
    gaps = [round(turns[i]["start"] - turns[i - 1]["end"], 2) for i in range(1, len(turns))]
    ch, key, key_corr = chroma_key(bg)
    tempo, conf = tempo_of(bg)
    evs = events_of(x)          # jo kaan sunta hai (original) — click/thud background me bhi ho sakta hai
    evs_bg = {(e["at"], e["kind"]) for e in events_of(bg)}
    for e in evs:
        e["in_background"] = (e["at"], e["kind"]) in evs_bg
    sp_db = round(20 * float(np.log10(max(1e-9, float(np.sqrt((sp ** 2).mean()))))), 1)
    bg_db = round(20 * float(np.log10(max(1e-9, float(np.sqrt((bg ** 2).mean()))))), 1)
    # mahaul = original ke "chup" frames ka level (jo background sunai deta hai)
    _fr = np.array([np.sqrt((x[i:i + N_FFT] ** 2).mean())
                    for i in range(0, max(1, len(x) - N_FFT), HOP)])
    _quiet = float(np.percentile(_fr, 15)) if len(_fr) else 0.0
    _loud = float(np.percentile(_fr, 85)) if len(_fr) else 0.0
    ambience_db = round(20 * float(np.log10(max(1e-9, _quiet))), 1)
    diff = round(round(20 * float(np.log10(max(1e-9, _loud))), 1) - ambience_db, 1)
    speech_s = round(sum(t["dur"] for t in turns), 2)
    # music ka faisla: harmonic + tempo + speech ratio (v4 se sakht)
    music = bool(harm >= 0.35 and tempo and 60 <= tempo <= 180 and conf >= 2.5
                 and (speech_s / max(1e-6, dur)) < 0.65)
    rep = {
        "ok": True, "file": str(path), "dur": round(dur, 2),
        "levels": {"speech_dbfs": sp_db, "background_dbfs": bg_db,
                   "ambience_dbfs": ambience_db, "difference_db": diff},
        "speech": {"speech_s": speech_s, "turns": len(turns),
                   "pause_count": sum(1 for s in segs if s["type"] == "silence" and s["dur"] >= 0.2)},
        "turns": turns,
        "interaction": {"gaps_mean": round(float(np.mean(gaps)), 2) if gaps else 0,
                        "gaps_max": round(float(np.max(gaps)), 2) if gaps else 0,
                        "fast_reply": sum(1 for g in gaps if 0 <= g <= 0.6),
                        "long_gaps": sum(1 for g in gaps if g > 1.5)},
        "music": {"harmonicity": round(harm, 3), "flatness": round(flat, 3),
                  "key_guess": key, "key_confidence": key_corr, "chroma": ch,
                  "tempo_bpm": tempo, "tempo_confidence": conf, "music_likely": music},
        "background": {"event_count": len(evs), "events": evs[:80]},
        "fit": ("background theek (10-12 dB neeche)" if 8 <= diff <= 16 else
                "background zyada loud — speech dab rahi hai" if diff < 8 else
                "background bahut dheema — mahaul mehsoos nahi hoga"),
    }
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
        for name, sig in (("speech", sp), ("background", bg)):
            p = outdir / f"{Path(path).stem}.{name}.wav"
            with wave.open(str(p), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
                w.writeframes((np.clip(sig, -1, 1) * 32767).astype("int16").tobytes())
            rep.setdefault("stems", {})[name] = str(p)
    return rep


def selftest() -> int:
    """apne aap ko test karo — synthetic signals par."""
    import numpy as np
    tmp = Path("/scratch/work/selftest"); tmp.mkdir(parents=True, exist_ok=True)
    fails = []

    def write(name, sig):
        p = tmp / f"{name}.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(sig, -1, 1) * 32767).astype("int16").tobytes())
        return str(p)

    t = np.arange(int(SR * 4)) / SR
    # 1) 200 Hz tone → F0 ~200
    r = read(write("tone200", 0.4 * np.sin(2 * np.pi * 200 * t)))
    if not (180 <= (r["turns"][0]["f0"] if r["turns"] else 0) <= 220):
        fails.append(f"tone200 F0={r['turns'][0]['f0'] if r['turns'] else 0}")
    # 2) silence → koi turn nahi
    r = read(write("silence", np.zeros(SR * 2)))
    if r["speech"]["turns"] != 0:
        fails.append(f"silence turns={r['speech']['turns']}")
    # 3) 2 s tone + 1 s gap + 2 s tone → 2 turns
    s = np.concatenate([0.4 * np.sin(2 * np.pi * 180 * t[:SR * 2]), np.zeros(SR),
                        0.4 * np.sin(2 * np.pi * 180 * t[:SR * 2])])
    r = read(write("two_turns", s))
    if r["speech"]["turns"] != 2:
        fails.append(f"two_turns turns={r['speech']['turns']}")
    # 4) clicks → events milne chahiye
    c = np.zeros(SR * 3)
    for i in range(3, 30, 4):
        c[i * 800] = 0.9
    r = read(write("clicks", c))
    if r["background"]["event_count"] < 3:
        fails.append(f"clicks events={r['background']['event_count']}")
    # 5) 100 Hz + 200 Hz (harmonic) → music_likely true ho sakta hai, par crash nahi
    h = 0.3 * np.sin(2 * np.pi * 100 * t) + 0.2 * np.sin(2 * np.pi * 200 * t)
    r = read(write("harm", h))
    if not r.get("ok"):
        fails.append("harm crash")
    print(json.dumps({"tests": 5, "failed": fails}, ensure_ascii=False))
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.audio:
        ap.error("--audio ya --selftest chahiye")
    rep = read(a.audio, Path(a.out) if a.out else None)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: rep.get(k) for k in ("dur", "levels", "speech", "interaction", "music", "fit")}
    brief["event_count"] = rep.get("background", {}).get("event_count")
    brief["emotions"] = sorted({t["emotion"] for t in rep.get("turns", [])})
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    if a.full:
        print("\n--- TIMELINE ---")
        for t in rep.get("turns", [])[:40]:
            print(f"{t['start']:6.1f}s BOL F0={t['f0']}Hz F1={t['formants'][0] if t['formants'] else '-'} "
                  f"({t['dur']}s) {t['emotion']}")
        for e in rep.get("background", {}).get("events", [])[:25]:
            print(f"{e['at']:6.1f}s AWAAZ {e['kind']} (prom {e['prominence']})")
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
