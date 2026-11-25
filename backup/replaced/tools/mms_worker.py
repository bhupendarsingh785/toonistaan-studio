#!/usr/bin/env python3
"""mms_worker.py — ek line MMS-VITS se banao (alag process me — memory saaf rehti hai).

Sandbox 1.4GB: torch + piper ek saath nahi chalte, par akela MMS chal jaata hai.
Isliye har line alag process me (memory wapas milti hai).

  python tools/mms_worker.py --text "नमस्ते" --out a.wav [--pitch 1.1]
"""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pitch", type=float, default=1.0)
    ap.add_argument("--model", default="facebook/mms-tts-hin")
    a = ap.parse_args()
    import numpy as np
    import soundfile as sf
    import torch
    torch.set_num_threads(1)
    from transformers import VitsModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.model)
    mdl = VitsModel.from_pretrained(a.model)
    inputs = tok(a.text, return_tensors="pt")
    with torch.no_grad():
        w = mdl(**inputs).waveform[0].numpy()
    sr = mdl.config.sampling_rate
    from scipy.signal import resample_poly
    from math import gcd
    up, down = 24000, sr
    g = gcd(up, down)
    y = resample_poly(w, up // g, down // g).astype(np.float64)
    if abs(a.pitch - 1.0) > 0.02:
        import subprocess, tempfile
        import ffbin
        ff = ffbin.ensure() or "ffmpeg"
        td = tempfile.mkdtemp()
        i0, o0 = Path(td) / "i.wav", Path(td) / "o.wav"
        sf.write(str(i0), y.astype("float32"), 24000)
        subprocess.run([ff, "-v", "error", "-y", "-i", str(i0), "-af",
                        f"rubberband=pitch={a.pitch:.4f}", "-ar", "24000", str(o0)], capture_output=True)
        if o0.exists():
            z, _ = sf.read(str(o0)); z = z.mean(1) if z.ndim > 1 else z
            if len(z) < len(y): z = np.pad(z, (0, len(y) - len(z)))
            y = z[: len(y)]
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.95
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    sf.write(a.out, y.astype("float32"), 24000)
    print("OK", round(len(y) / 24000, 2), "s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
