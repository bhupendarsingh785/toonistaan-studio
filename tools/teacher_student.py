#!/usr/bin/env python3
"""Teacher–Student — ElevenLabs se **seekho**, phir apne engine par lagao.

Idea (imaandar):
  • API se **awaaz ke bahar ka ilm** milta hai: har line ka audio + settings +
    naapa hua sur/raftaar/zor/rukna. **Model ke weights nahi milte** — woh band dabba hai.
  • Isliye hum **style** seekhte hain (kis bhaav me kitna sur/raftaar/zor), aur woh
    apne engine (piper/espeak/edge) par lagate hain. Baad me ElevenLabs ki zaroorat nahi.
  • Kisiki nakal (voice clone) nahi — sirf prosody ka pattern.

Kaam ke 4 step:
  1) collect()  — API se lines ka audio + meta (kharcha: har line = 1 call)
  2) measure()  — har file ka dur, F0 (sur), RMS (zor), pause (rukna)
  3) learn()    — bhaav ke hisaab se mapping banao -> astra/learned_style.json
  4) apply()    — voice_provider usi file ko pehle dekhta hai (seekha hua sach)

CLI:
  python tools/teacher_student.py plan                     # kitne call, kitna kharcha
  python tools/teacher_student.py collect --lines 12       # key chahiye
  python tools/teacher_student.py learn                    # naap se mapping
  python tools/teacher_student.py dry-run                  # bina key pipeline test
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "teacher_data"
LEARNED = ROOT / "astra" / "learned_style.json"

# bhaav -> test line
LINES = {
    "neutral":  "नमस्ते, आज हम एक नई कहानी सुनेंगे।",
    "dukh":     "मुझे बहुत तकलीफ़ हो रही है, बेटा।",
    "gussa":    "चुप रहो! मैंने तुम्हें मना किया था।",
    "khushi":   "अरे वाह! यह तो बहुत अच्छी खबर है।",
    "dar":      "वहाँ कोई है... मुझे डर लग रहा है।",
    "pyaar":    "बेटा, आ जा पास, मैं तुम्हारी माँ हूँ।",
}


def _ff() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()


def measure(path: Path, text: str = "") -> dict:
    """Awaaz ka asli naap: dur, sur (F0), zor (RMS), chup (silence)."""
    import numpy as np
    raw = subprocess.run([_ff(), "-v", "quiet", "-i", str(path), "-f", "s16le",
                          "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    if len(x) == 0:
        return {"dur": 0, "hz": 0, "rms": 0, "silence_ratio": 0}
    sr = 16000
    N, H = int(0.04 * sr), int(0.02 * sr)
    f0 = []
    for i in range(0, max(1, len(x) - N), H):
        seg = x[i:i + N]
        if float(np.sqrt((seg ** 2).mean())) < 0.02:
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, "full")[N - 1:]
        lo, hi = int(sr / 350), int(sr / 80)
        if hi >= len(ac):
            continue
        k = lo + int(np.argmax(ac[lo:hi]))
        if k > 0:
            f0.append(sr / k)
    frame = int(0.05 * sr)
    quiet = sum(1 for i in range(0, len(x) - frame, frame)
                if float(np.sqrt((x[i:i + frame] ** 2).mean())) < 0.01)
    total = max(1, len(x) // frame)
    dur = len(x) / sr
    return {"dur": round(dur, 2),
            "cps": round(len(text) / dur, 2) if (text and dur) else 0,   # akshar/second
            "hz": int(float(np.median(f0))) if f0 else 0,
            "rms": round(float(np.sqrt((x ** 2).mean())), 4),
            "silence_ratio": round(quiet / total, 3)}


def plan(lines: int = 12) -> dict:
    """Kitne call lagege — pehle batao, phir kharch karo."""
    per = max(1, lines // len(LINES))
    calls = per * len(LINES)
    return {"emotions": len(LINES), "per_emotion": per, "api_calls": calls,
            "note": "har call = 1 line (~3 s audio). Chhota test: --lines 6",
            "estimated_chars": calls * 35}


def collect(api_key: str, lines: int = 12, voice: str = "21m00Tcm4TlvDq8ikWAM") -> dict:
    """ElevenLabs se audio + meta — seekhne ke liye (kis bhaav me kya settings)."""
    import urllib.request
    per = max(1, lines // len(LINES))
    DATA.mkdir(exist_ok=True)
    rows, calls = [], 0
    for emo, text in LINES.items():
        for i in range(per):
            payload = json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
                                  "voice_settings": {"stability": 0.5, "similarity_boost": 0.75,
                                                     "style": 0.4, "use_speaker_boost": True}}).encode()
            req = urllib.request.Request(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                data=payload, headers={"xi-api-key": api_key, "Content-Type": "application/json"})
            out = DATA / f"{emo}_{i}.mp3"
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    out.write_bytes(r.read())
                calls += 1
                rows.append({"emotion": emo, "text": text, "file": str(out),
                             **measure(out, text)})
            except Exception as exc:
                rows.append({"emotion": emo, "text": text,
                             "error": f"{type(exc).__name__}: {str(exc)[:80]}"})
    meta = DATA / "teacher_meta.json"
    meta.write_text(json.dumps({"calls": calls, "rows": rows}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return {"calls": calls, "rows": len(rows), "meta": str(meta)}


def learn(meta_path: Path | None = None, source: str | None = None) -> dict:
    """Naap se mapping: bhaav -> (sur, raftaar, zor, rukna)."""
    meta_path = meta_path or (DATA / "teacher_meta.json")
    if not meta_path.exists():
        return {"ok": False, "why": "pehle collect karo (teacher_meta.json nahi)"}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    rows = [r for r in meta["rows"] if "hz" in r]
    src = source or ("elevenlabs (measured)" if meta.get("calls")
                     else f"{meta.get('mode', 'dry-run')} — apne engine ka naap")
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(r["emotion"], []).append(r)
    base = by.get("neutral") or []
    if not base:
        return {"ok": False, "why": "neutral line nahi mili — base ke bina mapping nahi"}
    b_hz = sum(r["hz"] for r in base) / len(base)
    b_dur = sum(r["dur"] for r in base) / len(base)
    b_cps = sum(r.get("cps", 0) for r in base) / len(base)
    b_rms = sum(r["rms"] for r in base) / len(base)
    style = {}
    for emo, rs in by.items():
        hz = sum(r["hz"] for r in rs) / len(rs)
        dur = sum(r["dur"] for r in rs) / len(rs)
        rms = sum(r["rms"] for r in rs) / len(rs)
        cps = sum(r.get("cps", 0) for r in rs) / len(rs)
        style[emo] = {"pitch": round(hz / b_hz, 3) if b_hz else 1.0,
                      "pace": round(cps / b_cps, 3) if b_cps else 1.0,
                      "energy": round(rms / b_rms, 3) if b_rms else 1.0,
                      "gap_ms": int(220 + 260 * max(0.0, (dur / b_dur - 1))) if b_dur else 220}
    out = {"source": src, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "style": style, "measured_from": len(rows)}
    LEARNED.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "file": str(LEARNED), "emotions": len(style), "from_rows": len(rows)}


def dry_run() -> dict:
    """Bina ElevenLabs key — pipeline sach me chalta hai? (apne engine se naap)"""
    sys.path.insert(0, str(ROOT))
    from tools import voice_provider as vp
    DATA.mkdir(exist_ok=True)
    rows = []
    for emo, text in LINES.items():
        out = DATA / f"dry_{emo}.wav"
        if vp.piper_tts(text, "dadi", str(out), bhaav=emo):
            rows.append({"emotion": emo, "text": text, "file": str(out),
                         **measure(out, text)})
    meta = DATA / "teacher_meta.json"
    meta.write_text(json.dumps({"calls": 0, "mode": "dry-run (piper)", "rows": rows},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    return {"rows": len(rows), "meta": str(meta), **learn(meta, source="piper dry-run")}


def main() -> int:
    ap = argparse.ArgumentParser(description="ElevenLabs se seekho, apne engine par lagao")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    p = sub.add_parser("collect"); p.add_argument("--lines", type=int, default=12)
    p.add_argument("--voice", default="21m00Tcm4TlvDq8ikWAM")
    sub.add_parser("learn")
    sub.add_parser("dry-run")
    a = ap.parse_args()
    if a.cmd == "plan":
        print(json.dumps(plan(), ensure_ascii=False, indent=1)); return 0
    if a.cmd == "collect":
        key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        if not key:
            print(json.dumps({"ok": False, "why": "ELEVENLABS_API_KEY nahi (GitHub secret me daalo)"},
                             ensure_ascii=False)); return 2
        print(json.dumps(collect(key, a.lines, a.voice), ensure_ascii=False)); return 0
    if a.cmd == "learn":
        print(json.dumps(learn(), ensure_ascii=False, indent=1)); return 0
    print(json.dumps(dry_run(), ensure_ascii=False, indent=1)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
