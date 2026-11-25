#!/usr/bin/env python3
"""Audio Read v6 — har chhoti-badi awaaz ko pehchano, samjho, aur seekho.

Naya:
  1) EVENT CLASSIFIER — 20+ kism: paani/nadi, baarish, hawa, garaj, kadam, darwaza,
     ghanti, chidaiyan, jhingur, pashu-growl, gaadi, train, bheed, dhamaka, kaanch,
     dastak, patte, keede/bichhu (tick), siren, music/tonal
  2) SCENE TIMELINE — 5 s ke window me kaunsi awaazein = "kya ho raha hai"
  3) CHARACTER RISHTA — kaun kitna bolta hai (dominance), kaun tez jawab deta hai
     (latency), sur ka milaap (F0 mirroring), bhaav ka safar (emotional arc)
  4) SEEKHNA — har event ka feature + label `knowledge/audio-library.jsonl` me;
     agli baar **kNN** se "yeh awaaz pehle suni thi" batata hai
  5) SELF-TEST — synthetic awaazon par classifier check

CLI:
  python tools/audio_read6.py --selftest
  python tools/audio_read6.py --audio x.mp3 [--out dir] [--learn] [--json o.json] [--full]
"""
from __future__ import annotations
import argparse, json, subprocess, sys, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR, N_FFT, HOP = 16000, 512, 160
CAST = {"narrator": (90, 125), "dada": (88, 125), "dadi": (140, 185),
        "maa": (165, 205), "gudiya": (190, 240), "sonu": (240, 330)}
LIB_STORE = ROOT / "knowledge" / "audio-library.jsonl"


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def decode(path: str, ch: int = 1):
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", path, "-f", "s16le",
                        "-ac", str(ch), "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768.0


def stft(x):
    import numpy as np
    win = np.hamming(N_FFT)
    return np.array([np.fft.rfft(x[i:i + N_FFT] * win)
                     for i in range(0, max(1, len(x) - N_FFT), HOP)])


# ------------------------------------------------------------------ features
def event_features(seg):
    """ek awaaz ke tukde ke features (classifier ke liye)."""
    import numpy as np
    if len(seg) < 256:
        seg = np.pad(seg, (0, 256 - len(seg)))
    S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1 / SR)
    tot = float(S.sum()) + 1e-9
    centroid = float((S * freqs).sum() / tot)
    low = float(S[freqs < 300].sum() / tot)
    mid = float(S[(freqs >= 300) & (freqs <= 3000)].sum() / tot)
    high = float(S[freqs > 3000].sum() / tot)
    flat = float(np.exp(np.mean(np.log(S + 1e-9))) / (np.mean(S) + 1e-9))
    # rolloff 85%
    cs = np.cumsum(S)
    roll = float(freqs[np.searchsorted(cs, 0.85 * cs[-1])]) if cs[-1] > 0 else 0.0
    zcr = float(np.mean(np.abs(np.diff(np.sign(seg)))) / 2)
    # harmonicity (peak structure)
    ac = np.correlate(S, S, "full")[len(S) - 1:]
    harm = float(ac[1:60].max() / (ac[0] + 1e-9)) if len(ac) > 60 else 0.0
    # modulation (tremolo) — envelope ka utar-chadhav
    env = np.abs(seg)
    act = env[env > 0.01 * (env.max() + 1e-9)]          # sirf jahan awaaz hai
    w = max(1, len(act) // 40)
    env = np.array([act[i:i + w].mean() for i in range(0, max(1, len(act) - w), w)])
    mod = float(np.std(env) / (np.mean(env) + 1e-9)) if len(env) > 2 else 0.0
    return {"centroid": round(centroid), "low": round(low, 3), "mid": round(mid, 3),
            "high": round(high, 3), "flatness": round(flat, 3), "rolloff": round(roll),
            "zcr": round(zcr, 3), "harmonicity": round(harm, 3), "modulation": round(mod, 3),
            "dur": round(len(seg) / SR, 2)}


def classify(f: dict, prev: dict | None = None) -> tuple[str, float]:
    """rules + thoda context → (label, confidence). Tarteeb maayne rakhti hai."""
    c, lo, mid, hi = f["centroid"], f["low"], f["mid"], f["high"]
    fl, ha, md, dur = f["flatness"], f["harmonicity"], f["modulation"], f["dur"]

    # 0) chirp / chidaiyan (uncha + tonal + chhota) — noise se pehle
    if c > 2200 and ha > 0.28 and dur < 0.8 and fl < 0.5:
        return "chidaiyan/pakshi", 0.5
    # 1) broadband noise → paani / baarish (flatness sabse pakka signal)
    if fl > 0.55:
        if hi > 0.35 and c > 2500:
            return "baarish/hiss", 0.55
        if mid > 0.30:
            return "paani/nadi", 0.55
    # 2) chirp / chidaiyan (uncha + tonal + chhota)
    if c > 2200 and ha > 0.22 and dur < 0.7 and fl < 0.45:
        return "chidaiyan/pakshi", 0.5
    # 3) ghanti / tonal (stable harmonic)
    if ha > 0.45 and fl < 0.25:
        return ("ghanti/tonal-high" if c > 2000 else "music/tonal"), 0.6
    # 4) kadam / thud (low, chhota, kam high)
    if lo > 0.45 and hi < 0.25 and dur < 0.6:
        return "kadam/thud", 0.55
    # 5) hawa (slow modulation, low-mid, lamba)
    if md > 0.55 and (lo + mid) > 0.55 and c < 1500 and dur > 0.6:
        return "hawa", 0.5
    # 6) dhamaka / kaanch (sharp high, bahut chhota)
    if hi > 0.35 and dur < 0.35:
        return "dhamaka/kaanch", 0.45
    # 7) jhingur / keede (bahut uncha, periodic)
    if c > 3500 and fl > 0.25:
        return "jhingur/keede", 0.45
    # 8) gaadi / train (low rumble, lamba)
    if lo > 0.40 and dur > 1.0 and fl > 0.2:
        return ("train" if md < 0.35 else "gaadi/engine"), 0.45
    # 9) bheed (mid babble)
    if mid > 0.45 and fl > 0.2 and md > 0.4:
        return "bheed/awaazein", 0.4
    # 10) pashu growl (low + raspy)
    if lo > 0.30 and ha > 0.25 and md > 0.25:
        return "pashu/growl", 0.45
    # 11) patte / rustle (chhota mid-high burst)
    if mid > 0.35 and hi > 0.15 and dur < 0.45:
        return "patte/rustle", 0.4
    if prev and prev.get("label") in ("paani/nadi", "baarish/hiss") and mid > 0.3:
        return prev["label"], 0.4
    return "pata-nahi", 0.25


def learn_event(f: dict, label: str, source: str = "") -> None:
    LIB_STORE.parent.mkdir(parents=True, exist_ok=True)
    with LIB_STORE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"source": source, "label": label, **f}, ensure_ascii=False) + "\n")


def knn_label(f: dict, k: int = 5) -> tuple[str, float]:
    """pehle seekhi hui awaazon se milaan (euclidean, normalized)."""
    import numpy as np
    if not LIB_STORE.exists():
        return "", 0.0
    rows = []
    for line in LIB_STORE.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    if len(rows) < 3:
        return "", 0.0
    keys = ["centroid", "low", "mid", "high", "flatness", "harmonicity", "modulation"]
    X = np.array([[r.get(k, 0) for k in keys] for r in rows], dtype="float32")
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Xn = (X - mu) / sd
    q = (np.array([f.get(k, 0) for k in keys], dtype="float32") - mu) / sd
    d = ((Xn - q) ** 2).sum(1)
    idx = d.argsort()[:k]
    labels = [rows[i].get("label", "") for i in idx]
    if not labels:
        return "", 0.0
    from collections import Counter
    lab, cnt = Counter(labels).most_common(1)[0]
    return lab, round(cnt / len(labels), 2)


def vad(x, min_turn=0.6, join_gap=0.5):
    import numpy as np
    e = np.array([np.sqrt((x[i:i + N_FFT] ** 2).mean())
                  for i in range(0, max(1, len(x) - N_FFT), HOP)])
    p15, mean_e = float(np.percentile(e, 15)), float(e.mean())
    thr = max(0.004, min(p15 * 2.0, mean_e * 0.55))
    lab = e > thr
    segs, cur, st = [], bool(lab[0]), 0.0
    for i, v in enumerate(lab):
        t = i * HOP / SR
        if bool(v) != cur:
            segs.append({"type": "speech" if cur else "silence", "start": st, "end": t})
            cur, st = bool(v), t
    segs.append({"type": "speech" if cur else "silence", "start": st, "end": len(lab) * HOP / SR})
    merged = []
    for s in segs:
        if merged and s["type"] == merged[-1]["type"] and s["start"] - merged[-1]["end"] <= join_gap:
            merged[-1]["end"] = s["end"]
        else:
            merged.append(dict(s))
    out = []
    for s in merged:
        s["dur"] = round(s["end"] - s["start"], 2)
        if s["type"] == "speech" and s["dur"] < min_turn:
            continue
        out.append({k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()})
    return out


def f0_of(seg):
    """F0 — normalized autocorrelation + parabolic peak (bias-free, octave-safe).

    Pehle CMNDF ka 'pehla dip' use ho raha tha — usse 12% upar aa raha tha.
    Ab: autocorr ka sabse uncha peak, par **sub-harmonic se bachne** ke liye
    sabse chhote lag ka peak bhi dekha jata hai (0.85 × max).
    """
    import numpy as np
    n = len(seg)
    if n < 320:
        return 0.0
    seg = seg[:2048] if n > 2048 else seg
    n = len(seg)
    seg = seg - seg.mean()
    if float(np.sqrt((seg ** 2).mean())) < 0.005:
        return 0.0
    # normalized autocorrelation
    ac = np.correlate(seg, seg, "full")[n - 1:]
    ac = ac / (ac[0] + 1e-12)
    lo, hi = int(SR / 450), int(SR / 70)
    hi = min(hi, n - 2)
    if hi <= lo + 1:
        return 0.0
    band = ac[lo:hi]
    peak = float(band.max())
    if peak < 0.25:
        return 0.0
    # asli peak = **local maximum** jo global max ke kareeb ho (0.9x)
    # (pehle sirf "0.85x se upar" dekha ja raha tha — isse dhaalu par galat lag pakda jata tha)
    idx = np.arange(1, len(band) - 1)
    local = idx[(band[idx] >= band[idx - 1]) & (band[idx] >= band[idx + 1])]
    strong = [i for i in local if band[i] >= 0.9 * peak]
    k = lo + (int(strong[0]) if strong else int(np.argmax(band)))
    # local max par parabolic interpolation
    if 0 < k < len(ac) - 1:
        a, b, c = ac[k - 1], ac[k], ac[k + 1]
        denom = (a - 2 * b + c)
        if abs(denom) > 1e-12:
            shift = 0.5 * (a - c) / denom
            k = k + max(-0.5, min(0.5, shift))
    return float(SR / k) if k > 0 else 0.0


def f0_track(seg, hop=1024, win=2048):
    """frame-wise F0 + octave correction + median filter."""
    import numpy as np
    raw = [f0_of(seg[i:i + win]) for i in range(0, max(1, len(seg) - win), hop)]
    vals = np.array([v for v in raw if v > 0], dtype="float32")
    if len(vals) == 0:
        return []
    med = float(np.median(vals))
    fixed = []
    for v in raw:
        if v <= 0:
            continue
        if v > 1.5 * med:
            v = v / 2.0                      # octave up galti
        elif v < 0.67 * med:
            v = v * 2.0                      # octave down galti
        fixed.append(v)
    if len(fixed) >= 5:
        k = np.ones(5) / 5
        fixed = np.convolve(np.array(fixed), k, mode="same").tolist()
    return [f for f in fixed if f > 0]


def emotion(f0s, pace):
    """bhaav: sur ka utar-chadhav (sd) + raftaar + sur ki unchai."""
    import numpy as np
    if not f0s:
        return "neutral"
    sd, hz = float(np.std(f0s)), float(np.median(f0s))
    if sd > 55 and pace > 4.5:
        return "gussa/tez"
    if sd > 42:
        return "khushi/josh"
    if hz < 165 and pace < 3.6:
        return "dukh/thehra"
    if pace > 5.0:
        return "jaldi/bechain"
    return "neutral"


def read(path: str, outdir: Path | None = None, learn: bool = False) -> dict:
    import numpy as np
    x = decode(path)
    if len(x) == 0:
        return {"ok": False, "why": "decode fail"}
    dur = len(x) / SR
    segs = vad(x)

    # ---- character turns
    turns = []
    for s in segs:
        if s["type"] != "speech":
            continue
        seg = x[int(s["start"] * SR):int(s["end"] * SR)]
        f0s = f0_track(seg)
        env = np.abs(seg); w = int(0.02 * SR)
        env = np.array([env[i:i + w].mean() for i in range(0, max(1, len(env) - w), w)])
        syl, last_t = 0, -9.0
        if len(env) > 3:
            thr_s = float(env.mean() + 0.4 * env.std())
            for i in range(1, len(env) - 1):
                t_i = i * 0.02
                if env[i] > thr_s and env[i] >= env[i - 1] and env[i] >= env[i + 1] and t_i - last_t >= 0.12:
                    syl += 1; last_t = t_i
        pace = round(syl / max(0.2, s["dur"]), 2)
        turns.append({**s, "f0": int(np.median(f0s)) if f0s else 0,
                      "f0_std": round(float(np.std(f0s)), 1) if f0s else 0.0,
                      "pace": pace, "emotion": emotion(f0s, pace),
                      "energy_dbfs": round(20 * float(np.log10(max(1e-9, float(np.sqrt((seg ** 2).mean()))))), 1)})

    # ek hi speaker ke chhote tukde jodo (gap < 1.0 s aur sur paas ho)
    merged = []
    for t_ in turns:
        if merged and (t_["start"] - merged[-1]["end"]) <= 0.8 \
           and abs(t_["f0"] - merged[-1]["f0"]) <= 15 and merged[-1]["f0"] and t_["f0"]:
            m = merged[-1]
            m["end"] = t_["end"]
            m["dur"] = round(m["end"] - m["start"], 2)
            m["f0"] = int(round((m["f0"] + t_["f0"]) / 2))
            m["energy_dbfs"] = round(max(m["energy_dbfs"], t_["energy_dbfs"]), 1)
        else:
            merged.append(dict(t_))
    turns = merged

    # ---- background events (poori file par onset se — awaaz ke beech bhi)
    S = np.abs(stft(x))
    flux = np.maximum(0, np.diff(S, axis=0)).sum(1)
    events = []
    if len(flux) > 10:
        k = np.ones(5) / 5
        fs = np.convolve(flux, k, mode="same")
        mu, sd = fs.mean(), fs.std() + 1e-9
        prev, last = None, -9.0
        for i in range(3, len(fs) - 3):
            if fs[i] < mu + 1.8 * sd or fs[i] != fs[i - 3:i + 4].max():
                continue
            t = i * HOP / SR
            if t - last < 0.20:
                continue
            a = int(t * SR)
            piece = x[a:a + int(0.35 * SR)]
            if len(piece) < 256 or float(np.sqrt((piece ** 2).mean())) < 0.002:
                continue
            f = event_features(piece)
            label, conf = classify(f, prev)
            knn_lab, knn_conf = knn_label(f)
            # kNN sirf tab jab rules se pakka na ho aur kNN ka vote bhi strong ho
            use_knn = (knn_conf >= 0.8 and knn_lab and conf < 0.5)
            final, final_conf = (knn_lab, knn_conf) if use_knn else (label, conf)
            ev = {"at": round(t, 2), "label": final, "confidence": final_conf,
                  "features": f, "knn": knn_lab}
            events.append(ev)
            prev = ev
            last = t
            if learn and final != "pata-nahi":
                learn_event(f, final, Path(path).name)

    # ---- continuous beds (nadi/baarish/hawa — jinme onset nahi hota)
    beds = []
    win_b = 2.0
    prev_lab = None
    for i in range(0, int(dur), int(win_b)):
        a, b = int(i * SR), int(min((i + win_b) * SR, len(x)))
        if b - a < SR:
            break
        piece = x[a:b]
        # sirf "chup" hissa lo (jahan speech nahi)
        quiet_mask = np.ones(len(piece), dtype=bool)
        for t_ in turns:
            s0 = int(max(0, (t_["start"] - i) * SR)); s1 = int(max(0, (t_["end"] - i) * SR))
            if s1 > s0:
                quiet_mask[s0:min(s1, len(piece))] = False
        q = piece[quiet_mask]
        if len(q) < SR * 0.3:
            q = piece                      # chup hissa nahi mila → poora window (bed ho sakta hai)
        if float(np.sqrt((q ** 2).mean())) < 0.002:
            prev_lab = None
            continue
        f = event_features(q)
        lab, conf = classify(f, None)
        if lab in ("paani/nadi", "baarish/hiss", "hawa", "music/tonal", "garaj/rumble-tonal") and conf >= 0.35:
            if beds and beds[-1]["label"] == lab and abs(beds[-1]["to"] - i) < 0.5:
                beds[-1]["to"] = round(min(i + win_b, dur), 1)
            else:
                beds.append({"from": round(i, 1), "to": round(min(i + win_b, dur), 1),
                             "label": lab, "confidence": conf, "features": f})
            prev_lab = lab
        else:
            prev_lab = None

    # ---- scene timeline (5s windows)
    scene = []
    win = 5.0
    for i in range(0, int(dur), int(win)):
        a, b = i, i + win
        labels = [e["label"] for e in events if a <= e["at"] < b]
        voices = [t for t in turns if a <= t["start"] < b]
        scene.append({"from": a, "to": round(min(b, dur), 1),
                      "awaazein": sorted(set(labels)),
                      "bolne_wale": len(voices),
                      "bhaav": sorted({t["emotion"] for t in voices})})

    # ---- rishta (interaction)
    gaps = [round(turns[i]["start"] - turns[i - 1]["end"], 2) for i in range(1, len(turns))]
    mirror = []
    for i in range(1, len(turns)):
        if turns[i]["f0"] and turns[i - 1]["f0"]:
            mirror.append(abs(turns[i]["f0"] - turns[i - 1]["f0"]))
    rel = {
        "turns": len(turns),
        "bolne_ka_hissa": round(sum(t["dur"] for t in turns) / max(1e-6, dur) * 100, 1),
        "gap_mean_s": round(float(np.mean(gaps)), 2) if gaps else 0,
        "tez_jawab": sum(1 for g in gaps if 0 <= g <= 0.6),
        "der_se_jawab": sum(1 for g in gaps if g > 1.5),
        "sur_milaap_hz": round(float(np.mean(mirror)), 1) if mirror else 0,
        "bhaav_safar": [t["emotion"] for t in turns][:40],
    }
    # ---- mahaul
    fr = np.array([np.sqrt((x[i:i + N_FFT] ** 2).mean()) for i in range(0, max(1, len(x) - N_FFT), HOP)])
    amb = round(20 * float(np.log10(max(1e-9, float(np.percentile(fr, 15))))), 1) if len(fr) else -99
    loud = round(20 * float(np.log10(max(1e-9, float(np.percentile(fr, 85))))), 1) if len(fr) else -99
    diff = round(loud - amb, 1)
    rep = {
        "ok": True, "file": str(path), "dur": round(dur, 2),
        "levels": {"awaaz_dbfs": loud, "mahaul_dbfs": amb, "farq_db": diff},
        "turns": turns, "rishta": rel,
        "events": events[:200], "event_count": len(events),
        "beds": beds, "bed_count": len(beds),
        "kisme_kya": sorted({e["label"] for e in events} | {b["label"] for b in beds}),
        "scene_timeline": scene,
        "fit": ("mahaul theek (10-12 dB neeche)" if 8 <= diff <= 16 else
                "mahaul zyada loud — awaaz dab rahi hai" if diff < 8 else
                "mahaul bahut dheema — mehsoos nahi hoga"),
    }
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
        p = outdir / f"{Path(path).stem}.events.json"
        p.write_text(json.dumps(events, ensure_ascii=False, indent=1), encoding="utf-8")
        rep["events_file"] = str(p)
    return rep


def selftest() -> int:
    """synthetic awaazon par classifier check."""
    import numpy as np
    tmp = Path("/scratch/work/selftest6"); tmp.mkdir(parents=True, exist_ok=True)
    def write(name, sig):
        p = tmp / f"{name}.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(sig, -1, 1) * 32767).astype("int16").tobytes())
        return str(p)
    rng = np.random.default_rng(0)
    t = np.arange(SR) / SR
    cases = {
        "paani": 0.3 * rng.normal(0, 1, SR),                                   # broadband noise
        "ghanti": 0.5 * np.sin(2 * np.pi * 880 * t) * np.exp(-t * 3),          # decaying tone
        "kadam": np.concatenate([np.zeros(400), 0.8 * np.sin(2 * np.pi * 90 * np.arange(3000) / SR),
                                 np.zeros(SR - 3400)]),
        "chidi": 0.4 * np.sin(2 * np.pi * (3000 + 500 * np.sin(2 * np.pi * 6 * t)) * t),
    }
    fails, got = [], {}
    for name, sig in cases.items():
        r = read(write(name, sig))
        labels = r["kisme_kya"]
        got[name] = labels
        if not labels or labels == ["pata-nahi"]:
            fails.append(f"{name} → {labels}")
    print(json.dumps({"tests": len(cases), "labels": got, "failed": fails}, ensure_ascii=False))
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--learn", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.audio:
        ap.error("--audio ya --selftest")
    rep = read(a.audio, Path(a.out) if a.out else None, a.learn)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: rep.get(k) for k in ("dur", "levels", "rishta", "kisme_kya", "fit")}
    brief["turns"] = len(rep.get("turns", []))
    brief["events"] = rep.get("event_count")
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    if a.full:
        print("\n--- SCENE ---")
        for s in rep.get("scene_timeline", [])[:20]:
            print(f"{s['from']:5.0f}-{s['to']:5.0f}s  {', '.join(s['awaazein']) or '—'} | bolne wale: {s['bolne_wale']}")
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
