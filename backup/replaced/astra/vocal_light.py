#!/usr/bin/env python3
"""
ASTRA — Vocal Light: awaaz ki jaanch BINA torch/whisper ke.

Kyun: v0.17 ka deep-learning module sahi hai, par torch (~2 GB) ke bina nahi chalta.
Isliye yahan wahi kaam **halke DSP** se hota hai — jo hamare system ke andar
seedha chal jata hai (Render/GitHub par bhi):

  - kitne **alag speaker** hain (energy + MFCC + k-means)
  - har awaaz ka **vector** (consistency check)
  - do awaaz **kitni milti** hain (0 = same, 1 = bilkul alag)
  - **prosody**: pitch, energy, bolne ki raftaar, chuppi

Sach: ye ASR (text) nahi karta aur pehchan (identity) nahi batata.
Speaker labels anonymous hain (SPEAKER_00...). Sirf naap hai, faisla nahi.

Chalao:
  python3 astra/vocal_light.py report kahani.mp3
  python3 astra/vocal_light.py compare a.mp3 b.mp3
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

SR = 16000


def ff():
    e = shutil.which("ffmpeg")
    if e:
        return e
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def load(path, seconds=None):
    cmd = [ff(), "-loglevel", "error", "-i", path]
    if seconds:
        cmd += ["-t", str(seconds)]
    cmd += ["-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or len(r.stdout) < SR // 2:
        return None
    return np.frombuffer(r.stdout, dtype=np.float32)


def frames(x, win=0.025, hop=0.010):
    w, h = int(SR * win), int(SR * hop)
    n = 1 + max(0, (len(x) - w) // h)
    return np.lib.stride_tricks.as_strided(
        x, shape=(n, w), strides=(x.strides[0] * h, x.strides[0])).copy()


def mfcc(x, n_mels=26, n_ceps=20):
    """Chhota MFCC — awaaz ka 'fingerprint' (bina kisi library ke)."""
    fr = frames(x)
    fr = fr * np.hamming(fr.shape[1])
    spec = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    freqs = np.fft.rfftfreq(fr.shape[1], 1 / SR)

    def hz2mel(f):
        return 2595 * np.log10(1 + f / 700)

    def mel2hz(m):
        return 700 * (10 ** (m / 2595) - 1)

    mel_pts = np.linspace(hz2mel(80), hz2mel(SR / 2), n_mels + 2)
    hz_pts = mel2hz(mel_pts)
    fb = np.zeros((n_mels, len(freqs)))
    for i in range(n_mels):
        lo, ce, hi = hz_pts[i], hz_pts[i + 1], hz_pts[i + 2]
        fb[i] = np.clip(np.minimum((freqs - lo) / max(1e-6, ce - lo),
                                   (hi - freqs) / max(1e-6, hi - ce)), 0, None)
    mel = np.log(spec @ fb.T + 1e-9)
    # DCT-II (manual)
    n = mel.shape[1]
    k = np.arange(n_ceps)[:, None]
    dct = np.cos(np.pi / n * (np.arange(n) + 0.5) * k) * np.sqrt(2.0 / n)
    return mel @ dct.T


def vad_mask(x):
    """Kahan awaaz hai (energy se) — chuppi nikal do."""
    fr = frames(x)
    e = np.sqrt((fr ** 2).mean(axis=1))
    thr = max(1e-4, np.percentile(e, 35) * 1.4)
    return e > thr, e


def pitch_track(x):
    """Simple pitch (autocorrelation) — prosody ke liye."""
    fr = frames(x, 0.040, 0.020)
    out = []
    for f in fr:
        f = f - f.mean()
        if np.sqrt((f ** 2).mean()) < 1e-3:
            out.append(0.0)
            continue
        ac = np.correlate(f, f, "full")[len(f) - 1:]
        lo, hi = int(SR / 400), int(SR / 70)
        hi = min(hi, len(ac) - 1)
        if hi <= lo + 2:
            out.append(0.0)
            continue
        lag = lo + int(np.argmax(ac[lo:hi]))
        out.append(SR / lag if lag else 0.0)
    return np.array(out)


def vector_of(x):
    """Array se voice vector (slice ke liye)."""
    if x is None or len(x) < SR // 2:
        return None
    mask, _ = vad_mask(x)
    c = mfcc(x)
    if mask.sum() < 8:
        return None
    v = c[mask]
    return np.concatenate([v.mean(axis=0), v.std(axis=0)])


def slice_vector(path, start, dur):
    """Audio ka ek hissa -> vector (line ke andar ki awaaz)."""
    cmd = [ff(), "-loglevel", "error", "-ss", f"{max(0.0, start):.3f}",
           "-t", f"{max(0.3, dur):.3f}", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or len(r.stdout) < SR // 3:
        return None
    return vector_of(np.frombuffer(r.stdout, dtype=np.float32))


def voice_vector(path, seconds=60):
    """Ek awaaz ka vector (MFCC mean+std) — consistency ke liye."""
    x = load(path, seconds)
    if x is None:
        return None
    mask, _ = vad_mask(x)
    c = mfcc(x)
    if mask.sum() < 10:
        return None
    v = c[mask]
    vec = np.concatenate([v.mean(axis=0), v.std(axis=0)])
    return vec


def similarity(a, b):
    if a is None or b is None:
        return None
    cos = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    return round(1.0 - cos, 4)      # 0 = same, bada = alag


def speakers(path, k_max=6, seconds=90):
    """Kitne alag speaker hain — MFCC clustering (k-means, numpy)."""
    x = load(path, seconds)
    if x is None:
        return {"error": "audio padha nahi ja saka"}
    mask, energy = vad_mask(x)
    c = mfcc(x)
    if mask.sum() < 20:
        return {"error": "awaaz bahut kam hai"}
    # sirf "awaaz jaisi" frames: energy theek + flatness kam (music/noise hatao)
    fr = frames(x)
    spec = np.abs(np.fft.rfft(fr * np.hamming(fr.shape[1]), axis=1)) + 1e-12
    flat = np.exp(np.log(spec).mean(axis=1)) / spec.mean(axis=1)
    speech = mask & (flat < np.percentile(flat[mask], 70)) & (energy > np.percentile(energy[mask], 25))
    if speech.sum() < 25:
        speech = mask
    V = c[speech]
    V = (V - V.mean(axis=0)) / (V.std(axis=0) + 1e-9)

    best = None
    rng = np.random.default_rng(3)
    for k in range(1, min(k_max, max(2, len(V) // 50)) + 1):
        # k-means (5 baar, best inertia)
        inertia = None
        for _ in range(5):
            idx = rng.choice(len(V), k, replace=False)
            C = V[idx].copy()
            for _ in range(12):
                d = ((V[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
                lab = d.argmin(axis=1)
                for j in range(k):
                    if (lab == j).any():
                        C[j] = V[lab == j].mean(axis=0)
            d = ((V[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
            it = float(d.min(axis=1).sum())
            if inertia is None or it < inertia:
                inertia, best_lab, best_C = it, lab, C
        # "knee" rule: k badhane se fayda kam ho to ruk jao
        # silhouette jaisa score: cluster alag hain ya nahi
        sil = 0.0
        if k > 1:
            d_all = ((V[:, None, :] - best_C[None, :, :]) ** 2).sum(axis=2)
            own = d_all[np.arange(len(V)), best_lab]
            other = d_all.copy()
            other[np.arange(len(V)), best_lab] = np.inf
            near = other.min(axis=1)
            sil = float(np.mean((near - own) / (np.maximum(near, own) + 1e-9)))
        cand = {"k": k, "inertia": inertia, "labels": best_lab.copy(), "C": best_C.copy(), "sil": sil}
        if best is None or sil > best.get("sil", -1) + 0.02:
            best = cand

    k = best["k"]
    lab = best["labels"]
    turns = []
    hop = 0.010
    prev = None
    start = 0.0
    idx = np.where(speech)[0]
    for i, t_i in enumerate(idx):
        l = int(lab[i]) if i < len(lab) else 0
        if prev is None:
            prev, start = l, t_i * hop
        elif l != prev:
            turns.append({"speaker": f"SPEAKER_{prev:02d}", "start": round(start, 2),
                          "end": round(t_i * hop, 2)})
            prev, start = l, t_i * hop
    if prev is not None:
        turns.append({"speaker": f"SPEAKER_{prev:02d}", "start": round(start, 2),
                      "end": round(float(idx[-1]) * hop, 2)})

    # bahut chhote turn hatao (noise)
    turns = [t for t in turns if t["end"] - t["start"] >= 0.25]
    counts = {}
    for t in turns:
        counts[t["speaker"]] = counts.get(t["speaker"], 0) + (t["end"] - t["start"])

    return {
        "speakers_detected": k,
        "turns": turns[:60],
        "talk_time": {kk: round(vv, 1) for kk, vv in sorted(counts.items())},
        "note": "labels anonymous hain (pehchan nahi) — sirf naap",
    }


def prosody(path, seconds=60):
    x = load(path, seconds)
    if x is None:
        return {"error": "audio nahi mila"}
    mask, energy = vad_mask(x)
    p = pitch_track(x)
    pv = p[p > 0]
    total = len(x) / SR
    speech = float(mask.mean()) * total
    return {
        "seconds": round(total, 2),
        "speech_ratio": round(float(mask.mean()), 3),
        "speech_seconds": round(speech, 2),
        "pause_ratio": round(1 - float(mask.mean()), 3),
        "energy_mean": round(float(energy.mean()), 4),
        "energy_var": round(float(energy.std()), 4),
        "pitch_mean_hz": round(float(pv.mean()), 1) if len(pv) else None,
        "pitch_std_hz": round(float(pv.std()), 1) if len(pv) else None,
        "note": "pitch sirf awaaz wale hisson ka andaza hai",
    }


def report(path):
    return {"file": os.path.basename(path), "speakers": speakers(path), "prosody": prosody(path)}


def main():
    if len(sys.argv) < 3:
        print("usage: vocal_light.py report <audio> | compare <a> <b>")
        return 1
    cmd = sys.argv[1]
    if cmd == "report":
        print(json.dumps(report(sys.argv[2]), ensure_ascii=False, indent=2))
        return 0
    if cmd == "compare":
        a, b = voice_vector(sys.argv[2]), voice_vector(sys.argv[3])
        d = similarity(a, b)
        print(json.dumps({"a": sys.argv[2], "b": sys.argv[3], "distance": d,
                          "same_lagti_hai": (d is not None and d < 0.25)}, ensure_ascii=False, indent=2))
        return 0
    print("pata nahi:", cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
