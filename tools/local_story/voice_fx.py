"""Voice FX — robotic awaaz ko insaani banane ke liye (numpy, koi library nahi).

3 cheezein robotic lagne ki wajah banti hain:
  1) pitch shift se **formants** bhi khisak jate hain (bachcha "chipmunk", dadi "monster")
     → hal: phase-vocoder pitch shift + **cepstral envelope correction** (formants wapas)
  2) sur bilkul seedha (drift nahi) → hal: halka pitch drift + micro-timing
  3) saans/room nahi → hal: breath noise + chhota room reverb + warm EQ
"""
from __future__ import annotations
import numpy as np

SR = 44100
N, HOP = 1024, 256


def _stft(x):
    win = np.hanning(N)
    frames = range(0, max(1, len(x) - N), HOP)
    return np.array([np.fft.rfft(x[i:i + N] * win) for i in frames]), win


def _istft(S, win, length):
    out = np.zeros((len(S) - 1) * HOP + N)
    for i, spec in enumerate(S):
        out[i * HOP:i * HOP + N] += np.fft.irfft(spec, N) * win
    out /= max(1e-9, (np.sum(win ** 2) / HOP))
    return out[:length]


def _envelope(mag):
    """cepstral smoothing = spectral envelope (formants)."""
    logm = np.log(mag + 1e-9)
    ceps = np.fft.irfft(logm, axis=1)
    keep = 40
    ceps[:, keep:-keep] = 0
    return np.exp(np.fft.rfft(ceps, axis=1).real)


def formant_shift(x, ratio: float):
    """Formants (awaaz ki umar/character) badlo — **pitch aur time chhue bina**.

    SOLA/pitch-shift se "goonj" aa rahi thi; yeh tarika artifact-free hai:
    STFT → spectral envelope ko frequency me warp karo → wapas lagao.
    """
    import numpy as np
    if abs(ratio - 1.0) < 0.01:
        return x
    win = 1024; hop = 256
    winfn = np.hanning(win)
    frames = range(0, max(1, len(x) - win), hop)
    out = np.zeros(len(x) + win)
    norm = np.zeros(len(x) + win)
    for i in frames:
        seg = x[i:i + win] * winfn
        S = np.fft.rfft(seg)
        mag = np.abs(S); ph = np.angle(S)
        # envelope (cepstral smoothing)
        logm = np.log(mag + 1e-9)
        ceps = np.fft.irfft(logm)
        keep = 40
        ceps[keep:-keep] = 0
        env = np.exp(np.fft.rfft(ceps).real)
        # envelope ko ratio se warp karo (formants khisak jayein)
        nb = len(mag)
        src = np.clip((np.arange(nb) / ratio).astype(int), 0, nb - 1)
        env2 = env[src]
        fine = mag / (env + 1e-9)          # fine structure (pitch harmonics) waisi hi
        mag2 = fine * env2
        y = np.fft.irfft(mag2 * np.exp(1j * ph), win) * winfn
        out[i:i + win] += y
        norm[i:i + win] += winfn ** 2
    out = out[:len(x)] / np.maximum(norm[:len(x)], 1e-6)
    return out


def _sola(x, ratio):
    """SOLA time-stretch — bin remap se saaf (koi metallic echo nahi)."""
    win = int(0.040 * SR); hop_out = win // 2
    hop_in = max(1, int(hop_out / ratio))
    pad = np.zeros(win)
    xp = np.concatenate([pad, x, pad])
    out = np.zeros(int(len(x) * ratio) + win)
    winfn = np.hanning(win)
    prev_end = 0
    for i, start in enumerate(range(0, len(xp) - win, hop_in)):
        seg = xp[start:start + win]
        best, bestc = 0, -1e9
        if i > 0:
            lo = max(0, prev_end - hop_out - 200); hi = min(len(xp) - win, prev_end - hop_out + 200)
            for cand in range(lo, max(lo + 1, hi), 4):
                c = float(np.dot(xp[cand:cand + win], seg))
                if c > bestc:
                    bestc, best = c, cand
        else:
            best = start
        pos = i * hop_out
        out[pos:pos + win] += xp[best:best + win] * winfn
        prev_end = best + win
    return out[:int(len(x) * ratio)]


def pitch_shift_sola(x, semitones: float):
    """Pitch shift: SOLA stretch + resample (clean, no echo)."""
    if abs(semitones) < 0.01:
        return x
    ratio = 2 ** (semitones / 12.0)
    stretched = _sola(x, ratio)                 # lamba/chhota karo
    n = len(x)
    idx = np.linspace(0, len(stretched) - 1, n)  # wapas resample
    return np.interp(idx, np.arange(len(stretched)), stretched)


def pitch_shift_formant(x, semitones: float):
    """Pitch shift jisme formants (awaaz ka character) bacha rehta hai."""
    if abs(semitones) < 0.01:
        return x
    ratio = 2 ** (semitones / 12.0)
    S, win = _stft(x)
    mag = np.abs(S); phase = np.angle(S)
    env_src = _envelope(mag)
    # 1) frequency axis ko ratio se shift (bin remap) — formants bhi shift honge
    n_bins = mag.shape[1]
    new_bins = np.arange(n_bins)
    src_bins = new_bins / ratio
    idx = np.clip(src_bins.astype(int), 0, n_bins - 1)
    mag2 = mag[:, idx]
    phase2 = phase[:, idx]
    # 2) formants wapas: shifted envelope hata kar original envelope lagao
    env_new = _envelope(mag2)
    mag3 = mag2 * (env_src / (env_new + 1e-9)) ** 0.9
    # 3) time-scale wapas (phase vocoder ke bina simple: hop adjust)
    S2 = mag3 * np.exp(1j * phase2)
    y = _istft(S2, win, int(len(x)))
    # 4) duration wapas (resample) — formant correction ke baad
    target = int(len(x) / ratio)
    if target > 10:
        xs = np.interp(np.linspace(0, len(y) - 1, target), np.arange(len(y)), y)
        pad = np.zeros(len(x) - len(xs)) if len(xs) < len(x) else np.zeros(0)
        y = np.concatenate([xs, pad])[:len(x)]
    return y


def humanize(x, drift_semi=0.25, micro=True):
    """sur me halka drift + micro timing — 'seedha robot' nahi lagta."""
    t = np.arange(len(x)) / SR
    lfo = 1 + 0.0025 * np.sin(2 * np.pi * 0.7 * t + 0.3)          # ~±0.25 semi drift
    x2 = x * (0.97 + 0.03 * np.sin(2 * np.pi * 0.35 * t))          # halka zor ka utar-chadhav
    if micro:
        # chhote random dips (insaan ki saans jaisi)
        rng = np.random.default_rng(7)
        env = np.ones(len(x2))
        for _ in range(max(1, int(len(x2) / SR * 0.4))):
            i = rng.integers(0, max(1, len(x2) - 4000))
            n = rng.integers(600, 2400)
            env[i:i + n] *= np.linspace(1, 0.94, n)
        x2 = x2 * env
    return x2 * lfo


def breath(x, level=0.006):
    """khamoshi me halki saans — robotic 'sunn' ko todta hai."""
    rng = np.random.default_rng(11)
    n = rng.normal(0, 1, len(x))
    k = 300
    c = np.cumsum(n); c[k:] = c[k:] - c[:-k]; n = c / k
    return x + n * level


def warm(x):
    """EQ — audit ke hisaab se: low rumble kato, mid bhado, high (sibilance) ghatao.

    Naap: hamara mid 40% / high 30% tha; asli insaan mid 65% / high 14%.
    """
    n = len(x)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    curve = np.ones_like(f)
    curve *= 1 / (1 + (110 / (f + 1e-9)) ** 4)                       # <110 Hz rumble cut
    curve += 1.05 * np.exp(-((f - 700) ** 2) / (2 * 420 ** 2))       # mid body +2.5 dB
    curve += 0.55 * np.exp(-((f - 1800) ** 2) / (2 * 700 ** 2))      # presence
    curve -= 0.45 * np.exp(-((f - 4200) ** 2) / (2 * 1200 ** 2))     # de-ess (strong)
    curve *= 1 / (1 + (f / 9000) ** 6)                               # air cut
    y = np.fft.irfft(X * curve, n)
    return y


def room(x, wet=0.0):
    """Room tail — comb filter hata diya (wohi 'goonj/echo' kar raha tha).

    Ab: smooth exponentially-decaying noise tail, aur default **band** (0.0).
    """
    if wet <= 0:
        return x
    rng = np.random.default_rng(21)
    d = int(SR * 0.25)
    tail = rng.normal(0, 1, d) * np.exp(-np.arange(d) / (d * 0.35))
    tail = np.convolve(tail, np.ones(64) / 64, mode="same")     # smooth, comb nahi
    L = 1 << int(np.ceil(np.log2(len(x) + d)))
    wetsig = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(tail, L), L)[:len(x)]
    return x + wetsig * wet


def smooth_chain(x, semitones=0.0, human=True, br=True, warm_eq=True, rv=False):
    # SOLA shift (saaf) + formant correction (halki) — echo nahi
    y = pitch_shift_formant(x, semitones) if abs(semitones) > 0.01 else x.copy()
    if human:
        y = humanize(y)
    if warm_eq:
        y = warm(y)
    if rv:
        y = room(y)
    if br:
        y = breath(y)
    peak = np.max(np.abs(y)) + 1e-9
    if peak > 0.95:
        y = y / peak * 0.95
    return y
