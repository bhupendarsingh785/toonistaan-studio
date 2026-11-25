#!/usr/bin/env python3
"""Optional ECAPA-TDNN speaker-consistency scoring for ASTRA.

This is a screening signal, not proof of identity, consent, or authorization.
The upstream checkpoint is trained on VoxCeleb; Hindi/domain calibration is not
provided. Do not apply a universal pass/fail threshold without local validation.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

MODEL_ID = "speechbrain/spkrec-ecapa-voxceleb"


def _load_model(device: str = "cpu", savedir: str | None = None):
    try:
        from speechbrain.inference.speaker import EncoderClassifier
    except Exception as exc:
        raise RuntimeError("ECAPA scoring ke liye SpeechBrain install karein: pip install speechbrain") from exc
    kwargs = {"source": MODEL_ID, "run_opts": {"device": device}}
    if savedir:
        kwargs["savedir"] = savedir
    return EncoderClassifier.from_hparams(**kwargs)


def _waveform(path: str | Path):
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from scipy.signal import resample_poly
    except Exception as exc:
        raise RuntimeError("ECAPA scoring ke liye numpy, soundfile, scipy aur torch zaroori hain") from exc
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    audio, sr = sf.read(str(p), dtype="float32", always_2d=True)
    if audio.size == 0 or not np.isfinite(audio).all():
        raise ValueError(f"Invalid audio: {p}")
    mono = audio.mean(axis=1)
    if len(mono) / sr < 1.5:
        raise ValueError(f"Speaker verification ke liye kam-se-kam 1.5 sec audio chahiye: {p.name}")
    if sr != 16000:
        import math
        g = math.gcd(int(sr), 16000)
        mono = resample_poly(mono, 16000 // g, int(sr) // g).astype("float32")
    peak = float(np.max(np.abs(mono)))
    if peak < 1e-5:
        raise ValueError(f"Silent audio: {p}")
    mono = mono / max(1.0, peak)
    return torch.from_numpy(mono).unsqueeze(0)


def cosine_similarity(reference: str | Path, candidate: str | Path, *, device: str = "cpu",
                       savedir: str | None = None, model=None) -> dict:
    """Return an uncalibrated cosine similarity score; no default identity decision."""
    import torch
    model = model or _load_model(device=device, savedir=savedir)
    ref = _waveform(reference)
    cand = _waveform(candidate)
    if device.startswith("cuda"):
        ref = ref.to(device); cand = cand.to(device)
    with torch.inference_mode():
        emb_a = model.encode_batch(ref)
        emb_b = model.encode_batch(cand)
        emb_a = torch.nn.functional.normalize(emb_a.reshape(1, -1).float(), dim=-1)
        emb_b = torch.nn.functional.normalize(emb_b.reshape(1, -1).float(), dim=-1)
        score = float(torch.sum(emb_a * emb_b, dim=-1).item())
    return {"reference": str(reference), "candidate": str(candidate),
            "cosine_similarity": round(score, 6), "decision": None,
            "model": MODEL_ID, "model_domain": "VoxCeleb-trained; Hindi/domain performance not calibrated",
            "interpretation": "Screening score only. No universal threshold; not identity proof or consent verification."}


def main() -> int:
    ap = argparse.ArgumentParser(description="ASTRA optional ECAPA-TDNN speaker similarity score")
    ap.add_argument("--reference", required=True); ap.add_argument("--candidate", required=True)
    ap.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    ap.add_argument("--savedir", default=None); ap.add_argument("--out", default=None)
    a = ap.parse_args()
    try:
        result = cosine_similarity(a.reference, a.candidate, device=a.device, savedir=a.savedir)
        payload = json.dumps(result, ensure_ascii=False, indent=2)
        if a.out:
            p = Path(a.out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(payload, encoding="utf-8")
        print(payload); return 0
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}"); return 1

if __name__ == "__main__":
    raise SystemExit(main())
