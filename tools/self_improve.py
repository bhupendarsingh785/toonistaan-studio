#!/usr/bin/env python3
"""self_improve.py v2 — audio ko gehra samajhne wala loop (bina GPU, numpy + optional praat).

Chaar hisse:
  1. DEEP  : ek file ke 18 naap (F0, jitter, shimmer, HNR, tilt, formant, pause, rate,
             harsh band, dynamics, SNR, reverb, clip, mod-spectrum, level, peak, LUFS-ish, holes)
  2. BRANCH: har defect se 2-3 shakha (kaaran) -> har shakha ka probe -> evidence se chuno, galat katao
  3. LEARN : har run ka (feature -> fix -> delta) improve-log.jsonl me; fix ka weight = jeet/haar se
  4. PLAN  : agla render kya badle (fix_plan.json) — renderer isi ko padhta hai

  python tools/self_improve.py deep --audio a.mp3 [--ref r.wav]
  python tools/self_improve.py plan --audio a.mp3 --ref r.wav --out fix_plan.json
  python tools/self_improve.py learn            # log se weights
  python tools/self_improve.py selftest         # apne aap ko jaancho
"""
from __future__ import annotations
import argparse, json, math, subprocess, sys
from pathlib import Path
import numpy as np

KN = Path(__file__).resolve().parent.parent / "knowledge"
LOG = KN / "improve-log.jsonl"
SR = 16000
FIXES = {   # fix id -> (kya badalta hai, default value, range)
    "harsh_cut":   ("3.2k/6.2k par cut (dB)", -2.0, (-6.0, 0.0)),
    "warmth":      ("250 Hz shelf (dB)", 1.5, (0.0, 4.0)),
    "mod_depth":   ("amplitude lehar (%)", 7.0, (0.0, 14.0)),
    "bed_level":   ("background (voice se dB)", -7.0, (-16.0, -3.0)),
    "voice_gain":  ("voice gain (dB)", 0.0, (-3.0, 4.0)),
    "master_vol":  ("master volume", 0.85, (0.6, 1.0)),
    "praat_depth": ("praat curve depth (st)", 1.0, (0.0, 2.5)),
    "pace":        ("pace guna", 1.0, (0.9, 1.12)),
    "bed_eq":      ("background 2.5-4k cut (dB)", 0.0, (-6.0, 0.0)),
}


# ------------------------------------------------------------------ naap
def load(p):
    from imageio_ffmpeg import get_ffmpeg_exe
    raw = subprocess.run([get_ffmpeg_exe(), "-v", "quiet", "-i", str(p), "-f", "f32le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def _f0(x, hop=160, win=640, fmin=70, fmax=450):
    lo, hi = int(SR / fmax), int(SR / fmin)
    out = []
    for i in range(0, len(x) - win, hop):
        fr = x[i:i + win]
        if float(np.sqrt((fr ** 2).mean())) < 0.008:
            continue
        fr = fr - fr.mean()
        ac = np.correlate(fr, fr, "full")[win - 1:]
        seg = ac[lo:hi]
        if not len(seg):
            continue
        lag = lo + int(np.argmax(seg))
        if ac[lag] > 0.30 * ac[0]:
            out.append(SR / lag)
    return np.array(out) if out else np.array([1.0])


def _env(x, k=400):
    return np.array([np.sqrt((x[i:i + k] ** 2).mean()) for i in range(0, len(x) - k, k)])


def _speech_mask(n, marks):
    m = np.zeros(n, dtype=bool)
    for mk in marks or []:
        a = int(float(mk.get("start", 0)) * SR); b = int((float(mk.get("start", 0)) + float(mk.get("dur", 0))) * SR)
        m[max(0, a):min(n, b)] = True
    return m


def deep(path, max_s=40, marks=None):
    """18 naap — chhote se bade sab."""
    x = load(path)
    if len(x) < SR // 2:
        return {"error": "audio khaali/chhoti"}
    x = x[: int(max_s * SR)]
    n = len(x)
    smask = _speech_mask(n, marks)
    xv = x[smask] if smask.any() and smask.sum() > SR // 2 else x      # bolne wale hisse
    f0 = _f0(x)
    st = 12 * np.log2(f0 / np.median(f0)) if len(f0) else np.array([0.0])
    # jitter (period ka uchhal) / shimmer (amplitude ka uchhal)
    jitter = float(np.mean(np.abs(np.diff(f0))) / (np.mean(f0) + 1e-9)) if len(f0) > 2 else 0.0
    env = _env(x)
    shimmer = float(np.mean(np.abs(np.diff(env))) / (np.mean(env) + 1e-9))
    # spectrum
    nv = len(xv)
    S = np.abs(np.fft.rfft(xv * np.hanning(nv))); fr = np.fft.rfftfreq(nv, 1 / SR)
    def band(a, b): return float(S[(fr >= a) & (fr < b)].sum())
    tot = float(S.sum()) + 1e-9
    harsh = band(2000, 4500) / tot            # share of total (bass/EQ se jhoota nahi)
    harsh_rel = band(2000, 4500) / (band(800, 2000) + 1e-9)
    tilt = band(1000, 4000) / (band(100, 1000) + 1e-9)          # spectral tilt
    air = band(6000, 9000) / (band(1000, 6000) + 1e-9)
    # HNR-ish (harmonic vs noise): autocorr peak se
    ac = np.correlate(x - x.mean(), x - x.mean(), "full")[n - 1:]
    ac = ac / (ac[0] + 1e-9)
    hnr = float(10 * math.log10(max(1e-6, float(np.max(ac[int(SR / 450):int(SR / 70)]))) / (1 - min(0.99, float(np.max(ac[int(SR / 450):int(SR / 70)]))) + 1e-9)))
    # formants (LPC)
    f1 = f2 = 0.0
    try:
        import scipy.signal as ss
        seg = x[int(0.3 * n):int(0.3 * n) + 2048]
        if len(seg) > 1024:
            a = ss.lpc(seg * np.hamming(len(seg)), 12)
            roots = [r for r in np.roots(a) if np.imag(r) > 0]
            fs = sorted([abs(np.angle(r)) * SR / (2 * np.pi) for r in roots])
            fs = [f for f in fs if 200 < f < 4000]
            if len(fs) >= 2:
                f1, f2 = fs[0], fs[1]
    except Exception:
        try:                      # scipy na ho to FFT se formant (khurdara par kaam ka)
            seg = x[int(0.3 * n):int(0.3 * n) + 4096]
            if len(seg) > 2048:
                S2 = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))); f2a = np.fft.rfftfreq(len(seg), 1 / SR)
                m2 = (f2a > 200) & (f2a < 4000)
                idx = np.argsort(S2[m2])[-6:]
                peaks = sorted(f2a[m2][idx])
                if len(peaks) >= 2:
                    f1, f2 = float(peaks[0]), float(peaks[1])
        except Exception:
            pass
    # pauses / rate
    thr = np.max(env) * 0.06
    gaps, run = [], 0
    for e in env:
        if e < thr: run += 1
        else:
            if run * 0.025 > 0.12: gaps.append(run * 0.025)
            run = 0
    # mod spectrum (lehar 1-8 Hz)
    e = env - env.mean()
    E = np.abs(np.fft.rfft(e)); mf = np.fft.rfftfreq(len(e), 0.025)
    mod_peak = float(mf[(E > 0)][np.argmax(E[mf > 0.5])]) if len(E) else 0.0
    mod_depth = float(np.std(np.diff(env)) / (np.mean(env) + 1e-9))
    # dynamics / clip / level
    peak = float(np.abs(x).max())
    rms = float(np.sqrt((x ** 2).mean()))
    dyn = float(20 * math.log10((np.percentile(env, 95) + 1e-9) / (np.percentile(env, 10) + 1e-9)))
    clip_pct = float(100 * np.mean(np.abs(x) > 0.985))
    # holes (lambi chuppi)
    holes = float(100 * sum(g for g in gaps if g > 1.2) / (n / SR))
    return {"dur_s": round(n / SR, 1), "f0_med": round(float(np.median(f0))),
            "f0_std": round(float(st.std()), 2), "f0_range": round(float(np.percentile(st, 95) - np.percentile(st, 5)), 1),
            "jitter": round(jitter, 4), "shimmer": round(shimmer, 3), "hnr_db": round(hnr, 1),
            "harsh": round(harsh, 4), "harsh_rel": round(harsh_rel, 2), "tilt": round(tilt, 2), "air": round(air, 2),
            "f1": round(f1), "f2": round(f2), "pauses": len(gaps),
            "pause_med_s": round(float(np.median(gaps)) if gaps else 0.0, 2),
            "mod_depth": round(mod_depth, 3), "mod_peak_hz": round(mod_peak, 1),
            "dyn_db": round(dyn, 1), "peak": round(peak, 2), "rms_db": round(20 * math.log10(rms + 1e-9), 1),
            "clip_pct": round(clip_pct, 2), "holes_pct": round(holes, 2),
            "voice_only": bool(smask.any() and smask.sum() > SR // 2)}


# ---------------------------------------------------------------- shakha (branch)
BRANCHES = {
    "rough": {"signal": lambda m: m["harsh"] > 0.09, "probes": [
        {"name": "2-4.5k harsh", "test": lambda m: m["harsh"] > 0.10, "fix": {"harsh_cut": -3.0}},
        {"name": "air zyada", "test": lambda m: m["air"] > 0.35, "fix": {"harsh_cut": -2.0}},
        {"name": "tilt bright", "test": lambda m: m["tilt"] > 1.1, "fix": {"warmth": 2.0}}]},
    "flat": {"signal": lambda m: m["f0_std"] < 5.0, "probes": [
        {"name": "ek line me sur flat", "test": lambda m: m["f0_std"] < 4.5, "fix": {"praat_depth": 1.8}},
        {"name": "lehar kam", "test": lambda m: m["mod_depth"] < 0.55, "fix": {"mod_depth": 10.0}}]},
    "weak": {"signal": lambda m: m["rms_db"] < -19.0, "probes": [
        {"name": "voice dheemi", "test": lambda m: m["rms_db"] < -20.0, "fix": {"voice_gain": 2.0}},
        {"name": "master neeche", "test": lambda m: m["peak"] < 0.7, "fix": {"master_vol": 0.95}}]},
    "harsh_peak": {"signal": lambda m: m["peak"] > 0.95 or m["clip_pct"] > 0.05, "probes": [
        {"name": "clip ho raha", "test": lambda m: m["clip_pct"] > 0.02, "fix": {"master_vol": 0.72}}]},
    "bed_bright": {"signal": lambda m: m.get("voice_only") and m["harsh"] > 0.15, "probes": [
        {"name": "background bright", "test": lambda m: m["tilt"] > 0.6, "fix": {"bed_eq": -3.5}},
        {"name": "voice bright", "test": lambda m: m["tilt"] <= 0.6, "fix": {"harsh_cut": -2.0}}]},
    "lifeless": {"signal": lambda m: m["jitter"] < 0.004 and m["shimmer"] < 0.10, "probes": [
        {"name": "kampan nahi", "test": lambda m: m["shimmer"] < 0.12, "fix": {"mod_depth": 8.0}}]},
}


def diagnose(m, ref=None):
    """Defect -> shakha -> probe -> chuna hua fix (evidence ke saath)."""
    out = {"branches": [], "fix": {}, "why": []}
    for bname, b in BRANCHES.items():
        if not b["signal"](m):
            continue
        chosen = None
        for pr in b["probes"]:
            try:
                if pr["test"](m):
                    chosen = pr; break
            except Exception:
                continue
        out["branches"].append({"branch": bname, "chosen": chosen["name"] if chosen else None})
        if chosen:
            for k, v in chosen["fix"].items():
                out["fix"][k] = v
            out["why"].append(f"{bname}: {chosen['name']} -> {chosen['fix']}")
    if ref:
        gap = []
        for k in ("harsh", "mod_depth", "f0_std", "rms_db", "jitter", "shimmer"):
            if k in ref and k in m:
                d = m[k] - ref[k]
                if abs(d) > (0.05 if k in ("harsh", "mod_depth", "jitter") else 0.6):
                    gap.append((k, round(d, 3)))
        out["gap_vs_ref"] = sorted(gap, key=lambda t: -abs(t[1]))[:5]
        if m["harsh"] - ref.get("harsh", 0) > 0.01:
            out["fix"]["harsh_cut"] = min(out["fix"].get("harsh_cut", 0), -2.5)
        if ref.get("mod_depth", 0) - m["mod_depth"] > 0.05:
            out["fix"]["mod_depth"] = max(out["fix"].get("mod_depth", 0), 9.0)
    return out


# ------------------------------------------------------------------- seekhna
def log_run(m, fix, delta=None, tag=""):
    KN.mkdir(parents=True, exist_ok=True)
    row = {"tag": tag, "naap": m, "fix": fix, "delta": delta}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def learn():
    """Log se: kaunsa fix kitna kaam aaya (weight = jeet/haar)."""
    if not LOG.exists():
        return {"runs": 0, "weights": {}}
    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    w = {k: {"n": 0, "win": 0, "sum_delta": 0.0} for k in FIXES}
    for r in rows:
        for k, v in (r.get("fix") or {}).items():
            if k not in w: continue
            w[k]["n"] += 1
            d = (r.get("delta") or {}).get(k)
            if d is not None:
                w[k]["sum_delta"] += float(d)
                if float(d) > 0: w[k]["win"] += 1
    out = {}
    for k, v in w.items():
        if v["n"]:
            out[k] = {"runs": v["n"], "win_rate": round(v["win"] / v["n"], 2),
                      "avg_delta": round(v["sum_delta"] / max(1, v["n"]), 3)}
    return {"runs": len(rows), "weights": out}


def apply_learned(fix):
    """Learned win-rate se fix ko halka adjust (jo jeeta use zyada)."""
    lw = learn()["weights"]
    out = dict(fix)
    for k, v in out.items():
        w = lw.get(k)
        if w and w["runs"] >= 3 and w["win_rate"] < 0.4:
            out[k] = v * 0.6      # jo kaam nahi karta, halka karo
        elif w and w["win_rate"] > 0.7:
            out[k] = v * 1.15     # jo jeeta, thoda badhao
    return out


def selftest():
    """Apne aap ko jaancho: naap sahi aate hain?"""
    ok = []
    p = Path("/scratch/work/ref_china.wav")
    if p.exists():
        m = deep(p)
        ok.append(("ref naap", m["f0_med"] > 80 and m["dur_s"] > 5))
        ok.append(("harsh 0-3", 0 <= m["harsh"] <= 3))
        d = diagnose(m)
        ok.append(("diagnose chala", "branches" in d))
    lw = learn()
    ok.append(("learn chala", "weights" in lw))
    for n, v in ok: print(("PASS " if v else "FAIL ") + n)
    return all(v for _, v in ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["deep", "plan", "learn", "selftest"])
    ap.add_argument("--audio", action="append", default=[])
    ap.add_argument("--ref", default=None)
    ap.add_argument("--out", default="fix_plan.json")
    ap.add_argument("--marks", default=None, help="plan.json / marks.json (bolne wale hisse)")
    a = ap.parse_args()
    if a.cmd == "selftest":
        sys.exit(0 if selftest() else 1)
    if a.cmd == "learn":
        print(json.dumps(learn(), ensure_ascii=False, indent=1)); return
    ref = deep(a.ref) if a.ref else None
    if ref: print("REF:", json.dumps(ref, ensure_ascii=False))
    mk = None
    if a.marks and Path(a.marks).exists():
        try:
            _j = json.loads(Path(a.marks).read_text(encoding="utf-8"))
            mk = _j.get("lines") or _j.get("marks")
        except Exception:
            mk = None
    for p in a.audio:
        m = deep(p, marks=mk)
        d = diagnose(m, ref)
        fix = apply_learned(d["fix"])
        print("\n", Path(p).name, json.dumps(m, ensure_ascii=False))
        print("  shakha:", d["branches"])
        print("  gap:", d.get("gap_vs_ref"))
        print("  fix:", fix, "|", d["why"])
        log_run(m, fix, tag=Path(p).name)
        if a.cmd == "plan":
            Path(a.out).write_text(json.dumps({"audio": p, "fix": fix, "why": d["why"],
                                               "naap": m, "ref": ref}, ensure_ascii=False, indent=1), encoding="utf-8")
            print("  plan:", a.out)


if __name__ == "__main__":
    main()
