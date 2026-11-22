#!/usr/bin/env python3
"""Shabd Live — line banate hi shabd ki jaanch + sudhaar (aadhe/adhoore shabd ka ilaaj).

Kaam:
 1. risky(text)   : kaunse shabd khatarnak hain (mahapraan, sanyukt, anusvar, angrezi, ank)
 2. variants(text): usi line ke 3-4 tarah (h-spell on/off, nasal, shabd tod, dhima)
 3. best(line)    : har variant banao -> whisper se padho -> akshar CER -> sabse kam wala chuno
 4. yaad          : knowledge/shabd-fixes.json me likho (shabd -> jeeta hua roop)

Chalao:
  python shabd_live.py --text "क्षत्रिय ने ठंडक में धुआँ देखा"
  python shabd_live.py --file kahani.txt --limit 3
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys, wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
KN = HERE.parent.parent / "knowledge"
sys.path.insert(0, str(HERE.parent / "realtime"))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

SR = 22050
RISKY = ["क्ष", "ज्ञ", "त्र", "श्र", "ऋ", "ॠ", "़", "ं", "ँ", "ः", "ङ", "ञ", "ऱ", "ळ"]


def risky(text: str) -> list[str]:
    """Khatarnak hisse — inhi par live jaanch sabse zyada kaam aati hai."""
    hits = []
    for ch in RISKY:
        if ch in text:
            hits.append(ch)
    if re.search(r"[A-Za-z]", text):
        hits.append("angrezi")
    if re.search(r"[0-9]", text):
        hits.append("ank")
    return sorted(set(hits))


def variants(text: str) -> list[tuple[str, str]]:
    """(naam, text) — jitne tarah se piper ko diya ja sakta hai."""
    import hindi_shabd as HS
    out = [("asis", text)]
    hs = HS.respell(text, hspell=True, nasal=True)
    if hs != text:
        out.append(("hspell", hs))
    nos = HS.respell(text, hspell=False, nasal=True)
    if nos not in (text, hs):
        out.append(("nasal", nos))
    # shabd ko halka tod (sanyukt akshar aksar aadhe bol jaate hain)
    split = re.sub(r"([क-ह])्([क-ह])", r"\1् \2", hs)
    if split != hs:
        out.append(("split", split))
    return out


_MODEL = None


def _model():
    """Ek hi baar load — har line par naya model = memory crash (naap se mila)."""
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel("small", device="cpu", compute_type="int8", download_root="/scratch/work/models")
    return _MODEL


def _say(text: str, voice: str, out: Path, ls: float = 1.0) -> bool:
    try:
        from piper import PiperVoice
        from piper.config import SynthesisConfig
        p = Path(f"/scratch/work/voices/hi_IN-{voice}-medium.onnx")
        v = PiperVoice.load(str(p), config_path=str(p) + ".json")
        with wave.open(str(out), "wb") as w:
            v.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=ls, noise_scale=0.62, noise_w_scale=0.75))
        return out.exists() and out.stat().st_size > 2000
    except Exception:
        return False


def _hear(path: Path, m) -> str:
    import numpy as np
    from imageio_ffmpeg import get_ffmpeg_exe
    raw = subprocess.run([get_ffmpeg_exe(), "-v", "quiet", "-i", str(path), "-f", "f32le",
                          "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).copy()
    segs, _ = m.transcribe(x, language="hi", beam_size=1, vad_filter=False)
    return " ".join(s.text.strip() for s in segs)


def _cer(want: str, got: str):
    import asr_gate as G
    return G.cer(want, got, phonetic=True)


def best(text: str, voice: str = "rohan", tries_limit: int = 4, model=None, keep: Path | None = None):
    """Line ke sabse acche roop ka faisla — naap ke saath."""
    import tempfile
    m = model or _model()
    results = []
    tmpd = Path(tempfile.mkdtemp(dir="/scratch/work"))
    for name, txt in variants(text)[:tries_limit]:
        p = tmpd / f"{name}.wav"
        if not _say(txt, voice, p):
            results.append({"variant": name, "text": txt, "ok": False, "note": "render fail"})
            continue
        got = _hear(p, m)
        c, _ = _cer(text, got)
        results.append({"variant": name, "text": txt, "heard": got, "cer": c,
                        "verdict": "PASS" if c < 0.15 else ("WARN" if c < 0.30 else "FAIL")})
    good = [r for r in results if r.get("cer") is not None]
    good.sort(key=lambda r: r["cer"])
    win = good[0] if good else None
    if win and keep is not None:
        src = tmpd / f"{win['variant']}.wav"
        if src.exists():
            keep.write_bytes(src.read_bytes())
    # yaad rakho
    try:
        f = KN / "shabd-fixes.json"
        mem = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        key = f"{voice}"
        mem.setdefault(key, {})
        if win and win["cer"] < 0.30:
            mem[key][text[:60]] = {"variant": win["variant"], "cer": win["cer"]}
        f.write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass
    return {"text": text, "risky": risky(text), "tries": results, "best": win}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default=None)
    ap.add_argument("--file", default=None)
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--voice", default="rohan")
    a = ap.parse_args()
    lines = []
    if a.text:
        lines = [a.text]
    elif a.file:
        lines = [l.split(":", 1)[-1].strip() for l in Path(a.file).read_text(encoding="utf-8").splitlines() if l.strip()][: a.limit]
    m = _model()
    for t in lines:
        r = best(t, a.voice, model=m)
        b = r["best"]
        print(f"\nTEXT: {t[:70]}")
        print(f"  risky: {r['risky']}")
        for tr in r["tries"]:
            print(f"   {tr['variant']:8s} cer={tr.get('cer')} {tr.get('verdict','')} heard: {str(tr.get('heard'))[:52]}")
        if b:
            print(f"  → BEST: {b['variant']} (cer {b['cer']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
