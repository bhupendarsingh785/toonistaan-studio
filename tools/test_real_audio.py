#!/usr/bin/env python3
"""test_real_audio.py — ASLI recording par poora test (banayi hui awaaz par nahi).

  python tools/test_real_audio.py            # saare test
  python tools/test_real_audio.py --json out.json

Kya naapta hai:
  denoise  — shor ka floor kitna gira, awaaz kitni bachi
  restore  — asli awaaz par hum/DC/click daal kar dekho kitna saaf hota hai
  occlude  — material ke hisaab se kitne dB ghata
  diarize  — asli baat-cheet me kitne speaker pakde
  adr      — asli awaaz ko tez/dheema karke wapas timing par baithaya?
  stream   — bhaari file tukdon me padhi gayi
  spatial  — doori/disha/goonj asli awaaz par
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

REAL = Path("/scratch/work/real")
SR = 22050
R = {}


def load(path: Path, sec: float = 25.0, sr: int = SR) -> np.ndarray:
    """Koi bhi format -> mono float, ffmpeg se (mp3/flac/ogg/wav sab)."""
    import ffbin
    ffbin.ensure()
    out = subprocess.run([sys.executable, "-c", "import sys;sys.path.insert(0,'%s');import ffbin;print(ffbin.ensure())" % (ROOT / "tools")],
                         capture_output=True, text=True)
    ff = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else "ffmpeg"
    raw = subprocess.run([ff, "-v", "quiet", "-t", str(sec), "-i", str(path),
                          "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return x / (np.max(np.abs(x)) + 1e-9)


def pick(tag: str) -> Path | None:
    idx = REAL / "index.json"
    if not idx.exists():
        return None
    for row in json.loads(idx.read_text(encoding="utf-8")):
        if Path(row["file"]).name.startswith(tag) and Path(row["file"]).exists():
            return Path(row["file"])
    return None


def rms(a):
    return float(np.sqrt((a ** 2).mean()) + 1e-12)


def floor_db(x, sr=SR, q=10):
    n = 1024
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::512]
    e = np.sqrt((fr ** 2).mean(1))
    return float(20 * np.log10(np.percentile(e, q) + 1e-9))


def test_denoise():
    import audio_pro as A
    p = pick("noise_street") or pick("conv2")
    if not p:
        return R.setdefault("denoise", {"status": "SKIP", "why": "asli clip nahi mili"})
    noise = load(p, 12.0)
    # asli shor me asli awaaz milao (donor speech)
    sp = pick("conv2") or pick("hi_speech")
    speech = load(sp, 8.0) if sp else np.zeros(len(noise))
    n = min(len(noise), len(speech))
    mix = 0.75 * noise[:n] + 0.55 * speech[:n]
    den = A.denoise(mix, SR)
    R["denoise"] = {
        "clip": p.name,
        "floor_in": round(floor_db(mix), 1), "floor_out": round(floor_db(den), 1),
        "floor_gain_db": round(floor_db(den) - floor_db(mix), 1),
        "level_keep": round(rms(den) / rms(mix), 3),
        "status": "OK",
    }


def test_restore():
    import audio_pro as A
    p = pick("conv2") or pick("hi_speech")
    if not p:
        return R.setdefault("restore", {"status": "SKIP"})
    x = load(p, 8.0)
    t = np.arange(len(x)) / SR
    bad = x + 0.25 * np.sin(2 * np.pi * 50 * t) + 0.15
    bad[int(0.5 * SR):int(0.5 * SR) + 50] += 2.0
    fixed = A.restore(bad, SR)
    def hum(a):
        X = np.abs(np.fft.rfft(a)); f = np.fft.rfftfreq(len(a), 1 / SR)
        return 20 * np.log10(X[np.abs(f - 50) < 1.5].max() / (np.sqrt(len(a)) / 2) + 1e-12)
    m = min(len(fixed), len(x))
    R["restore"] = {
        "clip": p.name, "hum_in": round(hum(bad), 1), "hum_out": round(hum(fixed), 1),
        "dc_in": round(float(np.mean(bad)), 3), "dc_out": round(float(np.mean(fixed)), 4),
        "voice_corr": round(float(np.corrcoef(fixed[:m], x[:m])[0, 1]), 3), "status": "OK",
    }


def test_occlude():
    import audio_pro as A
    p = pick("conv2") or pick("hi_speech")
    if not p:
        return R.setdefault("occlude", {"status": "SKIP"})
    x = load(p, 6.0)
    def band(a, f0):
        X = np.abs(np.fft.rfft(a)); f = np.fft.rfftfreq(len(a), 1 / SR)
        return float(20 * np.log10(X[np.abs(f - f0) < 25].max() + 1e-9))
    out = {}
    for m in ("parda", "deewar", "loha"):
        y = A.occlude(x, SR, m)
        out[m] = {"250Hz": round(band(y, 250) - band(x, 250), 1),
                  "1kHz": round(band(y, 1000) - band(x, 1000), 1),
                  "4kHz": round(band(y, 4000) - band(x, 4000), 1)}
    R["occlude"] = {"clip": p.name, "tl_db": out, "status": "OK"}


def test_diarize():
    import audio_pro as A
    p = pick("conv2")
    if not p:
        return R.setdefault("diarize", {"status": "SKIP"})
    x = load(p, 40.0)
    segs = A.diarize(x, SR)
    spk = sorted({s["speaker"] for s in segs})
    turns = len(segs)
    R["diarize"] = {"clip": p.name, "speakers": len(spk), "turns": turns,
                    "first": segs[:5], "status": "OK",
                    "note": "asli clip par ground-truth nahi — sirf kitne speaker/turn mile"}
    return segs


def test_adr():
    import audio_pro as A
    p = pick("conv2") or pick("hi_speech")
    if not p:
        return R.setdefault("adr", {"status": "SKIP"})
    x = load(p, 6.0)
    # actor ne tez bola (1.4x) — wapas timing par aana chahiye
    idx = np.linspace(0, len(x) - 1, int(len(x) / 1.4))
    rec = np.interp(idx, np.arange(len(x)), x)
    fit = A.adr_dtw(rec, x, SR)
    def env(a, hop=256, n=512):
        fr = np.lib.stride_tricks.sliding_window_view(a, n)[::hop]
        return np.sqrt((fr ** 2).mean(1))
    m = min(len(env(rec)), len(env(fit)), len(env(x)))
    R["adr"] = {
        "clip": p.name,
        "env_before": round(float(np.corrcoef(env(rec)[:m], env(x)[:m])[0, 1]), 3),
        "env_after": round(float(np.corrcoef(env(fit)[:m], env(x)[:m])[0, 1]), 3),
        "len_rec_s": round(len(rec) / SR, 2), "len_fit_s": round(len(fit) / SR, 2),
        "len_ref_s": round(len(x) / SR, 2), "status": "OK",
    }


def test_stream():
    import audio_pro as A
    p = pick("rain2") or pick("conv2")
    if not p:
        return R.setdefault("stream", {"status": "SKIP"})
    got = list(A.stream_chunks(p, chunk_s=20.0, overlap_s=0.5))
    total = sum(len(b) for _, b in got) / (got[0][1].shape[0] and 1) if got else 0
    R["stream"] = {"clip": p.name, "chunks": len(got),
                   "first_s": round(len(got[0][1]) / 22050, 1) if got else 0,
                   "last_t": round(got[-1][0], 1) if got else 0, "status": "OK"}


def test_spatial():
    import space as SP
    p = pick("conv2") or pick("hi_speech")
    if not p:
        return R.setdefault("spatial", {"status": "SKIP"})
    x = load(p, 3.0)
    row = {}
    for d in (1, 5, 20):
        m = SP.measure(SP.place_acoustic(x, dist=d, space="khula"))
        row[f"{d}m"] = {"level_db": m["level_db"], "hf_lf": m["hf_lf"]}
    for s in ("jungle", "hall"):
        m = SP.measure(SP.place_acoustic(x, dist=5, space=s))
        row[s] = {"rt": m["rt_bass_mid_high"], "iacc": m["iacc"]}
    pl = SP.measure(SP.place_acoustic(x, dist=4, pan=-0.8, space="jungle"))["pan"]
    pr = SP.measure(SP.place_acoustic(x, dist=4, pan=0.8, space="jungle"))["pan"]
    row["pan"] = {"left": pl, "right": pr}
    R["spatial"] = {"clip": p.name, **row, "status": "OK"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    for fn in (test_denoise, test_restore, test_occlude, test_diarize, test_adr, test_stream, test_spatial):
        try:
            fn()
        except Exception as e:
            R[fn.__name__.replace("test_", "")] = {"status": "FAIL", "why": f"{type(e).__name__}: {str(e)[:90]}"}
    print(json.dumps(R, ensure_ascii=False, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
        print("saved:", a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
