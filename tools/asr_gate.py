#!/usr/bin/env python3
"""ASR Gate — awaaz ko wapas padh kar dekho: shabd/akshar sahi bole gaye ya nahi.

faster-whisper (int8, CPU) se line ka audio padhta hai, `akshar.py` se akshar-akshar milaan karta hai,
aur CER deta hai. Har line ka nateeja + poora score. CI me gate ki tarah chalta hai.

Chalao:
  python tools/asr_gate.py --audio out.mp3 --marks story_local.json
  python tools/asr_gate.py --audio out.mp3 --marks story_local.json --json
  python tools/asr_gate.py --text "नमस्ते दुनिया" --audio line.wav        # ek line
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
try:
    import astra_paths as _AP
except ImportError:
    import sys as _s, pathlib as _pl
    _s.path.insert(0, str(_pl.Path(__file__).resolve().parent)); import astra_paths as _AP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "realtime"))
SR = 16000
MODEL_CACHE = (_AP.WORK / "models")


def _ffmpeg():
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def load16k(path, start=None, dur=None):
    import numpy as np
    FF = _ffmpeg()
    cmd = [FF, "-v", "quiet"]
    if start is not None:
        cmd += ["-ss", f"{max(0, start):.3f}"]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def model(size="small"):
    from faster_whisper import WhisperModel
    MODEL_CACHE.mkdir(parents=True, exist_ok=True)
    return WhisperModel(size, device="cpu", compute_type="int8", download_root=str(MODEL_CACHE))


# ---- Hindi phonetic distance (akshar/shak ko alag karta hai)
_ASP = {"क": "ख", "ग": "घ", "ज": "झ", "ड": "ढ", "द": "ध", "ब": "भ", "त": "थ", "प": "फ", "च": "छ", "ट": "ठ"}
_ASP.update({v: k for k, v in _ASP.items()})
_DENT_RETRO = [set("तट"), set("दड"), set("नण"), set("सषश"), set("लळ")]
_MATRA_LEN = [set("िी"), set("ुू"), set("ेै"), set("ोौ")]


def _phone_dist(a, b):
    """0 = same, 1 = bilkul alag; 0.2-0.5 = shak (varga/matra/nasal ka fark)."""
    if a == b:
        return 0.0
    if not a or not b:
        return 0.5          # akshar chhoot gaya / jud gaya — aadha galti
    ca, ma = a[0], a[1:]
    cb, mb = b[0], b[1:]
    if ca == cb:
        # sirf matra ka fark
        if ma == mb:
            return 0.0
        for grp in _MATRA_LEN:
            if ma in grp and mb in grp:
                return 0.25
        if (ma == "" or mb == ""):
            return 0.3      # schwa girna
        return 0.35
    if _ASP.get(ca) == cb or _ASP.get(cb) == ca:
        return 0.4          # mahapraan ka fark (ख↔क)
    for grp in _DENT_RETRO:
        if ca in grp and cb in grp:
            return 0.5      # dantya ↔ murdhanya
    if ma == mb:
        return 0.6          # vyanjan alag, matra same
    return 1.0


def cer(want, got, phonetic=True):
    """akshar CER. phonetic=True to shak wali galti aadhi ginti hai (insaani naap)."""
    try:
        import akshar as A
        r = A.align(A.normalize(want), A.normalize(got))
        ops = r[0] if isinstance(r, tuple) else r
        if isinstance(ops, list) and ops:
            total = 0.0
            bad = 0
            for pair in ops:
                e = pair[0][0] if pair[0] else None
                h = pair[1][0] if pair[1] else None
                d = _phone_dist(e or "", h or "") if phonetic else (0.0 if e == h else 1.0)
                total += d
                if d > 0.0:
                    bad += 1
            return round(total / max(1, len(ops)), 3), {"ops": len(ops), "bad": bad}
    except Exception:
        pass
    a, b = list(want or ""), list(got or "")
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return round(d[len(b)] / max(1, len(a)), 3), {}


def judge(audio, marks=None, text=None, size="small", limit=None):
    m = model(size)
    out = {"audio": str(audio), "model": size, "lines": []}
    if marks:
        data = json.loads(Path(marks).read_text(encoding="utf-8"))
        lines = data.get("marks", data) if isinstance(data, dict) else data
        for i, mk in enumerate(lines):
            if limit and i >= limit:
                break
            x = load16k(audio, mk.get("start", 0), mk.get("dur"))
            if len(x) < SR * 0.3:
                continue
            segs, _ = m.transcribe(x, language="hi", beam_size=1, vad_filter=False)
            got = " ".join(s.text.strip() for s in segs)
            want = mk.get("text", "")
            c, _ = cer(want, got)
            out["lines"].append({"who": mk.get("who", "?"), "want": want, "got": got,
                                 "cer": round(c, 3), "verdict": "PASS" if c < 0.15 else ("WARN" if c < 0.30 else "FAIL")})
    else:
        x = load16k(audio)
        segs, _ = m.transcribe(x, language="hi", beam_size=1, vad_filter=False)
        got = " ".join(s.text.strip() for s in segs)
        c, _ = cer(text or "", got)
        out["lines"].append({"who": "-", "want": text or "", "got": got, "cer": round(c, 3),
                             "verdict": "PASS" if c < 0.15 else ("WARN" if c < 0.30 else "FAIL")})
    cers = [l["cer"] for l in out["lines"]]
    out["mean_cer"] = round(sum(cers) / len(cers), 3) if cers else None
    out["overall"] = "PASS" if cers and max(cers) < 0.25 else ("WARN" if cers and max(cers) < 0.45 else "FAIL")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--marks", default=None)
    ap.add_argument("--text", default=None)
    ap.add_argument("--model", default="small")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = judge(a.audio, a.marks, a.text, a.model, a.limit)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        for l in r["lines"]:
            print(f"{l['verdict']:5s} {l['who']:9s} cer={l['cer']:<5} got: {l['got'][:60]}")
        print(f"\nmean CER {r['mean_cer']} | overall {r['overall']}")
    return 0 if r["overall"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
