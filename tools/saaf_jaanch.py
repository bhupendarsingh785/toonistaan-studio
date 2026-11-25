#!/usr/bin/env python3
"""saaf_jaanch.py — awaaz SAAF hai ya nahi: ek hi jagah poori jaanch (web se aayi har file ke liye).

Teen kism:  sfx (harkat/jeev: kutta, darwaza)   bed (lagataar mahaul: barish, jhingur)   awaaz (insaan ki reference)

Pakadta hai (har ek ka Hinglish kaaran ke saath):
  phatna (clip) · bahut dheemi · DC jhukaav · shor (sirf sfx/awaaz) · bijli ki bhinbhin 50/60 Hz
  goonj (awaaz) · BEEP / watermark tone (website ka nishaan) · shuru/ant me alag hissa (intro/jingle/outro)
  sfx me koi BOL raha hai (website ka naam, "this sound by...") · beech me awaaz gayab (dropout)
  dabbi awaaz (kam quality / phone jaisi) · kati hui shuruaat/ant · bolne ke shabd likhe text se mel nahi (whisper ho to)
  duplicate (fingerprint se — library me pehle se wahi awaaz)

  python tools/saaf_jaanch.py file.wav --kism sfx
  python tools/saaf_jaanch.py clip.mp3 --kism awaaz --text "jo bola gaya"
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal as ss

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
BAD, WARN = "kharab", "dhyaan"


def load(path):
    """Asli sample-rate par mono (bandwidth naapne ke liye resample nahi)."""
    try:
        y, sr = sf.read(str(path), always_2d=True)
    except Exception:
        import subprocess, tempfile, ffbin
        tmp = Path(tempfile.mkdtemp()) / "d.wav"
        subprocess.run([ffbin.ensure() or "ffmpeg", "-v", "error", "-y", "-i", str(path), str(tmp)], capture_output=True)
        y, sr = sf.read(str(tmp), always_2d=True)
    return y.mean(axis=1).astype(np.float64), int(sr)


def _frames(y, sr, win=0.02):
    n = max(1, int(win * sr))
    m = len(y) // n
    return np.sqrt(np.mean(y[:m * n].reshape(m, n) ** 2, axis=1) + 1e-12) if m else np.array([1e-6]), n


def fingerprint(y, sr):
    """'Angootha nishaan': pehle 10s ka 24-band x 24-pal ka naksha (zor se farq nahi padta).
    Do file ka mel (cos) > 0.95 = wahi awaaz (sirf zor/format badla)."""
    z = y[: sr * 10]
    f, t, S = ss.stft(z, sr, nperseg=2048, noverlap=1024)
    P = np.abs(S) ** 2
    edges = np.geomspace(80, min(sr / 2 - 1, 14000), 25)
    B = np.array([P[(f >= edges[i]) & (f < edges[i + 1])].sum(axis=0) for i in range(24)]) + 1e-12
    L = 10 * np.log10(B)
    cols = np.array_split(np.arange(L.shape[1]), 24) if L.shape[1] >= 24 else [np.arange(L.shape[1])] * 24
    M = np.stack([L[:, c].mean(axis=1) for c in cols], axis=1)
    M = (M - M.mean()) / (M.std() + 1e-9)
    v = M.flatten()
    return (v / (np.linalg.norm(v) + 1e-9)).round(4).tolist()


def same(fp1, fp2, thr=0.95):
    return len(fp1) == len(fp2) and float(np.dot(fp1, fp2)) >= thr


def _pure_tones(y, sr):
    """Website ka beep / watermark: bilkul patli (sine jaisi) aur pados se 30 dB oonchi tone, 0.4s+ tak.
    Jhingur/chidiya ki awaaz itni patli nahi hoti (unki chaudaai kai bin hoti hai) — isliye unhe nahi pakadta."""
    n = 8192 if sr >= 32000 else 4096
    f, t, S = ss.stft(y, sr, nperseg=n, noverlap=n // 2)
    D = 20 * np.log10(np.abs(S) + 1e-9)
    hop = (n // 2) / sr
    hits = {}
    for j in range(D.shape[1]):
        col = D[:, j]
        if col.max() < -70:
            continue
        nb = ss.medfilt(col, 61)
        k = int(np.argmax(col - nb))
        fr = f[k]
        if not (300 <= fr <= min(16000, sr / 2 - 200)) or col[k] - nb[k] < 30:
            continue
        width = np.sum(col[max(0, k - 12): k + 13] > col[k] - 10)
        if width <= 4:
            key = int(round(fr / 10.0))
            hits.setdefault(key, []).append(j)
    out = []
    for key, js in hits.items():
        js = sorted(js); run, best = 1, 1
        for a, b in zip(js, js[1:]):
            run = run + 1 if b - a <= 1 else 1; best = max(best, run)
        if best * hop >= 0.4 or len(js) * hop >= 1.5:
            out.append(key * 10)
    return sorted(set(out))


def _speech_like(y, sr):
    """Insaan ke bolne jaisa hissa (hissa 0–1): sur 80–400 Hz + 3–7 Hz ki shabd-dhadkan."""
    try:
        import parselmouth
        z = y if sr <= 24000 else ss.resample_poly(y, 16000, sr) if sr % 16000 == 0 else ss.resample(y, int(len(y) * 16000 / sr))
        r = 16000 if sr > 24000 else sr
        pt = parselmouth.Sound(z, r).to_pitch(pitch_floor=80, pitch_ceiling=400)
        fr = pt.selected_array["frequency"]
        voiced = float(np.mean(fr > 0)) if len(fr) else 0.0
        hnr = parselmouth.Sound(z, r).to_harmonicity()
        h = hnr.values[hnr.values > -100]
        hn = float(np.median(h)) if len(h) else -10
    except Exception:
        return 0.0, 0.0
    sos = ss.butter(4, [300 / (sr / 2), min(0.99, 3400 / (sr / 2))], btype="band", output="sos")
    env, n = _frames(ss.sosfilt(sos, y), sr, 0.01)
    env = env - env.mean()
    if len(env) < 64:
        return voiced, 0.0
    fq, pw = ss.welch(env, 100, nperseg=min(256, len(env)))
    syll = float(pw[(fq >= 3) & (fq <= 7)].sum() / (pw[(fq >= 0.5) & (fq <= 20)].sum() + 1e-12))
    return voiced * (1 if hn > 3 else 0.5), syll


def _whisper_text(y, sr):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    global _WM
    try:
        _WM
    except NameError:
        _WM = WhisperModel("small", device="cpu", compute_type="int8")
    z = ss.resample_poly(y, 16000, sr) if sr != 16000 else y
    segs, _ = _WM.transcribe(z.astype(np.float32), language="hi", vad_filter=True)
    return " ".join(s.text for s in segs).strip()


def _sim(a, b):
    import difflib, re
    k = lambda s: re.sub(r"[\s\.,!?।'\"-]+", "", s.lower())
    return difflib.SequenceMatcher(None, k(a), k(b)).ratio()


def jaanch(path, kism="sfx", text=None, allow_voice=False, library_fps=()):
    """Lautata hai: {score 0-100, theek, kami: [(kharab|dhyaan, kaaran)], naap, fingerprint}."""
    try:
        y, sr = load(path)
    except Exception as e:
        return {"score": 0, "theek": False, "kami": [(BAD, f"file khul nahi rahi ({type(e).__name__})")], "naap": {}, "fingerprint": []}
    kami, naap = [], {}
    dur = len(y) / sr; naap["lambai_s"] = round(dur, 2); naap["sr"] = sr
    lim = {"sfx": (0.3, 30), "bed": (8, 900), "awaaz": (4, 20)}[kism]
    if dur < lim[0]: kami.append((BAD, f"bahut chhoti ({dur:.1f}s) — kam se kam {lim[0]}s"))
    if dur > lim[1]: kami.append((WARN, f"bahut lambi ({dur:.0f}s) — kaam ka hissa kaat lenge"))
    if dur < 0.2:
        return {"score": 0, "theek": False, "kami": kami, "naap": naap, "fingerprint": []}
    peak = float(np.max(np.abs(y))); clip = float(np.mean(np.abs(y) > 0.985))
    naap["peak"] = round(peak, 3); naap["phata_%"] = round(clip * 100, 3)
    if clip > 0.001: kami.append((BAD, "awaaz phati hui hai (clipping) — saaf nahi"))
    if peak < 0.03: kami.append((BAD, "bahut dheemi / lagbhag khaali"))
    dc = float(np.mean(y)); naap["dc"] = round(dc, 4)
    if abs(dc) > 0.02: kami.append((WARN, "awaaz ek taraf jhuki (DC offset) — record karne wala yantra kharab"))

    e, n = _frames(y, sr)
    e = np.maximum(e, 3e-5)
    p95 = np.percentile(e, 95)
    snr = float(20 * np.log10(np.percentile(e, 90) / np.percentile(e, 8))); naap["snr_db"] = round(snr, 1)
    if kism in ("sfx", "awaaz") and snr < (25 if kism == "awaaz" else 15):
        kami.append((BAD if kism == "awaaz" else WARN, f"peeche shor zyada (SNR {snr:.0f} dB)"))

    quiet = np.repeat(e <= np.percentile(e, 15), n)[:len(y)]
    q = y[:len(quiet)][quiet]
    if kism != "bed" and len(q) > sr * 0.2 and np.sqrt(np.mean(q ** 2)) > 3e-4:
        f, p = ss.welch(q, sr, nperseg=8192)
        band = lambda a, b: p[(f >= a) & (f <= b)].sum()
        hum = float(10 * np.log10((band(47, 53) + band(97, 103) + band(57, 63) + band(117, 123) + 1e-18)
                                  / (band(20, 4000) + 1e-18)))
        naap["bhinbhin_db"] = round(hum, 1)
        if hum > -12: kami.append((BAD, "bijli/pankhe ki bhinbhin (50/60 Hz)"))

    # beech me awaaz gayab (dropout): bolte/bajte hue achanak 40 dB neeche 20–300 ms
    act = e > 0.2 * p95
    drop = 0
    for i in range(1, len(e) - 16):
        if act[i - 1] and e[i] < p95 * 0.01:
            j = i
            while j < len(e) and e[j] < p95 * 0.01: j += 1
            if 1 <= j - i <= 15 and j < len(e) and act[min(j, len(e) - 1)]: drop += 1
    naap["dropout"] = drop
    if drop >= 2 and kism != "sfx": kami.append((BAD, f"beech me {drop} jagah awaaz gayab (toota hua / galat edit)"))

    # kati hui shuru/ant
    edge = int(0.01 * sr)
    if kism != "bed" and len(y) > 4 * edge:
        lvl = lambda s: 20 * np.log10(np.sqrt(np.mean(s ** 2)) + 1e-9) - 20 * np.log10(p95)
        if lvl(y[:edge]) > -6 or lvl(y[-edge:]) > -6:
            kami.append((WARN, "shuru/ant kata hua (beech awaaz me kaati gayi) — fade laga denge"))

    # dabbi awaaz: 7 kHz ke upar kuch nahi (sasti mp3 / phone)
    if sr >= 32000:
        f, p = ss.welch(y, sr, nperseg=4096)
        hi = 10 * np.log10(p[f > 7000].sum() / (p.sum() + 1e-18) + 1e-18); naap["7k_upar_db"] = round(float(hi), 1)
        if hi < -50: kami.append((WARN if kism != "awaaz" else BAD, "dabbi awaaz (oonchi frequency kati — kam quality ya phone)"))

    tones = _pure_tones(y, sr); naap["beep_hz"] = tones
    if tones: kami.append((BAD, f"BEEP/watermark tone mili ({', '.join(map(str, tones[:3]))} Hz) — website ka nishaan ho sakta hai"))

    # shuru/ant ka hissa baaki se bilkul alag = intro/jingle/outro
    if dur > 10:
        def spec(seg):
            f, p = ss.welch(seg, sr, nperseg=2048)
            edges = np.geomspace(80, min(sr / 2 - 1, 12000), 25)
            return np.log10(np.array([p[(f >= edges[i]) & (f < edges[i + 1])].sum() for i in range(24)]) + 1e-15)
        mid = spec(y[int(sr * 3): -int(sr * 3)])
        for name, seg in (("shuru", y[:int(sr * 3)]), ("ant", y[-int(sr * 3):])):
            d = spec(seg) - mid
            if np.sqrt(np.mean((d - d.mean()) ** 2)) > 0.9 and np.abs(seg).max() > 0.1 * peak:
                kami.append((WARN, f"{name} ke 3 second baaki se bilkul alag (intro/jingle/outro?) — kaat denge"))

    vo, syl = _speech_like(y, sr); naap["bolna_jaisa"] = round(vo, 2); naap["shabd_dhadkan"] = round(syl, 2)
    if kism != "awaaz" and not allow_voice and vo > 0.35 and syl > 0.25:
        said = _whisper_text(y, sr)
        if said is None or len(said) > 3:
            kami.append((BAD, "is awaaz me koi BOL raha hai" + (f": '{said[:40]}'" if said else " (website ka naam/announcement?)")))

    if kism == "awaaz":
        try:
            import awaaz_bank as AB
            b = AB.jaanch(path)
            naap.update({k: v for k, v in b["naap"].items() if k in ("goonj_s", "sur_hz", "bolna_%")})
            if b["naap"].get("goonj_s", 0) > 0.35: kami.append((BAD, "goonj (echo) — clone me bhi goonj aayegi"))
            if not b["naap"].get("sur_hz"): kami.append((BAD, "insaan ki awaaz nahi mili"))
        except Exception:
            pass
        if text:
            said = _whisper_text(y, sr)
            if said is not None:
                s = _sim(said, text); naap["text_mel"] = round(s, 2)
                if s < 0.7: kami.append((BAD, f"bola hua likhe text se mel nahi khaata ({int(s*100)}%) — extra shabd/ad?"))

    fp = fingerprint(y, sr)
    if any(same(fp, o) for o in library_fps):
        kami.append((BAD, "ye awaaz library me pehle se hai (duplicate)"))
    score = max(0, 100 - 35 * sum(1 for k in kami if k[0] == BAD) - 8 * sum(1 for k in kami if k[0] == WARN))
    return {"score": score, "theek": not any(k[0] == BAD for k in kami), "kami": kami, "naap": naap, "fingerprint": fp}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("--kism", default="sfx", choices=["sfx", "bed", "awaaz"])
    ap.add_argument("--text", default=None); ap.add_argument("--insaan", action="store_true",
                                                             help="sfx me insaan ki awaaz chalegi (hansi, rona, bheed)")
    a = ap.parse_args()
    r = jaanch(a.file, a.kism, a.text, a.insaan)
    print(f"score {r['score']}  {'SAAF ✓' if r['theek'] else 'KHARAB ✗'}")
    for lvl, m in r["kami"]: print(f"  [{lvl}] {m}")
    print(json.dumps(r["naap"], ensure_ascii=False))
    return 0 if r["theek"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
