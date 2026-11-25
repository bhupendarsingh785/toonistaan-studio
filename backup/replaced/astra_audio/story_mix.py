from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
import json, math
import numpy as np
from scipy import signal
from .io import load_audio, probe_audio, save_wav, save_json_atomic

ROLES = {"dialogue", "narration", "music", "ambience", "sfx", "foley", "room_tone"}
ROLE_TARGET_RMS_DBFS = {
    "dialogue": -19.0, "narration": -19.0, "music": -30.0,
    "ambience": -35.0, "room_tone": -36.0, "sfx": -27.0, "foley": -29.0
}
ROLE_GAIN_LIMITS = {
    "dialogue": (-9.0, 6.0), "narration": (-9.0, 6.0),
    "music": (-24.0, 5.0), "ambience": (-24.0, 4.0),
    "room_tone": (-24.0, 3.0), "sfx": (-24.0, 5.0), "foley": (-24.0, 4.0)
}
MOOD_RULES = {
    "peaceful": {"music_db": 1.0, "ambience_db": 1.0, "sfx_db": -1.0},
    "tense": {"music_db": 2.0, "ambience_db": -0.5, "sfx_db": 1.0},
    "action": {"music_db": 1.5, "ambience_db": -1.0, "sfx_db": 2.0},
    "sad": {"music_db": 0.5, "ambience_db": 0.5, "sfx_db": -1.5},
    "neutral": {"music_db": 0.0, "ambience_db": 0.0, "sfx_db": 0.0}
}

def _finite_number(value, name, minimum=None, maximum=None):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return number

def _rms_db(x):
    x = np.asarray(x, dtype=np.float64)
    return float(20*np.log10(max(float(np.sqrt(np.mean(x*x))) if x.size else 0.0, 1e-9)))

def _resample(x, src_sr, dst_sr):
    if src_sr == dst_sr:
        return x
    g = math.gcd(int(src_sr), int(dst_sr))
    return signal.resample_poly(x, dst_sr//g, src_sr//g, axis=0).astype(np.float32)

def _smooth_envelope(target, sr, attack_ms=35, release_ms=280):
    target = np.asarray(target, dtype=np.float32)
    if len(target) == 0:
        return target
    attack = math.exp(-1.0/max(1.0, sr*attack_ms/1000.0))
    release = math.exp(-1.0/max(1.0, sr*release_ms/1000.0))
    out = np.empty_like(target)
    prev = float(target[0])
    for i, v in enumerate(target):
        coeff = attack if v > prev else release
        prev = coeff*prev + (1-coeff)*float(v)
        out[i] = prev
    return out

def _active_rms_db(x, sr, hop_ms=20):
    # Channel-energy aggregation avoids cancellation for anti-phase stereo content.
    mono = np.sqrt(np.mean(np.square(np.asarray(x, dtype=np.float64)), axis=1))
    hop = max(1, int(sr*hop_ms/1000))
    rms = np.asarray([
        np.sqrt(np.mean(mono[i:i+hop].astype(np.float64)**2))
        for i in range(0, len(mono), hop)
    ], dtype=np.float64)
    if not rms.size:
        return -180.0
    threshold = max(1e-5, float(np.max(rms))*0.035)
    active = rms[rms > threshold]
    if not active.size:
        return _rms_db(x)
    # Median active-frame energy avoids silence dragging down sparse SFX.
    return _rms_db(active)

def _activity_envelope(x, sr, hop_ms=20):
    # Use per-frame channel RMS, not a mono sum, so wide/anti-phase voice remains detectable.
    mono = np.sqrt(np.mean(np.square(np.asarray(x, dtype=np.float64)), axis=1)).astype(np.float32)
    hop = max(1, int(sr*hop_ms/1000))
    rms = np.empty((len(mono)+hop-1)//hop, dtype=np.float32)
    for i, start in enumerate(range(0, len(mono), hop)):
        seg = mono[start:start+hop]
        rms[i] = np.sqrt(np.mean(seg.astype(np.float64)**2)) if len(seg) else 0
    # Dynamic gate adapts to quiet narration while avoiding a hard absolute gate.
    peak = float(np.max(rms)) if len(rms) else 0
    threshold = max(1e-7, peak*0.075)
    active = np.clip((rms-threshold)/(threshold*2.5), 0, 1)
    return np.repeat(active, hop)[:len(x)]

def _scene_gain_curve(n, sr, scenes, role, creativity):
    curve = np.ones(n, dtype=np.float32)
    for scene in scenes:
        mood = str(scene.get("mood", "neutral")).lower()
        if mood not in MOOD_RULES:
            raise ValueError(f"Unsupported mood: {mood}. Choose {sorted(MOOD_RULES)}")
        start_s = _finite_number(scene.get("start_seconds", 0), "scene start_seconds", 0)
        end_s = _finite_number(scene.get("end_seconds", n/sr), "scene end_seconds", 0)
        if start_s >= n/sr:
            raise ValueError("Scene start_seconds must fall within the rendered timeline")
        if end_s <= start_s:
            raise ValueError("Every scene must have end_seconds greater than start_seconds")
        # A scene may end slightly beyond the longest audio stem; safely clip its
        # processing window to the actual render duration.
        start = int(start_s*sr)
        end = min(n, int(end_s*sr))
        if end <= start:
            continue
        rule = MOOD_RULES[mood]
        key = "music_db" if role == "music" else ("ambience_db" if role in {"ambience","room_tone"} else ("sfx_db" if role in {"sfx","foley"} else None))
        if key is None:
            continue
        intensity = _finite_number(scene.get("intensity", 0.5), "scene intensity", 0, 1)
        # Mood-based creative variation is intentionally modest and user-scalable.
        delta_db = rule[key] * (0.35 + 0.65*intensity) * creativity
        gain = 10**(delta_db/20)
        fade = max(1, min(int(0.35*sr), (end-start)//4))
        local = np.ones(end-start, dtype=np.float32)*gain
        if fade > 1:
            ramp = np.linspace(0, 1, fade, dtype=np.float32)
            local[:fade] = 1 + (gain-1)*ramp
            local[-fade:] = 1 + (gain-1)*ramp[::-1]
        curve[start:end] *= local
    return curve

def mix_story(spec_path: str | Path, output_path: str | Path, report_path: str | Path | None = None,
              overwrite: bool = False) -> dict:
    """Story-aware adaptive stem mixer. It never invents or downloads sound assets."""
    spec_path = Path(spec_path).resolve()
    if not spec_path.is_file():
        raise FileNotFoundError(f"Mix spec not found: {spec_path}")
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid UTF-8 JSON mix spec: {exc}") from exc
    if not isinstance(spec, dict):
        raise ValueError("Mix spec root must be a JSON object")
    if spec.get("review_required") is True or spec.get("schema") == "astra-story-mix-spec-review/v1":
        raise ValueError("This is a review-only story spec. Resolve scene timing and approval before rendering.")
    tracks_spec = spec.get("tracks", [])
    if not isinstance(tracks_spec, list) or not tracks_spec:
        raise ValueError("Mix spec must contain a non-empty tracks array")
    if len(tracks_spec) > 32:
        raise ValueError("At most 32 tracks are supported in one mix")
    creativity = _finite_number(spec.get("creativity", 0.5), "creativity", 0, 1)
    scenes = spec.get("scenes", [])
    if not isinstance(scenes, list):
        raise ValueError("scenes must be a JSON array")
    if len(scenes) > 10000:
        raise ValueError("At most 10000 scene entries are supported")
    if any(not isinstance(scene, dict) for scene in scenes):
        raise ValueError("Every scene entry must be a JSON object")
    target_sr = spec.get("sample_rate", 0)
    target_sr = int(target_sr) if target_sr else None
    if target_sr is not None and not 8000 <= target_sr <= 192000:
        raise ValueError("sample_rate must be between 8000 and 192000 Hz")
    memory_budget = int(spec.get("memory_budget_mb", 768))
    if memory_budget < 128 or memory_budget > 8192:
        raise ValueError("memory_budget_mb must be between 128 and 8192")

    # Probe every stem before decoding waveforms so the memory guard is genuinely preflight.
    prepared = []
    max_len_estimate = 0
    max_channels = 1
    for index, item in enumerate(tracks_spec):
        if not isinstance(item, dict):
            raise ValueError(f"Track #{index+1} must be a JSON object")
        if "path" not in item or not isinstance(item["path"], str) or not item["path"].strip():
            raise ValueError(f"Track #{index+1} requires a non-empty path")
        role = str(item.get("role", "unknown")).lower()
        if role not in ROLES:
            raise ValueError(f"Unknown role '{role}'. Valid roles: {sorted(ROLES)}")
        path = Path(item["path"])
        if not path.is_absolute() and not path.exists():
            path = spec_path.parent / path
        path = path.resolve()
        start_seconds = _finite_number(item.get("start_seconds",0.0), "track start_seconds", 0, 3600)
        info = probe_audio(path)
        if info["channels"] > 2:
            raise ValueError(
                f"Unsupported channel count ({info['channels']}). This mixer currently supports mono/stereo only; "
                "convert multichannel audio with an explicit channel map first."
            )
        if target_sr is None:
            target_sr = info["sample_rate"]
        estimated_frames = int(math.ceil(info["frames"] * target_sr / info["sample_rate"]))
        start_sample = int(start_seconds * target_sr)
        max_len_estimate = max(max_len_estimate, start_sample + estimated_frames)
        max_channels = max(max_channels, info["channels"])
        prepared.append({"spec":item,"role":role,"path":path,"info":info,
                         "start_sample":start_sample})
    estimated_bytes = int(max_len_estimate * max_channels * (4*len(prepared) + 16))
    if estimated_bytes > memory_budget * 1024 * 1024:
        raise MemoryError(
            f"Preflight estimates about {estimated_bytes/1024/1024:.0f} MiB of working memory, "
            f"above the configured {memory_budget} MiB budget. Split into shorter reels or raise the budget only if RAM is available."
        )

    loaded = []
    for item in prepared:
        data, sr, decoder = load_audio(item["path"])
        if data.shape[0] != item["info"]["frames"] or sr != item["info"]["sample_rate"]:
            raise RuntimeError(f"Audio changed between metadata preflight and decode: {item['path']}")
        data = _resample(data, sr, target_sr)
        loaded.append({"spec":item["spec"],"role":item["role"],"path":str(item["path"]),
                       "data":data,"decoder":decoder,"start_sample":item["start_sample"]})
    max_len = max(t["start_sample"]+len(t["data"]) for t in loaded)
    # Keep the estimate based on decoded frame counts too, in case a decoder's
    # metadata differs slightly from the waveform length.
    estimated_bytes = int(max_len * max(t["data"].shape[1] for t in loaded) * (4*len(loaded) + 16))
    if estimated_bytes > memory_budget * 1024 * 1024:
        raise MemoryError("Decoded waveform length exceeded the preflight memory estimate; no output was written.")
    channels = max(t["data"].shape[1] for t in loaded)
    # Keep mono/stereo track channel layout sensible; duplicate mono to stereo only if needed.
    for t in loaded:
        d=t["data"]
        if d.shape[1] == 1 and channels == 2:
            d=np.repeat(d,2,axis=1)
        elif d.shape[1] < channels:
            d=np.pad(d,((0,0),(0,channels-d.shape[1])))
        start=t["start_sample"]
        end=start+len(d)
        placed=np.zeros((max_len,channels),dtype=np.float32)
        placed[start:end]=d.astype(np.float32)
        fade_in_ms = _finite_number(t["spec"].get("fade_in_ms",0.0), "fade_in_ms", 0, 10000)
        fade_out_ms = _finite_number(t["spec"].get("fade_out_ms",0.0), "fade_out_ms", 0, 10000)
        fi=min(len(d),int(fade_in_ms*target_sr/1000))
        fo=min(len(d),int(fade_out_ms*target_sr/1000))
        if fi>1:
            placed[start:start+fi] *= np.linspace(0,1,fi,dtype=np.float32)[:,None]
        if fo>1:
            placed[end-fo:end] *= np.linspace(1,0,fo,dtype=np.float32)[:,None]
        t["data"]=placed
    dialogue_tracks=[t for t in loaded if t["role"] in {"dialogue","narration"}]
    dialogue_activity=np.zeros(max_len,dtype=np.float32)
    for t in dialogue_tracks:
        dialogue_activity=np.maximum(dialogue_activity,_activity_envelope(t["data"],target_sr))
    mix=np.zeros((max_len,channels),dtype=np.float64)
    track_reports=[]
    duck = spec.get("ducking", {})
    if not isinstance(duck, dict):
        raise ValueError("ducking must be a JSON object")
    duck_depth = _finite_number(duck.get("music_db", 6.0), "ducking.music_db", 0, 12)
    ambience_duck = _finite_number(duck.get("ambience_db", 2.0), "ducking.ambience_db", 0, 8)
    duck_strength = _smooth_envelope(dialogue_activity,target_sr)
    for t in loaded:
        role=t["role"]; data=t["data"]
        measured=_active_rms_db(data,target_sr)
        target=ROLE_TARGET_RMS_DBFS[role]
        auto_level_value = t["spec"].get("auto_level", True)
        if not isinstance(auto_level_value, bool):
            raise ValueError("auto_level must be a boolean")
        auto_level = auto_level_value
        requested_auto_gain_db=(target-measured) if auto_level else 0.0
        auto_gain_db=float(np.clip(requested_auto_gain_db,*ROLE_GAIN_LIMITS[role])) if auto_level else 0.0
        auto_level_clamped=bool(auto_level and abs(requested_auto_gain_db-auto_gain_db)>0.05)
        user_gain = _finite_number(t["spec"].get("gain_db",0.0), "track gain_db", -24, 12)
        scene_curve=_scene_gain_curve(max_len,target_sr,scenes,role,creativity)
        gain_curve=scene_curve.copy()
        duck_applied=0.0
        if dialogue_tracks and role == "music":
            duck_applied=duck_depth
            gain_curve *= 10**((-duck_depth*duck_strength)/20)
        elif dialogue_tracks and role in {"ambience","room_tone"}:
            duck_applied=ambience_duck
            gain_curve *= 10**((-ambience_duck*duck_strength)/20)
        gain_curve *= 10**((auto_gain_db+user_gain)/20)
        mixed_track=data.astype(np.float64)*gain_curve[:,None]
        mix += mixed_track
        track_reports.append({
            "path":t["path"],"role":role,"decoder":t["decoder"],
            "start_seconds":round(t["start_sample"]/target_sr,3),
            "fade_in_ms":float(t["spec"].get("fade_in_ms",0.0)),
            "fade_out_ms":float(t["spec"].get("fade_out_ms",0.0)),
            "input_rms_dbfs":round(measured,2),
            "role_target_rms_dbfs":target,
            "requested_auto_level_adjustment_db":round(requested_auto_gain_db,2),
            "automatic_level_adjustment_db":round(auto_gain_db,2),
            "auto_level_enabled":auto_level,
            "auto_level_was_clamped":auto_level_clamped,
            "user_gain_db":user_gain,
            "ducking_max_db":duck_applied,
            "scene_creativity":creativity,
            "output_contribution_rms_dbfs":round(_rms_db(mixed_track),2),
            "source_modified":False
        })
    # Global peak guard scales all stems together, preserving relative mix.
    peak=float(np.max(np.abs(mix))) if mix.size else 0.0
    peak_guard_db=0.0
    if peak > 0.95:
        scale=0.95/peak
        mix *= scale
        peak_guard_db=20*math.log10(scale)
    output_candidate=Path(output_path).resolve()
    report_candidate=Path(report_path).resolve() if report_path else None
    source_resolved={Path(t["path"]).resolve() for t in loaded}
    protected_paths=source_resolved | {spec_path}
    if output_candidate in protected_paths:
        raise ValueError("Output path must not overwrite the mix spec or any input audio track")
    if output_candidate.exists() and not overwrite:
        raise FileExistsError(f"Output already exists; pass overwrite=True only after backing it up: {output_candidate}")
    if report_candidate is not None and report_candidate in protected_paths:
        raise ValueError("Report path must not overwrite the mix spec or any input audio track")
    if report_candidate is not None and report_candidate == output_candidate:
        raise ValueError("Report path and audio output path must be different")
    if report_candidate is not None and report_candidate.exists() and not overwrite:
        raise FileExistsError(f"Report already exists; pass overwrite=True only after backing it up: {report_candidate}")
    output=save_wav(output_candidate,mix.astype(np.float32),target_sr)
    report={
        "schema":"astra-story-aware-mix-report/v1",
        "output":str(output),
        "duration_seconds":round(max_len/target_sr,3),
        "sample_rate":target_sr,
        "track_count":len(loaded),
        "scenes":scenes,
        "resource_safety":{
            "processing_mode":"in_memory",
            "estimated_working_set_mb":round(estimated_bytes/1024/1024,1),
            "configured_memory_budget_mb":memory_budget,
            "preflight_memory_guard_passed":True,
            "long_form_note":"For very long episodes, render shorter reels; this implementation is not a streaming/chunked stem mixer."
        },
        "creativity":creativity,
        "dialogue_driven_ducking_enabled":bool(dialogue_tracks),
        "global_peak_guard_gain_db":round(peak_guard_db,2),
        "output_peak_dbfs":round(20*math.log10(max(float(np.max(np.abs(mix))),1e-9)),2) if mix.size else None,
        "tracks":track_reports,
        "creative_policy":{
            "uses_only_user_supplied_tracks":True,
            "generates_or_downloads_new_sfx":False,
            "story_mood_adjustments_are_modest":True,
            "user_track_gain_is_respected_as_an_offset":True,
            "auto_leveling_is_role_aware_and_bounded":True,
            "level_adjustment_clamp_is_reported":True,
            "dialogue_ducking_is_smooth_not_hard_gating":True,
            "source_files_overwritten":False,
            "note":"Role/mood tags are user-provided metadata. Automatic voice/source recognition is not performed."
        },
        "warnings":[
            f"Scene {i+1} end time was clipped to the actual render duration"
            for i, scene in enumerate(scenes)
            if isinstance(scene, dict) and _finite_number(scene.get("end_seconds", max_len/target_sr),
                                                          "scene end_seconds", 0) > max_len/target_sr
        ]
    }
    if report_candidate is not None:
        save_json_atomic(report_candidate, report)
    return report
