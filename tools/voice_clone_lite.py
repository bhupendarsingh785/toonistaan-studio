#!/usr/bin/env python3
"""voice_clone_lite.py — bina GPU, bina bhaari model: apni awaaz ki nakal (profile match).

Kaam (asli, naap ke saath):
  1) **enroll**  — 5-15s recording se profile: sur (F0), awaaz ka rang (24 band envelope),
                   raftaar, chamak. Ijazat (consent) lazmi.
  2) **speak**   — piper se line banao (profile ke gender/umar se), phir **convert**:
                   sur ko target par le jao + spectral envelope target se milao.
  3) **naap**    — F0 kitna kareeb aaya, rang (spectral cosine) kitna mila.

XTTS/indicf5 jaisa "asli" cloning nahi (wo GPU maangta hai) — par yahi 1.43GB sandbox me
chalta hai, aur naap se batata hai kitna kareeb aaya.

  python tools/voice_clone_lite.py enroll --name dadi --audio x.wav --consent
  python tools/voice_clone_lite.py speak --name dadi --text "नमस्ते, मैं दादी हूँ।" --out a.wav
  python tools/voice_clone_lite.py test
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
K = ROOT / "knowledge"
PROF = K / "voice-profiles"
SR = 24000          # piper ka sample rate
BANDS = 24


# ---------- audio ----------
def load(path, sr=SR, sec=20.0):
    import ffbin
    ff = ffbin.ensure() or "ffmpeg"
    raw = subprocess.run([ff, "-v", "quiet", "-t", str(sec), "-i", str(path),
                          "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True).stdout
    if len(raw) < sr // 2:
        return None
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return x / (np.max(np.abs(x)) + 1e-9)


def f0_track(x, sr=SR, win=0.04, hop=0.02):
    w, h = int(win * sr), int(hop * sr)
    out = []
    for i in range(0, len(x) - w, h):
        seg = x[i:i + w]
        if np.sqrt((seg ** 2).mean()) < 0.01:
            continue
        ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
        lo, hi = int(sr / 500), min(int(sr / 60), len(ac) - 1)
        if hi <= lo:
            continue
        lag = np.argmax(ac[lo:hi]) + lo
        out.append(sr / (lag + 1e-9))
    return np.array(out) if out else np.array([0.0])


def envelope(x, sr=SR, n_fft=1024):
    """Awaaz ka rang: 24 band ka average magnitude (log)."""
    if len(x) < n_fft * 2:
        return np.zeros(BANDS)
    fr = np.lib.stride_tricks.sliding_window_view(x, n_fft)[:: n_fft // 2]
    X = np.abs(np.fft.rfft(fr * np.hanning(n_fft), axis=1)) + 1e-9
    f = np.fft.rfftfreq(n_fft, 1 / sr)
    edges = np.geomspace(60, min(10000, sr / 2 - 200), BANDS + 1)
    out = []
    for i in range(BANDS):
        m = (f >= edges[i]) & (f < edges[i + 1])
        out.append(float(np.log(X[:, m].mean() + 1e-9)) if m.any() else -20.0)
    return np.array(out)


def profile_of(x, sr=SR):
    f0 = f0_track(x, sr)
    voiced = f0[(f0 > 60) & (f0 < 500)]
    env = envelope(x, sr)
    # raftaar: bolne ke hisse ka % (rough)
    n = int(0.02 * sr)
    e = np.array([np.sqrt((x[i:i + n] ** 2).mean()) for i in range(0, len(x) - n, n)])
    active = float((e > 0.15 * (e.max() + 1e-9)).mean()) if len(e) else 0.0
    return {
        "f0_median": float(np.median(voiced)) if len(voiced) else 0.0,
        "f0_low": float(np.percentile(voiced, 15)) if len(voiced) else 0.0,
        "f0_high": float(np.percentile(voiced, 85)) if len(voiced) else 0.0,
        "env": [round(float(v), 2) for v in env],
        "active": round(active, 3),
    }


# ---------- conversion ----------
def _pitch_shift(x, factor, sr=SR):
    if abs(factor - 1.0) < 0.01:
        return x
    from scipy.signal import resample_poly
    from math import gcd
    # sur badalne ke liye lambai ulti taraf jaati hai: factor<1 (neeche) -> lambai badhti hai
    up, down = 100, int(round(factor * 100))
    g = gcd(up, down)
    y = resample_poly(x, up // g, down // g)
    # lambai wahi rakho
    if len(y) > len(x):
        y = y[: len(x)]
    else:
        y = np.pad(y, (0, len(x) - len(y)))
    return y


def _match_envelope(x, target_env, sr=SR, n_fft=1024):
    """Spectral envelope ko target se milao (band-wise gain) — awaaz ka rang badalta hai."""
    cur = envelope(x, sr, n_fft)
    gain_db = np.clip(np.array(target_env) - cur, -18.0, 18.0)
    fr = np.lib.stride_tricks.sliding_window_view(x, n_fft)[:: n_fft // 2]
    win = np.hanning(n_fft)
    f = np.fft.rfftfreq(n_fft, 1 / sr)
    edges = np.geomspace(60, min(10000, sr / 2 - 200), BANDS + 1)
    g = np.ones(len(f))
    for i in range(BANDS):
        m = (f >= edges[i]) & (f < edges[i + 1])
        g[m] = 10 ** (gain_db[i] / 20.0)
    out = np.zeros(len(x) + n_fft)
    wsum = np.zeros(len(x) + n_fft)
    hop = n_fft // 2
    for i in range(len(fr)):
        seg = np.fft.irfft(np.fft.rfft(fr[i] * win) * g, n=n_fft) * win
        out[i * hop:i * hop + n_fft] += seg
        wsum[i * hop:i * hop + n_fft] += win ** 2
    out = out[:len(x)] / np.maximum(wsum[:len(x)], 1e-6)
    return out


def convert(x, prof, sr=SR):
    """Awaaz ko profile ki taraf le jao: sur + rang."""
    target_f0 = prof.get("f0_median") or 0.0
    cur = profile_of(x, sr)
    factor = 1.0
    if target_f0 > 60 and cur["f0_median"] > 60:
        factor = float(np.clip(target_f0 / cur["f0_median"], 0.5, 1.8))
    y = _pitch_shift(x, factor, sr)
    # doosra daur: naap kar bacha hua fark theek karo (ek hi baar me poora nahi milta)
    for _ in range(2):
        now = profile_of(y, sr)["f0_median"]
        if now < 60 or target_f0 < 60:
            break
        need = target_f0 / now
        if abs(need - 1.0) < 0.03:
            break
        y = _pitch_shift(y, float(np.clip(need, 0.6, 1.6)), sr)
    y = _match_envelope(y, prof["env"], sr)
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.95
    return y, {"pitch_factor": round(factor, 3),
               "f0_before": round(cur["f0_median"], 1), "f0_target": round(target_f0, 1)}


# ---------- speak ----------
def _piper_line(text, out: Path, gender="f"):
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    import wave
    model = Path("/scratch/work/voices") / ("hi_IN-priyamvada-medium.onnx" if gender == "f" else "hi_IN-pratham-medium.onnx")
    if not model.exists():
        return False
    v = PiperVoice.load(str(model), config_path=str(model) + ".json")
    with wave.open(str(out), "wb") as w:
        v.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=1.0, noise_scale=0.667, noise_w_scale=0.8))
    return out.exists() and out.stat().st_size > 2000


def enroll(name: str, audio: str, consent: bool) -> dict:
    if not consent:
        raise PermissionError("ijazat (consent) ke bina enroll nahi hota")
    x = load(audio)
    if x is None:
        raise ValueError("audio padhi nahi ja saki")
    prof = profile_of(x)
    prof["name"] = name
    prof["consent"] = True
    PROF.mkdir(parents=True, exist_ok=True)
    (PROF / f"{name}.json").write_text(json.dumps(prof, ensure_ascii=False, indent=1), encoding="utf-8")
    return prof


def speak(name: str, text: str, out: Path, gender="f") -> dict:
    p = PROF / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"profile nahi: {name} (pehle enroll karo)")
    prof = json.loads(p.read_text(encoding="utf-8"))
    tmp = out.with_suffix(".raw.wav")
    if not _piper_line(text, tmp, gender):
        raise RuntimeError("piper se line nahi bani")
    x = load(tmp)
    y, info = convert(x, prof)
    import soundfile as sf
    sf.write(str(out), y.astype(np.float32), SR)
    after = profile_of(y)
    return {**info, "f0_after": round(after["f0_median"], 1),
            "env_cos": round(float(np.dot(np.array(prof["env"]), np.array(after["env"])) /
                                   ((np.linalg.norm(prof["env"]) * np.linalg.norm(after["env"])) + 1e-9)), 3)}


def test() -> int:
    """Apne aap jaanch: ek asli awaaz se profile, phir usi awaaz me line banao."""
    # asli awaaz: library se (purane render par depend nahi)
    src = None
    for pat in ("man-talking", "woman-crying", "speech", "voice"):
        got = sorted(Path("/scratch/input").glob(f"*{pat}*"))
        if got:
            src = got[0]; break
    if src is None:
        print("test ke liye awaaz nahi mili"); return 1
    print("test awaaz:", src.name[:50])
    prof = enroll("test_voice", str(src), consent=True)
    print("profile: f0", round(prof["f0_median"], 1), "Hz | active", prof["active"])
    out = Path("/scratch/work/clone_test.wav")
    r = speak("test_voice", "नमस्ते, यह आवाज़ की जाँच है।", out)
    print("convert:", r)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["enroll", "speak", "test", "profiles"])
    ap.add_argument("--name", default="")
    ap.add_argument("--audio", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--out", default="/scratch/work/clone-out.wav")
    ap.add_argument("--consent", action="store_true")
    a = ap.parse_args()
    if a.cmd == "test":
        return test()
    if a.cmd == "profiles":
        for p in sorted(PROF.glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            print(f"{d['name']}: f0 {round(d['f0_median'],1)} Hz")
        return 0
    if a.cmd == "enroll":
        prof = enroll(a.name, a.audio, a.consent)
        print(json.dumps({k: v for k, v in prof.items() if k != "env"}, ensure_ascii=False, indent=1))
        return 0
    r = speak(a.name, a.text or "नमस्ते।", Path(a.out))
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
