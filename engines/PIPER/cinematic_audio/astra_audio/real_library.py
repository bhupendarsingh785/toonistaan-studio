"""Real-file audio library indexing and safe production-spec assembly.

The scanner computes technical descriptors from actual audio files. Filename
hints are explicitly not semantic recognition. Source files are never changed.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib, json, math
import numpy as np
from .io import load_audio, probe_audio, save_json_atomic
from .analyzer import analyze_array

AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".mp3", ".m4a", ".aac"}

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _filename_hints(name: str) -> list[str]:
    low = name.casefold().replace("_", " ").replace("-", " ")
    groups = {
        "crying_sobbing": ("cry", "crying", "sobbing", "weep", "रोना", "सिसक"),
        "laughter": ("laugh", "giggle", "chuckle", "हँसी", "हंसी"),
        "conch": ("conch", "shankh", "शंख"),
        "bell_chime": ("bell", "chime", "घंटी"),
        "peacock": ("peacock", "मोर"),
        "birds": ("bird", "birds", "चिड़िया", "पक्षी"),
        "chant": ("mantra", "chant", "om ", "gayatri", "मंत्र"),
        "music": ("music", "groove", "melody", "song", "beat"),
        "ambience": ("ambience", "ambient", "atmosphere", "roomtone", "room tone"),
        "voice": ("voice", "babble", "talk", "narration", "speech"),
        "roar": ("roar", "growl", "गर्जना"),
    }
    return [label for label, words in groups.items() if any(w in low for w in words)]

def index_audio_library(root: str | Path, output: str | Path | None = None,
                        recursive: bool = True, max_files: int = 5000) -> dict:
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    iterator = root.rglob("*") if recursive else root.iterdir()
    files = sorted(p for p in iterator if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)
    if len(files) > max_files:
        raise ValueError(f"Audio library has {len(files)} files; safety limit is {max_files}")
    assets, errors = [], []
    for path in files:
        try:
            meta = probe_audio(path)
            if meta["channels"] > 2:
                errors.append({"path": str(path), "error": f"unsupported_channels:{meta['channels']}"})
                continue
            audio, sr, decoder = load_audio(path)
            analysis = analyze_array(audio, sr, str(path))
            digest = _sha256(path)
            hints = _filename_hints(path.name)
            assets.append({
                "asset_id": digest[:20],
                "asset_name": path.name,
                "path": str(path),
                "relative_path": str(path.relative_to(root)),
                "sha256": digest,
                "file_size_bytes": path.stat().st_size,
                "duration_seconds": round(len(audio) / sr, 4),
                "sample_rate": sr,
                "channels": int(audio.shape[1]),
                "decoder": decoder,
                "filename_category_hints": hints,
                "technical_profile": {
                    "peak_dbfs": analysis["peak_dbfs"],
                    "true_peak_estimate_dbfs": analysis["approx_true_peak_dbfs"],
                    "rms_dbfs": analysis["rms_dbfs"],
                    "activity_ratio_estimate": analysis["activity_ratio_estimate"],
                    "clipped_sample_count": analysis["clipped_sample_count"],
                    "stereo_correlation": analysis["stereo_correlation"],
                    "spectral_centroid_hz_median": analysis["spectral"]["spectral_centroid_hz_median"],
                    "spectral_flux_p95": analysis["spectral"]["spectral_flux_p95"],
                },
                "license_status": "unknown_requires_verification",
                "audition_status": "not_auditioned",
                "commercial_use_allowed": False,
                "source_modified": False,
                "classification_basis": "filename hints + measured acoustic features; not semantic audio recognition",
            })
        except Exception as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    result = {
        "schema": "astra-real-audio-library-index/v1",
        "root": str(root),
        "asset_count": len(assets),
        "error_count": len(errors),
        "assets": assets,
        "errors": errors,
        "policy": {
            "source_files_modified": False,
            "semantic_audio_recognition_performed": False,
            "filename_hints_are_not_verified_labels": True,
            "unknown_licence_blocks_commercial_use": True,
            "audition_required_before_production": True,
        },
    }
    if output:
        save_json_atomic(output, result)
    return result

def build_production_spec(analysis: dict, library: dict, narration_path: str | Path,
                          approvals: dict, music_path: str | Path | None = None,
                          sample_rate: int = 48000, creativity: float = 0.25,
                          allow_unlicensed_personal_preview: bool = False) -> dict:
    """Build a render-ready mix only from explicit per-cue approvals and timestamps.

    approvals format:
      {"cue_0001":{"asset_id":"...","start_seconds":12.5,"approved":true}}
    Unknown licence may be used only for a private preview when explicitly
    enabled; output remains marked not cleared for commercial release.
    """
    from .story_intelligence import SCHEMA as STORY_SCHEMA
    if not isinstance(analysis, dict) or analysis.get("schema") != STORY_SCHEMA:
        raise ValueError("Unsupported story analysis report")
    if not isinstance(library, dict) or library.get("schema") != "astra-real-audio-library-index/v1":
        raise ValueError("Unsupported real audio library index")
    if not isinstance(approvals, dict):
        raise ValueError("approvals must be an object keyed by cue_id")
    narration = Path(narration_path).resolve()
    if not narration.is_file():
        raise FileNotFoundError(narration)
    tracks = [{"path": str(narration), "role": "narration", "auto_level": True, "gain_db": 0}]
    if music_path:
        music = Path(music_path).resolve()
        if not music.is_file():
            raise FileNotFoundError(music)
        tracks.append({"path": str(music), "role": "music", "auto_level": True, "gain_db": -3})
    by_id = {a["asset_id"]: a for a in library.get("assets", [])}
    seen_cues = set()
    inserted = []
    omitted = []
    missing = []
    commercial_clear = True
    for scene in analysis.get("scenes", []):
        for cue in scene.get("sound_cues", []):
            if cue.get("cue_type") != "sound_event":
                continue
            cue_id = cue.get("cue_id")
            approval = approvals.get(cue_id)
            if not approval:
                missing.append(cue_id)
                continue
            if approval.get("approved") is not True:
                missing.append(cue_id)
                continue
            if approval.get("omit") is True:
                reason = str(approval.get("reason", "")).strip()
                if not reason:
                    raise ValueError(f"{cue_id}: an omitted cue requires a reason")
                omitted.append({"cue_id": cue_id, "event": cue.get("event"),
                                "scene_id": scene.get("scene_id"), "user_approved": True,
                                "omitted": True, "reason": reason})
                continue
            if cue_id in seen_cues:
                raise ValueError(f"Duplicate cue_id in story analysis: {cue_id}")
            seen_cues.add(cue_id)
            asset_id = approval.get("asset_id")
            asset = by_id.get(asset_id) if asset_id else None
            if asset is None and approval.get("asset_name"):
                matches = [a for a in library.get("assets", [])
                           if a.get("asset_name") == approval.get("asset_name")]
                if len(matches) == 1:
                    asset = matches[0]
                    asset_id = asset["asset_id"]
                elif len(matches) > 1:
                    raise ValueError(f"{cue_id}: asset_name is ambiguous; use asset_id")
            if not asset:
                raise ValueError(f"{cue_id}: approved asset_id/asset_name not found in library")
            source = Path(asset["path"]).resolve()
            if not source.is_file() or _sha256(source) != asset["sha256"]:
                raise ValueError(f"{cue_id}: source asset missing or changed since library scan")
            try:
                start = float(approval["start_seconds"])
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"{cue_id}: explicit start_seconds is required")
            if not math.isfinite(start) or start < 0 or start > 3600:
                raise ValueError(f"{cue_id}: start_seconds must be between 0 and 3600")
            license_ok = str(asset.get("license_status", "")).lower() in {
                "cleared", "licensed", "approved", "public_domain", "cc0"
            }
            audition_ok = asset.get("audition_status") in {"auditioned", "approved"}
            if not license_ok:
                commercial_clear = False
                if not allow_unlicensed_personal_preview:
                    raise PermissionError(
                        f"{cue_id}: asset licence is not cleared; use only after licence verification "
                        "or explicitly enable private preview mode"
                    )
            if not audition_ok and not allow_unlicensed_personal_preview:
                raise PermissionError(f"{cue_id}: asset must be auditioned before production")
            role = "foley" if cue.get("suggested_role") == "foley" else "sfx"
            tracks.append({
                "path": str(source), "role": role, "start_seconds": start,
                "auto_level": True, "gain_db": -2, "fade_in_ms": 80,
            })
            inserted.append({
                "cue_id": cue_id, "event": cue.get("event"), "scene_id": scene.get("scene_id"),
                "asset_id": asset_id, "asset_name": asset["asset_name"],
                "start_seconds": start, "role": role, "user_approved": True,
                "licence_cleared": license_ok, "auditioned": audition_ok,
            })
    if missing:
        raise ValueError("Production blocked; unresolved/unapproved cues: " + ", ".join(missing))
    if len(tracks) > 32:
        raise ValueError("Mix exceeds 32-track limit")
    duration = probe_audio(narration)["duration_seconds"]
    scenes = []
    src_scenes = analysis.get("scenes", [])
    for i, scene in enumerate(src_scenes):
        start = scene.get("start_time_seconds")
        next_start = src_scenes[i+1].get("start_time_seconds") if i+1 < len(src_scenes) else None
        if isinstance(start, (int, float)):
            end = next_start if isinstance(next_start, (int, float)) and next_start > start else (
                duration if i == len(src_scenes)-1 else None)
            if end is not None:
                end = min(float(end), duration)
                start = float(start)
                if end > start:
                    scenes.append({"scene_id": scene["scene_id"], "start_seconds": start,
                                   "end_seconds": end, "mood": scene.get("mixer_mood_suggestion", "neutral"),
                                   "intensity": 0.45})
    return {
        "schema": "astra-story-mix-spec/v1", "sample_rate": int(sample_rate),
        "creativity": float(creativity), "memory_budget_mb": 768,
        "ducking": {"music_db": 6.0, "ambience_db": 2.0},
        "tracks": tracks, "scenes": scenes,
        "production_manifest": {
            "story_sha256": analysis.get("script_sha256"),
            "narration_path": str(narration),
            "inserted_sfx_count": len(inserted),
            "inserted_sfx": inserted,
            "omitted_cue_count": len(omitted),
            "omitted_cues": omitted,
            "commercial_release_cleared": commercial_clear,
            "private_preview_only": not commercial_clear,
            "all_cues_explicitly_approved": True,
            "all_sfx_have_explicit_timestamps": True,
            "source_assets_modified": False,
        },
    }


def produce_story_audio(script_path: str | Path, library_root: str | Path,
                        approvals: dict, narration_path: str | Path,
                        output_dir: str | Path, music_path: str | Path | None = None,
                        sample_rate: int = 48000, creativity: float = 0.25,
                        allow_unlicensed_personal_preview: bool = False) -> dict:
    """Run index -> story analysis -> approved SFX spec -> mix -> technical QA.

    This is a real local pipeline. It does not synthesize narration, infer cue
    timestamps, or certify human listening quality. Existing outputs are never
    overwritten.
    """
    from .story_intelligence import analyze_script_file
    from .story_mix import mix_story
    from .quality_check import quality_check
    outdir = Path(output_dir).resolve()
    root = Path(library_root).resolve()
    if outdir == root or root in outdir.parents:
        raise ValueError("Output directory must be outside the source audio library")
    narration = Path(narration_path).resolve()
    music = Path(music_path).resolve() if music_path else None
    if not narration.is_file():
        raise FileNotFoundError(narration)
    if music and not music.is_file():
        raise FileNotFoundError(music)
    outdir.mkdir(parents=True, exist_ok=True)
    names = ["library-index.json", "story-analysis.json", "production-mix-spec.json",
             "production-mix.wav", "mix-report.json", "qa-report.json", "production-summary.json"]
    paths = {name: outdir/name for name in names}
    existing = [str(p) for p in paths.values() if p.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite existing production outputs: " + ", ".join(existing))
    library = index_audio_library(root, paths["library-index.json"])
    analysis = analyze_script_file(script_path, paths["story-analysis.json"])
    spec = build_production_spec(
        analysis, library, narration, approvals, music, sample_rate, creativity,
        allow_unlicensed_personal_preview
    )
    save_json_atomic(paths["production-mix-spec.json"], spec)
    mix_report = mix_story(paths["production-mix-spec.json"], paths["production-mix.wav"],
                           paths["mix-report.json"], overwrite=False)
    qa = quality_check(paths["production-mix.wav"], paths["qa-report.json"])
    summary = {
        "schema": "astra-audio-production-run/v1",
        "status": "technical_qa_pass" if qa["status"] == "PASS" else "technical_qa_review",
        "library_asset_count": library["asset_count"],
        "story_scene_count": analysis["scene_count"],
        "story_sound_cue_count": analysis["summary"]["sound_event_candidate_count"],
        "inserted_sfx_count": spec["production_manifest"]["inserted_sfx_count"],
        "omitted_cue_count": spec["production_manifest"]["omitted_cue_count"],
        "duration_seconds": mix_report["duration_seconds"],
        "sample_rate": mix_report["sample_rate"],
        "track_count": mix_report["track_count"],
        "quality_status": qa["status"],
        "quality_warnings": qa["warnings"],
        "commercial_release_cleared": spec["production_manifest"]["commercial_release_cleared"],
        "human_listening_certified": False,
        "narration_generated": False,
        "source_assets_modified": False,
        "outputs": {k: str(v) for k, v in paths.items()},
        "limitations": [
            "Narration was supplied by the user; no TTS voice was generated.",
            "SFX assets and timestamps were explicitly approved; no automatic semantic placement was claimed.",
            "Technical QA is not a human listening or dialogue intelligibility certification.",
        ],
    }
    save_json_atomic(paths["production-summary.json"], summary)
    return summary
