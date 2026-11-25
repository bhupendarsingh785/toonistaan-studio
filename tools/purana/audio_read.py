#!/usr/bin/env python3
"""Audio Read v2 — audio ko theek se padho: kab, kya, kaun, kitni der.

Jo audio_profile se aage hai:
  1) SEGMENTS   — speech vs non-speech, har hisse ka time
  2) SPEAKERS   — F0+timbre se cluster: kaun bol raha hai, kab se kab tak (turns)
  3) EVENTS     — background ki awaazein: kab, kitni der, kaisi (thud / hiss / tonal)
  4) BED TIMELINE — background 5 s ke tukdon me kitna (kab tez hua)
  5) SPEECH QUALITY — clarity (HF ratio), SNR, clipping, pace, pause, ending contour
  6) TIMELINE   — sab kuch ek table me: 12.4s par "kadam", 15.0s par "speaker B"

CLI: python tools/audio_read.py --audio x.mp3 [--json out.json] [--full]
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CAST = {"narrator": (90, 125), "dada": (88, 125), "dadi": (140, 185),
        "maa": (165, 205), "gudiya": (190, 240), "sonu": (240, 330)}


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def decode(path: str, sr: int = 16000, ch: int = 1):
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", path, "-f", "s16le",
                        "-ac", str(ch), "-ar", str(sr), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768.0


def frames(x, sr, win=0.032, hop=0.016):
    """rms/zcr per frame + hop **seconds** me (0.016 s)."""
    import numpy as np
    N, H = int(win * sr), int(hop * sr)
    idx = range(0, max(1, len(x) - N), H)
    rms = np.array([np.sqrt((x[i:i + N] ** 2).mean()) for i in idx]) if len(x) > N else np.array([0.0])
    zcr = np.array([np.mean(np.abs(np.diff(np.sign(x[i:i + N])))) / 2 for i in idx]) if len(x) > N else np.array([0.0])
    return rms, zcr, hop


def f0_frame(seg, sr):
    import numpy as np
    N = len(seg)
    if N < 160 or float(np.sqrt((seg ** 2).mean())) < 0.02:
        return 0.0
    seg = seg - seg.mean()
    ac = np.correlate(seg, seg, "full")[N - 1:]
    lo, hi = int(sr / 400), int(sr / 70)
    if hi >= len(ac):
        return 0.0
    k = lo + int(np.argmax(ac[lo:hi]))
    return sr / k if k > 0 else 0.0


def segments(x, sr, rms, hop):
    """speech/non-speech hisse (energy + zero-crossing)."""
    import numpy as np
    thr = max(0.008, float(np.percentile(rms, 25)) * 1.8)
    lab = rms > thr
    segs, cur, start = [], (bool(lab[0]) if len(lab) else False), 0.0
    for i, v in enumerate(lab):
        t = i * hop                      # hop seconds me hai
        if bool(v) != cur:
            if t - start > 0.12:
                segs.append({"type": "speech" if cur else "silence",
                             "start": round(start, 2), "end": round(t, 2)})
            cur, start = bool(v), t
    segs.append({"type": "speech" if cur else "silence",
                 "start": round(start, 2), "end": round(len(lab) * hop, 2)})
    for s in segs:
        s["dur"] = round(s["end"] - s["start"], 2)
    return segs


def speakers(x, sr, segs):
    """har speech hisse ka F0 + centroid; phir 2-4 cluster (kaun bol raha hai)."""
    import numpy as np
    rows = []
    for s in segs:
        if s["type"] != "speech":
            continue
        a, b = int(s["start"] * sr), int(s["end"] * sr)
        seg = x[a:b]
        if len(seg) < sr * 0.2:
            continue
        N, H = 640, 320
        f0s = [f0_frame(seg[i:i + N], sr) for i in range(0, max(1, len(seg) - N), H)]
        f0s = [f for f in f0s if f > 0]
        mag = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) + 1e-9
        freqs = np.fft.rfftfreq(len(seg), 1 / sr)
        centroid = float((mag * freqs).sum() / mag.sum())
        hf = float(mag[freqs > 3000].sum() / mag.sum())
        rows.append({"start": s["start"], "end": s["end"], "dur": s["dur"],
                     "f0": int(np.median(f0s)) if f0s else 0,
                     "f0_std": round(float(np.std(f0s)), 1) if f0s else 0.0,
                     "centroid": round(centroid), "hf_ratio": round(hf, 3)})
    # simple clustering by F0 (insaan ka sur sabse bada farq hai)
    if not rows:
        return []
    f0s = sorted(r["f0"] for r in rows if r["f0"] > 0)
    if not f0s:
        return rows
    import numpy as np
    arr = np.array(f0s)
    thr = np.median(arr)
    for r in rows:
        r["voice"] = "A (bhaari/neeche)" if (r["f0"] and r["f0"] < thr) else "B (halka/upar)"
    return rows


def events(x, sr, segs):
    """background/onsets: kab, kitni der, kaisi (thud/hiss/tonal)."""
    import numpy as np
    N, H = 1024, 512
    flux, flat, bands = [], [], []
    prev = None
    for i in range(0, max(1, len(x) - N), H):
        seg = x[i:i + N] * np.hanning(N)
        mag = np.abs(np.fft.rfft(seg)) + 1e-9
        freqs = np.fft.rfftfreq(N, 1 / sr)
        flat.append(float(np.exp(np.mean(np.log(mag))) / np.mean(mag)))
        bands.append((float(mag[freqs < 300].sum()), float(mag[(freqs > 3000)].sum())))
        if prev is not None:
            flux.append(float(np.maximum(0, mag - prev).sum()))
        prev = mag
    if not flux:
        return [], 0.0
    f = np.array(flux)
    thr = f.mean() + 2.2 * f.std()
    hits, last = [], -9
    for i, v in enumerate(f):
        t = i * H / sr
        if v > thr and t - last > 0.25:
            low, high = bands[min(i, len(bands) - 1)]
            kind = ("thud/impact" if low > high * 1.5 else
                    "hiss/noise" if high > low * 1.5 else "tonal/mixed")
            hits.append({"at": round(t, 2), "kind": kind})
            last = t
    return hits[:60], round(float(np.mean(flat)), 4)


def bed_timeline(x, sr, win=5.0):
    """background 5 s ke tukdon me: level aur flatness (kab tez hua)."""
    import numpy as np
    out = []
    step = int(win * sr)
    for i in range(0, len(x) - step + 1, step):
        seg = x[i:i + step]
        rms = float(np.sqrt((seg ** 2).mean()))
        N = 1024
        mags = []
        for j in range(0, max(1, len(seg) - N), N):
            m = np.abs(np.fft.rfft(seg[j:j + N] * np.hanning(N))) + 1e-9
            mags.append(float(np.exp(np.mean(np.log(m))) / np.mean(m)))
        out.append({"from": round(i / sr, 1), "to": round((i + step) / sr, 1),
                    "level_dbfs": round(20 * np.log10(max(1e-9, rms)), 1),
                    "flatness": round(float(np.mean(mags)) if mags else 0.0, 3)})
    return out


def read(path: str) -> dict:
    import numpy as np
    x = decode(path)
    if len(x) == 0:
        return {"ok": False, "why": "decode fail"}
    sr = 16000
    dur = len(x) / sr
    rms, zcr, hop = frames(x, sr)
    segs = segments(x, sr, rms, hop)
    spk = speakers(x, sr, segs)
    evs, flatness = events(x, sr, segs)
    beds = bed_timeline(x, sr)

    speech = [s for s in segs if s["type"] == "speech"]
    sil = [s for s in segs if s["type"] == "silence"]
    pauses = [s["dur"] for s in sil if s["dur"] >= 0.2]
    rms_all = float(np.sqrt((x ** 2).mean()))
    peak = float(np.max(np.abs(x)))
    clip = float(np.mean(np.abs(x) > 0.98) * 100)
    noise = float(np.percentile(rms, 10))
    snr = round(20 * np.log10(max(1e-9, float(np.mean([r for r in rms if r > noise]))) / max(1e-9, noise)), 1)
    f0s = [r["f0"] for r in spk if r["f0"] > 0]
    hz = int(np.median(f0s)) if f0s else 0
    best = min(CAST.items(), key=lambda kv: 0 if kv[1][0] <= hz <= kv[1][1]
               else min(abs(hz - kv[1][0]), abs(hz - kv[1][1])))

    # pace: speech frames me energy peaks = syllabus ka andaaza
    syl = 0
    prev = 0.0
    for v in rms:
        if v > noise * 2 and prev <= noise * 2:
            syl += 1
        prev = v
    speech_s = sum(s["dur"] for s in speech)
    pace = round(syl / speech_s, 2) if speech_s > 0.3 else 0.0

    # ending contour (aakhri speech segment ka F0 shuru vs aakhir)
    contour = "pata nahi"
    if spk:
        last = spk[-1]
        a, b = int(last["start"] * sr), int(last["end"] * sr)
        seg = x[a:b]
        n = len(seg) // 2
        f1 = [f0_frame(seg[i:i + 640], sr) for i in range(0, max(1, n - 640), 320)]
        f2 = [f0_frame(seg[n + i:n + i + 640], sr) for i in range(0, max(1, len(seg) - n - 640), 320)]
        f1 = [f for f in f1 if f > 0]; f2 = [f for f in f2 if f > 0]
        if f1 and f2:
            d = (sum(f2) / len(f2)) - (sum(f1) / len(f1))
            contour = "neeche girta (vakya khatam)" if d < -4 else ("upar uthta (sawaal jaisa)" if d > 4 else "flat")

    rep = {
        "ok": True, "file": str(path), "dur": round(dur, 2),
        "level": {"rms_dbfs": round(20 * np.log10(max(1e-9, rms_all)), 1),
                  "peak": round(peak, 2), "clipping_pct": round(clip, 2),
                  "snr_db": snr, "noise_floor_dbfs": round(20 * np.log10(max(1e-9, noise)), 1)},
        "speech": {"segments": len(speech), "speech_s": round(sum(s["dur"] for s in speech), 2),
                   "silence_s": round(sum(s["dur"] for s in sil), 2),
                   "pauses": {"count": len(pauses),
                              "mean_s": round(float(np.mean(pauses)), 2) if pauses else 0,
                              "max_s": round(float(np.max(pauses)), 2) if pauses else 0}},
        "pace_syl_per_s": pace,
        "pitch": {"median_hz": hz, "closest_cast": best[0], "band": list(best[1]),
                  "range_hz": [min(f0s) if f0s else 0, max(f0s) if f0s else 0],
                  "variability": round(float(np.std(f0s)), 1) if f0s else 0},
        "turns": spk,
        "events": evs, "background_flatness": flatness,
        "bed_timeline": beds,
        "ending_contour": contour,
        "segments": segs,
    }
    return rep


def timeline_text(rep: dict) -> list[str]:
    rows = []
    for t in rep.get("turns", []):
        rows.append((t["start"], f"BOL {t['voice']} F0={t['f0']}Hz ({t['dur']}s)"))
    for e in rep.get("events", []):
        rows.append((e["at"], f"AWAAZ {e['kind']}"))
    rows.sort(key=lambda r: r[0])
    return [f"{t:6.1f}s  {txt}" for t, txt in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description="audio ko padho (deep)")
    ap.add_argument("--audio", required=True)
    ap.add_argument("--json", default="")
    ap.add_argument("--full", action="store_true", help="timeline bhi print karo")
    a = ap.parse_args()
    rep = read(a.audio)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: rep[k] for k in ("dur", "level", "speech", "pace_syl_per_s", "pitch",
                                 "background_flatness", "ending_contour") if k in rep}
    brief["events_count"] = len(rep.get("events", []))
    brief["turns_count"] = len(rep.get("turns", []))
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    if a.full:
        print("\n--- TIMELINE ---")
        for line in timeline_text(rep):
            print(line)
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
