#!/usr/bin/env python3
"""
Rachna — ek baar seekhi awaaz se hazaaron naye roop (100% local).

Do tareeke, DNA ke roop (type) ke hisaab se:
  events  (bhaunk, ghanti, kadam): asli tukdon (units) ko nayi laya me jodo — har tukda apne sur, zor, chamak ke saath;
          kabhi do tukdon ko milao (morph). Laya DNA ke IOI se, halat se tez/dheemi, be-tartibi (jitter) ke saath.
  texture (barish, taali, bheed) : granular — asli recording ke 60–180 ms ke daane, random jagah se, overlap ke saath:
          kabhi na dohrane wali lambi awaaz, rang wahi.
Halat (situation): bhaav, aakaar (chhota/bada/bachcha), zor (halka/tez) -> knowledge/situation-rules.json.

Khud jaanch (QA) har roop par:
  pehchaan  : naye roop ka DNA-embed asli se kitna milta hai (>= 0.80 warna phenk do)
  naya-pan  : pichhle 24 roopon se kitna alag (memory.json) — ek jaisa dobara nahi
6 ummeedwar banao -> jo pehchaan me paas + sabse naya, woh chuno.

python tools/world/rachna.py --name cow --n 6 --emotion dar --out-dir out/
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
import numpy as np
import librosa
from scipy import signal as ss

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import seekho as SK

SR = 48000
RULES_PATH = ROOT / "knowledge" / "situation-rules.json"
_CACHE = {}

def rules():
    if "rules" not in _CACHE: _CACHE["rules"] = json.load(open(RULES_PATH, encoding="utf-8"))
    return _CACHE["rules"]

def load_learned(name):
    if name in _CACHE: return _CACHE[name]
    d = SK.LEARN_DIR / name
    if not (d / "dna.json").exists(): return None
    dna = json.load(open(d / "dna.json", encoding="utf-8"))
    import soundfile as sf
    y, sr = sf.read(d / "source.wav"); y = y.astype(np.float64)
    _CACHE[name] = (dna, y); return _CACHE[name]

def is_learned(name): return (SK.LEARN_DIR / name / "dna.json").exists()

def all_embeds():
    """Saari seekhi awaazon ke pehchaan-vector (pehchaan test ke liye: kya roop apni hi awaaz jaisa hai?)."""
    if "_all" not in _CACHE:
        out = {}
        for d in SK.LEARN_DIR.glob("*/dna.json"):
            j = json.load(open(d, encoding="utf-8"))
            if j.get("embed_version") == 2: out[j["name"]] = np.array(j["embed"])
        _CACHE["_all"] = out
    return _CACHE["_all"]

# ---------------------------------------------------------------- halat -> parameters
def situation_from_text(text):
    """Line ke shabd se aakaar/zor: 'बड़ा कुत्ता ज़ोर से भौंका' -> size=bada, intensity=tez."""
    R = rules(); sit = {}
    import spotting as S
    for k, words in R["size_words"].items():
        if S.has(text, words): sit["size"] = k
    for k, words in R["intensity_words"].items():
        if S.has(text, words): sit["intensity"] = k
    return sit

def params_for(sit, rng):
    R = rules(); p = {"pitch_st": 0.0, "tempo": 1.0, "gain_db": 0.0, "bright": 1.0, "jitter": 0.0, "count": 1.0}
    for group, key in (("emotion", sit.get("emotion")), ("size", sit.get("size")), ("intensity", sit.get("intensity"))):
        for k, v in R.get(group, {}).get(key or "", {}).items():
            if k in ("tempo", "bright", "count"): p[k] *= v
            else: p[k] += v
    b = R["base_random"]                         # har baar thoda alag — insaan/jaanwar kabhi do baar ek jaisa nahi
    p["pitch_st"] += rng.normal(0, b["pitch_st"] / 2)
    p["tempo"] *= math.exp(rng.normal(0, b["tempo"]))
    p["gain_db"] += rng.normal(0, b["gain_db"] / 2)
    p["bright"] *= math.exp(rng.normal(0, b["bright"]))
    p["jitter"] += b["jitter"]
    return p

# ---------------------------------------------------------------- DSP
def repitch(x, st):
    """Sur badlo (resample): asli jaisa — bada jaanwar = neecha aur thoda lamba."""
    if abs(st) < 0.05: return x
    r = 2 ** (st / 12)
    n = max(32, int(len(x) / r))
    return ss.resample_poly(x, n, len(x)) if len(x) < 2_000_000 else np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)

def tilt(x, bright):
    """Chamak: >1 = tez/khula, <1 = dabba/naram (simple shelving mix)."""
    if abs(bright - 1) < 0.02: return x
    sos = ss.butter(1, 2500 / (SR / 2), "high", output="sos")
    hi = ss.sosfilt(sos, x)
    return x + hi * (bright - 1) * 1.5

def fade(x, a=0.004, b=0.02):
    n = len(x); ka, kb = min(n // 4, int(a * SR)), min(n // 3, int(b * SR))
    x = x.copy()
    if ka: x[:ka] *= np.linspace(0, 1, ka)
    if kb: x[-kb:] *= np.linspace(1, 0, kb)
    return x

# ---------------------------------------------------------------- rachna: events
def make_events(dna, src, p, rng, dur=None):
    units = dna["units"]
    if not units: return make_texture(dna, src, p, rng, dur)
    segs = [src[int(u["s"] * SR):int(u["e"] * SR)] for u in units]
    ioi = np.array(dna["rhythm"]["ioi"] or [max(0.25, (units[0]["e"] - units[0]["s"]) * 1.3)])
    n_units = max(1, int(round(len(units) * p["count"] * rng.uniform(0.7, 1.3))))
    if dur: n_units = 10_000
    out = []; t = 0.0; last = -1; seq = []
    total = dur or 60.0
    while len(seq) < n_units and t < total:
        k = int(rng.integers(len(segs)))
        if len(segs) > 1 and k == last: k = (k + 1 + int(rng.integers(len(segs) - 1))) % len(segs)
        seg = segs[k]
        if len(segs) > 1 and rng.random() < 0.15:            # morph: do tukdon ka mel — naya tukda
            j = (k + 1) % len(segs); o = segs[j]; m = min(len(seg), len(o))
            w = rng.uniform(0.3, 0.7); seg = seg[:m] * (1 - w) + o[:m] * w
        st = p["pitch_st"] + rng.normal(0, 0.35)              # har tukde ka apna halka sur
        g = 10 ** ((p["gain_db"] + rng.normal(0, 1.2)) / 20)
        u = fade(tilt(repitch(seg, st), p["bright"])) * g
        out.append((t, u)); seq.append(k); last = k
        base = ioi[int(rng.integers(len(ioi)))] if len(ioi) else 0.4
        gap = base / p["tempo"] * math.exp(rng.normal(0, p["jitter"]))
        gap = max(gap, len(u) / SR * 0.85)                    # tukde ek-doosre par na chadhen (zyada)
        t += gap
        if dur is None and len(seq) >= n_units: break
        if dur and len(seq) % max(2, len(units)) == 0 and rng.random() < 0.5:
            t += rng.uniform(0.6, 2.0)                        # halat me: beech-beech me saans/ruka
    L = int((t + 1.0) * SR) if dur is None else int(dur * SR)
    y = np.zeros(L)
    for t0, u in out:
        i = int(t0 * SR)
        if i >= L: break
        m = min(len(u), L - i); y[i:i + m] += u[:m]
    return y, seq

# ---------------------------------------------------------------- rachna: texture (granular)
def make_texture(dna, src, p, rng, dur=None):
    D = dur or dna["duration_s"] * rng.uniform(0.8, 1.6)
    n = int(D * SR); y = np.zeros(n + SR); t = 0
    seq = []
    while t < n:
        g = int(rng.uniform(0.06, 0.18) * SR / p["tempo"] ** 0.3)
        s = int(rng.integers(0, max(1, len(src) - g)))
        grain = src[s:s + g]
        grain = repitch(grain, p["pitch_st"] + rng.normal(0, 0.25))
        w = np.hanning(len(grain)); y[t:t + len(grain)] += grain * w
        seq.append(s // 4800)
        t += max(1, int(len(grain) * 0.5))
    y = tilt(y[:n], p["bright"]) * 10 ** (p["gain_db"] / 20)
    k = int(0.05 * SR); y[:k] *= np.linspace(0, 1, k); y[-k:] *= np.linspace(1, 0, k)
    return y, seq

# ---------------------------------------------------------------- QA: pehchaan + naya-pan
def fingerprint(p, seq):
    h = hashlib.md5(str(seq[:40]).encode()).hexdigest()[:8]
    return {"pitch": round(p["pitch_st"], 2), "tempo": round(p["tempo"], 3), "bright": round(p["bright"], 3), "seq": h, "n": len(seq)}

def novelty(fp, memory):
    if not memory: return 1.0
    ds = []
    for m in memory:
        d = abs(fp["pitch"] - m["pitch"]) / 2 + abs(math.log(fp["tempo"] / m["tempo"])) * 3 + abs(math.log(fp["bright"] / m["bright"])) * 3
        d += 0.0 if fp["seq"] == m["seq"] else 0.6
        ds.append(d)
    return float(min(1.0, min(ds)))

def load_limits(name):
    p = SK.LEARN_DIR / name / "limits.json"
    return json.load(open(p)) if p.exists() else {"pitch_ok": [], "pitch_fail": [], "safe": [-6.0, 6.0]}

def update_limits(name, pitch, passed):
    """Har roop se seekho: kitna sur badalne par awaaz pehchaan me rehti hai (surakshit seema)."""
    L = load_limits(name)
    (L["pitch_ok"] if passed else L["pitch_fail"]).append(round(pitch, 2))
    L["pitch_ok"] = L["pitch_ok"][-60:]; L["pitch_fail"] = L["pitch_fail"][-60:]
    lo, hi = -6.0, 6.0
    fails_lo = [f for f in L["pitch_fail"] if f < 0]; fails_hi = [f for f in L["pitch_fail"] if f > 0]
    oks = L["pitch_ok"]
    if fails_lo: lo = max(lo, max([f for f in fails_lo if f <= min([o for o in oks if o < 0] or [0])] or [min(fails_lo)]) + 0.25)
    if fails_hi: hi = min(hi, min([f for f in fails_hi if f >= max([o for o in oks if o > 0] or [0])] or [max(fails_hi)]) - 0.25)
    L["safe"] = [round(min(lo, -0.5), 2), round(max(hi, 0.5), 2)]
    (SK.LEARN_DIR / name / "limits.json").write_text(json.dumps(L), encoding="utf-8")
    return L

def variant(name, sit=None, rng=None, dur=None, remember=True):
    """Ek naya roop. Returns (audio, info) ya (None, reason)."""
    L = load_learned(name)
    if L is None: return None, "not learned"
    dna, src = L; sit = sit or {}; rng = rng or np.random.default_rng()
    R = rules()["qa"]
    memp = SK.LEARN_DIR / name / "memory.json"
    memory = json.load(open(memp)) if memp.exists() else []
    ref = np.array(dna["embed"]); best = None
    safe = load_limits(name)["safe"]
    shrink = 1.0; trials = []
    for c in range(R["candidates"] + 3):
        if c >= R["candidates"]:
            if best and best[2]["passed"]: break
            shrink *= 0.5                                  # fail hua? halat ka asar aadha karke phir koshish
        p = params_for(sit, rng)
        p["pitch_st"] = float(np.clip(p["pitch_st"] * shrink, *safe))
        p["bright"] = 1 + (p["bright"] - 1) * shrink
        maker = make_events if dna["type"] == "events" else make_texture
        y, seq = maker(dna, src, p, rng, dur)
        if not np.any(y): continue
        ya = librosa.resample(y[: SR * 8], orig_sr=SR, target_sr=SK.ASR)
        e = SK.embed(ya, SK.ASR, dna.get("embed_fmax", 5000))
        sim = SK.similarity(e, ref)
        others = [SK.similarity(e, v) for k, v in all_embeds().items() if k != name]
        rival = max(others) if others else 0.0
        fp = fingerprint(p, seq); nov = novelty(fp, memory)
        ok = sim >= R["min_similarity"] and sim >= rival + R.get("min_margin", 0.1)   # apni awaaz se sabse zyada mile
        trials.append((p["pitch_st"], ok))
        score = (1 if ok else 0) * 2 + nov + sim * 0.5
        if best is None or score > best[0]: best = (score, y, dict(params={k: round(v, 3) for k, v in p.items()}, similarity=round(sim, 3),
                                                                  novelty=round(nov, 3), passed=ok, rival=round(rival, 3), units_used=len(seq), fingerprint=fp))
    if best is None: return None, "empty"
    _, y, info = best
    for pt, ok_ in trials: update_limits(name, pt, ok_)     # har koshish se seekho
    if remember:
        memory = (memory + [info["fingerprint"]])[-R["memory"]:]
        memp.write_text(json.dumps(memory), encoding="utf-8")
    y = y / (np.abs(y).max() + 1e-9)
    return y, info

def combinations(name):
    """Kitne alag roop mumkin: tukde-kram x sur x laya x chamak x halat (andaaza, neeche ki seema)."""
    L = load_learned(name)
    if L is None: return 0
    dna, _ = L; u = max(1, len(dna["units"]))
    seq = u ** min(6, max(2, u)) if dna["type"] == "events" else 10 ** 6
    return int(seq * 20 * 15 * 10 * (len(rules()["emotion"]) * 4 * 3))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--name", required=True); ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--emotion"); ap.add_argument("--size"); ap.add_argument("--intensity"); ap.add_argument("--dur", type=float)
    ap.add_argument("--out-dir", default="."); ap.add_argument("--seed", type=int)
    a = ap.parse_args(); rng = np.random.default_rng(a.seed)
    import soundfile as sf
    Path(a.out_dir).mkdir(parents=True, exist_ok=True)
    sit = {k: v for k, v in dict(emotion=a.emotion, size=a.size, intensity=a.intensity).items() if v}
    for i in range(a.n):
        y, info = variant(a.name, sit, rng, a.dur)
        if y is None: print(info); break
        f = Path(a.out_dir) / f"{a.name}_{'_'.join(sit.values()) or 'neutral'}_{i + 1}.wav"
        sf.write(f, (y * 0.9).astype(np.float32), SR)
        print(f.name, info["similarity"], info["novelty"], info["params"])
    print("mumkin roop (kam se kam):", f"{combinations(a.name):,}")
