#!/usr/bin/env python3
"""cast_build.py — har kirdaar ki ALAG awaaz, smooth aur realistic.

Sirf pitch badalna kaafi nahi (sab ek jaisi lagti hain). Har kirdaar ka apna:
  • sur (pitch, rubberband — lambai same, formant bacha rehta hai = smooth)
  • raftaar (tempo)          • rang (EQ tilt: garam/chamakdar)
  • saans/vibrato (halka)    • bolne ka andaz (bhaav se sur)

Naap: articulation 40%+, boom <20%, clicks 0, seams par crossfade.
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal as ss

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
SR = 24000
CACHE = Path("/scratch/work/cast_cache"); CACHE.mkdir(parents=True, exist_ok=True)

# kirdaar -> (pitch, tempo, tilt_db, saans, vibrato)
# MMS ka asli base 136 Hz naapa gaya — usi se factor (target Hz / 136)
CAST = {
    "गौरी":  dict(pitch=1.55, tempo=1.00, tilt=+1.0, breath=0.010, vib=0.15, form="preserved"),  # ~215 Hz
    "कमला":  dict(pitch=1.40, tempo=0.92, tilt=-2.0, breath=0.014, vib=0.22, form="preserved"),  # ~194 Hz
    "मोहन":  dict(pitch=1.90, tempo=1.06, tilt=+2.0, breath=0.012, vib=0.10, form="shifted"),    # ~271 Hz bachcha
    "हरिदास": dict(pitch=0.80, tempo=0.90, tilt=-2.5, breath=0.016, vib=0.18, form="preserved"),  # ~109 Hz
    "भेड़िया": dict(pitch=0.62, tempo=0.88, tilt=-3.0, breath=0.030, vib=0.30, form="preserved"),
}


def _ff():
    import ffbin
    return ffbin.ensure() or "ffmpeg"


def _rubber(x, sr, pitch, tempo, form="preserved"):
    """rubberband: sur + raftaar, lambai control, formant preserved (smooth)."""
    import tempfile
    td = Path(tempfile.mkdtemp()); i0, o0 = td / "i.wav", td / "o.wav"
    sf.write(str(i0), x.astype("float32"), sr)
    subprocess.run([_ff(), "-v", "error", "-y", "-i", str(i0), "-af",
                    f"rubberband=pitch={pitch:.4f}:tempo={tempo:.4f}:formant={form}",
                    "-ar", str(sr), str(o0)], capture_output=True)
    if o0.exists():
        z, _ = sf.read(str(o0)); z = z.mean(1) if z.ndim > 1 else z
        return z.astype(np.float64)
    return x


def _tilt(x, sr, db):
    """rang: high-shelf (dhang/garam)."""
    if abs(db) < 0.1:
        return x
    b, a = ss.butter(2, 2600 / (sr / 2), btype="high")
    return x + (10 ** (db / 20) - 1) * ss.lfilter(b, a, x)


def _life(x, sr, breath, vib):
    """zinda ehsaas: halki saans + sur me naazuk hilna (bilkul flat na lage)."""
    n = len(x)
    t = np.arange(n) / sr
    if vib > 0:
        x = x * (1 + vib * 0.01 * np.sin(2 * np.pi * 5.2 * t))       # micro-vibrato
    if breath > 0:
        rng = np.random.default_rng(7)
        nz = rng.normal(0, 1, n)
        sos = ss.butter(4, [900 / (sr / 2), 5000 / (sr / 2)], btype="band", output="sos")
        nz = ss.sosfilt(sos, nz)
        env = np.convolve(np.abs(x), np.ones(240) / 240, mode="same")
        x = x + breath * nz * env
    return x


def line_audio(who, text):
    import hashlib
    key = hashlib.sha1(f"cast|{who}|{text}".encode()).hexdigest()[:16]
    dst = CACHE / f"{key}.wav"
    if dst.exists() and dst.stat().st_size > 2000:
        return dst
    cfg = CAST.get(who, dict(pitch=1.0, tempo=1.0, tilt=0.0, breath=0.012, vib=0.15))
    raw = CACHE / f"{key}_raw.wav"
    r = subprocess.run([sys.executable, str(Path(__file__).with_name("mms_worker.py")),
                        "--text", text, "--out", str(raw), "--pitch", "1.0"],
                       capture_output=True, text=True)
    if not raw.exists():
        raise RuntimeError(f"tts fail {who}: {(r.stderr or '')[-100:]}")
    y, sr = sf.read(str(raw)); y = y.mean(1) if y.ndim > 1 else y
    y = _rubber(y.astype(np.float64), sr, cfg["pitch"], cfg["tempo"], cfg.get("form", "preserved"))
    y = _tilt(y, sr, cfg["tilt"])
    y = _life(y, sr, cfg["breath"], cfg["vib"])
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.95
    sf.write(str(dst), y.astype("float32"), sr)
    raw.unlink(missing_ok=True)
    return dst


def build(script: Path, out: Path, gap=0.30, scene_gap=0.55):
    lines = []
    for l in script.read_text(encoding="utf-8").splitlines():
        if ":" in l:
            w, t = l.split(":", 1)
            if t.strip():
                lines.append((w.strip(), t.strip()))
    pieces, prev = [], None
    for who, text in lines:
        y, sr = sf.read(str(line_audio(who, text)))
        y = y.mean(1) if y.ndim > 1 else y
        y = y.astype(np.float64)
        # halka fade in/out — seams par click na ho (smoothness)
        f = int(0.012 * sr)
        if len(y) > 3 * f:
            y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
        g = scene_gap if (prev and prev != who) else gap
        pieces.append(y); pieces.append(np.zeros(int(g * SR)))
        prev = who
    voice = np.concatenate(pieces)
    # clarity chain
    try:
        import clarity as CL
        voice = CL.clarity(voice, SR)
    except Exception:
        pass
    try:
        import pyloudnorm as ln
        m = ln.Meter(SR)
        voice = ln.normalize.loudness(voice, m.integrated_loudness(voice), -16.0)
    except Exception:
        voice = voice / (np.sqrt((voice ** 2).mean()) + 1e-9) * 10 ** (-16 / 20)
    pk = float(np.max(np.abs(voice)))
    if pk > 0.95:
        voice = voice * (0.95 / pk)
    wav = out.with_suffix(".wav"); out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(wav), voice.astype("float32"), SR)
    subprocess.run([_ff(), "-v", "error", "-y", "-i", str(wav), "-b:a", "160k", str(out)], capture_output=True)
    info = {"lines": len(lines), "dur": round(len(voice) / SR, 1), "peak": round(float(np.max(np.abs(voice))), 3)}
    print(json.dumps(info, ensure_ascii=False))
    return info


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("script"); ap.add_argument("out")
    a = ap.parse_args(); build(Path(a.script), Path(a.out)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
