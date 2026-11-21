#!/usr/bin/env python3
"""Voice A/B — kaunsi setting sabse insaan jaisi hai (naap kar, andaza nahi).

Naap:
  • F0 median + **F0 std** (insaan ki awaaz me sur ka utar-chadhav hota hai; robotic flat hota hai)
  • raftaar (akshar/second)
  • chupai % (ruke hue)
  • energy std (zor ka badalna)

Variants: model (v3 / v4-flash) × speaker × temperature × pace

CLI: python tools/voice_ab.py --out ab/
"""
from __future__ import annotations
import argparse, base64, json, os, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEXT = ("बेटा, आ जा पास। आज मैं तुम्हें एक कहानी सुनाती हूँ — "
        "उस जंगल में एक छोटी नदी बहती थी, और उसके किनारे एक बूढ़ा पेड़ था।")

VARIANTS = [
    {"name": "v3_priya_t06_p10",   "model": "bulbul:v3", "speaker": "priya",  "temperature": 0.6,  "pace": 1.0},
    {"name": "v3_priya_t085_p10",  "model": "bulbul:v3", "speaker": "priya",  "temperature": 0.85, "pace": 1.0},
    {"name": "v3_ishita_t075_p10", "model": "bulbul:v3", "speaker": "ishita", "temperature": 0.75, "pace": 1.0},
    {"name": "v3_suhani_t075_p105","model": "bulbul:v3", "speaker": "suhani", "temperature": 0.75, "pace": 1.05},
    {"name": "v3_ritu_t085_p10",   "model": "bulbul:v3", "speaker": "ritu",   "temperature": 0.85, "pace": 1.0},
    {"name": "v4_default_t075",    "model": "bulbul:v4-flash", "speaker": None, "temperature": 0.75, "pace": 1.0},
]


def _keys() -> list[str]:
    ks = []
    for n in ["SARVAM_API_KEY"] + [f"SARVAM_API_KEY_{i}" for i in range(2, 13)]:
        k = (os.environ.get(n) or "").strip().strip('"').strip("'")
        if k and k not in ks:
            ks.append(k)
    return ks


def _render(v: dict, out: Path, key: str) -> tuple[bool, str]:
    payload = {"text": TEXT, "language_code": "hi-IN", "model": v["model"],
               "pace": v["pace"], "pitch": 0.0, "loudness": 1.0,
               "temperature": v["temperature"], "speech_sample_rate": 24000,
               "output_audio_codec": "wav"}
    if v.get("speaker"):
        payload["speaker"] = v["speaker"]
    req = urllib.request.Request("https://api.sarvam.ai/text-to-speech",
                                 data=json.dumps(payload).encode(),
                                 headers={"api-subscription-key": key,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
        audio = base64.b64decode((data.get("audios") or [""])[0])
        if len(audio) < 5000:
            return False, "audio bahut chhota"
        out.write_bytes(audio)
        return True, ""
    except Exception as exc:
        body = ""
        try:
            body = exc.read().decode()[:160]      # type: ignore[attr-defined]
        except Exception:
            body = str(exc)[:160]
        return False, body


def _measure(p: Path, text: str) -> dict:
    import numpy as np
    from imageio_ffmpeg import get_ffmpeg_exe
    raw = subprocess.run([get_ffmpeg_exe(), "-v", "quiet", "-i", str(p), "-f", "s16le",
                          "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    if len(x) == 0:
        return {"ok": False}
    sr, N, H = 16000, 640, 320
    f0, energy = [], []
    for i in range(0, max(1, len(x) - N), H):
        seg = x[i:i + N]
        rms = float(np.sqrt((seg ** 2).mean()))
        if rms < 0.02:
            continue
        energy.append(rms)
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, "full")[N - 1:]
        lo, hi = int(sr / 350), int(sr / 80)
        if hi >= len(ac):
            continue
        k = lo + int(np.argmax(ac[lo:hi]))
        if k > 0:
            f0.append(sr / k)
    dur = len(x) / sr
    frame = int(0.05 * sr)
    quiet = sum(1 for i in range(0, len(x) - frame, frame)
                if float(np.sqrt((x[i:i + frame] ** 2).mean())) < 0.01)
    return {"ok": True, "dur": round(dur, 2),
            "cps": round(len(text) / dur, 2),
            "hz_med": int(np.median(f0)) if f0 else 0,
            "hz_std": round(float(np.std(f0)), 1) if f0 else 0,
            "energy_std": round(float(np.std(energy)), 4) if energy else 0,
            "silence_pct": round(100 * quiet / max(1, len(x) // frame), 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Sarvam voice A/B (naturalness naap)")
    ap.add_argument("--out", default=str(ROOT / "ab"))
    a = ap.parse_args()
    outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)
    keys = _keys()
    if not keys:
        print(json.dumps({"ok": False, "why": "SARVAM key nahi"}))
        return 2
    rows, ki = [], 0
    for v in VARIANTS:
        f = outdir / f"{v['name']}.wav"
        ok, err = False, ""
        for attempt in range(len(keys)):
            ok, err = _render(v, f, keys[(ki + attempt) % len(keys)])
            if ok:
                ki = (ki + attempt) % len(keys)
                break
        m = _measure(f, TEXT) if ok else {"ok": False}
        rows.append({**v, **m, "file": str(f) if ok else "", "error": err[:120]})
        print(f"{v['name']:22s} {'OK ' if ok else 'FAIL'} {m.get('hz_std','-')} std | "
              f"{m.get('cps','-')} akshar/s | {m.get('silence_pct','-')}% chup {err[:40]}")
    rep = outdir / "ab_report.json"
    rep.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    good = [r for r in rows if r.get("ok")]
    if good:
        # sabse "insaan jaisa": sur ka utar-chadhav zyada + raftaar insaani + kam chupai
        good.sort(key=lambda r: (-(r["hz_std"]), -r["cps"], r["silence_pct"]))
        print(json.dumps({"best": good[0]["name"], "hz_std": good[0]["hz_std"],
                          "report": str(rep)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
