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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "realtime"))
SR = 16000
MODEL_CACHE = Path("/scratch/work/models")


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


def cer(want, got):
    """akshar-level CER. akshar.align() -> (ops, E, H) tuple deta hai."""
    try:
        import akshar as A
        r = A.align(A.normalize(want), A.normalize(got))
        ops = r[0] if isinstance(r, tuple) else r
        if isinstance(ops, list) and ops:
            bad = 0
            for pair in ops:
                e = pair[0][0] if pair[0] else None
                h = pair[1][0] if pair[1] else None
                if e != h:
                    bad += 1
            return bad / max(1, len(ops)), {"ops": len(ops), "bad": bad}
    except Exception:
        pass
    a, b = list(want or ""), list(got or "")
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return (d[len(b)] / max(1, len(a))), {}


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
                                 "cer": round(c, 3), "verdict": "PASS" if c < 0.25 else ("WARN" if c < 0.45 else "FAIL")})
    else:
        x = load16k(audio)
        segs, _ = m.transcribe(x, language="hi", beam_size=1, vad_filter=False)
        got = " ".join(s.text.strip() for s in segs)
        c, _ = cer(text or "", got)
        out["lines"].append({"who": "-", "want": text or "", "got": got, "cer": round(c, 3),
                             "verdict": "PASS" if c < 0.25 else ("WARN" if c < 0.45 else "FAIL")})
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
