#!/usr/bin/env python3
"""Audio Read v4 — andar kya chal raha hai: awaaz, music, background, mahaul.

Kaam:
  1) STEMS       — spectral subtraction se **speech alag**, **background alag** (aur music/tonal)
  2) MUSIC       — key/scale (chroma), tempo, tonal-ness, kitna loud
  3) BACKGROUND  — kitne tarah ki awaazein, kab, kaisi (thud/hiss/tonal), level timeline
  4) EMOTION     — har speaker turn ka bhaav (pace+sur+energy se): khushi/dukh/gussa/dar/neutral
  5) INTERACTION — kaun kitna bolta hai, kitne gap, overlap, kaun pehle shuru karta hai
  6) FIT         — hamare pipeline ke target se tulna: music bed dialogue se kitna neeche, ducking kitni

CLI: python tools/audio_read4.py --audio x.mp3 --out outdir [--full]
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR = 16000
N_FFT, HOP = 512, 160


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def decode(path: str, sr: int = SR):
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", path, "-f", "s16le",
                        "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768.0


def stft(x, n=N_FFT, hop=HOP):
    import numpy as np
    win = np.hamming(n)
    frames = [x[i:i + n] * win for i in range(0, max(1, len(x) - n), hop)]
    return np.array([np.fft.rfft(f) for f in frames]), hop


def istft(S, n=N_FFT, hop=HOP, length=None):
    import numpy as np
    win = np.hamming(n)
    out = np.zeros((len(S) - 1) * hop + n)
    for i, spec in enumerate(S):
        seg = np.fft.irfft(spec, n) * win
        out[i * hop:i * hop + n] += seg
    out /= (np.sum(win ** 2) / hop) if hop else 1.0
    return out[:length] if length else out


def stems(x):
    """speech vs background: stationary background (median spectrum) hata do."""
    import numpy as np
    S, hop = stft(x)
    mag = np.abs(S)
    med = np.median(mag, axis=0)                     # jo har waqt maujood = background
    mask_bg = np.clip(med[None, :] / (mag + 1e-9), 0, 1)
    bg = istft(S * mask_bg, length=len(x))
    n = min(len(x), len(bg))
    bg = bg[:n]
    sp = x[:n] - bg
    # music/tonal = background me jo stable harmonic hai (spectral flatness kam)
    flat = np.exp(np.mean(np.log(mag + 1e-9), axis=1)) / (np.mean(mag, axis=1) + 1e-9)
    tonal = float((flat < 0.25).mean())
    return sp, bg, tonal, flat


def chroma(bg):
    """kaunse sur (12 pitch class) — dhun/scale ka andaaza."""
    import numpy as np
    S, _ = stft(bg)
    mag = np.abs(S).mean(0)
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    ch = np.zeros(12)
    for f, m in zip(freqs, mag):
        if 60 <= f <= 2000 and m > 0:
            pc = int(round(12 * np.log2(f / 261.63))) % 12
            ch[pc] += m
    if ch.sum() == 0:
        return {}, ""
    ch = ch / ch.sum()
    top = sorted(zip(names, ch), key=lambda t: -t[1])[:4]
    key = top[0][0]
    return {n: round(float(v), 3) for n, v in zip(names, ch)}, key


def tempo_of(bg):
    import numpy as np
    S, _ = stft(bg)
    mag = np.abs(S)
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


def vad(x):
    import numpy as np
    N = 512
    e = np.array([np.sqrt((x[i:i + N] ** 2).mean()) for i in range(0, max(1, len(x) - N), HOP)])
    thr = max(0.006, float(np.percentile(e, 15)) * 2.0)
    lab = e > thr
    segs, cur, st = [], bool(lab[0]), 0.0
    for i, v in enumerate(lab):
        t = i * HOP / SR
        if bool(v) != cur:
            if t - st > 0.10:
                segs.append({"type": "speech" if cur else "silence",
                             "start": round(st, 2), "end": round(t, 2), "dur": round(t - st, 2)})
            cur, st = bool(v), t
    segs.append({"type": "speech" if cur else "silence",
                 "start": round(st, 2), "end": round(len(lab) * HOP / SR, 2),
                 "dur": round(len(lab) * HOP / SR - st, 2)})
    return segs


def f0_of(seg):
    import numpy as np
    N = len(seg)
    if N < 320:
        return 0.0
    seg = seg - seg.mean()
    ac = np.correlate(seg, seg, "full")[N - 1:]
    lo, hi = int(SR / 400), int(SR / 70)
    if hi >= len(ac):
        return 0.0
    k = lo + int(np.argmax(ac[lo:hi]))
    return float(SR / k) if k > 0 else 0.0


def emotion_of(f0s, energy, pace):
    import numpy as np
    if not f0s:
        return "neutral"
    hz, sd = float(np.median(f0s)), float(np.std(f0s))
    if hz < 150 and pace < 3.2:
        return "dukh/thakaan"
    if sd > 45 and pace > 4.0:
        return "gussa/tez"
    if sd > 40:
        return "khushi/josh"
    if pace < 3.0:
        return "thehra/dukh"
    return "neutral"


def read(path: str, outdir: Path | None = None) -> dict:
    import numpy as np
    x = decode(path)
    if len(x) == 0:
        return {"ok": False, "why": "decode fail"}
    dur = len(x) / SR
    sp, bg, tonal, flat = stems(x)
    segs = vad(sp)

    # speaker turns + emotion
    turns = []
    for s in segs:
        if s["type"] != "speech" or s["dur"] < 0.2:
            continue
        a, b = int(s["start"] * SR), int(s["end"] * SR)
        seg = sp[a:b]
        N, H = 640, 320
        f0s = [f0_of(seg[i:i + N]) for i in range(0, max(1, len(seg) - N), H)]
        f0s = [f for f in f0s if f > 0]
        en = float(np.sqrt((seg ** 2).mean()))
        pace = round(len(f0s) * 0.02 / max(1e-6, s["dur"]) * 50, 2)
        turns.append({**s, "f0": int(np.median(f0s)) if f0s else 0,
                      "f0_std": round(float(np.std(f0s)), 1) if f0s else 0.0,
                      "energy_dbfs": round(20 * np.log10(max(1e-9, en)), 1),
                      "emotion": emotion_of(f0s, en, pace)})
    # interaction
    gaps = []
    for i in range(1, len(turns)):
        gaps.append(round(turns[i]["start"] - turns[i - 1]["end"], 2))
    interaction = {"turns": len(turns),
                   "gaps": {"mean_s": round(float(np.mean(gaps)), 2) if gaps else 0,
                            "max_s": round(float(np.max(gaps)), 2) if gaps else 0,
                            "min_s": round(float(np.min(gaps)), 2) if gaps else 0},
                   "back_and_forth": sum(1 for g in gaps if 0 <= g <= 0.6),
                   "long_gaps": sum(1 for g in gaps if g > 1.5)}

    # background events
    Sb, _ = stft(bg)
    magb = np.abs(Sb)
    flux = np.maximum(0, np.diff(magb, axis=0)).sum(1)
    events = []
    if len(flux) > 8:
        mu, sd = flux.mean(), flux.std() + 1e-9
        freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
        last = -9
        for i in range(2, len(flux) - 2):
            if flux[i] > mu + 1.9 * sd and flux[i] == flux[i - 2:i + 3].max():
                t = round(i * HOP / SR, 2)
                if t - last < 0.15:
                    continue
                spec = magb[i]
                low, high = float(spec[freqs < 300].sum()), float(spec[freqs > 3000].sum())
                mid = float(spec[(freqs >= 300) & (freqs <= 3000)].sum()) + 1e-9
                events.append({"at": t,
                               "kind": ("thud/impact" if low > high * 1.6 and low > mid * 0.5 else
                                        "hiss/noise" if high > mid * 0.7 else "tonal/mixed")})
                last = t

    ch, key = chroma(bg)
    tempo, conf = tempo_of(bg)
    speech_s = sum(t["dur"] for t in turns)
    bg_lvl = round(20 * np.log10(max(1e-9, float(np.sqrt((bg ** 2).mean())))), 1)
    sp_lvl = round(20 * np.log10(max(1e-9, float(np.sqrt((sp ** 2).mean())))), 1)

    # FIT judgement (hamare pipeline target: bed dialogue se ~10-12 dB neeche)
    diff = round(sp_lvl - bg_lvl, 1)
    fit = ("background theek hai (speech se ~10-12 dB neeche)" if 8 <= diff <= 16 else
           "background zyada loud hai — speech dab rahi hai" if diff < 8 else
           "background bahut dheema — mahaul mehsoos nahi hoga")

    rep = {
        "ok": True, "file": str(path), "dur": round(dur, 2),
        "levels": {"speech_dbfs": sp_lvl, "background_dbfs": bg_lvl, "difference_db": diff},
        "speech": {"speech_s": round(speech_s, 2), "segments": len(turns)},
        "turns": turns, "interaction": interaction,
        "music": {"tonal_ratio": round(tonal, 3), "key_guess": key, "chroma": ch,
                  "tempo_bpm": tempo, "tempo_confidence": conf,
                  "music_likely": bool(tempo and 60 <= tempo <= 180 and conf >= 3.0 and tonal > 0.2)},
        "background": {"events": events, "event_count": len(events),
                       "flatness_mean": round(float(np.mean(flat)), 3)},
        "fit": fit,
    }
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
        for name, sig in (("speech", sp), ("background", bg)):
            p = outdir / f"{Path(path).stem}.{name}.wav"
            import wave
            with wave.open(str(p), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
                w.writeframes((np.clip(sig, -1, 1) * 32767).astype("int16").tobytes())
            rep.setdefault("stems", {})[name] = str(p)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    outdir = Path(a.out) if a.out else None
    rep = read(a.audio, outdir)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: rep.get(k) for k in ("dur", "levels", "speech", "interaction", "music", "fit")}
    brief["background_events"] = rep.get("background", {}).get("event_count")
    brief["emotions"] = sorted({t["emotion"] for t in rep.get("turns", [])})
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
