from __future__ import annotations
from pathlib import Path
import json, math
import numpy as np
from scipy import signal
from .io import load_audio, save_json_atomic

def _db(v: float) -> float:
    return float(20.0 * math.log10(max(float(v), 1e-12)))

def _chunked_true_peak(x: np.ndarray, oversample: int = 4, chunk_seconds: float = 10.0,
                       sample_rate: int = 48000) -> float:
    """Bounded-memory oversampled peak estimate with overlap at chunk boundaries."""
    if len(x) <= 1:
        return float(np.max(np.abs(x))) if x.size else 0.0
    chunk = max(1, int(chunk_seconds * sample_rate))
    margin = 64
    peak = 0.0
    for start in range(0, len(x), chunk):
        end = min(len(x), start + chunk)
        left = max(0, start - margin)
        right = min(len(x), end + margin)
        segment = x[left:right].astype(np.float64, copy=False)
        up = signal.resample_poly(segment, oversample, 1, axis=0)
        core_start = (start - left) * oversample
        core_end = min(len(up), (end - left) * oversample)
        if core_end > core_start:
            local_peak = float(np.max(np.abs(up[core_start:core_end])))
            peak = max(peak, local_peak)
    return peak

def quality_check(path: str | Path, report_path: str | Path | None = None,
                  peak_limit_dbfs: float = -1.0,
                  true_peak_limit_dbtp: float = -1.0,
                  max_dc_dbfs: float = -50.0) -> dict:
    """
    Non-destructive post-render QA. True peak is an oversampled estimate,
    not a standards-certified BS.1770 meter. No audio is modified.
    """
    src = Path(path).resolve()
    if report_path is not None and Path(report_path).resolve() == src:
        raise ValueError("QA report path must not overwrite the audio being checked")
    x, sr, decoder = load_audio(src)
    if x.ndim != 2 or x.shape[0] == 0:
        raise ValueError("Audio is empty or has an unsupported channel layout")
    if not np.isfinite(x).all():
        raise ValueError("Decoded audio contains NaN or infinite samples")
    channels = int(x.shape[1])
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(np.square(x.astype(np.float64)))))
    dc = np.mean(x.astype(np.float64), axis=0)
    dc_peak = float(np.max(np.abs(dc)))
    # Oversampling catches inter-sample peaks missed by sample peak.
    true_peak = _chunked_true_peak(x, oversample=4, chunk_seconds=10.0, sample_rate=int(sr))
    clipped = int(np.count_nonzero(np.abs(x) >= 0.999969))
    silence_threshold = 10 ** (-60 / 20)
    silent_frames = np.mean(np.max(np.abs(x), axis=1) < silence_threshold)
    channel_rms = np.sqrt(np.mean(np.square(x.astype(np.float64)), axis=0))
    corr = None
    if channels >= 2 and np.std(x[:, 0]) > 1e-12 and np.std(x[:, 1]) > 1e-12:
        corr = float(np.corrcoef(x[:, 0], x[:, 1])[0, 1])
    peak_db = _db(peak)
    true_peak_db = _db(true_peak)
    dc_db = _db(dc_peak)
    warnings = []
    if peak_db > peak_limit_dbfs:
        warnings.append(f"Sample peak exceeds configured limit ({peak_limit_dbfs:.1f} dBFS)")
    if true_peak_db > true_peak_limit_dbtp:
        warnings.append(f"Estimated true peak exceeds configured limit ({true_peak_limit_dbtp:.1f} dBTP)")
    if clipped:
        warnings.append("Decoded samples at or near full scale detected")
    if dc_db > max_dc_dbfs:
        warnings.append(f"DC offset exceeds configured limit ({max_dc_dbfs:.1f} dBFS)")
    if silent_frames > 0.80:
        warnings.append("More than 80% of frames are near-silent; verify intentional pauses and source completeness")
    if channels >= 2 and corr is not None and corr < -0.2:
        warnings.append("Strong negative stereo correlation; check mono compatibility")
    if channels >= 2 and min(channel_rms) > 1e-9:
        imbalance = abs(_db(channel_rms[0]) - _db(channel_rms[1]))
        if imbalance > 6:
            warnings.append(f"Left/right channel RMS imbalance is {imbalance:.1f} dB")
    report = {
        "schema": "astra-audio-quality-report/v1",
        "file": str(src),
        "decoder": decoder,
        "duration_seconds": round(len(x) / sr, 3),
        "sample_rate": int(sr),
        "channels": channels,
        "sample_peak_dbfs": round(peak_db, 2),
        "estimated_true_peak_dbtp": round(true_peak_db, 2),
        "integrated_rms_dbfs": round(_db(rms), 2),
        "dc_offset_dbfs_by_channel": [round(_db(v), 2) for v in dc],
        "near_silence_percent": round(float(silent_frames) * 100, 2),
        "near_full_scale_sample_count": clipped,
        "channel_rms_dbfs": [round(_db(v), 2) for v in channel_rms],
        "stereo_correlation": round(corr, 4) if corr is not None else None,
        "warnings": warnings,
        "status": "REVIEW" if warnings else "PASS",
        "limitations": [
            "True peak is a chunked 4x oversampled estimate, not a certified BS.1770 measurement.",
            "No perceptual listening test or speech intelligibility test is performed.",
            "Silence may be intentional; review warnings in story context."
        ],
        "source_modified": False
    }
    if report_path:
        out = Path(report_path)
        save_json_atomic(out, report)
    return report
