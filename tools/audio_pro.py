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
def denoise(x, sr=SR, strength=2.0, floor=0.06, nperseg=1024, smooth=0.92):
    """Shor saaf — do kadam:

    1. **Shor ka naqsha** har bin ke sabse chup hisse se (chup frame ki zaroorat nahi).
    2. **Decision-directed Wiener** (Ephraim-Malah ka saaf roop): pichhle frame ki
       saaf awaaz se andaaza, phir gain — isse "musical noise" (chidiya jaisi chhit)
       nahi banti, jo simple subtraction me hoti hai.

    smooth = kitna pichhle frame par bharosa (0.9+ = zyada smooth, kam chhit).
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if len(x) < nperseg * 4:
        return x.astype(np.float32)
    from scipy.signal import stft, istft
    f, t, Z = stft(x, fs=sr, nperseg=nperseg, noverlap=int(nperseg * 0.75))
    P = np.abs(Z) ** 2
    # |STFT|^2 exponential hota hai: 10th percentile ≈ 0.105 × asli shor
    # (isliye bias theek karna zaroori hai, warna shor ka naqsha 10x chhota rehta hai)
    noise = np.percentile(P, 10, axis=1, keepdims=True) / 0.105 + 1e-14
    # decision-directed a priori SNR
    gamma = P / noise                       # posteriori
    xi = np.zeros_like(P)
    G = np.zeros_like(P)
    prev = np.maximum(gamma[:, 0] - 1.0, floor)
    for i in range(P.shape[1]):
        xi[:, i] = smooth * prev + (1 - smooth) * np.maximum(gamma[:, i] - 1.0, 0.0)
        g = xi[:, i] / (1.0 + xi[:, i])                  # Wiener gain
        g = np.maximum(g, floor)
        # kam shor wali jagah par gain 1 ke kareeb (awaaz na chhute)
        g = np.where(gamma[:, i] > 6.0, np.maximum(g, 0.85), g)
        G[:, i] = g
        prev = g ** 2 * gamma[:, i]
    Zc = G * Z
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
MATERIALS = {
    # (base TL @500Hz dB, dhalan dB/octave, level loss dB)  — asli naap ke aas-paas
    "deewar":  (18.0, 3.0, 6.0),
    "parda":   (6.0, 1.2, 2.0),
    "darwaza": (10.0, 2.0, 3.5),
    "zameen":  (12.0, 2.5, 4.0),
    "sheesha": (22.0, 4.5, 7.0),
    "loha":    (26.0, 5.0, 9.0),
}


def occlude(x, sr=SR, wall="deewar", dist=1.0, thickness=1.0):
    """Deewar ke peeche se aati awaaz — material ke hisaab se (base + dhalan).

    Har material ki apni transmission loss hoti hai: upar ki frequency zyada marti
    hai (isliye deewar ke peeche se awaaz "ghutti hui" sunai deti hai), aur motai
    (thickness) badhne par aur dabti hai.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    base_db, slope, loss_db = MATERIALS.get(wall, MATERIALS["deewar"])
    base_db *= max(0.3, thickness)
    loss_db *= max(0.3, thickness)
    X = np.fft.rfft(x)
    f = np.maximum(np.fft.rfftfreq(len(x), 1 / sr), 20.0)
    tl_db = base_db + slope * np.log2(f / 500.0)          # Hz ke hisaab se
    tl_db = np.clip(tl_db, 0.0, 60.0)
    g = 10 ** (-(tl_db + loss_db) / 20.0)
    y = np.fft.irfft(X * g, n=len(x))
    # doori ka asar bhi
    y = y / max(0.8, dist)
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
def diarize(x, sr=SR, max_speakers=4, win_s=0.5, min_share=0.15):
    """Kaun kab bola — 3-4 awaazein bhi alag.

    Har 0.5s tukde ka "chehra": sur (F0), mel-band energy (awaaz ka rang),
    aur bolne ka dhang. Phir clustering, aur k chhota rakho jab tak har speaker
    ka hissa min_share se bada rahe (warna faltu speaker ban jaate hain).
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    n = int(win_s * sr)
    feats, spans = [], []
    for i in range(0, len(x) - n, n):        # tukde overlap nahi — speaker badalna saaf dikhe
        seg = x[i:i + n]
        if np.sqrt((seg ** 2).mean()) < 0.008:
            continue
        # F0 (autocorrelation)
        ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
        lo, hi = int(sr / 400), int(sr / 70)
        if hi >= len(ac):
            continue
        f0 = sr / (np.argmax(ac[lo:hi]) + lo + 1e-9)
        # mel-jaisa rang (6 band) + centroid
        X = np.abs(np.fft.rfft(seg)) + 1e-12
        f = np.fft.rfftfreq(len(seg), 1 / sr)
        bands = []
        for (a, b) in ((80, 300), (300, 800), (800, 1600), (1600, 3000), (3000, 5000), (5000, 8000)):
            m = (f >= a) & (f < b)
            bands.append(np.log(X[m].sum() + 1e-9))
        cent = float((X * f).sum() / X.sum())
        # sur ko zyada wazan do — insaan ki pehchaan sur se hi sabse zyada hoti hai
        feats.append([2.5 * np.log(f0), cent / 1000.0] + bands)
        spans.append((i / sr, (i + n) / sr))
    if len(feats) < 4:
        return []
    F = np.array(feats)
    F = (F - F.mean(0)) / (F.std(0) + 1e-9)

    # agglomerative clustering: jodte jao jab tak doori chhoti ho (k pehle se tay nahi)
    # thr data se: sabse kareebi jodiyon ki doori ke hisaab se
    D = ((F[:, None, :] - F[None, :, :]) ** 2).sum(2) ** 0.5
    np.fill_diagonal(D, np.inf)
    base = float(np.median(D.min(1))) if len(F) > 2 else 1.0

    def cluster(thr=None):
        thr = thr if thr is not None else max(0.35, 1.6 * base)
        clusters = [[i] for i in range(len(F))]
        while len(clusters) > 1:
            best = None
            for a in range(len(clusters)):
                for b in range(a + 1, len(clusters)):
                    ca = F[clusters[a]].mean(0)
                    cb = F[clusters[b]].mean(0)
                    d = float(np.sqrt(((ca - cb) ** 2).sum()))
                    if best is None or d < best[0]:
                        best = (d, a, b)
            if best is None or best[0] > thr:
                break
            _, a, b = best
            clusters[a] += clusters[b]
            clusters.pop(b)
        lab = np.zeros(len(F), dtype=int)
        for j, idxs in enumerate(clusters):
            lab[idxs] = j
        return lab, len(clusters)

    lab, k = cluster()
    # bahut chhote cluster (min_share se kam) ko sabse kareeb wale me mila do
    while k > 2:
        share = np.bincount(lab, minlength=k) / len(lab)
        tiny = int(np.argmin(share))
        if share[tiny] >= min_share:
            break
        others = [j for j in range(k) if j != tiny]
        dists = [float(np.sqrt(((F[lab == tiny].mean(0) - F[lab == j].mean(0)) ** 2).sum())) for j in others]
        lab[lab == tiny] = others[int(np.argmin(dists))]
        lab = np.array([{o: n for n, o in enumerate(sorted(set(lab)))}[int(v)] for v in lab])
        k = len(set(lab))
    # chhote-chhote badlav hatao
    for i in range(1, len(lab) - 1):
        if lab[i - 1] == lab[i + 1] != lab[i]:
            lab[i] = lab[i - 1]

    segs = []
    for (a, b), l in zip(spans, lab):
        if segs and segs[-1]["speaker"] == int(l) and abs(segs[-1]["t1"] - a) < 0.3:
            segs[-1]["t1"] = round(b, 2)
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


def _frames(x, sr, n=512, hop=256):
    if len(x) < n * 2:
        return np.zeros((1, 12))
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop]
    X = np.abs(np.fft.rfft(fr * np.hanning(n), axis=1)) + 1e-10
    f = np.fft.rfftfreq(n, 1 / sr)
    edges = np.geomspace(80, min(8000, sr / 2 - 100), 13)
    out = []
    for i in range(12):
        m = (f >= edges[i]) & (f < edges[i + 1])
        out.append(np.log(X[:, m].sum(1) + 1e-9) if m.any() else np.zeros(len(X)))
    F = np.stack(out, 1)
    return (F - F.mean(0)) / (F.std(0) + 1e-9)


def adr_dtw(recorded, reference, sr=SR, band=None):
    """ADR gehra: DTW se shabd-dar-shabd timing milao (sirf shuruaat nahi).

    record ki hui line ko reference ki timing par "kheench" deta hai — jahan actor
    ne dheere bola wahan kheench, jahan tez bola wahan sikod.
    """
    rec = np.asarray(recorded, dtype=np.float64)
    ref = np.asarray(reference, dtype=np.float64)
    if rec.ndim > 1:
        rec = rec.mean(1)
    if ref.ndim > 1:
        ref = ref.mean(1)
    A = _frames(rec, sr)
    B = _frames(ref, sr)
    if len(A) < 3 or len(B) < 3:
        return adr(rec, ref, sr)
    # cost matrix + DTW (Sakoe-Chiba band ke saath, tez)
    N, M = len(A), len(B)
    band = band or max(30, abs(N - M) + 20)
    INF = 1e9
    D = np.full((N, M), INF)
    D[0, 0] = np.sqrt(((A[0] - B[0]) ** 2).sum())
    for i in range(1, N):
        lo, hi = max(0, i - band), min(M, i + band + 1)
        for j in range(lo, hi):
            c = np.sqrt(((A[i] - B[j]) ** 2).sum())
            D[i, j] = c + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    # path wapas
    i, j = N - 1, M - 1
    path = [(i, j)]
    while i > 0 or j > 0:
        opts = []
        if i > 0 and j > 0:
            opts.append((D[i - 1, j - 1], i - 1, j - 1))
        if i > 0:
            opts.append((D[i - 1, j], i - 1, j))
        if j > 0:
            opts.append((D[i, j - 1], i, j - 1))
        _, i, j = min(opts)
        path.append((i, j))
    path.reverse()
    # rec ke frames -> ref ke frames
    hop = 256
    src_idx = np.array([p[0] * hop for p in path], dtype=float)
    dst_idx = np.array([p[1] * hop for p in path], dtype=float)
    order = np.argsort(dst_idx)
    dst_idx, src_idx = dst_idx[order], src_idx[order]
    tgt = np.arange(len(ref))
    src_at = np.interp(tgt, dst_idx, src_idx)
    src_at = np.clip(src_at, 0, len(rec) - 1)
    out = np.interp(src_at, np.arange(len(rec)), rec)
    return out.astype(np.float32)


# ---------------- test ----------------
def _test():
    sr = SR
    rng = np.random.default_rng(5)
    t = np.arange(int(3.0 * sr)) / sr
    # 1) shor saaf
    voice = np.zeros(len(t))
    for a0 in (0.2, 1.1, 2.0):
        seg = slice(int(a0 * sr), int((a0 + 0.7) * sr))
        tt = t[seg] - t[seg][0]
        voice[seg] = sum((0.45 / k) * np.sin(2 * np.pi * 160 * k * tt) for k in range(1, 12)) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * tt))
    noisy = voice + 0.09 * rng.normal(0, 1, len(t))
    den = denoise(noisy, sr)
    rms = lambda a: float(np.sqrt((a ** 2).mean()) + 1e-12)  # noqa: E731
    snr_i = 20 * np.log10(rms(voice) / (np.sqrt(((noisy - voice) ** 2).mean()) + 1e-12))
    snr_o = 20 * np.log10(rms(voice) / (np.sqrt(((den - voice) ** 2).mean()) + 1e-12))
    sp = slice(int(1.15 * sr), int(1.75 * sr))
    print(f"denoise: SNR {snr_i:.1f} -> {snr_o:.1f} dB ({snr_o - snr_i:+.1f}) | awaaz bachi {np.corrcoef(den[sp], voice[sp])[0, 1]:.3f}")

    # 2) kharab recording
    bad = (voice + 0.3 * np.sin(2 * np.pi * 50 * t) + 0.2).copy()
    bad[500] += 3.0
    fixed = restore(bad, sr)
    def hum(a):
        X = np.abs(np.fft.rfft(a)); f = np.fft.rfftfreq(len(a), 1 / sr)
        return 20 * np.log10(X[np.abs(f - 50) < 1.5].max() / (np.sqrt(len(a)) / 2) + 1e-12)
    print(f"restore: hum {hum(bad):.1f} -> {hum(fixed):.1f} dBFS | DC {np.mean(bad):+.3f} -> {np.mean(fixed):+.4f}"
          f" | awaaz bachi {np.corrcoef(fixed[2000:40000], voice[2000:40000])[0, 1]:.3f}")

    # 3) deewar ke peeche
    src = sum(np.sin(2 * np.pi * f * t[:sr]) for f in (250, 1000, 4000))
    def band_db(y, f0):
        X = np.abs(np.fft.rfft(y)); f = np.fft.rfftfreq(len(y), 1 / sr)
        return 20 * np.log10(X[np.abs(f - f0) < 20].max() + 1e-9)
    for m in ("parda", "deewar", "loha"):
        y = occlude(src, sr, m)
        print(f"occlude {m:7s}: 250Hz {band_db(y,250)-band_db(src,250):+.1f} dB | 4kHz {band_db(y,4000)-band_db(src,4000):+.1f} dB")

    # 4) lamba audio
    import tempfile
    from pathlib import Path as _P
    pp = _P(tempfile.mkdtemp()) / "long.wav"
    sf.write(pp, np.tile(voice, 20).astype(np.float32), sr)
    got = list(stream_chunks(pp, chunk_s=5.0, overlap_s=0.5))
    print(f"stream: {len(got)} tukde, pehla {len(got[0][1]) / sr:.1f}s, aakhri t={got[-1][0]:.1f}s")

    # 5) kaun kab bola
    def tone(f0, dur=1.2):
        tt = np.arange(int(dur * sr)) / sr
        return sum((0.5 / k) * np.sin(2 * np.pi * f0 * k * tt) for k in range(1, 10)) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * tt))
    for truth, name in (([(120, "A"), (120, "A"), (220, "B"), (220, "B")], "2 speaker"),
                        ([(110, "A"), (180, "B"), (260, "C"), (110, "A"), (180, "B")], "3 speaker")):
        mixv = np.concatenate([tone(f) for f, _ in truth])
        segs = diarize(mixv, sr)
        import collections
        mp, ok, tot = {}, 0.0, 0.0
        for sgm in segs:
            mid = (sgm["t0"] + sgm["t1"]) / 2
            idx = min(len(truth) - 1, int(mid / 1.2))
            mp.setdefault(sgm["speaker"], collections.Counter())[truth[idx][1]] += (sgm["t1"] - sgm["t0"])
        for k, v in mp.items():
            ok += v.most_common(1)[0][1]; tot += sum(v.values())
        print(f"diarize {name}: {len(mp)} speaker mile | purity {ok / max(tot, 1e-9) * 100:.0f}%")

    # 6) ADR (syllable-level)
    def syll(f0, dur):
        tt = np.arange(int(dur * sr)) / sr
        return sum((0.5 / k) * np.sin(2 * np.pi * f0 * k * tt) for k in range(1, 8)) * np.hanning(len(tt))
    ref = np.concatenate([syll(f, 0.3) for f in (150, 200, 180, 220, 160, 240)])
    rec = np.concatenate([syll(f, 0.22) for f in (150, 200, 180, 220, 160, 240)])
    def env(x, hop=256, n=512):
        fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop]
        return np.sqrt((fr ** 2).mean(1))
    ef = env(ref)
    fit = adr_dtw(rec, ref, sr)
    m = min(len(env(rec)), len(env(fit)), len(ef))
    print(f"adr_dtw: envelope match {np.corrcoef(env(rec)[:m], ef[:m])[0,1]:.3f} -> {np.corrcoef(env(fit)[:m], ef[:m])[0,1]:.3f}"
          f" | lambai {len(rec)/sr:.2f}s -> {len(fit)/sr:.2f}s (ref {len(ref)/sr:.2f}s)")


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        _test()
    else:
        print(__doc__)
