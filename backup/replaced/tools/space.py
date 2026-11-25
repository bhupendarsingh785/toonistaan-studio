#!/usr/bin/env python3
"""space.py v2 — jagah ko MAHSUUS karana: doori, disha, deewarein, goonj.

Aankh band karke sunne wale ko pata chale: awaaz kitni door se, kis taraf se,
aur kis tarah ki jagah me hai (khula / kamra / jungle / hall / gufa).

Asli acoustics ke niyam jo yahan lagte hain:
  1. **Doori**: level 1/d, hawa upar ki frequency kha jaati hai (band-wise),
     aur awaaz d/343 s der se pahunchti hai.
  2. **Disha**: equal-power pan + **ITD** (kaan ke beech 0–0.6 ms) + **ILD**;
     door par localisation dhundhli hoti hai (IACC girta hai).
  3. **Deewarein (early reflections)**: 6 shuruati reflection, jagah ke hisaab se
     (kamra/hall me saaf, jungle me bikhri, khule me sirf zameen ki).
  4. **Goonj (late reverb)**: RT60 frequency ke hisaab se — bass der tak rehta hai
     (asli kamre aisa hi karte hain), isliye awaaz "garm" aur gehra lagta hai.

  python tools/space.py --test        # naap ke saath saabit
  python tools/space.py --demo out.wav
"""
from __future__ import annotations
import argparse
import numpy as np

SR = 44100
C_AIR = 343.0

# rt = (bass, mid, high) seconds | er = shuruati reflection (ms, gain, pan) | diff = bikhraav
SPACES = {
    "khula":  {"rt": (0.55, 0.45, 0.35), "diff": 0.25,
               "er": [(11, 0.10, -0.6), (19, 0.06, 0.5)]},                     # zameen ki halki goonj
    "kamra":  {"rt": (0.70, 0.55, 0.42), "diff": 0.50,
               "er": [(7, 0.22, -0.8), (11, 0.18, 0.7), (17, 0.14, -0.4),
                      (23, 0.10, 0.5), (31, 0.07, -0.2)]},
    "jungle": {"rt": (1.30, 1.05, 0.75), "diff": 0.80,
               "er": [(14, 0.12, -0.7), (22, 0.10, 0.6), (29, 0.08, -0.3),
                      (38, 0.06, 0.4), (47, 0.05, -0.5), (61, 0.04, 0.2)]},   # ped bikhre hue
    "hall":   {"rt": (2.90, 2.40, 1.70), "diff": 0.70,
               "er": [(16, 0.26, -0.9), (23, 0.22, 0.8), (34, 0.18, -0.5),
                      (45, 0.14, 0.6), (58, 0.10, -0.3), (72, 0.07, 0.4)]},   # saaf deewarein
    "gufa":   {"rt": (3.40, 2.80, 1.90), "diff": 0.90,
               "er": [(9, 0.20, -0.7), (13, 0.18, 0.7), (21, 0.16, -0.5),
                      (27, 0.14, 0.5), (39, 0.10, -0.6), (52, 0.08, 0.6)]},
}
BANDS = [(60, 300), (300, 2500), (2500, 12000)]


# ---------- filters ----------
def _band(x, lo, hi, sr=SR):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    m = ((f >= lo) & (f < hi)).astype(float)
    # kinare dhale (tikha kataav shor karta hai)
    k = max(1, int(len(f) * 0.01))
    m = np.convolve(m, np.hanning(k) / np.hanning(k).sum(), "same")
    return np.fft.irfft(X * m, n=len(x))


def air_cutoff(dist: float) -> float:
    """Hawa ka absorption: 1 m ~18 kHz, 10 m ~7 kHz, 30 m ~3 kHz."""
    return 18000.0 / (1.0 + max(0.0, dist - 1.0) / 3.2)


def _air_absorb(x, dist: float, sr=SR):
    """Band-wise hawa absorption — door ki awaaz dhundhli (par bass bacha rehta hai)."""
    if dist <= 1.2:
        return x
    out = np.zeros_like(x)
    for lo, hi in BANDS:
        g = 1.0 if hi <= 400 else 1.0 / (1.0 + max(0.0, dist - 1.0) / (7.0 if hi > 2000 else 22.0))
        out += _band(x, lo, hi, sr) * g
    return out


# ---------- goonj ----------
def _late_reverb(x, space: str, sr=SR, seed=7):
    """Late reverb: har band ka apna decay (bass der tak) — asli kamre jaisa."""
    p = SPACES.get(space, SPACES["kamra"])
    n = int(max(p["rt"]) * sr)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / sr
    chans = []
    for ch in range(2):
        y = np.zeros(n + len(x))
        for (lo, hi), rt in zip(BANDS, p["rt"]):
            noise = rng.normal(0, 1, n)
            noise = _band(noise, lo, hi, sr)
            env = np.exp(-6.9 * t / rt)
            y[:n] += noise * env * p["diff"]
        y = np.convolve(x, y)[: len(x)]
        chans.append(y)
    # stereo decorrelation (goonj charon taraf se aati hai)
    return chans[0], chans[1]


def _early(x, space: str, sr=SR, pan=0.0):
    """Deewaron/zameen se shuruati reflection — jagah ka "aakar" isi se banta hai."""
    p = SPACES.get(space, SPACES["kamra"])
    out = np.zeros((2, len(x) + int(0.12 * sr)))
    for ms, g, ep in p["er"]:
        d = int(ms / 1000 * sr)
        ang = ((ep + pan) / 2 + 1) * np.pi / 4
        gl, gr = np.cos(ang), np.sin(ang)
        out[0, d:d + len(x)] += x * g * gl
        out[1, d:d + len(x)] += x * g * gr
    return out[:, : len(x)]


def place_acoustic(x, dist: float = 1.0, pan: float = 0.0, space: str = "khula", sr: int = SR):
    """Mono -> stereo: doori + disha + deewarein + goonj, sab asli niyamon se."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=0)
    d = max(0.4, float(dist))
    p = float(np.clip(pan, -1.0, 1.0))

    # 1) hawa (door = dhundhli) + doori ka level
    #    1/d seedha nahi — asli duniya me paas ka girna tez, door ka dheema hota hai,
    #    aur bahut door ki awaaz poori gayab nahi hoti (thodi si rehti hai)
    gain = max(1.0 / (1.0 + (d - 1.0) / 1.5), 0.022)   # -33 dB se zyada chup nahi (pehchaan bani rahe)
    y = _air_absorb(x, d, sr) * gain

    # 2) pahunchne ki deri
    delay = int(d / C_AIR * sr)
    if delay:
        y = np.concatenate([np.zeros(delay), y])

    # 3) deewarein (early reflections) — door par ye bhi halki
    er = _early(y, space, sr, p) * (1.0 / (1.0 + 0.06 * d))

    # 4) goonj (late) — door par hissa zyada, par hawi na ho
    wet_gain = float(np.clip(0.12 + 0.20 * np.log1p(d), 0.10, 0.80)) / (d ** 0.35)
    wl, wr = _late_reverb(y, space, sr)
    wl = np.pad(wl, (0, max(0, len(y) - len(wl))))[: len(y)] * wet_gain
    wr = np.pad(wr, (0, max(0, len(y) - len(wr))))[: len(y)] * wet_gain

    # 5) disha: equal-power + ITD (kaan ke beech deri) + ILD
    ang = (p + 1) * np.pi / 4
    gl, gr = np.cos(ang), np.sin(ang)
    itd = int(abs(p) * 0.6 / 1000 * sr)          # max 0.6 ms
    dl = y.copy(); dr = y.copy()
    if itd:
        pad = np.zeros(itd)
        if p > 0:                                 # daayein se -> daayen kaan par pehle
            dr = np.concatenate([dr, pad])[: len(y)]
            dl = np.concatenate([pad, dl])[: len(y)]
        else:
            dl = np.concatenate([dl, pad])[: len(y)]
            dr = np.concatenate([pad, dr])[: len(y)]

    # door par chaudai badhti hai (localisation dhundhli)
    width = float(np.clip(0.02 + 0.035 * d, 0.02, 0.18))
    l = dl * gl + wl * gl + er[0]
    r = dr * gr + wr * gr + er[1]
    l += width * wr * 0.35
    r += width * wl * 0.35

    st = np.vstack([l, r])
    peak = float(np.max(np.abs(st))) or 1.0
    if peak > 0.98:
        st = st / peak * 0.98
    return st


def place_acoustic_3d(x, dist=1.0, pan=0.0, elev=0.0, space="khula", sr=SR):
    """Upar/neeche (elev) bhi: upar ki awaaz thodi tez-upar sunai deti hai."""
    st = place_acoustic(x, dist=dist, pan=pan, space=space, sr=sr)
    if abs(elev) < 0.05:
        return st
    # upar (elev>0): upar ki frequency thodi badhti hai; neeche: thodi kam
    g = 1.0 + 0.25 * float(np.clip(elev, -1, 1))
    X = np.fft.rfft(st, axis=1)
    f = np.fft.rfftfreq(st.shape[1], 1 / sr)
    tilt = 10 ** ((np.log2(np.maximum(f, 1) / 1000.0) * (g - 1.0) * 6.0) / 20)
    st = np.fft.irfft(X * tilt[None, :], n=st.shape[1])
    return st


def place_moving(x, dist0=1.0, dist1=20.0, pan0=-0.9, pan1=0.9,
                 space="khula", sr=SR, doppler=True, pass_by=False, speed=12.0):
    """Chalti awaaz: paas aati-door jaati (Doppler + level + disha badalti hai).

    x: awaaz (mono). Awaaz shuru se ant tak chalti hai — dist/pan shuru se ant tak badalte hain.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=0)
    n = len(x)
    t = np.linspace(0, 1, n)
    if pass_by:
        # paas se guzarti awaaz: d = sqrt((v*t')^2 + dmin^2) — pehle paas, phir door
        dur = n / sr
        tt = (t - 0.5) * dur
        dmin = max(0.8, min(dist0, dist1))
        d = np.sqrt((speed * tt) ** 2 + dmin ** 2)
        d = np.clip(d, dmin, max(dist0, dist1, speed * dur))
        p = np.clip(tt / (dur / 2), -1, 1)
    else:
        d = dist0 + (dist1 - dist0) * t
        p = pan0 + (pan1 - pan0) * t
    # Doppler: paas aate waqt pitch upar, door jaate waqt neeche (velocity se)
    if doppler:
        v = np.gradient(d) * sr                      # m/s (d badal rahi hai per sample)
        c = C_AIR
        rate = np.clip(c / (c + v), 0.90, 1.12)      # paas aati awaaz upar, door jaati neeche
        # input par kaunsi jagah padhni hai: paas aate waqt dheere padho (pitch upar)
        pos = np.cumsum(rate)      # paas aati awaaz tez padhi jaati hai = pitch upar
        pos = pos[pos < n - 1]
        if len(pos) > 32:
            x = np.interp(pos, np.arange(n), x)
            x = np.pad(x, (0, max(0, n - len(x))))[:n]
    # chhote tukdon me place karo (har tukde ki apni doori/disha)
    blk = max(256, int(0.10 * sr))
    out = np.zeros((2, n))
    for i in range(0, n, blk):
        j = min(n, i + blk)
        seg = x[i:j]
        st = place_acoustic(seg, dist=float(d[i]), pan=float(p[i]), space=space, sr=sr)
        m = min(st.shape[1], n - i)
        out[:, i:i + m] += st[:, :m]
    peak = float(np.max(np.abs(out))) or 1.0
    if peak > 0.98:
        out = out / peak * 0.98
    return out


# ---------- naap ----------
def measure(st, sr: int = SR) -> dict:
    st = np.asarray(st)
    if st.ndim == 1:
        st = np.vstack([st, st])
    m = st.mean(axis=0)
    rms = float(np.sqrt((m ** 2).mean()) + 1e-12)
    X = np.abs(np.fft.rfft(m)) + 1e-12
    f = np.fft.rfftfreq(len(m), 1 / sr)
    hf = float(X[(f > 4000) & (f < 12000)].sum())
    lf = float(X[(f > 100) & (f < 1000)].sum())
    # RT60 per band
    rts = []
    for lo, hi in BANDS:
        b = _band(m, lo, hi, sr)
        e = np.cumsum((b[::-1] ** 2))[::-1]
        e_db = 10 * np.log10(e / (e[0] + 1e-12) + 1e-12)
        try:
            i5 = int(np.argmax(e_db <= -5)); i25 = int(np.argmax(e_db <= -25))
            rts.append(round(float((i25 - i5) / sr * 2), 2))
        except Exception:
            rts.append(0.0)
    # ITD (cross-correlation) aur IACC (spaciousness)
    # ITD sirf seedhi (direct) awaaz par naapo — goonj milane par 0 aa jaata hai
    w = int(0.04 * sr)
    a = st[0][:w] - st[0][:w].mean(); b = st[1][:w] - st[1][:w].mean()
    cc = np.correlate(a, b, "full")
    lag = int(np.argmax(np.abs(cc))) - (len(b) - 1)
    itd_ms = round(lag / sr * 1000, 2)
    iacc = round(float(np.max(np.abs(cc)) / (np.sqrt((a ** 2).sum() * (b ** 2).sum()) + 1e-12)), 2)
    pan = round(float((np.sqrt((st[1] ** 2).mean()) - np.sqrt((st[0] ** 2).mean())) /
                      (np.sqrt((st[1] ** 2).mean()) + np.sqrt((st[0] ** 2).mean()) + 1e-12)), 2)
    return {"level_db": round(20 * np.log10(rms), 1), "hf_lf": round(hf / lf, 4),
            "rt_bass_mid_high": rts, "itd_ms": itd_ms, "iacc": iacc, "pan": pan}


def _burst(sec=1.2, sr=SR, voice_like=False):
    """voice_like=True -> insaan ki awaaz jaisa (low-mid me energy), warna broadband."""
    t = np.arange(int(sec * sr)) / sr
    if voice_like:
        f0 = 140.0
        y = sum((0.6 / k) * np.sin(2 * np.pi * f0 * k * t) for k in range(1, 22))
        env = np.exp(-t / 0.25)
        return y * env
    rng = np.random.default_rng(3)
    return rng.normal(0, 1, len(t)) * np.exp(-t / 0.05)


def _test():
    b = _burst()
    v = _burst(voice_like=True)
    print("1) DOORI (khula maidan) — insaan jaisi awaaz:")
    for d in (1, 5, 15, 40):
        m = measure(place_acoustic(v, dist=d, space="khula"))
        print(f"   {d:>2} m | level {m['level_db']:>6} dB | HF/LF {m['hf_lf']:.4f}")
    print("   (broadband shor par wahi doori zyada girti hai — hawa upar ki awaaz kha jaati hai):")
    for d in (1, 15, 40):
        m = measure(place_acoustic(b, dist=d, space="khula"))
        print(f"   {d:>2} m | level {m['level_db']:>6} dB | HF/LF {m['hf_lf']:.4f}")
    print("2) JAGAH (8 m) — goonj ka rang aur lambai:")
    for s in SPACES:
        m = measure(place_acoustic(b, dist=8, space=s))
        print(f"   {s:<7} | RT {m['rt_bass_mid_high']} | IACC {m['iacc']} (kam = zyada chaudi) | HF/LF {m['hf_lf']}")
    print("3) DISHA (5 m) — pan, ITD aur spaciousness:")
    for p in (-1.0, -0.5, 0.0, 0.5, 1.0):
        m = measure(place_acoustic(b, dist=5, pan=p, space="jungle"))
        print(f"   pan {p:+.1f} -> naapa {m['pan']:+.2f} | ITD {m['itd_ms']:+.2f} ms | IACC {m['iacc']}")


def _demo(path: str):
    sr = SR
    rng = np.random.default_rng(11)
    t = np.arange(int(0.9 * sr)) / sr
    src = (np.sin(2 * np.pi * 220 * t) * np.exp(-t / 0.12) * 0.5 +
           rng.normal(0, 0.35, len(t)) * np.exp(-t / 0.06))
    seq = [(1, 0.0, "khula"), (6, -0.8, "khula"), (20, 0.8, "khula"),
           (20, 0.0, "jungle"), (20, 0.0, "hall"), (20, -0.5, "gufa")]
    parts = []
    for d, p, sp in seq:
        st = place_acoustic(src, dist=d, pan=p, space=sp)
        parts.append(np.concatenate([st, np.zeros((2, int(0.35 * sr)))], axis=1))
    out = np.concatenate(parts, axis=1)
    out = out / np.max(np.abs(out)) * 0.9
    import soundfile as sf
    sf.write(path, out.T, sr)
    print("demo likha:", path, round(out.shape[1] / sr, 1), "s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--demo", default="")
    a = ap.parse_args()
    if a.test:
        _test()
    if a.demo:
        _demo(a.demo)


if __name__ == "__main__":
    main()
