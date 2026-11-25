from __future__ import annotations
import numpy as np
from scipy import signal

def build_acoustic_map(data: np.ndarray, sr: int, window_seconds: float = 0.5) -> dict:
    """Create review cues for changes in energy/spectrum; never labels sound identity."""
    x = np.asarray(data, dtype=np.float32)
    if x.ndim == 1: x = x[:, None]
    if sr <= 0 or window_seconds < 0.1:
        raise ValueError("Invalid sample rate or window size")
    mono = np.mean(x, axis=1)
    size = max(1, int(sr*window_seconds))
    frames = []
    prev_centroid = None
    for start in range(0, len(mono), size):
        seg = mono[start:start+size]
        if not len(seg): continue
        rms = float(np.sqrt(np.mean(seg.astype(np.float64)**2)))
        peak = float(np.max(np.abs(seg)))
        # centroid estimate for this short segment
        if len(seg) >= 32:
            f, p = signal.periodogram(seg, sr)
            centroid = float(np.sum(f*p)/max(np.sum(p),1e-12))
        else:
            centroid = 0.0
        energy_db = 20*np.log10(max(rms,1e-12))
        change = abs(centroid-prev_centroid) if prev_centroid is not None else 0.0
        tags = []
        if energy_db < -65: tags.append("very_quiet_acoustic_region")
        if peak > 0.95: tags.append("near_peak_region")
        if change > max(700.0, 0.35*max(centroid,1.0)): tags.append("spectral_change_review")
        frames.append({
            "start_seconds":round(start/sr,3),
            "end_seconds":round(min(len(mono),start+size)/sr,3),
            "rms_dbfs":round(float(energy_db),2),
            "peak_dbfs":round(float(20*np.log10(max(peak,1e-12))),2),
            "centroid_hz_estimate":round(centroid,1),
            "spectral_change_hz_estimate":round(change,1),
            "review_tags":tags
        })
        prev_centroid=centroid
    return {
        "schema":"astra-acoustic-map/v1",
        "window_seconds":window_seconds,
        "frames":frames,
        "semantic_labels_performed":False,
        "warning":"These are acoustic change markers only. Do not interpret them as footsteps, doors, voices, crying, vehicles, or any specific source without model/human confirmation."
    }
