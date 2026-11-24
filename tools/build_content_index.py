#!/usr/bin/env python3
"""build_content_index.py — clips ko CONTENT se index karo (naam se nahi).

  python tools/build_content_index.py

Padhta hai: knowledge/audio-library.jsonl (naam+tag), knowledge/audio-tags-guess.jsonl
(ASR ke baad ka sach), knowledge/audio-durations.json
Likhta hai: knowledge/audio-content-index.json
"""
from __future__ import annotations
import json
from pathlib import Path

K = Path("knowledge")


def _load(p, default=None):
    f = K / p
    if not f.exists():
        return default
    return json.loads(f.read_text(encoding="utf-8"))


def main() -> int:
    lib = [json.loads(l) for l in (K / "audio-library.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    guess = [json.loads(l) for l in (K / "audio-tags-guess.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    durs = _load("audio-durations.json", {}) or {}
    quarantine = set(_load("quarantine-explicit.json", []) or [])

    gmap = {g["file"]: g for g in guess}
    idx: dict[str, list] = {}
    skipped_q = 0
    for r in lib:
        f = r.get("file")
        if not f:
            continue
        if f in quarantine:
            skipped_q += 1
            continue
        tags = list(r.get("tags") or ["other"])
        g = gmap.get(f)
        if g:
            if g.get("asr") == "speech":
                tags = ["speech/voice"]
            elif g.get("guess") and g["guess"] not in tags:
                tags = [g["guess"]]
        sec = durs.get(f) or 0
        src = r.get("tag_src") or ("asr" if (g and g.get("asr")) else "name")
        rec = {"file": f, "sec": round(float(sec), 2), "tag_src": src}
        for t in tags:
            idx.setdefault(t, []).append(rec)

    # har tag me lambi clips pehle (bed ke liye kaam ki), chhoti SFX baad me
    for t in idx:
        idx[t].sort(key=lambda r: -r["sec"])
    out = {"count": sum(len(v) for v in idx.values()), "tags": {t: v for t, v in sorted(idx.items())},
           "quarantined": skipped_q}
    (K / "audio-content-index.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("tags:", {t: len(v) for t, v in sorted(idx.items(), key=lambda kv: -len(kv[1]))})
    print("quarantine chhode:", skipped_q, "| kul entries:", out["count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
