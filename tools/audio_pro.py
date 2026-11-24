#!/usr/bin/env python3
"""audio_pro.py — jo 6 kaam system me nahi the (ab naap ke saath):

  denoise(x, sr)                  — shor saaf (spectral gate, profile chup frames se)
  restore(x, sr)                  — kharab recording sudhaaro (DC, hum, click, clip)
  occlude(x, sr, wall="deewar")   — deewar ke peeche se aati awaaz (dabbi, kam upar ki)
  stream_chunks(path, ...)        — lamba audio tukdon me padho (memory me poora na aaye)
  diarize(x, sr)                  — kaun kab bola (speaker badalna pakdo)
  adr(recorded, reference, sr)    — dobara record ki line ko original timing par fit karo

  python tools/audio_pro.py --test
"""
from __future__ import annotations
import numpy as np
import soundfile as sf

SR = 22050


# ---------------- 1) shor saaf ----------------
def denoise(x, sr=SR, strength=2.0, floor=0.10, nperseg=1024):
    """Shor saaf — STFT ke power se shor ghataao (scipy se, isliye reconstruction saaf).

    Shor ka naqsha har frequency bin ke sabse chup hisse se banta hai (chup frame
    zaroori nahi) — isliye lagataar bolne wali recording par bhi kaam karta hai.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if len(x) < nperseg * 4:
        return x.astype(np.float32)
    from scipy.signal import stft, istft
    f, t, Z = stft(x, fs=sr, nperseg=nperseg, noverlap=int(nperseg * 0.75))
    P = np.abs(Z) ** 2
    noise = np.percentile(P, 10, axis=1, keepdims=True) + 1e-14
    Pc = np.maximum(P - strength * noise, floor * P)
    Zc = np.sqrt(Pc) * (Z / (np.abs(Z) + 1e-14))
    _, y = istft(Zc, fs=sr, nperseg=nperseg, noverlap=int(nperseg * 0.75))
    y = y[: len(x)]
    if len(y) < len(x):
        y = np.pad(y, (0, len(x) - len(y)))
    return y.astype(np.float32)


# ---------------- 2) kharab recording sudhaar ----------------
def restore(x, sr=SR, hum_hz=50.0, harmonics=(1, 2)):
    x = np.asarray(x, dtype=np.float64)
    x = x - np.mean(x)                                   # DC
    # hum (50/60 Hz + harmonics): sine ko naap kar ghatao (voice ko chhede bina)
    if hum_hz and len(x) > sr:
        t = np.arange(len(x)) / sr
        for k in harmonics:      # sirf wahin jahan hum ho (voice ke harmonic ko na chhede)
            w = 2 * np.pi * hum_hz * k * t
            s_, c_ = np.sin(w), np.cos(w)
            a = 2 * np.dot(x, s_) / len(x)
            b = 2 * np.dot(x, c_) / len(x)
            x = x - (a * s_ + b * c_)
    # click (achanak chubhne wali awaaz) — median filter se pakdo
    k = 5
    pad = np.pad(x, k, mode="edge")
    med = np.array([np.median(pad[i:i + 2 * k + 1]) for i in range(0, len(x), max(1, len(x) // 20000) or 1)])
    if len(med) > 10:
        thr = np.median(np.abs(x)) * 8 + 1e-6
        bad = np.abs(x) > thr
        if bad.any():
            idx = np.flatnonzero(bad)
            for i in idx:
                a, b = max(0, i - 3), min(len(x), i + 4)
                x[i] = np.median(x[a:b])
    # clip (chhat tak chadhna) — sirf jab sach me chhat ke paar ho
    peak = np.max(np.abs(x)) or 1.0
    if peak > 1.0:
        x = np.tanh(x / peak * 1.1) / np.tanh(1.1)
    peak = np.max(np.abs(x)) or 1.0
    if peak > 0.95:
        x = x / peak * 0.95
    return x.astype(np.float32)


# ---------------- 3) deewar ke peeche se awaaz ----------------
def occlude(x, sr=SR, wall="deewar", dist=1.0):
    """Deewar/parda/patti ke peeche se aati awaaz: upar ki frequency aur level girta hai."""
    x = np.asarray(x, dtype=np.float64)
    prof = {"deewar": (900.0, 0.45), "parda": (2500.0, 0.65), "darwaza": (1800.0, 0.55),
            "zameen": (600.0, 0.35)}.get(wall, (1200.0, 0.5))
    fc, lvl = prof
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    H = 1.0 / np.sqrt(1.0 + (f / fc) ** 2)
    y = np.fft.irfft(X * H, n=len(x)) * lvl / max(0.6, dist)
    return y.astype(np.float32)


# ---------------- 4) lamba audio tukdon me ----------------
def stream_chunks(path, chunk_s=30.0, overlap_s=0.5, sr=None):
    """Lamba audio ko tukdon me padho — poora memory me nahi aata."""
    info = sf.info(str(path))
    sr = sr or info.samplerate
    n = int(chunk_s * sr)
    ov = int(overlap_s * sr)
    start = 0
    total = info.frames
    with sf.SoundFile(str(path)) as f:
        while start < total:
            f.seek(start)
            block = f.read(n, dtype="float32", always_2d=False)
            if block is None or len(block) == 0:
                break
            yield start / sr, block
            if len(block) < n:
                break
            start += max(1, n - ov)


# ---------------- 5) kaun kab bola ----------------
def diarize(x, sr=SR, max_speakers=2, win_s=0.5):
    """Speaker badalna pakdo: har tukde ka sur (F0) + rang (centroid), phir cluster."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    n = int(win_s * sr)
    feats, spans = [], []
    for i in range(0, len(x) - n, n):
        seg = x[i:i + n]
        if np.sqrt((seg ** 2).mean()) < 0.01:
            continue
        # F0: autocorrelation
        ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
        lo, hi = int(sr / 350), int(sr / 70)
        if hi >= len(ac):
            continue
        f0 = sr / (np.argmax(ac[lo:hi]) + lo + 1e-9)
        X = np.abs(np.fft.rfft(seg)) + 1e-12
        f = np.fft.rfftfreq(len(seg), 1 / sr)
        cent = float((X * f).sum() / X.sum())
        feats.append([f0, cent / 1000.0])
        spans.append((i / sr, (i + n) / sr))
    if len(feats) < 3:
        return []
    F = np.array(feats)
    F = (F - F.mean(0)) / (F.std(0) + 1e-9)
    # 2-means (k=2..max_speakers me sabse alag)
    best = None
    for k in [2] + [x for x in range(3, max_speakers + 1)]:
        rng = np.random.default_rng(7)
        C = F[rng.choice(len(F), k, replace=False)]
        for _ in range(12):
            d = ((F[:, None, :] - C[None, :, :]) ** 2).sum(2)
            lab = d.argmin(1)
            for j in range(k):
                if (lab == j).any():
                    C[j] = F[lab == j].mean(0)
        spread = float(sum(((F[lab == j] - C[j]) ** 2).sum() for j in range(k)) / len(F))
        if best is None or spread < best[0] * 0.6:
            best = (spread, lab, k)
    _, lab, k = best
    # chhote-chhote badlav (0.5s) hatao — speaker 0.5s me nahi badalta
    lab = lab.copy()
    for i in range(1, len(lab) - 1):
        if lab[i - 1] == lab[i + 1] != lab[i]:
            lab[i] = lab[i - 1]
    segs = []
    for (a, b), l in zip(spans, lab):
        if segs and segs[-1]["speaker"] == int(l) and abs(segs[-1]["t1"] - a) < 0.05:
            segs[-1]["t1"] = b
        else:
            segs.append({"speaker": int(l), "t0": round(a, 2), "t1": round(b, 2)})
    return segs


# ---------------- 6) ADR (dobara record ki line ko fit karo) ----------------
def adr(recorded, reference, sr=SR):
    """Nayi record ki hui line ko original ki timing par baithao (offset + lambai)."""
    rec = np.asarray(recorded, dtype=np.float64)
    ref = np.asarray(reference, dtype=np.float64)
    if rec.ndim > 1:
        rec = rec.mean(1)
    if ref.ndim > 1:
        ref = ref.mean(1)
    # lambai milao (time-scale)
    if len(rec) != len(ref) and len(rec) > 32:
        idx = np.linspace(0, len(rec) - 1, len(ref))
        rec = np.interp(idx, np.arange(len(rec)), rec)
    # offset: dono ke "shuru hone" ko milao (onset), phir baithao
    def onset(a):
        env = np.abs(a)
        thr = env.max() * 0.25
        idx = np.flatnonzero(env > thr)
        return int(idx[0]) if len(idx) else 0
    o_rec, o_ref = onset(rec), onset(ref)
    shift = o_ref - o_rec
    if shift > 0:
        rec = np.concatenate([np.zeros(shift), rec])
    elif shift < 0:
        rec = rec[-shift:]
    rec = np.pad(rec, (0, max(0, len(ref) - len(rec))))[:len(ref)]
    return rec.astype(np.float32)


# ---------------- test ----------------
def _test():
    sr = SR
    t = np.arange(int(2.0 * sr)) / sr
    voice = sum((0.5 / k) * np.sin(2 * np.pi * 150 * k * t) for k in range(1, 15)) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))
    rng = np.random.default_rng(2)
    noisy = voice + 0.12 * rng.normal(0, 1, len(t))   # bina pause wali recording
    def snr(a, clean=voice):
        e = np.sqrt(((a[:len(clean)] - clean) ** 2).mean())
        return 20 * np.log10(np.sqrt((clean ** 2).mean()) / (e + 1e-12))
    den = denoise(noisy, sr)
    print(f"denoise: SNR {snr(noisy):.1f} dB -> {snr(den):.1f} dB")

    bad = voice.copy()
    bad += 0.3 * np.sin(2 * np.pi * 50 * t)               # hum
    bad += 0.2                                             # DC
    bad[500] += 3.0                                        # click
    fixed = restore(bad, sr)
    def hum_db(a):
        X = np.abs(np.fft.rfft(a)); f = np.fft.rfftfreq(len(a), 1 / sr)
        return 20 * np.log10(X[np.abs(f - 50) < 2].max() / (np.median(X) + 1e-12))
    def hum_abs(a):
        X = np.abs(np.fft.rfft(a)); f = np.fft.rfftfreq(len(a), 1 / sr)
        h = X[np.abs(f - 50) < 2].max()
        s150 = X[np.abs(f - 150) < 3].max()
        return 20 * np.log10((h + 1e-12) / (s150 + 1e-12))
    print(f"restore: hum {hum_abs(bad):.1f} -> {hum_abs(fixed):.1f} dBFS | DC {np.mean(bad):+.3f} -> {np.mean(fixed):+.4f}"
          f" | awaaz bachi {np.corrcoef(fixed[2000:40000], voice[2000:40000])[0,1]:.3f}")

    o = occlude(voice, sr, "deewar")
    def hf(a):
        X = np.abs(np.fft.rfft(a)); f = np.fft.rfftfreq(len(a), 1 / sr)
        return float(X[(f > 2000) & (f < 8000)].sum() / (X.sum() + 1e-12))
    print(f"occlude: HF hissa {hf(voice):.4f} -> {hf(o):.4f} | level {20*np.log10(np.sqrt((o**2).mean())+1e-9):.1f} dB")

    import tempfile
    from pathlib import Path
    p = Path(tempfile.mkdtemp()) / "long.wav"
    sf.write(p, np.tile(voice, 20).astype(np.float32), sr)
    got = list(stream_chunks(p, chunk_s=5.0, overlap_s=0.5))
    print(f"stream: {len(got)} tukde, pehla {len(got[0][1])/sr:.1f}s, aakhri t={got[-1][0]:.1f}s")

    # do "speaker": alag F0
    v1 = sum((0.5 / k) * np.sin(2 * np.pi * 110 * k * t) for k in range(1, 12))
    v2 = sum((0.5 / k) * np.sin(2 * np.pi * 210 * k * t) for k in range(1, 12))
    mixv = np.concatenate([v1[:sr], v2[:sr], v1[:sr]])
    segs = diarize(mixv, sr)
    print(f"diarize: {len(segs)} hisse ->", [(s['speaker'], s['t0'], s['t1']) for s in segs][:6])

    ref = np.zeros(int(3 * sr)); ref[int(1.0 * sr):int(2.0 * sr)] = voice[:sr]
    rec = np.zeros(int(2.4 * sr)); rec[int(0.2 * sr):int(1.2 * sr)] = voice[:sr] * 0.9
    fitted = adr(rec, ref, sr)
    def peak_at(a):
        return int(np.argmax(np.abs(a)) / sr * 100) / 100
    print(f"adr: ref shikhar {peak_at(ref)}s, record {peak_at(rec)}s -> fit {peak_at(fitted)}s")


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        _test()
    else:
        print(__doc__)
