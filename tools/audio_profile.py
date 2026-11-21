#!/usr/bin/env python3
"""Audio Profile — kisi bhi audio ko padho: bolne ka andaaz, sur, tune, background.

Swag koi bhi audio bhejta hai → hum use "padh" kar batate hain:
  • awaaz ka sur (F0 median/std/range), jitter (kaanpna)
  • bolne ki raftaar, rukne ka pattern (kitni baar, kitna lamba)
  • zor ka badalna (expressiveness), chupai
  • background: noise floor, bed hai ya nahi (spectral flatness), music vs speech
  • background events (kitne onsets), stereo width
  • "andaaz" ka nichod: pitch range, pace variation, ending contour
  • hamare cast se tulna: kaunsa persona sabse kareeb + kya badalna hai

CLI: python tools/audio_profile.py --audio x.mp3 [--json out.json] [--compare]
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CAST = {  # hamare locked presets ke F0 targets (voice-core)
    "narrator": (90, 125), "dada": (88, 125), "dadi": (140, 185),
    "maa": (165, 205), "gudiya": (190, 240), "sonu": (240, 330),
}


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def load(path: str, sr: int = 16000) -> tuple:
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", path, "-f", "s16le",
                        "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768.0
    # stereo (width ke liye)
    r2 = subprocess.run([ffmpeg(), "-v", "quiet", "-i", path, "-f", "s16le",
                         "-ac", "2", "-ar", str(sr), "-"], capture_output=True)
    st = np.frombuffer(r2.stdout, dtype=np.int16).astype("float32") / 32768.0
    return x, st, sr


def f0_track(x, sr: int = 16000) -> "list[float]":
    import numpy as np
    N, H = 640, 320
    out = []
    for i in range(0, max(1, len(x) - N), H):
        seg = x[i:i + N]
        if float(np.sqrt((seg ** 2).mean())) < 0.02:
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, "full")[N - 1:]
        lo, hi = int(sr / 400), int(sr / 70)
        if hi >= len(ac):
            continue
        k = lo + int(np.argmax(ac[lo:hi]))
        if k > 0:
            out.append(sr / k)
    return out


def profile(path: str) -> dict:
    import numpy as np
    x, st, sr = load(path)
    if len(x) == 0:
        return {"ok": False, "why": "audio khaali/decode fail"}
    dur = len(x) / sr
    rms = float(np.sqrt((x ** 2).mean()))
    peak = float(np.max(np.abs(x)))
    f0 = f0_track(x, sr)
    arr = np.array(f0) if f0 else np.array([0.0])

    # pause pattern (50 ms frames)
    w = int(0.05 * sr)
    fr = np.array([np.sqrt((x[i:i + w] ** 2).mean()) for i in range(0, len(x) - w, w)])
    thr = max(0.008, float(np.percentile(fr, 20)) * 1.5)
    silent = fr < thr
    pauses, run = [], 0
    for s in silent:
        if s:
            run += 1
        elif run:
            pauses.append(run * 0.05); run = 0
    if run:
        pauses.append(run * 0.05)

    # spectral flatness (background bed vs clean speech) + onsets
    N = 1024; H = 512
    flat, flux = [], []
    prev = None
    for i in range(0, max(1, len(x) - N), H):
        seg = x[i:i + N] * np.hanning(N)
        mag = np.abs(np.fft.rfft(seg)) + 1e-9
        flat.append(float(np.exp(np.mean(np.log(mag))) / np.mean(mag)))
        if prev is not None:
            flux.append(float(np.maximum(0, mag - prev).sum()))
        prev = mag
    flatness = float(np.mean(flat)) if flat else 0.0
    onsets = int(sum(1 for f in flux if f > (np.mean(flux) + 2 * np.std(flux)))) if flux else 0

    # stereo width
    width = 0.0
    if len(st) > 1000:
        L, R = st[0::2], st[1::2]
        n = min(len(L), len(R))
        if n > 100:
            corr = float(np.corrcoef(L[:n], R[:n])[0, 1]) if np.std(L[:n]) > 1e-6 else 1.0
            width = round(1.0 - max(-1.0, min(1.0, corr)), 3)

    hz_med = int(np.median(arr))
    hz_std = round(float(np.std(arr)), 1)
    hz_p10, hz_p90 = int(np.percentile(arr, 10)), int(np.percentile(arr, 90))
    jitter = round(float(np.mean(np.abs(np.diff(arr))) / max(1e-6, np.mean(arr))), 4) if len(arr) > 2 else 0.0

    # "andaaz" ka nichod
    pace_var = round(float(np.std(fr) / max(1e-6, np.mean(fr))), 3)
    gender = "male" if hz_med < 155 else ("female" if hz_med < 240 else "child/high")
    age_guess = ("budha/budhi" if hz_med < 150 else
                 "jawaan" if hz_med < 235 else "bachcha")

    rep = {
        "ok": True, "file": str(path), "dur": round(dur, 2),
        "rms_dbfs": round(20 * np.log10(max(1e-9, rms)), 1), "peak": round(peak, 2),
        "silence_pct": round(100 * float(silent.mean()), 1),
        "pauses": {"count": len(pauses), "mean_s": round(float(np.mean(pauses)), 2) if pauses else 0,
                   "max_s": round(float(np.max(pauses)), 2) if pauses else 0},
        "pitch": {"median_hz": hz_med, "std_hz": hz_std, "p10": hz_p10, "p90": hz_p90,
                  "range_hz": hz_p90 - hz_p10, "jitter": jitter},
        "voice": {"gender_guess": gender, "age_guess": age_guess},
        "expressiveness": {"f0_std": hz_std, "energy_variation": pace_var},
        "background": {"noise_floor_dbfs": round(20 * np.log10(max(1e-9, float(np.percentile(fr, 10)))), 1),
                       "spectral_flatness": round(flatness, 4),
                       "bed_likely": bool(flatness > 0.35),
                       "onsets": onsets, "stereo_width": width},
    }
    # hamare cast se tulna
    best, bestd = None, 1e9
    for name, (lo, hi) in CAST.items():
        d = 0 if lo <= hz_med <= hi else min(abs(hz_med - lo), abs(hz_med - hi))
        if d < bestd:
            best, bestd = name, d
    rep["compare"] = {"closest_cast": best, "distance_hz": int(bestd),
                      "advice": ("band ke andar hai — theek" if bestd == 0
                                 else f"{'pitch badhao' if hz_med < CAST[best][0] else 'pitch ghatao'} ~{int(bestd)} Hz")}
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description="kisi bhi audio ko padho")
    ap.add_argument("--audio", required=True)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    rep = profile(a.audio)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
