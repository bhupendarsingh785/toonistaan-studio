#!/usr/bin/env python3
"""Voice Extract — video ya audio se awaaz nikaalo, saaf karo, reference banao.

Kaam:
  1) video/audio se audio nikaalta hai (ffmpeg)
  2) shor kam karta hai (highpass + afftdn + loudnorm)
  3) sabse saaf 5-15 second ka hissa chunta hai (kam shor, zyada bolna)
  4) reference.wav + meta.json banata hai
  5) transcript: faster-whisper mile to khud likh deta hai, warna khaali (tum likh do)

Command:
  python tools/voice_extract.py run --in dadi.mp4 --out voices/dadi --seconds 12
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path
import numpy as np

def _ff() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def _load(path: str, sr: int = 16000) -> np.ndarray:
    r = subprocess.run([_ff(), "-v", "quiet", "-i", path, "-f", "s16le", "-ac", "1",
                        "-ar", str(sr), "-"], capture_output=True)
    if not r.stdout:
        raise RuntimeError(f"audio nahi mila: {path}")
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0

def extract_audio(src: str, out_wav: str, sr: int = 24000) -> str:
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", src, "-vn",
                        "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", out_wav],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"audio nikalne me dikkat: {r.stderr[:200]}")
    return out_wav

def clean_audio(src: str, out_wav: str) -> str:
    """Shor kam + awaaz saaf (bolne wali awaaz ke liye)."""
    af = "highpass=f=90,afftdn=nf=-25,loudnorm=I=-18:TP=-2:LRA=9"
    r = subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", src, "-af", af,
                        "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", out_wav],
                       capture_output=True, text=True)
    if r.returncode != 0:          # afftdn na ho to simple rasta
        subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", src, "-af",
                        "highpass=f=90,loudnorm=I=-18:TP=-2", "-ac", "1", "-ar", "24000",
                        "-c:a", "pcm_s16le", out_wav], check=True)
    return out_wav

def best_window(x: np.ndarray, sr: int = 24000, seconds: float = 12.0) -> tuple[float, float]:
    """Sabse saaf window: zyada bolna, kam shor."""
    n = int(seconds * sr); step = int(0.5 * sr)
    if len(x) <= n:
        return 0.0, len(x) / sr
    best = (-1e9, 0)
    w = int(0.05 * sr)
    for i in range(0, len(x) - n, step):
        seg = x[i:i + n]
        rms = np.array([np.sqrt((seg[j:j + w] ** 2).mean()) for j in range(0, len(seg) - w, w)])
        if len(rms) < 5:
            continue
        # top 30% ka औसत (percentile se compare karne par barabar values par khali ho jata hai)
        k = max(1, len(rms) // 3)
        voiced = float(np.sort(rms)[-k:].mean())
        floor = float(np.percentile(rms, 10))
        # bolne ka hissa bhi count karo — warna aadha khaali window bhi barabar lagta hai
        talk = float((rms > max(0.01, float(np.median(rms)) * 0.5)).mean())
        score = voiced * (0.35 + 0.65 * talk) - 0.5 * floor
        if not np.isfinite(score):
            continue
        if score > best[0]:
            best = (score, i)
    return best[1] / sr, seconds

def transcribe(path: str) -> tuple[str, str]:
    """faster-whisper ho to transcript. Warna khaali + wajah."""
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return "", "faster-whisper nahi mila (pip install faster-whisper) — transcript tum likho"
    try:
        m = WhisperModel(os.environ.get("WHISPER_SIZE", "small"), device="cpu", compute_type="int8")
        segs, _ = m.transcribe(path, language="hi", beam_size=5, vad_filter=True)
        return " ".join(s.text.strip() for s in segs).strip(), "whisper se likha (check kar lo)"
    except Exception as exc:
        return "", f"whisper fail: {type(exc).__name__}"

def best_windows(x: np.ndarray, sr: int = 24000, seconds: float = 12.0, count: int = 1) -> list[tuple[float, float]]:
    """Ek se zyada saaf hisse (multi-reference ke liye) — alag-alag jagah se."""
    n = int(seconds * sr); step = int(0.5 * sr)
    if len(x) <= n:
        return [(0.0, len(x) / sr)]
    scored = []
    w = int(0.05 * sr)
    for i in range(0, len(x) - n, step):
        seg = x[i:i + n]
        rms = np.array([np.sqrt((seg[j:j + w] ** 2).mean()) for j in range(0, len(seg) - w, w)])
        if len(rms) < 5:
            continue
        k = max(1, len(rms) // 3)
        voiced = float(np.sort(rms)[-k:].mean())
        floor = float(np.percentile(rms, 10))
        talk = float((rms > max(0.01, float(np.median(rms)) * 0.5)).mean())
        score = voiced * (0.35 + 0.65 * talk) - 0.5 * floor
        if np.isfinite(score):
            scored.append((score, i))
    scored.sort(reverse=True)
    picked = []
    for score, i in scored:
        if all(abs(i - j) >= n for _, j in picked):   # overlap na ho
            picked.append((score, i))
        if len(picked) >= count:
            break
    return [(i / sr, seconds) for _, i in picked] or [(0.0, seconds)]


def run(src: str, out_dir: str, seconds: float = 12.0, do_clean: bool = True,
        transcribe_it: bool = True, windows: int = 1) -> dict:
    od = Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    raw = str(od / "extracted.wav")
    extract_audio(src, raw)
    step1 = clean_audio(raw, str(od / "cleaned.wav")) if do_clean else raw
    x = _load(step1, 24000)
    wins = best_windows(x, 24000, seconds, windows)
    refs = []
    for idx, (start, dur) in enumerate(wins, 1):
        ref = str(od / ("reference.wav" if idx == 1 else f"reference_{idx}.wav"))
        subprocess.run([_ff(), "-loglevel", "error", "-y", "-ss", str(start), "-t", str(dur),
                        "-i", step1, "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", ref], check=True)
        refs.append({"file": ref, "start_sec": round(start, 2), "duration_sec": round(dur, 2)})
    ref = refs[0]["file"]
    text, why = transcribe(ref) if transcribe_it else ("", "transcribe band (--no-transcribe)")
    meta = {"source": os.path.abspath(src), "reference": ref, "references": refs,
            "start_sec": refs[0]["start_sec"], "duration_sec": refs[0]["duration_sec"],
            "cleaned": do_clean, "transcript": text, "transcript_note": why}
    (od / "extract.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta

def main() -> int:
    ap = argparse.ArgumentParser(description="video/audio se awaaz nikaalo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--in", dest="src", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--seconds", type=float, default=12.0)
    r.add_argument("--no-clean", action="store_true")
    r.add_argument("--no-transcribe", action="store_true")
    r.add_argument("--windows", type=int, default=1, help="kitne saaf hisse chahiye (multi-reference)")
    a = ap.parse_args()
    try:
        meta = run(a.src, a.out, a.seconds, not a.no_clean,
                   transcribe_it=not a.no_transcribe, windows=max(1, a.windows))
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"[x] {type(exc).__name__}: {exc}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
