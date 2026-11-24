#!/usr/bin/env python3
"""auto_label.py — clip ko SUN kar label lagao (naam par bharosa nahi).

Har clip par saboot jama karta hai:
  • ASR (whisper) — sach me shabd hain? (insaan)
  • bolne ka dhang — 3-9 Hz modulation (insaan)
  • sur ki sthirti + harmonic — music
  • chhotke (transients) — kadam / chot
  • broadband + sur nahi — paani / mahaul
  • creature model — kaunsa jeev (top-1)
Phir label + confidence + saboot likhta hai. Kam confidence = label nahi.

  python tools/auto_label.py --n 120 --offset 0
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
K = ROOT / "knowledge"
INP = Path("/scratch/input")
EXTRA = Path("/scratch/work/library_extra")
OUT = K / "labels-audited.jsonl"
SR = 16000


def decode(path: Path, sec=8.0, sr=SR):
    import ffbin
    ff = ffbin.ensure() or "ffmpeg"
    raw = subprocess.run([ff, "-v", "quiet", "-t", str(sec), "-i", str(path),
                          "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True).stdout
    if len(raw) < sr // 2:
        return None
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return x / (np.max(np.abs(x)) + 1e-9)


_ASR = None


def asr_has_words(x, sr=SR):
    """Whisper se poochho — sach me shabd hain?"""
    global _ASR
    try:
        if _ASR is None:
            from faster_whisper import WhisperModel
            _ASR = WhisperModel("base", device="cpu", compute_type="int8")
        segs, _ = _ASR.transcribe(x.astype(np.float32), language=None, vad_filter=True, beam_size=1)
        text = " ".join(s.text.strip() for s in segs).strip()
        words = [w for w in text.split() if len(w) > 1]
        return len(words) >= 2, text[:60]
    except Exception as e:
        return None, f"asr fail {type(e).__name__}"


def evidence(x, sr=SR):
    n = 1024
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::512]
    X = np.abs(np.fft.rfft(fr * np.hanning(n), axis=1)) + 1e-10
    f = np.fft.rfftfreq(n, 1 / sr)
    spec = X.mean(0)
    flat = float(np.exp(np.log(spec + 1e-12).mean()) / (spec.mean() + 1e-12))
    e = np.sqrt((fr ** 2).mean(1))
    # bolne ka dhang
    mod = np.abs(np.fft.rfft(e - e.mean()))
    mf = np.fft.rfftfreq(len(e), 512 / sr)
    speech_mod = float(mod[(mf > 3) & (mf < 9)].sum() / (mod.sum() + 1e-12))
    # chhotke (onsets)
    d = np.diff(e)
    onsets = float((d > 0.12 * (np.max(e) + 1e-9)).sum() / max(1e-6, len(x) / sr))
    # sur
    seg = x[: min(len(x), sr)]
    ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
    lo, hi = int(sr / 500), min(int(sr / 70), len(ac) - 1)
    f0 = sr / (np.argmax(ac[lo:hi]) + lo + 1e-9) if hi > lo else 0.0
    # harmonic hissa (sur ke gunaaharon par energy)
    harm = 0.0
    if f0 > 40:
        tot = spec.sum() + 1e-12
        h = sum(spec[np.abs(f - f0 * k) < 15].sum() for k in range(1, 8))
        harm = float(h / tot)
    peak_bins = np.argmax(X[:, (f > 80) & (f < 3000)], axis=1)
    stab = float(np.std(peak_bins) / (np.mean(peak_bins) + 1e-9))
    return {"flat": round(flat, 3), "speech_mod": round(speech_mod, 3), "onsets": round(onsets, 2),
            "f0": round(float(f0), 1), "harm": round(harm, 3), "stab": round(stab, 3),
            "rms": round(float(np.sqrt((x ** 2).mean())), 3)}


def decide(ev, has_words):
    """Saboot se label — niyam saaf, andaza nahi."""
    if has_words:
        return "insaan", 0.9, "ASR ne shabd suna"
    if ev["speech_mod"] > 0.5 and ev["f0"] > 70 and ev["stab"] < 0.35:
        return "insaan", 0.6, "bolne ka dhang (mod>0.5)"
    if ev["harm"] > 0.45 and ev["stab"] < 0.10 and ev["flat"] < 0.05:
        return "music", 0.75, "sur sthir + harmonic"
    if ev["onsets"] > 2.2 and ev["flat"] > 0.05:
        return "harkat", 0.65, "bahut chhotke (kadam/chot)"
    if ev["flat"] > 0.20 and ev["harm"] < 0.25:
        return "prakriti", 0.7, "broadband, sur nahi (paani/hawa)"
    if ev["f0"] > 40 and ev["harm"] > 0.25:
        return "janwar", 0.55, "sur hai par sthir nahi (jeev ki awaaz)"
    return None, 0.0, "saboot kaafi nahi"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--no-asr", action="store_true")
    a = ap.parse_args()
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["file"])
            except Exception:
                pass
    files = [p for p in sorted(INP.glob("*")) if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".ogx")]
    files += [p for p in sorted(EXTRA.glob("*")) if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".oga")]
    files = [p for p in files if p.name not in done][a.offset:a.offset + a.n]
    print(f"label karne: {len(files)} (pehle se {len(done)})")
    rows = []
    fh = OUT.open("a", encoding="utf-8")
    for i, p in enumerate(files, 1):
        x = decode(p)
        if x is None:
            continue
        ev = evidence(x)
        has_words = None
        text = ""
        # ASR sirf tab jab saboot bolne ki taraf ishaara kare (warna bahut dheema)
        if not a.no_asr and (ev["speech_mod"] > 0.35 or (70 < ev["f0"] < 330 and ev["harm"] < 0.4)):
            has_words, text = asr_has_words(x)
        label, conf, why = decide(ev, bool(has_words))
        row = {"file": p.name, "label": label, "conf": conf, "why": why, "asr_text": text, **ev}
        rows.append(row)
        fh.write(json.dumps(row, ensure_ascii=False) + "\n"); fh.flush()
        if i % 20 == 0:
            print(f"  {i}/{len(files)} ...")
    fh.close()
    lab = [r for r in rows if r["label"]]
    from collections import Counter
    print(f"label mile: {len(lab)}/{len(rows)} |", dict(Counter(r["label"] for r in lab)))
    print("file:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
