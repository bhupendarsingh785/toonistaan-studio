#!/usr/bin/env python3
"""asr_check.py — clips me insaan ki awaaz hai ya nahi, whisper se check karo.

  python tools/asr_check.py knowledge/audio-tags-guess.jsonl --limit 140

Har clip ke liye: speech hai?, kaunsi bhasha, thoda text. Nateeja
knowledge/audio-asr-check.jsonl me judta jaata hai (resumable).
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audio_decode import decode

OUT = Path("knowledge/audio-asr-check.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tags", nargs="?", default="knowledge/audio-tags-guess.jsonl")
    ap.add_argument("--dir", default="/scratch/input")
    ap.add_argument("--limit", type=int, default=140)
    ap.add_argument("--model", default="base")
    ap.add_argument("--secs", type=int, default=25)
    a = ap.parse_args()

    rows = [json.loads(l) for l in Path(a.tags).read_text(encoding="utf-8").splitlines() if l.strip()]
    done = set()
    if OUT.exists():
        for l in OUT.read_text(encoding="utf-8").splitlines():
            if l.strip():
                try:
                    done.add(json.loads(l)["file"])
                except Exception:
                    pass
    todo = [r for r in rows if r.get("verify") == "pending" and r["file"] not in done][: a.limit]
    if not todo:
        print("kuch bacha nahi — sab check ho chuka")
        return 0

    from faster_whisper import WhisperModel
    m = WhisperModel(a.model, device="cpu", compute_type="int8")
    base = Path(a.dir)
    n_speech = 0
    with OUT.open("a", encoding="utf-8") as f:
        for r in todo:
            p = base / r["file"]
            if not p.exists():
                continue
            x = decode(str(p), secs=a.secs)
            if x is None:
                rec = {"file": r["file"], "asr": "decode_fail"}
            elif len(x) < 2000:
                rec = {"file": r["file"], "asr": "too_short", "samples": len(x)}
            else:
                try:
                    segs, info = m.transcribe(x, beam_size=1, vad_filter=True)
                    txt = " ".join(s.text.strip() for s in segs).strip()
                except Exception as e:
                    txt, info = "", None
                    print("err", r["file"][:30], repr(e)[:60], file=sys.stderr)
                sp = len(txt) >= 3
                n_speech += int(sp)
                rec = {"file": r["file"], "asr": "speech" if sp else "no_speech",
                       "lang": getattr(info, "language", None),
                       "lang_p": round(getattr(info, "language_probability", 0) or 0, 2),
                       "text": txt[:80]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    print("check hue:", len(todo), "| speech mile:", n_speech)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
