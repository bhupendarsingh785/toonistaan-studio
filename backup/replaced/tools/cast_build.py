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
# ASLI sur par banao (bada shift = patli/robotic "bhrrr" awaaz)
# piper priyamvada = asli female 207 Hz, pratham = male 97 Hz — inhe chhedna nahi
CAST = {
    "गौरी":  dict(engine="piper-f", pitch=1.00, tempo=1.00, tilt=+1.0, breath=0.010, vib=0.15, form="preserved"),  # 207 Hz
    "कमला":  dict(engine="piper-f", pitch=0.93, tempo=0.92, tilt=-2.0, breath=0.014, vib=0.22, form="preserved"),  # ~192 Hz
    "मोहन":  dict(engine="piper-f", pitch=1.30, tempo=1.05, tilt=+2.0, breath=0.012, vib=0.10, form="shifted"),    # ~269 Hz bachcha
    "हरिदास": dict(engine="piper-m", pitch=1.12, tempo=0.90, tilt=-2.5, breath=0.016, vib=0.18, form="preserved"),  # ~109 Hz
    "सरपंच": dict(engine="piper-m", pitch=1.20, tempo=0.98, tilt=-0.5, breath=0.014, vib=0.16, form="preserved"),
    "वाचक":  dict(engine="piper-m", pitch=1.15, tempo=1.00, tilt=0.0, breath=0.012, vib=0.14, form="preserved"),
    "भेड़िया": dict(engine="piper-m", pitch=0.90, tempo=0.88, tilt=-3.0, breath=0.030, vib=0.30, form="preserved"),
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


_PV = {}


def _piper_line(text, dst, model_name):
    """piper se line — asli sur par (koi bada shift nahi)."""
    import wave
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    v = _PV.get(model_name)
    if v is None:
        mp = Path("/scratch/work/voices") / model_name
        v = PiperVoice.load(str(mp), config_path=str(mp) + ".json")
        _PV[model_name] = v
    with wave.open(str(dst), "wb") as w:
        v.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=1.32))
    return dst.exists()


def line_audio(who, text):
    import hashlib
    key = hashlib.sha1(f"cast|{who}|{text}".encode()).hexdigest()[:16]
    dst = CACHE / f"{key}.wav"
    if dst.exists() and dst.stat().st_size > 2000:
        return dst
    cfg = CAST.get(who, dict(engine="piper-f", pitch=1.0, tempo=1.0, tilt=0.0, breath=0.012, vib=0.15))
    raw = CACHE / f"{key}_raw.wav"
    eng = cfg.get("engine", "piper-f")
    if eng.startswith("piper"):
        _piper_line(text, raw, "hi_IN-priyamvada-medium.onnx" if eng.endswith("f") else "hi_IN-pratham-medium.onnx")
    else:
        subprocess.run([sys.executable, str(Path(__file__).with_name("mms_worker.py")),
                        "--text", text, "--out", str(raw), "--pitch", "1.0"], capture_output=True)
    if not raw.exists():
        raise RuntimeError(f"tts fail {who}")
    y, sr = sf.read(str(raw)); y = y.mean(1) if y.ndim > 1 else y
    y = _rubber(y.astype(np.float64), sr, cfg["pitch"], cfg["tempo"], cfg.get("form", "preserved"))
    y = _tilt(y, sr, cfg["tilt"])
    y = _life(y, sr, cfg["breath"], cfg["vib"])
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.95
    sf.write(str(dst), y.astype("float32"), sr)
    raw.unlink(missing_ok=True)
    return dst


def _trim(y, sr, keep=0.04):
    """Chunk ke shuru/ant ki khaali awaaz kaato (warna piper ki silence + hamara gap = lambi chupp)."""
    env = np.abs(y)
    k = int(0.01 * sr)
    e = np.convolve(env, np.ones(k) / k, mode="same")
    thr = 0.06 * (np.percentile(e, 95) + 1e-9)
    idx = np.flatnonzero(e > thr)
    if len(idx) < 10:
        return y
    a = max(0, idx[0] - int(keep * sr))
    b = min(len(y), idx[-1] + int(keep * sr))
    return y[a:b]


def _legato(y, sr, ms=55):
    """Chupp aur bolne ke jod par narmi (60ms) — 'ruk-ruk' ki jhatke wali cut khatam."""
    env = np.abs(y)
    k = max(3, int(0.008 * sr))
    e = np.convolve(env, np.ones(k) / k, mode="same")
    thr = 0.07 * (np.percentile(e, 95) + 1e-9)
    soft = np.clip(e / (thr * 2.0 + 1e-12), 0.0, 1.0)      # 0 = chupp, 1 = bol raha
    n = max(8, int(ms / 1000 * sr))
    sm = np.convolve(soft, np.hanning(n) / np.hanning(n).sum(), mode="same")
    gain = 0.35 + 0.65 * sm                                  # chupp me bhi 35% rehne do (cut na lage)
    return y * gain


def _breath(sr, dur=0.22, level=0.012):
    """Saans lene ki halki awaaz (chupp ki jagah) — insaan jaisa."""
    n = int(dur * sr)
    rng = np.random.default_rng(11)
    nz = rng.normal(0, 1, n)
    from scipy import signal as ss
    sos = ss.butter(4, [400 / (sr / 2), 3000 / (sr / 2)], btype="band", output="sos")
    nz = ss.sosfilt(sos, nz)
    env = np.hanning(n) ** 1.5
    return level * nz * env / (np.max(np.abs(nz * env)) + 1e-9)


def build(script: Path, out: Path, gap=0.12, scene_gap=0.34):
    lines = []
    for l in script.read_text(encoding="utf-8").splitlines():
        if ":" in l:
            w, t = l.split(":", 1)
            if t.strip():
                lines.append((w.strip(), t.strip()))
    import re as _re
    pieces, prev = [], None
    for who, text in lines:
        text = text.replace(",", " ")      # piper comma par lamba pause deta hai -> ruk-ruk
        # line ko danda par todkar chhote gap se jodo — piper ke lambe pause ki jagah
        parts = [c.strip() for c in _re.split(r"(?<=[।!?])\s*", text) if c.strip()]
        if len(parts) > 1:
            ys = []
            for pi_, part in enumerate(parts):
                yy, sr_ = sf.read(str(line_audio(who, part)))
                yy = yy.mean(1) if yy.ndim > 1 else yy
                yy = _trim(yy.astype(np.float64), sr_)
                ys.append(yy)
                if pi_ < len(parts) - 1:
                    ys.append(np.zeros(int(0.11 * SR)))
            y = np.concatenate(ys); sr = SR
        else:
            y, sr = sf.read(str(line_audio(who, text)))
            y = y.mean(1) if y.ndim > 1 else y
            y = y.astype(np.float64)
        y = _trim(y, sr)                       # khaali hissa kaato
        # bahut chhota fade (click na ho, par ruk-ruk na lage)
        f = int(0.006 * sr)
        if len(y) > 3 * f:
            y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
        g = scene_gap if (prev and prev != who) else gap
        pieces.append(y)
        if g > 0.2:
            pieces.append(_breath(SR, min(0.24, g * 0.7)))   # chupp ki jagah saans
            pieces.append(np.zeros(int(max(0.0, g - min(0.24, g * 0.7)) * SR)))
        else:
            pieces.append(np.zeros(int(g * SR)))
        prev = who
    voice = np.concatenate(pieces)
    voice = _legato(voice, SR)
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
