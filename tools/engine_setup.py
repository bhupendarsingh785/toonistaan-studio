#!/usr/bin/env python3
"""Engine Setup — chaaron engine ko install karo, chala kar dekho, sach batao.

Kaam:
  1) pip se jo aa sakta hai install karta hai (piper-tts, edge-tts, espeakng-loader)
  2) piper ka Hindi model download karta hai (models/)
  3) har engine ka ASLI render karke file ka size batata hai — bina chalaye "ok" nahi
  4) jo nahi chala, uska kaaran saaf likhta hai (key nahi / internet nahi / binary nahi)

CLI:
  python tools/engine_setup.py            # sab check (jo missing hai install karke)
  python tools/engine_setup.py --check    # sirf check, kuch install nahi
"""
from __future__ import annotations
import argparse, ctypes, json, os, subprocess, sys, time, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
PIPER_MODEL = "hi_IN-priyamvada-medium"
HF = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/"
      "priyamvada/medium/")


def _pip(*pkgs: str) -> str:
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", *pkgs],
                       capture_output=True, text=True)
    return "ok" if r.returncode == 0 else f"fail: {r.stderr.strip()[:120]}"


def ensure_piper_model() -> str:
    MODELS.mkdir(exist_ok=True)
    got = []
    for name in (f"{PIPER_MODEL}.onnx", f"{PIPER_MODEL}.onnx.json"):
        dest = MODELS / name
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        r = subprocess.run(["curl", "-sL", "-o", str(dest), HF + name],
                           capture_output=True, text=True)
        if r.returncode != 0 or not dest.exists():
            return f"model download fail ({name})"
        got.append(name)
    return "ok" if (MODELS / f"{PIPER_MODEL}.onnx").exists() else "model nahi mila"


# ------------------------------------------------------------------ render
def test_piper() -> dict:
    try:
        import piper  # noqa: F401
    except Exception:
        return {"ok": False, "why": "piper-tts install nahi"}
    m = ensure_piper_model()
    if m != "ok":
        return {"ok": False, "why": m}
    try:
        os.environ.setdefault("PIPER_MODEL_DIR", str(MODELS))
        sys.path.insert(0, str(ROOT))
        from tools import voice_provider as vp
        out = Path("/tmp/engine_piper.wav")
        t = time.time()
        ok = vp.piper_tts("नमस्ते, मैं आपकी आवाज़ हूँ।", "dadi", str(out))
        return {"ok": bool(ok), "secs": round(time.time() - t, 1),
                "kb": out.stat().st_size // 1024 if out.exists() else 0,
                "why": "" if ok else "render fail"}
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {str(e)[:100]}"}


def test_espeak() -> dict:
    """espeak-ng ka library (pip ka espeakng-loader) — asli WAV banata hai."""
    try:
        import espeakng_loader
    except Exception:
        return {"ok": False, "why": "espeakng-loader install nahi"}
    try:
        lib = ctypes.CDLL(espeakng_loader.get_library_path())
        lib.espeak_Initialize(2, 0, espeakng_loader.get_data_path().encode(), 0)
        if lib.espeak_SetVoiceByName(b"hi") != 0:
            lib.espeak_SetVoiceByName(b"en")
        chunks: list[bytes] = []

        CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short),
                              ctypes.c_int, ctypes.c_void_p)
        def _cb(wav, n, events):
            if wav and n > 0:
                chunks.append(bytes(bytearray(ctypes.cast(wav, ctypes.POINTER(
                    ctypes.c_char * (n * 2))).contents)))
            return 0
        cb = CB(_cb)
        lib.espeak_SetSynthCallback(cb)
        lib.espeak_Synth(b"namaste, main aapki aawaz hoon", 0, 0, 1, 0, 0,
                         None, None)
        audio = b"".join(chunks)
        if not audio:
            return {"ok": False, "why": "espeak ne audio nahi diya"}
        out = Path("/tmp/engine_espeak.wav")
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
            w.writeframes(audio)
        return {"ok": out.stat().st_size > 2000, "kb": out.stat().st_size // 1024,
                "why": "" if out.stat().st_size > 2000 else "file khali"}
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {str(e)[:100]}"}


def test_edge() -> dict:
    import shutil
    binary = shutil.which("edge-tts")
    if not binary:
        return {"ok": False, "why": "edge-tts install nahi"}
    out = Path("/tmp/engine_edge.mp3")
    out.unlink(missing_ok=True)
    try:
        r = subprocess.run([binary, "--voice", "hi-IN-MadhurNeural",
                            "--text", "नमस्ते", "--write-media", str(out)],
                           capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return {"ok": False, "why": "timeout (internet dheema)"}
    if r.returncode == 0 and out.exists() and out.stat().st_size > 2000:
        return {"ok": True, "kb": out.stat().st_size // 1024}
    err = (r.stderr or "").strip().splitlines()
    tail = err[-1][:110] if err else "render fail"
    if "name resolution" in tail or "Cannot connect" in tail:
        tail = "internet band (proxy) — GitHub runner par chalta hai"
    return {"ok": False, "why": tail}


def test_elevenlabs() -> dict:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return {"ok": False, "why": "key nahi (GitHub secret me daalo)"}
    try:
        import urllib.request, json as js
        req = urllib.request.Request("https://api.elevenlabs.io/v1/user",
                                     headers={"xi-api-key": key})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = js.loads(resp.read().decode())
        return {"ok": True, "note": data.get("subscription", {}).get("tier", "?")}
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {str(e)[:100]}"}


ENGINES = {"piper": test_piper, "espeak": test_espeak,
           "edge": test_edge, "elevenlabs": test_elevenlabs}
PACKAGES = {"piper": ["piper-tts"], "espeak": ["espeakng-loader"],
            "edge": ["edge-tts"], "elevenlabs": []}


def setup(install: bool = True) -> dict:
    report = {}
    for name, fn in ENGINES.items():
        if install and PACKAGES.get(name):
            _pip(*PACKAGES[name])
        report[name] = fn()
    ok = [n for n, r in report.items() if r.get("ok")]
    return {"engines": report, "ok": ok, "ok_count": len(ok),
            "total": len(ENGINES),
            "verdict": "sab taiyar" if len(ok) == len(ENGINES) else
                       ("kaam chalau" if ok else "kuch bhi taiyar nahi")}


def main() -> int:
    ap = argparse.ArgumentParser(description="chaar engine install + asli test")
    ap.add_argument("--check", action="store_true", help="sirf check, install nahi")
    a = ap.parse_args()
    rep = setup(install=not a.check)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if rep["ok_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
