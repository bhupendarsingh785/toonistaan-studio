"""Consent-aware dataset manifest builder for future voice-model fine-tuning."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

AUDIO_EXTS = {".wav", ".flac", ".ogg", ".mp3", ".m4a"}


def build_voice_dataset_manifest(root: str | Path, output: str | Path, *,
                                  consent_file: str | Path,
                                  min_clip_seconds: float = 1.0,
                                  max_clip_seconds: float = 20.0) -> dict[str, Any]:
    """Index root/SPEAKER_ID/audio files; consent JSON maps IDs to explicit permission.

    This prepares data only. It does not train, clone, or synthesize a voice.
    """
    import soundfile as sf
    root = Path(root).expanduser().resolve()
    consent_path = Path(consent_file).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    consent = json.loads(consent_path.read_text(encoding="utf-8"))
    if not isinstance(consent, dict):
        raise ValueError("consent_file must be a JSON object keyed by speaker ID")
    records = []
    errors = []
    for speaker_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        speaker = speaker_dir.name
        permission = consent.get(speaker)
        if not isinstance(permission, dict) or permission.get("voice_training_consent") is not True:
            errors.append({"speaker_id": speaker, "reason": "explicit voice_training_consent missing"})
            continue
        for audio in sorted(p for p in speaker_dir.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS):
            try:
                info = sf.info(str(audio))
                duration = float(info.duration)
                if not min_clip_seconds <= duration <= max_clip_seconds:
                    errors.append({"file": str(audio), "reason": "duration_out_of_range", "duration": duration})
                    continue
                records.append({"speaker_id": speaker, "path": str(audio), "duration_seconds": duration,
                                "sample_rate": info.samplerate, "channels": info.channels,
                                "consent_reference": permission.get("consent_reference")})
            except Exception as exc:
                errors.append({"file": str(audio), "reason": str(exc)})
    if not records:
        raise ValueError("No eligible audio clips found; check speaker folders, formats and explicit consent")
    speakers = sorted({r["speaker_id"] for r in records})
    if len(speakers) < 2:
        warning = "Only one consented speaker found; do not claim a general multi-speaker model can be trained."
    else:
        warning = None
    result = {"schema_version": "1.0", "purpose": "dataset preparation only",
              "training_executed": False, "voice_cloning_executed": False,
              "speaker_count": len(speakers), "clip_count": len(records),
              "total_duration_seconds": round(sum(r["duration_seconds"] for r in records), 3),
              "records": records, "excluded": errors,
              "warnings": [warning] if warning else [],
              "next_requirements": ["transcripts with verified word-level text", "train/validation/test split by speaker",
                                    "balanced emotion/style labels", "rights and consent audit", "held-out listening evaluation"]}
    out = Path(output).expanduser().resolve()
    if out in {consent_path}:
        raise ValueError("Output must not overwrite consent file")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    return result
