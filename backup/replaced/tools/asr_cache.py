#!/usr/bin/env python3
"""ASR Cache — audio ko chhote tukdon me transcribe karke cache karta hai (tez + resumable).

2-core pod par poora file ek baar me slow hota hai; isliye 15 s ke chunks,
har chunk ka result cache (JSON) — dobara chalane par sirf naye chunk bante hain.

CLI: python tools/asr_cache.py --audio x.mp3 --cache asr.json [--model base] [--chunk 15]
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
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
    r = subprocess.run([ffmpeg(), "-v", "quiet", "-i", path, "-f", "f32le",
                        "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def transcribe(audio: str, cache: str, model="base", chunk=15.0) -> dict:
    import numpy as np
    x = decode(audio)
    cpath = Path(cache)
    state = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else {"chunks": {}}
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=4,
                     download_root="/scratch/work/whisper")
    n = len(x)
    step = int(chunk * SR)
    for i in range(0, n, step):
        key = str(i // step)
        if key in state["chunks"]:
            continue
        seg = x[i:i + step + SR // 2]           # thoda overlap (shabd na kate)
        segs, _ = m.transcribe(seg, language="hi", vad_filter=False, beam_size=1,
                               condition_on_previous_text=False, word_timestamps=True)
        words = []
        for s in segs:
            for w in (s.words or []):
                t = re.sub(r"[^\u0900-\u097F]", "", w.word or "")
                if t:
                    words.append({"w": t,
                                  "start": round(w.start + i / SR, 2),
                                  "end": round(w.end + i / SR, 2)})
        state["chunks"][key] = words
        cpath.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    words = []
    seen = set()
    for k in sorted(state["chunks"], key=lambda s: int(s)):
        for w in state["chunks"][k]:
            sig = (w["w"], round(w["start"], 1))
            if sig in seen:
                continue
            seen.add(sig)
            words.append(w)
    words.sort(key=lambda w: w["start"])
    return {"dur": round(n / SR, 1), "words": words, "chunks_done": len(state["chunks"])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--model", default="base")
    ap.add_argument("--chunk", type=float, default=15.0)
    a = ap.parse_args()
    r = transcribe(a.audio, a.cache, a.model, a.chunk)
    print(json.dumps({"dur": r["dur"], "words": len(r["words"]), "chunks": r["chunks_done"],
                      "sample": " ".join(w["w"] for w in r["words"][:18])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
