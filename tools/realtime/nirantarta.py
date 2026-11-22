"""
Nirantarta — har kirdaar ki awaaz poori kahani (aur agli kahaniyon) me ek jaisi rahe.

Har line par naap: sur (F0 median), raftaar (laghu-guru matra/second), zor (dB), chamak (centroid), rang (MFCC timbre).
Kirdaar ka "profile" (knowledge/voice-profiles.json) — pehli kahani se bana, har line se dheere update.
Line profile se bahut hati to "bhatakna" (drift):
  sur   > 8%   (bhaav ke hisaab se chhoot: gussa/dar +8% tak theek, dukh −6% tak)
  raftaar > 15% ya 2.5 x apna utaar-chadhav
  zor   > 2.5 dB
  chamak > 12%
  rang  (timbre) doori > 0.35
Sudhaar: zor/chamak line par hi; sur/raftaar ke liye TTS ko naya param (pitch_st, rate) dekar dobara.
"""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np

EMO_F0 = {"gussa": 0.08, "dar": 0.08, "khushi": 0.05, "dukh": -0.06, "cheekh": 0.12}

def features(y, sr, n_units):
    """n_units = akshar.matra_units(text) (laghu-guru ginti) — raftaar = matra/second."""
    import librosa
    yt, _ = librosa.effects.trim(y, top_db=35)
    if len(yt) < 1024: yt = np.pad(yt, (0, 1024))
    f0 = librosa.yin(yt, fmin=70, fmax=450, sr=sr, frame_length=1024)
    rms = librosa.feature.rms(y=yt, frame_length=1024, hop_length=256)[0]
    speech = rms > rms.max() * 0.1
    speech_s = speech.sum() * 256 / sr
    voiced = f0[(f0 > 70) & (f0 < 450)]
    M = librosa.feature.mfcc(y=yt, sr=sr, n_mfcc=13, hop_length=256)[1:]
    k = min(M.shape[1], len(speech)); mf = M[:, :k][:, speech[:k]]
    cen = librosa.feature.spectral_centroid(y=yt, sr=sr, hop_length=256)[0]
    return {"f0": float(np.median(voiced)) if len(voiced) else 0.0,
            "rate": n_units / max(speech_s, 0.2),
            "loud": float(20 * np.log10(np.sqrt(np.mean(yt[np.abs(yt) > 1e-4] ** 2)) + 1e-9)),
            "bright": float(np.mean(cen[: len(speech)][speech[: len(cen)]])) if speech.any() else float(np.mean(cen)),
            "timbre": [round(float(x), 2) for x in (mf.mean(1) if mf.size else np.zeros(12))]}

class Profiles:
    def __init__(self, path):
        self.path = Path(path)
        self.p = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def key(self, who, engine): return f"{engine}/{who}"

    def check(self, who, engine, feat, emotion="neutral"):
        k = self.key(who, engine); P = self.p.get(k)
        if not P or P.get("n", 0) < 3:
            return {"ok": True, "learning": True, "drift": [], "n": (P or {}).get("n", 0)}
        drift = []
        V = P.get("var", {})
        def tol(x, rel):        # seema = max(fixed %, 2.5 x is kirdaar ka apna utaar-chadhav)
            sd = math.sqrt(V.get(x, 0.0) / max(P["n"] - 1, 1)); return max(rel * abs(P[x]), 2.5 * sd)
        exp_f0 = P["f0"] * (1 + EMO_F0.get(emotion, 0.0))
        if feat["f0"] and abs(feat["f0"] - exp_f0) > tol("f0", 0.08):
            drift.append({"what": "sur", "got": round(feat["f0"]), "want": round(exp_f0), "fix": {"pitch_st": round(12 * math.log2(exp_f0 / feat["f0"]), 2)}})
        if abs(feat["rate"] - P["rate"]) > tol("rate", 0.15):
            drift.append({"what": "raftaar", "got": round(feat["rate"], 2), "want": round(P["rate"], 2), "fix": {"rate": round(feat["rate"] / P["rate"], 3)}})
        if abs(feat["loud"] - P["loud"]) > max(2.5, tol("loud", 0)):
            drift.append({"what": "zor", "got": round(feat["loud"], 1), "want": round(P["loud"], 1), "fix": {"gain_db": round(P["loud"] - feat["loud"], 2)}})
        if abs(feat["bright"] - P["bright"]) > tol("bright", 0.14):
            drift.append({"what": "chamak", "got": round(feat["bright"]), "want": round(P["bright"]), "fix": {"presence_db": round(4 * math.log2(P["bright"] / feat["bright"]), 2)}})
        t = np.array(feat["timbre"]); pt = np.array(P["timbre"])
        dist = float(np.sqrt(np.mean(((t - pt) / 20) ** 2)))
        dmax = max(0.45, P.get("d_mean", 0.3) + 3 * math.sqrt(P.get("d_var", 0.0) / max(P["n"] - 1, 1)))
        if dist > dmax: drift.append({"what": "rang", "got": round(dist, 3), "want": f"< {dmax:.2f}", "fix": {"rerender": True}})
        for d in drift: d["severity"] = "soft" if d["what"] in ("chamak", "rang") else "hard"   # chamak/rang shabdon se badalte hain
        return {"ok": not any(d["severity"] == "hard" for d in drift), "drift": drift, "n": P["n"], "timbre_dist": round(dist, 3)}

    def update(self, who, engine, feat, emotion="neutral"):
        """Sirf saaf (pass) aur bina-badle param wali lines se seekho; bhaav wali line ka sur neutral par laakar.
        Har maap ka mean + utaar-chadhav (variance, Welford) — seema kirdaar khud sikhata hai."""
        k = self.key(who, engine); P = self.p.get(k)
        f0n = feat["f0"] / (1 + EMO_F0.get(emotion, 0.0)) if feat["f0"] else 0
        if not P:
            self.p[k] = {"n": 1, "f0": f0n, "rate": feat["rate"], "loud": feat["loud"], "bright": feat["bright"], "timbre": feat["timbre"],
                         "var": {"f0": 0.0, "rate": 0.0, "loud": 0.0, "bright": 0.0}, "d_mean": 0.3, "d_var": 0.0}
        else:
            a = 1 / min(P["n"] + 1, 20)                      # 20 line ke baad dheere badle (bhatke nahi)
            V = P.setdefault("var", {"f0": 0.0, "rate": 0.0, "loud": 0.0, "bright": 0.0})
            d = float(np.sqrt(np.mean(((np.array(feat["timbre"]) - np.array(P["timbre"])) / 20) ** 2)))
            dm = P.get("d_mean", 0.3); P["d_mean"] = dm + (d - dm) * a; P["d_var"] = P.get("d_var", 0.0) + (d - dm) * (d - P["d_mean"])
            for x, v in (("f0", f0n), ("rate", feat["rate"]), ("loud", feat["loud"]), ("bright", feat["bright"])):
                if v:
                    old = P[x]; P[x] = (1 - a) * P[x] + a * v; V[x] = V.get(x, 0.0) + (v - old) * (v - P[x])
            P["timbre"] = [round((1 - a) * p + a * v, 2) for p, v in zip(P["timbre"], feat["timbre"])]
            P["n"] += 1
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.p, ensure_ascii=False, indent=1), encoding="utf-8")
