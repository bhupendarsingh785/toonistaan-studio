"""
Gates — har line ki awaaz ki turant jaanch (< 50 ms) + wahin sudhaar.

Spec ke 5 gate + 2 naye:
  clipping    peak > 0.98                     -> gain −2 dB (line par hi)
  echo        17–31 ms ka cepstral peak        -> 'no_fx' ke saath dobara render
              (spec ka autocorrelation tareeka sur (F0) ke harmonics ko echo samajh leta hai:
               105 Hz awaaz ka 2–3 guna period = 19 / 28.5 ms! Isliye F0 ke multiples chhod kar dekhte hain)
  brightness  voiced centroid voice-profile ki range se bahar -> presence shelf ±0.8 dB (har koshish)
  gap         line ke andar > 0.35 s           -> 0.20 s
  ant-kata    line ka aakhri 25 ms tez (TTS ne beech me kaata) -> dobara render  [naya]
  khaali      line me awaaz hi nahi / bahut chhoti            -> dobara render  [naya]
(Vakya ke baad pause story jodte waqt duniya.py lagata hai.)
"""
from __future__ import annotations
import numpy as np
from scipy import signal as ss
import re

def _frames(y, sr, win=0.025, hop=0.010):
    w, h = int(win * sr), int(hop * sr)
    if len(y) < w: y = np.pad(y, (0, w - len(y)))
    return np.lib.stride_tricks.sliding_window_view(y, w)[::h]

def db(x): return 20 * np.log10(np.maximum(x, 1e-12))

def f0_period(y, sr):
    try:
        import librosa
        f0 = librosa.yin(y[: sr * 3], fmin=70, fmax=400, sr=sr, frame_length=1024)
        f = float(np.median(f0[(f0 > 70) & (f0 < 400)])) if np.any((f0 > 70) & (f0 < 400)) else 0
        return 1 / f if f else None
    except Exception:
        return None

def echo_score(y, sr):
    """Real cepstrum (voiced frames ka average), 17–31 ms; F0 period ke multiples (±1 ms) chhod do."""
    fr = _frames(y, sr, 0.064, 0.016)
    e = np.sqrt((fr ** 2).mean(1)); fr = fr[e > np.percentile(e, 60)]
    if len(fr) == 0: return 0.0, None
    X = np.abs(np.fft.rfft(fr * np.hanning(fr.shape[1]), axis=1)) + 1e-9
    c = np.fft.irfft(np.log(X), axis=1).mean(0)
    q = np.arange(len(c)) / sr
    band = (q >= 0.017) & (q <= 0.031)
    T = f0_period(y, sr)
    if T:
        for k in range(1, 6): band &= ~((q > k * T - 0.001) & (q < k * T + 0.001))
    ref = np.abs(c[(q > 0.002) & (q < 0.012)]).max() + 1e-9
    if not band.any(): return 0.0, T
    return float(np.abs(c[band]).max() / ref), T

def centroid_voiced(y, sr):
    fr = _frames(y, sr, 0.032, 0.016); e = np.sqrt((fr ** 2).mean(1))
    fr = fr[e > np.percentile(e, 50)]
    if len(fr) == 0: return 0.0
    X = np.abs(np.fft.rfft(fr * np.hanning(fr.shape[1]), axis=1)); f = np.fft.rfftfreq(fr.shape[1], 1 / sr)
    return float((X * f).sum() / (X.sum() + 1e-9))

def inner_gaps(y, sr, thr_db=-40):
    fr = _frames(y, sr); d = db(np.sqrt((fr ** 2).mean(1))); d -= d.max()
    q = d < thr_db; gaps = []; i = 0
    first = np.argmax(~q); last = len(q) - np.argmax(~q[::-1])
    i = first
    while i < last:
        if q[i]:
            j = i
            while j < last and q[j]: j += 1
            gaps.append((i * 0.010, j * 0.010)); i = j
        else: i += 1
    return gaps

def presence(y, sr, db_change):
    """High shelf ~3 kHz: + = chamak zyada, − = kam."""
    sos = ss.butter(2, 3000 / (sr / 2), "high", output="sos"); hi = ss.sosfilt(sos, y)
    return y + hi * (10 ** (db_change / 20) - 1)

def allowed_gaps(text):
    """Line ke andar viraam: vakya (। ! ? …) = 0.75 s tak, comma = 0.45 s tak — utne lambe ruke theek hain."""
    if not text: return []
    t = text.strip().rstrip("।!?.… \"'")
    return sorted([0.75] * len(re.findall(r"[।!?…]|\.\.\.", t)) + [0.45] * t.count(","), reverse=True)

def excess_gaps(y, sr, text=None, limit=0.35):
    """> limit wale gap jo viraam ki chhoot me nahi aate (sabse lambe gap ko sabse badi chhoot)."""
    allow = allowed_gaps(text); bad = []
    for g in sorted([g for g in inner_gaps(y, sr) if g[1] - g[0] > limit], key=lambda g: g[0] - g[1]):
        if allow and g[1] - g[0] <= allow[0]: allow.pop(0)
        else: bad.append(g)
    return sorted(bad)

def check(y, sr, profile=None, text=None):
    """Returns list of gate results [{gate, ok, value, fix}]."""
    P = profile or {}
    res = []
    dur = len(y) / sr
    peak = float(np.abs(y).max()) if len(y) else 0.0
    res.append({"gate": "khaali", "ok": dur > 0.25 and peak > 0.01, "value": round(dur, 2), "fix": "rerender"})
    if not res[-1]["ok"]: return res
    res.append({"gate": "clipping", "ok": peak <= 0.98, "value": round(peak, 3), "fix": "gain-2"})
    es, T = echo_score(y, sr)
    res.append({"gate": "echo", "ok": es <= P.get("echo_max", 0.78), "value": round(es, 3), "fix": "rerender_no_fx",
                "note": f"F0 period {T * 1000:.1f} ms chhoda" if T else ""})
    c = centroid_voiced(y, sr)
    if P.get("bright"):        # sirf tab jab is awaaz ki range di ho; warna nirantarta apne profile se chamak dekhti hai
        lo, hi = P["bright"]
        res.append({"gate": "brightness", "ok": lo <= c <= hi, "value": round(c), "fix": "presence+0.8" if c < lo else "presence-0.8", "range": [lo, hi]})
    gaps = excess_gaps(y, sr, text)
    res.append({"gate": "gap", "ok": not gaps, "value": [round(b - a, 2) for a, b in gaps], "fix": "gap0.20"})
    tail = y[-int(0.025 * sr):]; body = np.sqrt(np.mean(y ** 2)) + 1e-9
    cut = np.sqrt(np.mean(tail ** 2)) / body
    res.append({"gate": "ant-kata", "ok": cut < 0.5, "value": round(float(cut), 3), "fix": "rerender"})
    return res

def apply_fix(y, sr, fix, gate_res=None, text=None):
    """Line par hi lagne wale sudhaar. Returns (y, applied?)."""
    if fix == "gain-2": return y * 10 ** (-2 / 20), True
    if fix in ("presence+0.8", "presence-0.8"): return presence(y, sr, 0.8 if fix.endswith("+0.8") else -0.8), True
    if fix == "gap0.20":
        out, last, keep = [], 0, int(0.10 * sr)
        for a_, b_ in excess_gaps(y, sr, text):
            ia, ib = int(a_ * sr), int(b_ * sr)
            out.append(y[last:ia + keep]); last = ib - keep
        out.append(y[last:])
        return np.concatenate(out), True
    return y, False
