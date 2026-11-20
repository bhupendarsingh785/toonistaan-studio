#!/usr/bin/env python3
"""Streaming WAV quality diagnostics for ASTRA generated audio.
These objective checks do not replace listening tests or speaker-identity evaluation.
"""
from __future__ import annotations
from pathlib import Path
import math

def inspect_wav(path: str | Path, *, min_duration_sec: float = 0.05,
                silence_rms_threshold: float = 1e-4, clipping_peak: float = 0.9995) -> dict:
    try:
        import numpy as np
        import soundfile as sf
    except Exception as exc:
        raise RuntimeError("Audio QA needs numpy and soundfile") from exc
    p=Path(path)
    if not p.is_file(): raise FileNotFoundError(p)
    info=sf.info(str(p))
    if info.format != "WAV": raise ValueError("Output must be a WAV file")
    if info.frames <= 0 or info.samplerate < 8000 or info.channels not in (1,2):
        raise ValueError("Unsupported/empty WAV properties")
    frames=0; sum_sq=0.0; peak=0.0; clipped=0; quiet=0
    total=info.frames*info.channels
    with sf.SoundFile(str(p),mode="r") as f:
        while True:
            block=f.read(65536,dtype="float32",always_2d=True)
            if len(block)==0: break
            if not np.isfinite(block).all(): raise ValueError("WAV contains NaN/Inf")
            absb=np.abs(block)
            peak=max(peak,float(absb.max(initial=0.0)))
            clipped += int(np.count_nonzero(absb >= clipping_peak))
            sum_sq += float(np.sum(block.astype(np.float64)**2))
            quiet += int(np.count_nonzero(absb < silence_rms_threshold))
            frames += len(block)
    duration=frames/info.samplerate
    if duration < min_duration_sec: raise ValueError("WAV is too short")
    rms=math.sqrt(sum_sq/max(1,total))
    clip_ratio=clipped/max(1,total); quiet_ratio=quiet/max(1,total)
    warnings=[]
    if rms < 0.003: warnings.append("very_low_rms")
    if clip_ratio > 0.001: warnings.append("clipping_detected")
    if quiet_ratio > 0.98: warnings.append("mostly_silence")
    return {"path":str(p),"sample_rate":int(info.samplerate),"channels":int(info.channels),
            "duration_sec":round(duration,3),"peak":round(peak,6),"rms":round(rms,6),
            "clipped_sample_ratio":round(clip_ratio,8),"quiet_sample_ratio":round(quiet_ratio,6),
            "warnings":warnings,"pass":not ("mostly_silence" in warnings or "clipping_detected" in warnings)}
