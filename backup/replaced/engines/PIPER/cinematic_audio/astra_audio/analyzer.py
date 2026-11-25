from __future__ import annotations
from pathlib import Path
import numpy as np
from scipy import signal
from .io import load_audio

def _db(v: float) -> float:
    return float(round(20*np.log10(max(float(v), 1e-12)), 2))

def _frame_rms(x: np.ndarray, frame: int, hop: int) -> np.ndarray:
    if len(x) < frame:
        x = np.pad(x, (0, frame-len(x)))
    return np.asarray([
        np.sqrt(np.mean(x[s:s+frame]**2))
        for s in range(0, len(x)-frame+1, hop)
    ], dtype=np.float64)

def _spectral_features(mono: np.ndarray, sr: int) -> dict:
    # Bound memory for very long assets: analyze up to 60 seconds sampled
    # evenly across the complete recording, and resample to <=16 kHz.
    max_samples = int(sr * 60)
    if len(mono) > max_samples:
        indices = np.linspace(0, len(mono)-max_samples, num=6, dtype=int)
        chunks = [mono[i:i+max_samples//6] for i in indices]
        mono = np.concatenate(chunks)
    if sr > 16000:
        mono = signal.resample_poly(mono, 16000, sr)
        sr = 16000
    nperseg = min(2048, max(256, 2**int(np.floor(np.log2(max(256, sr*0.046))))))
    f, _, z = signal.stft(mono, fs=sr, nperseg=nperseg,
                          noverlap=min(nperseg-1, nperseg*3//4))
    mag = np.abs(z)
    denom = np.maximum(np.sum(mag, axis=0), 1e-12)
    centroid = np.sum(f[:, None]*mag, axis=0)/denom
    bandwidth = np.sqrt(np.sum(((f[:, None]-centroid[None, :])**2)*mag, axis=0)/denom)
    # Spectral flux is a change indicator, not a semantic event classifier.
    norm = mag / np.maximum(np.linalg.norm(mag, axis=0, keepdims=True), 1e-12)
    flux = np.sqrt(np.sum(np.maximum(0, np.diff(norm, axis=1))**2, axis=0))
    return {
        "spectral_centroid_hz_median": round(float(np.median(centroid)), 2),
        "spectral_bandwidth_hz_median": round(float(np.median(bandwidth)), 2),
        "spectral_flux_p95": round(float(np.percentile(flux, 95)), 6) if flux.size else 0.0,
        "spectral_features_note": "Acoustic descriptors only; not speech/music/scene recognition."
    }

def _timeline(x: np.ndarray, sr: int, window_s: float = 1.0) -> list[dict]:
    mono = np.mean(x, axis=1)
    win = max(1, int(sr*window_s))
    out = []
    for start in range(0, len(mono), win):
        seg = mono[start:start+win]
        if not len(seg): continue
        rms = float(np.sqrt(np.mean(seg.astype(np.float64)**2)))
        peak = float(np.max(np.abs(seg)))
        out.append({
            "start_seconds": round(start/sr, 3),
            "end_seconds": round(min(len(mono), start+win)/sr, 3),
            "rms_dbfs": _db(rms),
            "peak_dbfs": _db(peak),
            "low_level": bool(rms < 1e-4),
            "review_hint": "quiet_segment_preserve_until_context_checked" if rms < 1e-4 else None
        })
    return out

def analyze_array(data: np.ndarray, sr: int, source: str = "") -> dict:
    raw = np.asarray(data)
    if raw.ndim == 1: raw = raw[:, None]
    if raw.size == 0: raise ValueError("Audio is empty")
    finite = np.isfinite(raw)
    x = np.nan_to_num(raw.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(x*x)))
    frame = max(1, int(sr*0.025)); hop = max(1, int(sr*0.010))
    mono = np.mean(x, axis=1)
    e = _frame_rms(mono, frame, hop)
    floor = max(1e-5, float(np.percentile(e, 20))*1.8)
    active = e > floor
    activity_ratio = float(np.mean(active)) if e.size else 0.0
    runs, in_run, start_i = [], False, 0
    for i, flag in enumerate(active):
        if flag and not in_run: start_i=i; in_run=True
        if in_run and (not flag or i == len(active)-1):
            end_i = i if not flag else i+1
            if end_i-start_i >= 3:
                runs.append({"start": round(start_i*hop/sr,3), "end": round(end_i*hop/sr,3)})
            in_run=False
    clip_count = int(np.sum(np.abs(x) >= 0.999))
    over_unity_count = int(np.sum(np.abs(x) > 1.0))
    duration = len(x)/sr
    channel_rms = [float(np.sqrt(np.mean(x[:,i]**2))) for i in range(x.shape[1])]
    dc = [float(np.mean(x[:,i])) for i in range(x.shape[1])]
    stereo_corr = None
    if x.shape[1] >= 2:
        a, b = x[:,0], x[:,1]
        stereo_corr = float(np.corrcoef(a,b)[0,1]) if np.std(a)>1e-12 and np.std(b)>1e-12 else None
    zcr = float(np.mean(np.signbit(mono[1:]) != np.signbit(mono[:-1]))) if len(mono)>1 else 0.0
    # Approximate inter-sample peak with 4x polyphase oversampling.
    true_peak = peak
    if len(x) > 32:
        try:
            # Chunked oversampling avoids allocating a 4x copy of long recordings.
            chunk = max(32, int(sr*2))
            for start in range(0, len(x), chunk):
                piece = x[start:min(len(x), start+chunk)]
                if len(piece) > 16:
                    true_peak = max(true_peak, float(np.max(np.abs(
                        signal.resample_poly(piece, 4, 1, axis=0)))))
        except Exception:
            pass
    crest = peak/max(rms,1e-12)
    features = _spectral_features(mono, sr)
    warnings = []
    if not np.all(finite): warnings.append("non_finite_samples_replaced_for_analysis")
    if clip_count: warnings.append("decoded_full_scale_samples_review_source_clipping_unconfirmed")
    if abs(np.mean(mono)) > 0.01: warnings.append("possible_dc_offset_review")
    if stereo_corr is not None and stereo_corr < 0.1: warnings.append("low_stereo_correlation_check_before_mono_conversion")
    if _db(true_peak) > -0.1: warnings.append("near_full_scale_true_peak_check")
    return {
        "schema":"astra-audio-analysis/v2", "source":str(source),
        "sample_rate":int(sr), "channels":int(x.shape[1]),
        "duration_seconds":round(duration,4), "samples":int(len(x)),
        "finite_sample_ratio":float(np.mean(finite)),
        "peak_dbfs":_db(peak), "approx_true_peak_dbfs":_db(true_peak),
        "rms_dbfs":_db(rms), "crest_factor_db":round(20*np.log10(max(crest,1e-12)),2),
        "dc_offset_per_channel": [round(v,8) for v in dc],
        "channel_rms_dbfs": [_db(v) for v in channel_rms],
        "stereo_correlation": round(stereo_corr,5) if stereo_corr is not None else None,
        "zero_crossing_rate":round(zcr,6),
        "clipped_sample_count":clip_count,
        "clipped_sample_ratio":float(round(clip_count/x.size,8)),
        "over_unity_sample_count":over_unity_count,
        "over_unity_sample_ratio":float(round(over_unity_count/x.size,8)),
        "activity_ratio_estimate":round(activity_ratio,4),
        "activity_regions_estimate":runs,
        "low_level_ratio_estimate":round(1-activity_ratio,4),
        "spectral":features,
        "timeline_1s":_timeline(x,sr),
        "diagnostic_warnings":warnings,
        "notes":[
            "Energy/activity and spectral changes are acoustic estimates, not semantic recognition.",
            "Quiet segments may contain room tone, breath, rain, wind, distant action, or intentional silence; never auto-delete them.",
            "No speaker identity, emotion, animal identity, sound-source, or scene understanding is claimed."
        ]
    }

def analyze_audio(path: str | Path) -> dict:
    data, sr, decoder = load_audio(path)
    result = analyze_array(data, sr, str(path))
    result["decoder"] = decoder
    return result
