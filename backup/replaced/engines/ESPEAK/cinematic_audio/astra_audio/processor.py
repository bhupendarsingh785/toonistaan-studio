from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import numpy as np
from scipy import signal
from .io import load_audio, save_wav
from .analyzer import analyze_array
from .quality import compare_reports
from .policy import build_policy

@dataclass
class ProcessingOptions:
    highpass_hz: float | None = None
    hum_hz: float | None = None
    hum_q: float = 25.0
    noise_start_seconds: float | None = None
    noise_end_seconds: float | None = None
    denoise_strength: float = 0.0  # 0..1; conservative by default
    normalize_peak_dbfs: float | None = None
    preserve_ambience: bool = True
    asset_profile: str = "unknown"  # speech|music|chant|ambience|sfx|unknown
    allow_non_speech_denoise: bool = False
    tags: tuple[str, ...] = ()

    def validate(self, sr: int):
        if self.highpass_hz is not None and not (0 < self.highpass_hz < sr/2):
            raise ValueError("highpass_hz must be between 0 and Nyquist")
        if self.hum_hz is not None and not (0 < self.hum_hz < sr/2):
            raise ValueError("hum_hz must be between 0 and Nyquist")
        if not 0 <= self.denoise_strength <= 1:
            raise ValueError("denoise_strength must be 0..1")
        valid_profiles = {"speech", "music", "chant", "ambience", "sfx", "unknown"}
        if self.asset_profile not in valid_profiles:
            raise ValueError(f"asset_profile must be one of {sorted(valid_profiles)}")
        if self.denoise_strength > 0 and self.asset_profile != "speech" and not self.allow_non_speech_denoise:
            raise ValueError(
                "Automatic denoise is blocked for music/chant/ambience/SFX/unknown assets. "
                "Set asset_profile='speech' only for confirmed speech, or explicitly set "
                "allow_non_speech_denoise=True after auditioning a noise-only profile."
            )
        if (self.noise_start_seconds is None) != (self.noise_end_seconds is None):
            raise ValueError("Provide both noise_start_seconds and noise_end_seconds")
        if self.noise_start_seconds is not None:
            if self.noise_start_seconds < 0 or self.noise_end_seconds <= self.noise_start_seconds:
                raise ValueError("Invalid noise profile interval")
        if self.normalize_peak_dbfs is not None and not (-12 <= self.normalize_peak_dbfs <= 0):
            raise ValueError("normalize_peak_dbfs must be between -12 and 0 dBFS")

def _filter_sos(x, sos):
    return signal.sosfiltfilt(sos, x, axis=0).astype(np.float32)

def _spectral_denoise(x, sr, start, end, strength):
    # Conservative stationary-noise spectral reduction. Profile must be noise-only.
    a, b = int(start*sr), int(end*sr)
    if a < 0 or b > len(x) or b-a < max(256, int(sr*0.15)):
        raise ValueError("Noise profile interval is too short or outside the audio")
    mono_noise = np.mean(x[a:b], axis=1)
    nperseg = min(2048, max(256, 2**int(np.floor(np.log2(max(256, sr*0.046))))))
    noverlap = nperseg*3//4
    freqs, _, zn = signal.stft(mono_noise, fs=sr, nperseg=nperseg, noverlap=min(noverlap,nperseg-1))
    noise_mag = np.mean(np.abs(zn), axis=1)
    out = np.zeros_like(x, dtype=np.float32)
    for ch in range(x.shape[1]):
        f, t, z = signal.stft(x[:,ch], fs=sr, nperseg=nperseg, noverlap=min(noverlap,nperseg-1))
        mag = np.abs(z)
        # Soft spectral floor prevents musical-noise holes and reduces aggressive gating.
        floor = noise_mag[:,None] * (1.0 + 1.5*(1-strength))
        gain = np.maximum(0.16, 1.0 - strength * (floor / np.maximum(mag, 1e-9)))
        _, rec = signal.istft(z*gain, fs=sr,
                              nperseg=nperseg, noverlap=min(noverlap,nperseg-1))
        if len(rec) < len(x): rec=np.pad(rec,(0,len(x)-len(rec)))
        out[:,ch] = rec[:len(x)]
    return out

def process_audio(input_path: str | Path, output_path: str | Path,
                  options: ProcessingOptions | None = None, overwrite: bool = False) -> dict:
    options = options or ProcessingOptions()
    input_resolved = Path(input_path).resolve()
    output_resolved = Path(output_path).resolve()
    if input_resolved == output_resolved:
        raise ValueError("Output path must not overwrite the original input audio")
    if output_resolved.exists() and not overwrite:
        raise FileExistsError(f"Processed output already exists; set overwrite=True only after backing it up: {output_resolved}")
    x, sr, decoder = load_audio(input_path)
    if not np.isfinite(x).all():
        raise ValueError("Input audio contains NaN or infinite samples; refusing processing")
    options.validate(sr)
    before = analyze_array(x, sr, str(input_path))
    y = x.copy()
    actions = []
    if options.highpass_hz:
        sos = signal.butter(3, options.highpass_hz, btype="highpass", fs=sr, output="sos")
        y = _filter_sos(y, sos); actions.append({"action":"highpass","hz":options.highpass_hz})
    if options.hum_hz:
        b, a = signal.iirnotch(options.hum_hz, options.hum_q, fs=sr)
        y = signal.filtfilt(b, a, y, axis=0).astype(np.float32)
        actions.append({"action":"hum_notch","hz":options.hum_hz,"q":options.hum_q})
    if options.denoise_strength > 0:
        if options.noise_start_seconds is None:
            raise ValueError("Denoising requires an explicitly selected noise-only profile interval")
        y = _spectral_denoise(y, sr, options.noise_start_seconds,
                              options.noise_end_seconds, options.denoise_strength)
        actions.append({"action":"spectral_noise_reduction",
                        "strength":options.denoise_strength,
                        "profile_interval":[options.noise_start_seconds, options.noise_end_seconds]})
    if options.normalize_peak_dbfs is not None:
        peak = float(np.max(np.abs(y)))
        target = 10**(options.normalize_peak_dbfs/20)
        if peak > 1e-9:
            gain = min(target/peak, 10.0)  # cap boost to +20 dB
            y = y*gain
            actions.append({"action":"peak_normalize","target_dbfs":options.normalize_peak_dbfs,
                            "gain_db":round(20*np.log10(max(gain,1e-9)),2)})
    # Safety ceiling; do not hard clip. If over, scale entire file down.
    peak = float(np.max(np.abs(y)))
    if peak > 0.98:
        y = y*(0.98/peak)
        actions.append({"action":"safety_peak_attenuation","from_peak":peak})
    output_path = save_wav(output_path, y, sr)
    after = analyze_array(y, sr, str(output_path))
    flags = []
    if after["clipped_sample_count"] > 0: flags.append("clipping_detected")
    if after["activity_ratio_estimate"] < 0.02: flags.append("very_low_activity_review")
    if options.denoise_strength > 0: flags.append("listen_for_speech_or_ambience_damage")
    quality_gate = compare_reports(before, after)
    flags.extend(quality_gate["flags"])
    policy_info = build_policy(options.tags)
    policy_info["asset_profile"] = options.asset_profile
    policy_info["non_speech_denoise_override"] = options.allow_non_speech_denoise
    report = {
        "schema":"astra-audio-report/v1",
        "status":"review_required" if flags else ("processed" if actions else "unchanged_passthrough"),
        "input":str(input_path), "output":str(output_path), "decoder":decoder,
        "options":asdict(options), "actions":actions,
        "policy":policy_info, "quality_gate":quality_gate,
        "before":before, "after":after, "review_flags":sorted(set(flags)),
        "preservation_policy":{
            "original_overwritten":False,
            "ambience_preservation_requested":options.preserve_ambience,
            "semantic_classification_performed":False,
            "uncertain_content_auto_deleted":False
        }
    }
    return report
