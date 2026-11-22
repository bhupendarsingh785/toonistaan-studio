#!/usr/bin/env python3
"""Audio Read v3 — deep research wala padhne ka system (numpy only).

Research se liye gaye tarike:
  • MFCC + k-means clustering = **speaker diarization** (kaun kab bol raha hai)
  • LPC (Levinson–Durbin) → **F1/F2 formants** = awaaz ki umar/kism ka pata
  • Spectral-flux onset + peak picking = **background events** (kab, kitni der, kaisi)
  • Onset autocorrelation = **tempo** (music hai ya nahi)
  • Per-second loudness + approx LUFS + dynamic range = level ki sacchai
  • Decay slope = **reverb** (kamra bada hai ya chhota)

CLI: python tools/audio_read3.py --audio x.mp3 [--json o.json] [--full]
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CAST = {"narrator": (90, 125), "dada": (88, 125), "dadi": (140, 185),
        "maa": (165, 205), "gudiya": (190, 240), "sonu": (240, 330)}
SR = 16000


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


# ------------------------------------------------------------------ features
def mel_fb(n_mels=26, n_fft=512, sr=SR):
    import numpy as np
    def hz2mel(f): return 2595 * np.log10(1 + f / 700)
    def mel2hz(m): return 700 * (10 ** (m / 2595) - 1)
    pts = mel2hz(np.linspace(hz2mel(50), hz2mel(sr / 2 - 100), n_mels + 2))
    bins = np.floor((n_fft + 1) * pts / sr).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1))
    for m in range(1, n_mels + 1):
        l, c, r = bins[m - 1], bins[m], bins[m + 1]
        if c == l: c = l + 1
        if r == c: r = c + 1
        for k in range(l, min(c, fb.shape[1])): fb[m - 1, k] = (k - l) / (c - l)
        for k in range(c, min(r, fb.shape[1])): fb[m - 1, k] = (r - k) / (r - c)
    return fb


def stft_mag(x, n_fft=512, hop=160):
    import numpy as np
    win = np.hamming(n_fft)
    frames = range(0, max(1, len(x) - n_fft), hop)
    return np.array([np.abs(np.fft.rfft(x[i:i + n_fft] * win)) for i in frames]), hop


def mfcc(mag, fb, n_mfcc=13):
    import numpy as np
    logmel = np.log(mag @ fb.T + 1e-9)
    n = fb.shape[0]
    dct = np.array([[np.cos(np.pi * k * (2 * m + 1) / (2 * n)) for m in range(n)] for k in range(n_mfcc)])
    return logmel @ dct.T


def f0_of(seg, sr=SR):
    import numpy as np
    N = len(seg)
    if N < 320:
        return 0.0
    seg = seg - seg.mean()
    ac = np.correlate(seg, seg, "full")[N - 1:]
    lo, hi = int(sr / 400), int(sr / 70)
    if hi >= len(ac):
        return 0.0
    k = lo + int(np.argmax(ac[lo:hi]))
    return float(sr / k) if k > 0 else 0.0


def lpc_formants(seg, sr=SR, order=12):
    """Levinson–Durbin LPC → F1/F2 (Hz)."""
    import numpy as np
    seg = np.append(seg[0], seg[1:] - 0.97 * seg[:-1])       # pre-emphasis
    seg = seg * np.hamming(len(seg))
    r = np.correlate(seg, seg, "full")[len(seg) - 1:]
    r = r[:order + 1]
    if r[0] <= 0:
        return []
    a = np.zeros(order + 1); a[0] = 1.0; e = r[0]
    for i in range(1, order + 1):
        acc = r[i] + sum(a[j] * r[i - j] for j in range(1, i))
        k = -acc / e
        a_new = a.copy()
        for j in range(1, i):
            a_new[j] = a[j] + k * a[i - j]
        a_new[i] = k
        a = a_new; e *= (1 - k * k)
        if e <= 0:
            break
    roots = np.roots(a)
    roots = [x for x in roots if np.imag(x) > 0.01]
    fr = sorted(np.degrees(np.arctan2(np.imag(x), np.real(x))) / 360 * sr for x in roots)
    return [round(f) for f in fr if 200 < f < 4000][:3]


def kmeans(X, k, iters=25, seed=0):
    import numpy as np
    rng = np.random.default_rng(seed)
    C = X[rng.choice(len(X), k, replace=False)]
    lab = np.zeros(len(X), dtype=int)
    for _ in range(iters):
        d = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
        new = d.argmin(1)
        if (new == lab).all():
            break
        lab = new
        for j in range(k):
            if (lab == j).any():
                C[j] = X[lab == j].mean(0)
    inertia = float(((X - C[lab]) ** 2).sum())
    return lab, C, inertia


# ------------------------------------------------------------------ main read
def read(path: str) -> dict:
    import numpy as np
    x = decode(path)
    if len(x) == 0:
        return {"ok": False, "why": "decode fail"}
    dur = len(x) / SR
    mag, hop = stft_mag(x)
    fb = mel_fb()
    M = mfcc(mag, fb)
    frame_t = hop / SR

    # energy + VAD (adaptive)
    N = 512
    energy = np.array([np.sqrt((x[i:i + N] ** 2).mean()) for i in range(0, max(1, len(x) - N), hop)])
    n = min(len(energy), len(M))
    energy, M = energy[:n], M[:n]
    noise = float(np.percentile(energy, 15))
    thr = max(0.006, noise * 2.0)
    speech = energy > thr

    # segments
    segs, cur, st = [], bool(speech[0]), 0.0
    for i, v in enumerate(speech):
        t = i * frame_t
        if bool(v) != cur:
            if t - st > 0.10:
                segs.append({"type": "speech" if cur else "silence",
                             "start": round(st, 2), "end": round(t, 2), "dur": round(t - st, 2)})
            cur, st = bool(v), t
    segs.append({"type": "speech" if cur else "silence",
                 "start": round(st, 2), "end": round(n * frame_t, 2),
                 "dur": round(n * frame_t - st, 2)})

    # per speech-segment features → speaker clustering
    feats, meta = [], []
    for s in segs:
        if s["type"] != "speech" or s["dur"] < 0.18:
            continue
        a, b = int(s["start"] * SR), int(s["end"] * SR)
        seg = x[a:b]
        i0, i1 = int(s["start"] / frame_t), int(s["end"] / frame_t)
        mf = M[i0:i1].mean(0) if i1 > i0 else M[0]
        f0 = f0_of(seg)
        if f0 <= 0:
            continue
        feats.append(list(mf) + [f0 / 100.0])
        meta.append({"start": s["start"], "end": s["end"], "dur": s["dur"], "f0": int(f0),
                     "formants": lpc_formants(seg)})
    turns, spk_stats = [], []
    if feats:
        X = np.array(feats, dtype="float32")
        X = (X - X.mean(0)) / (X.std(0) + 1e-6)
        best = None
        for k in (1, 2, 3):
            if k > len(X):
                break
            lab, C, inertia = kmeans(X, k)
            score = inertia / max(1, len(X)) + 0.35 * k        # elbow-ish
            if best is None or score < best[0]:
                best = (score, k, lab)
        _, k, lab = best
        # asli jaanch: alag speaker tabhi jab F0 me saaf farq ho (>=18 Hz) aur dono bade hon
        def _stats(lab, k):
            out = []
            for j in range(k):
                idx = [i for i, l in enumerate(lab) if l == j]
                if not idx:
                    continue
                f0s = [meta[i]["f0"] for i in idx]
                dur = sum(meta[i]["dur"] for i in idx)
                out.append((int(np.median(f0s)), len(idx), dur))
            return out
        while k > 1:
            st_ = _stats(lab, k)
            ok_split = (len(st_) == k
                        and min(x_[2] for x_ in st_) >= 0.8
                        and min(x_[1] for x_ in st_) >= 2
                        and (max(x_[0] for x_ in st_) - min(x_[0] for x_ in st_)) >= 18)
            if ok_split:
                break
            k -= 1
            lab, C, inertia = kmeans(X, k)
        for i, m in enumerate(meta):
            turns.append({**m, "speaker": f"S{int(lab[i]) + 1}"})
        for j in range(k):
            grp = [t for t in turns if t["speaker"] == f"S{j+1}"]
            if not grp:
                continue
            f0s = [t["f0"] for t in grp]
            f1s = [t["formants"][0] for t in grp if t["formants"]]
            f2s = [t["formants"][1] for t in grp if len(t["formants"]) > 1]
            spk_stats.append({"speaker": f"S{j+1}", "turns": len(grp),
                              "total_s": round(sum(t["dur"] for t in grp), 2),
                              "f0_median": int(np.median(f0s)),
                              "f1_median": int(np.median(f1s)) if f1s else 0,
                              "f2_median": int(np.median(f2s)) if f2s else 0,
                              "age_guess": ("budha/budhi" if np.median(f0s) < 150 else
                                            "jawaan" if np.median(f0s) < 235 else "bachcha")})

    # onsets / events (spectral flux + peak picking)
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(1)
    if len(flux) > 5:
        k = np.ones(5) / 5
        flux_s = np.convolve(flux, k, mode="same")
        mu, sd = flux_s.mean(), flux_s.std() + 1e-9
        peaks = [i for i in range(2, len(flux_s) - 2)
                 if flux_s[i] > mu + 1.8 * sd and flux_s[i] == flux_s[i - 2:i + 3].max()]
        events, last = [], -9
        freqs = np.fft.rfftfreq(512, 1 / SR)
        for i in peaks:
            t = round(i * frame_t, 2)
            if t - last < 0.12:
                continue
            spec = mag[i]
            low = float(spec[freqs < 300].sum()); high = float(spec[freqs > 3000].sum())
            mid = float(spec[(freqs >= 300) & (freqs <= 3000)].sum()) + 1e-9
            kind = ("thud/impact" if low > high * 1.6 and low > mid * 0.6 else
                    "hiss/noise" if high > mid * 0.8 else "tonal/mixed")
            # decay (reverb) — agle 200 ms me energy kitni tez girti hai
            j = min(len(energy) - 1, i + int(0.2 / frame_t))
            decay = round(float(energy[i]) / max(1e-9, float(energy[j])), 2)
            events.append({"at": t, "kind": kind, "decay_ratio": decay})
            last = t
    else:
        events = []

    # tempo (music?) — onset envelope autocorrelation
    tempo, tempo_conf = 0, 0.0
    if len(flux) > 40:
        env = flux - flux.mean()
        ac = np.correlate(env, env, "full")[len(env) - 1:]
        lo, hi = int(60 / 180 / frame_t), int(60 / 60 / frame_t)
        if hi < len(ac):
            lag = lo + int(np.argmax(ac[lo:hi]))
            tempo = int(60 / (lag * frame_t)) if lag > 0 else 0
            tempo_conf = round(float(ac[lag] / (np.mean(np.abs(ac)) + 1e-9)), 2)

    # loudness (per second) + LUFS-ish + dynamic range
    per_s = []
    for i in range(0, len(x) - SR + 1, SR):
        r = float(np.sqrt((x[i:i + SR] ** 2).mean()))
        per_s.append(round(20 * np.log10(max(1e-9, r)), 1))
    rms_all = float(np.sqrt((x ** 2).mean()))
    lufs = round(20 * np.log10(max(1e-9, rms_all)) - 0.7, 1)     # approx
    dr = round(max(per_s) - min(per_s), 1) if per_s else 0

    # syllable rate (flux peaks in speech band, per speech second)
    band = mag[:, (np.fft.rfftfreq(512, 1 / SR) >= 300) & (np.fft.rfftfreq(512, 1 / SR) <= 3000)].sum(1)
    bflux = np.maximum(0, np.diff(band))
    # syllable = speech-band ke ubharte peaks, kam se kam 0.12 s alag (warna over-count)
    syl, last_t = 0, -9.0
    if len(bflux):
        thr_b = bflux.mean() + 1.4 * bflux.std()
        for i, v in enumerate(bflux):
            t = i * frame_t
            if v > thr_b and t - last_t >= 0.12:
                syl += 1
                last_t = t
    speech_s = sum(s["dur"] for s in segs if s["type"] == "speech")
    pace = round(syl / speech_s, 2) if speech_s > 0.3 else 0.0

    f0s = [t["f0"] for t in turns] or [0]
    hz = int(np.median(f0s))
    best_cast = min(CAST.items(), key=lambda kv: 0 if kv[1][0] <= hz <= kv[1][1]
                    else min(abs(hz - kv[1][0]), abs(hz - kv[1][1])))

    return {
        "ok": True, "file": str(path), "dur": round(dur, 2),
        "level": {"rms_dbfs": round(20 * np.log10(max(1e-9, rms_all)), 1),
                  "lufs_approx": lufs, "peak": round(float(np.max(np.abs(x))), 2),
                  "clipping_pct": round(float(np.mean(np.abs(x) > 0.98) * 100), 2),
                  "noise_floor_dbfs": round(20 * np.log10(max(1e-9, noise)), 1),
                  "dynamic_range_db": dr, "per_second_dbfs": per_s},
        "speech": {"speech_s": round(speech_s, 2),
                   "silence_s": round(sum(s["dur"] for s in segs if s["type"] == "silence"), 2),
                   "segments": sum(1 for s in segs if s["type"] == "speech"),
                   "pause_count": sum(1 for s in segs if s["type"] == "silence" and s["dur"] >= 0.2),
                   "pace_syl_per_s": pace},
        "pitch": {"median_hz": hz, "range_hz": [int(min(f0s)), int(max(f0s))],
                  "variability": round(float(np.std(f0s)), 1),
                  "closest_cast": best_cast[0], "band": list(best_cast[1])},
        "speakers": spk_stats, "turns": turns,
        "events": events, "event_count": len(events),
        "tempo_bpm": tempo,
        "background": {"onsets": len(events), "tempo_bpm": tempo, "tempo_confidence": tempo_conf,
                       # music tabhi maano jab speech kam ho aur beat pakka ho
                       "music_likely": bool(tempo and 60 <= tempo <= 180 and tempo_conf >= 3.0
                                            and (speech_s / max(1e-6, dur)) < 0.55)},
    }


def timeline(rep: dict) -> list[str]:
    rows = [(t["start"], f"BOL {t['speaker']} F0={t['f0']}Hz F1={t['formants'][0] if t['formants'] else '-'} ({t['dur']}s)")
            for t in rep.get("turns", [])]
    rows += [(e["at"], f"AWAAZ {e['kind']}") for e in rep.get("events", [])]
    rows.sort(key=lambda r: r[0])
    return [f"{t:6.1f}s  {txt}" for t, txt in rows]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--json", default="")
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    rep = read(a.audio)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: rep.get(k) for k in ("dur", "level", "speech", "pitch", "speakers",
                                     "event_count", "tempo_bpm", "background")}
    if brief.get("level"):
        brief["level"].pop("per_second_dbfs", None)
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    if a.full:
        print("\n--- TIMELINE ---")
        for line in timeline(rep):
            print(line)
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
