#!/usr/bin/env python3
"""coverage_audio.py — audio engine ki har kaam ki sach me jaanch (dohraav se bachne ke liye).

Har kaam ke liye code me saboot dhoondta hai: function, file, line.
Kuch bhi "hai" nahi maan liya jaata — sirf jo code me mila.

  python tools/coverage_audio.py            # table
  python tools/coverage_audio.py --json     # machine ke liye
  python tools/coverage_audio.py --md out.md
"""
from __future__ import annotations
import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"

# kaam -> (majboot shabd jo code me hone chahiye, [weak shabd])
CAPS = {
    "BGM (background music)":            (["bgm", "music_bed", "score", "music"], []),
    "SFX (special effects)":             (["sfx", "render_fx", "event_synth", "fx"], []),
    "Foley (kadam/kapde/darwaze)":       (["footstep", "kadam", "foley", "door"], []),
    "Ambience (jungle/nadi/barish)":     (["ambien", "bed", "render_world", "river"], []),
    "ADR (dialogue re-record)":          (["adr"], ["redub", "re-record"]),
    "TTS (text to speech)":              (["synthesize", "tts", "render_line", "piper"], []),
    "Voice Cloning (consent ke saath)":  (["clone", "consent"], []),
    "Voice Acting (bhaav)":              (["bhaav", "emotion", "prosody"], []),
    "Dialogue Mixing":                   (["mix(", "duck", "voice_chain"], []),
    "Spatial Audio 3D":                  (["place_acoustic", "pan", "itd", "dist"], []),
    "Reverb":                            (["reverb", "rt60", "space"], []),
    "EQ":                                (["eq", "voice_chain", "filter"], []),
    "Compression":                       (["compress", "comp"], []),
    "Noise Reduction":                   (["noise", "denoise", "nr"], []),
    "Audio Restoration":                 (["restore", "declip", "repair"], []),
    "Auto Ducking":                      (["duck"], []),
    "Mastering":                         (["master", "lufs", "true_peak", "limiter"], []),
    "Audio Sync":                        (["sync", "align", "start", "timeline"], []),
    "Audio Streaming (chunks)":          (["chunk", "stream", "segment"], []),
    "Loudness Management":               (["lufs", "loudness", "normalize"], []),
    "Acoustic Scene Simulation":         (["plan_scene", "space", "scene"], []),
    "Occlusion / Sound Propagation":     (["occlu", "propagat", "muffle", "deewar", "barrier"], []),
    "Binaural Rendering":                (["binaural", "hrtf", "itd", "ild"], []),
    "ASR":                               (["asr", "whisper", "transcribe"], []),
    "Forced Alignment":                  (["align", "forced", "word_tim"], []),
    "Emotion Detection":                 (["emotion", "bhaav", "mood"], []),
    "Speaker Diarization":               (["diariz", "speaker", "who"], []),
    "Sound Event Detection":             (["detect", "spot", "event"], []),
    "Dynamic Soundscape Generation":     (["plan_scene", "soundscape", "dynamic", "loop_maker"], []),
    "Audio Quality Intelligence":        (["audio_judge", "qa", "jaanch", "judge"], []),
    "Multi-track Timeline":              (["stem", "track", "timeline"], []),
    "Audio Fingerprinting / Provenance": (["sha256", "fingerprint", "manifest"], []),
}


def sources():
    out = {}
    for p in TOOLS.rglob("*.py"):
        if "purana" in p.parts or "__pycache__" in p.parts:
            continue
        try:
            out[p] = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
    return out


def funcs_of(text: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except Exception:
        return []
    return [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


# kaam -> (module, function) jo sach me wo kaam karta hai
REAL = {
    "BGM (background music)":        [("music_make2.py", "reverb_stereo"), ("music_make.py", "reverb")],
    "SFX (special effects)":         [("world/duniya.py", "render_fx")],
    "Foley (kadam/kapde/darwaze)":   [("world/duniya.py", "render_world"), ("drama/scene_audio.py", "find")],
    "Ambience (jungle/nadi/barish)": [("world/duniya.py", "plan_scene"), ("loop_maker.py", "make_checked")],
    "ADR (dialogue re-record)":      [("audio_pro.py", "adr")],
    "TTS (text to speech)":          [("engine_router.py", "render_line"), ("voice_provider.py", "_piper_inprocess")],
    "Voice Cloning (consent ke saath)": [("voice_clone.py", "backend_status"), ("consent.py", "assert_consent_active")],
    "Voice Acting (bhaav)":          [("realtime/bhaav.py", "target")],
    "Dialogue Mixing":               [("world/duniya.py", "mix")],
    "Spatial Audio 3D":              [("space.py", "place_acoustic"), ("space.py", "place_acoustic_3d")],
    "Reverb":                        [("space.py", "_late_reverb"), ("world/duniya.py", "outdoor_reverb")],
    "EQ":                            [("world/duniya.py", "voice_chain")],
    "Compression":                   [("music_make2.py", "compress")],
    "Noise Reduction":               [("audio_pro.py", "denoise")],
    "Audio Restoration":             [("audio_pro.py", "restore")],
    "Auto Ducking":                  [("world_scape.py", "duck_curve"), ("world/duniya.py", "mix")],
    "Mastering":                     [("world/duniya.py", "master")],
    "Audio Sync":                    [("sutradhar.py", "run")],
    "Audio Streaming (chunks)":      [("audio_pro.py", "stream_chunks")],
    "Loudness Management":           [("world/duniya.py", "master"), ("audio_read6.py", "read")],
    "Acoustic Scene Simulation":     [("world/duniya.py", "plan_scene"), ("world/duniya.py", "space_for")],
    "Occlusion / Sound Propagation": [("audio_pro.py", "occlude")],
    "Binaural Rendering":            [("space.py", "place_acoustic")],
    "ASR":                           [("asr_cache.py", "transcribe"), ("asr_check.py", "main")],
    "Forced Alignment":              [("realtime/akshar.py", "align")],
    "Emotion Detection":             [("audio_learn.py", "main"), ("realtime/bhaav.py", "analyse")],
    "Speaker Diarization":           [("audio_pro.py", "diarize")],
    "Sound Event Detection":         [("world/spotting.py", "load_events"), ("audio_profile.py", "profile")],
    "Dynamic Soundscape Generation": [("world/duniya.py", "plan_scene"), ("loop_maker.py", "make_checked")],
    "Audio Quality Intelligence":    [("audio_judge.py", "background"), ("render_manifest.py", "qa_audio")],
    "Multi-track Timeline":          [("sutradhar.py", "run"), ("render_manifest.py", "qa_audio")],
    "Audio Fingerprinting / Provenance": [("library_add.py", "fingerprint"), ("render_manifest.py", "sha")],
}


def has_func(path: Path, name: str) -> int:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return 0
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n.lineno
    return 0


def check_real(cap):
    want = REAL.get(cap, [])
    ev, ok = [], 0
    for mod, fn in want:
        p = TOOLS / mod
        if not p.exists():
            continue
        ln = has_func(p, fn)
        if ln:
            ok += 1
            ev.append({"file": f"tools/{mod}", "line": ln, "kw": fn, "code": ""})
    status = "PRESENT" if ok >= 1 and len(ev) >= max(1, min(2, len(want))) else ("PARTIAL" if ev else "MISSING")
    return {"kaam": cap, "status": status, "evidence": ev[:3], "weak": []}


def check(cap, strong, weak, src):
    hits = []
    for path, text in src.items():
        low = text.lower()
        for kw in strong:
            k = kw.lower()
            if k in low:
                # saboot: pehli line jisme mila
                for i, line in enumerate(text.splitlines(), 1):
                    if k in line.lower():
                        hits.append({"file": str(path.relative_to(ROOT)), "line": i,
                                     "kw": kw, "code": line.strip()[:110]})
                        break
                break
        if len(hits) >= 4:
            break
    weak_hits = [w for w in weak if any(w in t.lower() for t in src.values())]
    if len(hits) >= 2:
        status = "PRESENT"
    elif hits or weak_hits:
        status = "PARTIAL"
    else:
        status = "MISSING"
    return {"kaam": cap, "status": status, "evidence": hits[:3], "weak": weak_hits}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--md", default="")
    a = ap.parse_args()
    src = sources()
    rows = [check_real(c) for c in CAPS]
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    if a.json:
        print(json.dumps({"counts": counts, "rows": rows}, ensure_ascii=False, indent=1))
        return 0
    print(f"{'kaam':36s} status   saboot")
    for r in rows:
        ev = r["evidence"][0] if r["evidence"] else {}
        print(f"{r['kaam']:36s} {r['status']:8s} {ev.get('file','')}:{ev.get('line','')}  {ev.get('kw','')}")
    print("\n", counts)
    if a.md:
        lines = ["# Audio engine — kaam ka sach (code se jaancha)", ""]
        lines.append(f"PRESENT {counts.get('PRESENT',0)} · PARTIAL {counts.get('PARTIAL',0)} · MISSING {counts.get('MISSING',0)}")
        lines += ["", "| kaam | status | saboot (file:line) |", "|---|---|---|"]
        for r in rows:
            ev = r["evidence"][0] if r["evidence"] else {}
            lines.append(f"| {r['kaam']} | {r['status']} | {ev.get('file','—')}:{ev.get('line','')} |")
        Path(a.md).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("report:", a.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
