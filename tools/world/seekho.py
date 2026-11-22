#!/usr/bin/env python3
"""
Seekho — ek recording se awaaz ka "DNA" seekhna (100% local).

Ek baar suno -> gehra vishleshan (deep analysis) -> DNA file + tukde (units) -> sound-events.json me darj.
Uske baad rachna.py us DNA se hazaaron naye roop banata hai (halat ke hisaab se), har baar alag, par pehchaan wahi.

DNA me kya hai (sab naap, andaaza nahi):
  roop (type)      : 'events' (bhaunk, ghanti, kadam — alag-alag tukde) ya 'texture' (barish, taali, bheed — lagataar)
  tukde (units)    : har onset ka shuru/ant, zor, apna sur (f0), chamak (centroid)
  laya (rhythm)    : tukdon ke beech ka samay (IOI): median, phailav, pattern
  sur (pitch)      : f0 median/range, kitna sureela (voiced ratio)
  rang (spectrum)  : 40 mel band ka profile, centroid, flatness (shor vs sur), rolloff
  aakaar (envelope): attack, decay, AM rate (kaanpna/phadphadana)
  pehchaan (embed) : ek chhota vector jisse banaye roop ki asli se tulna hoti hai

Use:
  python tools/world/seekho.py --file gaay.wav --name cow --kw "गाय,बछड़ा,रंभा" --pan 0.5 --dist 5
  python tools/world/seekho.py --library astra/library      # library ki har file se seekho (naam se event)
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np
import librosa

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LEARN_DIR = ROOT / "knowledge" / "learned"
EVENTS_PATH = ROOT / "knowledge" / "sound-events.json"
SR = 44100   # sutradhar/voice ke saath ek hi SR (warna stems misalign)
ASR = 22050   # vishleshan ka sample rate (tez)

def load(path, sr=SR):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).astype(np.float64)

def trim(y, sr, top_db=40):
    yt, idx = librosa.effects.trim(y, top_db=top_db)
    return yt, idx

def embed(y, sr=ASR, fmax=5000):
    """Pehchaan vector (v2): sirf awaaz wale frame; recording ki asli bandwidth tak.
    13 MFCC (timbre) mean+std + envelope ka kaanpna (1–25 Hz, 4 band) + sur (voiced, f0)."""
    yt, _ = librosa.effects.trim(y, top_db=35)
    if len(yt) < 2048: yt = np.pad(yt, (0, 2048 - len(yt)))
    hop = 256
    M = librosa.feature.melspectrogram(y=yt, sr=sr, n_mels=32, fmax=fmax, n_fft=1024, hop_length=hop)
    rms = librosa.feature.rms(y=yt, frame_length=1024, hop_length=hop)[0][: M.shape[1]]
    keep = 20 * np.log10(rms + 1e-9) > 20 * np.log10(rms.max() + 1e-9) - 35
    if keep.sum() < 3: keep[:] = True
    mf = librosa.feature.mfcc(S=librosa.power_to_db(M[:, keep] + 1e-10), n_mfcc=14)[1:]
    env = rms[keep]; env = env / (env.max() + 1e-9)
    if len(env) > 8:
        mod = np.abs(np.fft.rfft((env - env.mean()) * np.hanning(len(env)))); fr = np.fft.rfftfreq(len(env), hop / sr)
        mb = np.array([mod[(fr >= a) & (fr < b)].sum() for a, b in ((1, 3), (3, 6), (6, 12), (12, 25))]); mb = mb / (mb.sum() + 1e-9)
    else:
        mb = np.zeros(4)
    f0 = librosa.yin(yt, fmin=60, fmax=2000, sr=sr)
    v = float(np.nanmean(librosa.pyin(yt[: sr * 4], fmin=60, fmax=1500, sr=sr)[1]))
    v = 0.0 if not np.isfinite(v) else v
    return np.concatenate([mf.mean(1) / 20, mf.std(1) / 10, mb, [v, np.log2(np.median(f0) / 100) * v / 2]])

def similarity(a, b):
    """0..1 — 1 = bilkul wahi. Alag awaazein aam taur par < 0.45."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.shape != b.shape: return 0.0
    return float(np.exp(-3 * np.sqrt(np.mean((a - b) ** 2))))

def embed_fmax(source_sr):
    return float(min(8000, (source_sr or 22050) / 2 * 0.9))

def analyse(y, sr=ASR, fmax=5000):
    """Gehra vishleshan: tukde, laya, sur, rang, aakaar."""
    dur = len(y) / sr
    hop = 256
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=hop)[0]
    rdb = 20 * np.log10(rms + 1e-9)
    on_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    onsets = librosa.onset.onset_detect(onset_envelope=on_env, sr=sr, hop_length=hop, units="time")
    # tukde (units) = awaaz ke "kshetra": khamoshi (>=80 ms) se alag. Goonj (decay) tukde ke andar hi rehti hai.
    floor = np.percentile(rdb, 5); thr = max(floor + 8, rdb.max() - 30)
    loud = rdb > thr
    gap_min = int(0.08 * sr / hop); regions = []; i = 0
    while i < len(loud):
        if loud[i]:
            j = i
            while j < len(loud):
                if not loud[j]:
                    k = j
                    while k < len(loud) and not loud[k]: k += 1
                    if k - j >= gap_min or k == len(loud): break
                    j = k
                else: j += 1
            regions.append((i, j)); i = j
        else: i += 1
    units = []
    tail_thr = rdb.max() - 50
    for ri, (r0, r1) in enumerate(regions):
        # poonchh (decay) tak badhao: jab tak -50 dB na ho jaaye ya agla tukda na aa jaaye
        nxt = regions[ri + 1][0] if ri + 1 < len(regions) else len(rdb)
        e_fr = r1
        while e_fr < nxt - 1 and rdb[e_fr] > tail_thr: e_fr += 1
        prv = regions[ri - 1][1] if ri > 0 else 0
        s_fr = r0
        while s_fr > prv and rdb[s_fr - 1] > tail_thr and r0 - s_fr < int(0.05 * sr / hop): s_fr -= 1
        s0 = max(0, s_fr * hop - int(0.005 * sr)); e0 = min(len(y), e_fr * hop + int(0.02 * sr))
        if (e0 - s0) / sr < 0.03: continue
        seg = y[s0:e0]
        f0 = librosa.yin(seg, fmin=60, fmax=2000, sr=sr, frame_length=1024) if len(seg) > 1024 else np.array([0.0])
        cen = librosa.feature.spectral_centroid(y=seg, sr=sr, n_fft=512, hop_length=128)[0]
        units.append({"s": round(s0 / sr, 4), "e": round(e0 / sr, 4), "peak_db": round(float(20 * np.log10(np.abs(seg).max() + 1e-9)), 2),
                      "f0": round(float(np.median(f0)), 1), "centroid": round(float(np.mean(cen)), 1)})
    gaps = 1 - loud.mean()
    on_rate = len(onsets) / max(dur, 0.1)
    vr0 = librosa.pyin(y[: sr * 6], fmin=60, fmax=1500, sr=sr, frame_length=2048)[1] if dur > 0.2 else np.array([0])
    voiced = float(np.nanmean(vr0))
    # chhote/dheeme bache-khuche tukde hatao (sabse zor wale se 20 dB neeche)
    if units:
        top = max(u["peak_db"] for u in units); units = [u for u in units if u["peak_db"] > top - 20]
    # roop: texture (taali, barish, hawa, bheed) ya events (pukaar, chot, ghanti)
    #  - be-sur (voiced<0.2) aur lamba lagataar tukda -> texture
    #  - ek hi bahut lamba tukda jiska level dhalta nahi (hawa/toofan) -> texture
    #  - chot jo shuru me sabse tez aur phir dhalti hai (gong, gilaas) -> events
    r100 = librosa.feature.rms(y=y, frame_length=int(0.1 * sr), hop_length=int(0.1 * sr))[0]; d100 = 20 * np.log10(r100 + 1e-9)
    dl = d100[d100 > d100.max() - 30]; decay_corr = float(np.corrcoef(np.arange(len(dl)), dl)[0, 1]) if len(dl) > 2 else -1.0
    longest = max([u["e"] - u["s"] for u in units] or [dur])
    if (voiced < 0.2 and longest > 1.2) or (longest > 2.5 and decay_corr > -0.5):
        kind = "texture"
    else:
        kind = "events"
    starts = np.array([u["s"] for u in units]); ioi = np.diff(starts) if len(starts) > 1 else np.array([])
    f0 = librosa.yin(y, fmin=60, fmax=2000, sr=sr, frame_length=2048)
    vr = vr0
    cen = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    flat = librosa.feature.spectral_flatness(y=y)[0]
    roll = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
    # aakaar: attack/decay of the loudest unit
    pk = int(np.argmax(rms)); att = pk * hop / sr
    after = np.flatnonzero(rdb[pk:] < rdb[pk] - 20); dec = (after[0] if len(after) else len(rdb) - pk) * hop / sr
    # AM rate (envelope modulation)
    env = rms - rms.mean(); spec = np.abs(np.fft.rfft(env * np.hanning(len(env)))); fr = np.fft.rfftfreq(len(env), hop / sr)
    band = (fr > 2) & (fr < 40); am = float(fr[band][np.argmax(spec[band])]) if band.any() else 0.0
    M = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=40); prof = np.log10(M.mean(1) + 1e-10)
    return {
        "type": kind, "duration_s": round(dur, 3),
        "units": units,
        "onset_rate": round(on_rate, 2), "gap_ratio": round(float(gaps), 3), "decay_corr": round(decay_corr, 3), "voiced": round(voiced, 3),
        "rhythm": {"count": len(units), "ioi_median": round(float(np.median(ioi)), 4) if len(ioi) else None,
                   "ioi_spread": round(float(np.std(ioi) / (np.median(ioi) + 1e-9)), 3) if len(ioi) > 1 else 0.0,
                   "ioi": [round(float(x), 4) for x in ioi]},
        "pitch": {"f0_median": round(float(np.nanmedian(f0)), 1), "f0_p10": round(float(np.nanpercentile(f0, 10)), 1),
                  "f0_p90": round(float(np.nanpercentile(f0, 90)), 1), "voiced_ratio": round(float(np.nanmean(vr)), 3)},
        "colour": {"centroid": round(float(np.mean(cen)), 1), "flatness": round(float(np.mean(flat)), 4),
                   "rolloff": round(float(np.mean(roll)), 1), "mel_profile": [round(float(x - prof.max()), 3) for x in prof]},
        "shape": {"attack_s": round(att, 3), "decay_s": round(dec, 3), "am_hz": round(am, 2)},
        "embed": [round(float(x), 4) for x in embed(y, sr, fmax)], "embed_fmax": fmax, "embed_version": 2,
    }

def learn(path, name, kw=None, pan=0.0, dist=2.0, level=-14, category="learned", source_note=None):
    y48 = load(path); y48, _ = trim(y48, SR)
    y = librosa.resample(y48, orig_sr=SR, target_sr=ASR)
    try:
        sr0 = int(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate", "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.split()[0])
    except Exception:
        sr0 = None
    dna = analyse(y, ASR, embed_fmax(sr0))
    d = LEARN_DIR / name; d.mkdir(parents=True, exist_ok=True)
    import soundfile as sf
    sf.write(d / "source.wav", (y48 / (np.abs(y48).max() + 1e-9) * 0.9).astype(np.float32), SR)
    dna.update({"name": name, "learned_from": str(Path(path).name), "source_sr": sr0, "learned_on": time.strftime("%Y-%m-%d"),
                "note": source_note, "times_used": 0})
    (d / "dna.json").write_text(json.dumps(dna, ensure_ascii=False, indent=1), encoding="utf-8")
    # gyaan-kosh me darj karo
    kb = json.load(open(EVENTS_PATH, encoding="utf-8"))
    e = kb["events"].get(name, {})
    e.update({"learned": f"learned/{name}", "level": e.get("level", level), "pan": e.get("pan", pan), "dist": e.get("dist", dist),
              "at": e.get("at", "word"), "category": e.get("category", category)})
    if kw: e["kw"] = sorted(set(e.get("kw", [])) | set(kw))
    e.setdefault("kw", [])
    if dna["type"] == "texture" and "state" not in e:
        e["at"] = "line"
    kb["events"][name] = e
    EVENTS_PATH.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
    idx_p = LEARN_DIR / "index.json"
    idx = json.load(open(idx_p, encoding="utf-8")) if idx_p.exists() else {}
    idx[name] = {"type": dna["type"], "units": len(dna["units"]), "from": dna["learned_from"], "on": dna["learned_on"]}
    idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    return dna

def learn_library(root):
    """Library ki har file: naam se event pehchaano (sound-events.json ke lib patterns), seekho."""
    import fnmatch
    kb = json.load(open(EVENTS_PATH, encoding="utf-8")); done = []
    for p in Path(root).rglob("*"):
        if p.suffix.lower() not in (".wav", ".mp3", ".flac", ".ogg"): continue
        for name, e in kb["events"].items():
            if any(fnmatch.fnmatch(p.name.lower(), pat) for pat in e.get("lib", [])):
                if not (LEARN_DIR / name / "dna.json").exists():
                    learn(p, name); done.append((name, p.name))
                break
    return done

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ek recording se awaaz seekho")
    ap.add_argument("--file"); ap.add_argument("--name"); ap.add_argument("--kw", default="")
    ap.add_argument("--pan", type=float, default=0.0); ap.add_argument("--dist", type=float, default=2.0)
    ap.add_argument("--level", type=float, default=-14); ap.add_argument("--library")
    a = ap.parse_args()
    if a.library:
        for n, f in learn_library(a.library): print("seekha:", n, "<-", f)
    else:
        dna = learn(a.file, a.name, [k.strip() for k in a.kw.split(",") if k.strip()], a.pan, a.dist, a.level)
        r = dna["rhythm"]; p = dna["pitch"]; c = dna["colour"]
        print(f"seekha '{a.name}': roop={dna['type']} · tukde={r['count']} · laya={r['ioi_median']}s (±{r['ioi_spread']}) · "
              f"sur={p['f0_median']}Hz (sureela {p['voiced_ratio']}) · chamak={c['centroid']}Hz · shor={c['flatness']} · AM={dna['shape']['am_hz']}Hz")
