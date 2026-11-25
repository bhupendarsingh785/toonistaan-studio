#!/usr/bin/env python3
"""Voice Match — "kitna match hua" ka imandar naap.

Sach pehle: 100% copy koi system nahi deta. Isliye yahan jhoothi % nahi dete.
Hum teen cheezein naapte hain aur saaf batate hain ki yeh "pehchaan ka saboot" nahi:
  1) sur (F0) ka farq
  2) awaaz ka rang (MFCC ka cosine)
  3) saaf-saafai (speech/silence ratio)

Commands:
  python tools/voice_match.py check --ref dadi.wav --new out.wav
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np


def _load(path: str, sr: int = 16000) -> np.ndarray:
    import subprocess
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        ff = get_ffmpeg_exe()
    except Exception:
        ff = "ffmpeg"
    r = subprocess.run([ff, "-v", "quiet", "-i", path, "-f", "s16le", "-ac", "1",
                        "-ar", str(sr), "-"], capture_output=True)
    if not r.stdout:
        raise RuntimeError(f"audio padha nahi ja saka: {path}")
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def f0_median(x: np.ndarray, sr: int = 16000) -> float:
    N, H = int(0.04 * sr), int(0.02 * sr)
    vals = []
    for i in range(0, len(x) - N, H):
        f = x[i:i + N]
        if np.sqrt((f ** 2).mean()) < 0.02:
            continue
        f = f - f.mean()
        ac = np.correlate(f, f, "full")[N - 1:]
        lo, hi = int(sr / 400), int(sr / 70)
        if hi >= len(ac):
            continue
        k = lo + int(np.argmax(ac[lo:hi]))
        if k > 0:
            vals.append(sr / k)
    return float(np.median(vals)) if vals else 0.0


def mfcc_cosine(a: np.ndarray, b: np.ndarray, sr: int = 16000, n_mfcc: int = 13) -> float:
    """Bahut halka MFCC (dummy filterbank) — sirf rang compare karne ke liye."""
    def feat(x):
        N, H = int(0.025 * sr), int(0.010 * sr)
        frames = []
        for i in range(0, max(1, len(x) - N), H):
            f = x[i:i + N]
            if len(f) < N:
                break
            sp = np.abs(np.fft.rfft(f * np.hamming(N)))[: N // 2]
            if sp.sum() <= 0:
                continue
            mel = np.log(sp[: n_mfcc * 4] + 1e-8)
            frames.append(mel.reshape(n_mfcc, -1).mean(axis=1))
        if not frames:
            return np.zeros(n_mfcc)
        return np.mean(frames, axis=0)

    va, vb = feat(a), feat(b)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def speech_ratio(x: np.ndarray, sr: int = 16000) -> float:
    w = int(0.05 * sr)
    rms = np.array([np.sqrt((x[i:i + w] ** 2).mean()) for i in range(0, len(x) - w, w)]) if len(x) > w else np.array([0.0])
    thr = max(0.01, float(np.median(rms)) * 0.4)
    return float((rms > thr).mean()) if len(rms) else 0.0


def check(ref: str, new: str) -> dict:
    a, b = _load(ref), _load(new)
    fa, fb = f0_median(a), f0_median(b)
    hz_diff = abs(fa - fb)
    hz_pct = (hz_diff / fa * 100) if fa else 0.0
    cos = mfcc_cosine(a, b)
    return {
        "ref_f0_hz": round(fa, 1), "new_f0_hz": round(fb, 1),
        "f0_diff_hz": round(hz_diff, 1), "f0_diff_percent": round(hz_pct, 1),
        "timbre_cosine": round(cos, 3),
        "speech_ratio_ref": round(speech_ratio(a), 2),
        "speech_ratio_new": round(speech_ratio(b), 2),
        "verdict": ("bahut kareeb" if hz_pct <= 5 and cos >= 0.9 else
                    "kareeb" if hz_pct <= 12 and cos >= 0.8 else
                    "alag lag raha hai"),
        "warning": ("Yeh rough naap hai — pehchaan ka saboot nahi. "
                    "Asli similarity ke liye speaker-embedding model (ECAPA/resemblyzer) chahiye."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="voice match (rough, imandar)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("--ref", required=True); c.add_argument("--new", required=True)
    a = ap.parse_args()
    try:
        print(json.dumps(check(a.ref, a.new), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"[x] {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
