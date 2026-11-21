#!/usr/bin/env python3
"""Horror Read — darr wale show ka blueprint: kab tension, kab scream, kab khamoshi.

Chunked analysis (lambe file ke liye memory-safe):
  1) har 5 s block: zor, chamak, speech %, music %, onsets
  2) scream detection: uncha F0 + tez zor + high band
  3) tension curve: brightness + music + onsets ka mix
  4) "darr ke mode": khamoshi → build → scream → release (pattern)
CLI: python tools/horror_read.py --audio x.mp3 [--json o.json] [--step 5]
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SR = 16000


def ffmpeg() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def decode(path: str):
    import numpy as np
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", path, "-f", "s16le",
                        "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768.0


def block_stats(seg):
    import numpy as np
    n = len(seg)
    if n < SR:
        return None
    rms = float(np.sqrt((seg ** 2).mean()))
    N, H = 1024, 512
    frames = range(0, max(1, n - N), H)
    S = np.empty((len(frames), N // 2 + 1), dtype="float32")
    for k, i in enumerate(frames):
        S[k] = np.abs(np.fft.rfft(seg[i:i + N] * np.hanning(N)))
    f = np.fft.rfftfreq(N, 1 / SR)
    low = float(S[:, f < 300].sum()); mid = float(S[:, (f >= 300) & (f < 3000)].sum())
    high = float(S[:, f >= 3000].sum()); tot = low + mid + high + 1e-9
    cent = float((S.mean(0) * f).sum() / (S.mean(0).sum() + 1e-9))
    flat = float(np.mean(np.exp(np.mean(np.log(S + 1e-9), axis=1)) / (np.mean(S, axis=1) + 1e-9)))
    flux = np.maximum(0, np.diff(S, axis=0)).sum(1)
    onsets = int((flux > flux.mean() + 2 * flux.std()).sum()) if len(flux) > 4 else 0
    # speech/awaaz hissa (energy frames)
    e = np.array([np.sqrt((seg[i:i + N] ** 2).mean()) for i in range(0, max(1, n - N), H)])
    speech_pct = float((e > max(0.006, np.percentile(e, 15) * 2)).mean() * 100)
    # scream: bahut tez + high band + uncha
    scream = bool(rms > 0.12 and high / tot > 0.28 and cent > 2200)
    return {"rms_db": round(20 * float(np.log10(max(1e-9, rms))), 1),
            "bright": round(cent), "low_pct": round(100 * low / tot),
            "mid_pct": round(100 * mid / tot), "high_pct": round(100 * high / tot),
            "flatness": round(flat, 3), "onsets": onsets,
            "speech_pct": round(speech_pct, 1), "scream": scream}


def mode_of(b: dict, prev: dict | None) -> str:
    if b["rms_db"] < -38 and b["speech_pct"] < 8:
        return "khamoshi (darr se pehle)"
    if b["scream"]:
        return "SCREAM / jhatka"
    if b["onsets"] >= 12 and b["bright"] > 1800:
        return "build (tension chad rahi)"
    if b["flatness"] > 0.35 and b["mid_pct"] > 45:
        return "music/bed (mahaul)"
    if b["speech_pct"] > 40:
        return "baat (kahani chalti)"
    return "chalu (normal)"


def read(path: str, step: int = 5) -> dict:
    x = decode(path)
    if len(x) == 0:
        return {"ok": False, "why": "decode fail"}
    dur = len(x) / SR
    rows = []
    n = int(step * SR)
    prev = None
    for i in range(0, len(x) - n + 1, n):
        b = block_stats(x[i:i + n])
        if not b:
            continue
        b["at"] = i // SR
        b["mode"] = mode_of(b, prev)
        rows.append(b)
        prev = b
    # file ke apne naap se threshold (fixed number galat the)
    import numpy as np
    rms_arr = np.array([r["rms_db"] for r in rows])
    hi_arr = np.array([r["high_pct"] for r in rows])
    on_arr = np.array([r["onsets"] for r in rows])
    q_loud = float(np.percentile(rms_arr, 92))
    q_quiet = float(np.percentile(rms_arr, 8))
    q_high = float(np.percentile(hi_arr, 75))
    q_on = float(np.percentile(on_arr, 80))
    for r in rows:
        if r["rms_db"] <= q_quiet and r["speech_pct"] < 25:
            r["mode"] = "khamoshi (darr se pehle)"
        elif r["rms_db"] >= q_loud and r["high_pct"] >= q_high:
            r["mode"] = "SCREAM / jhatka"
            r["scream"] = True
        elif r["onsets"] >= q_on and r["bright"] > 1500:
            r["mode"] = "build (tension chad rahi)"
        elif r["flatness"] > 0.30 and r["mid_pct"] > 45 and r["speech_pct"] < 30:
            r["mode"] = "music/bed (mahaul)"
        elif r["speech_pct"] > 40:
            r["mode"] = "baat (kahani chalti)"
        else:
            r["mode"] = "chalu (normal)"
    from collections import Counter
    modes = Counter(r["mode"] for r in rows)
    screams = [r["at"] for r in rows if r["scream"]]
    sil = [r["at"] for r in rows if r["mode"].startswith("khamoshi")]
    loud = sorted(rows, key=lambda r: -r["rms_db"])[:5]
    rep = {"ok": True, "file": Path(path).name, "dur": round(dur, 1), "step_s": step,
           "blocks": len(rows), "modes": dict(modes), "screams_at": screams[:40],
           "silence_at": sil[:40], "loudest_at": [r["at"] for r in loud],
           "timeline": rows}
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--json", default="")
    ap.add_argument("--step", type=int, default=5)
    a = ap.parse_args()
    rep = read(a.audio, a.step)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: rep.get(k) for k in ("ok", "dur", "blocks", "modes", "screams_at", "silence_at", "loudest_at")}
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
