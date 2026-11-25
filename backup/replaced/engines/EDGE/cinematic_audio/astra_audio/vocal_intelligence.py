"""Optional deep-learning vocal intelligence adapters for ASTRA.

All heavyweight ML dependencies are lazy-loaded. No model weights are downloaded
until the corresponding feature is explicitly enabled by the caller.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def backend_status() -> dict[str, Any]:
    """Report installed optional backends without importing/downloading models."""
    import importlib.util
    checks = {
        "faster_whisper": "faster_whisper",
        "pyannote_audio": "pyannote.audio",
        "speechbrain": "speechbrain",
        "transformers": "transformers",
        "torch": "torch",
        "deepfilternet": "df",
        "audio_separator": "audio_separator",
    }
    result = {}
    for label, module in checks.items():
        try:
            result[label] = importlib.util.find_spec(module) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            result[label] = False
    return {"backends": result, "models_downloaded_by_check": False}


def _require_file(path: str | Path) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Audio file not found: {p}")
    return p


def _transcribe(path: Path, model_size: str, language: str | None,
                device: str, compute_type: str) -> list[dict[str, Any]]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("ASR backend missing. Install: pip install faster-whisper") from exc
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(str(path), language=language, word_timestamps=True,
                                      vad_filter=True, beam_size=5)
    rows = []
    for seg in segments:
        words = []
        for word in (getattr(seg, "words", None) or []):
            words.append({"start": float(word.start), "end": float(word.end),
                          "text": word.word, "probability": float(word.probability)})
        rows.append({"start": float(seg.start), "end": float(seg.end),
                     "text": seg.text.strip(), "language": getattr(info, "language", None),
                     "language_probability": float(getattr(info, "language_probability", 0.0)),
                     "avg_logprob": float(getattr(seg, "avg_logprob", 0.0)),
                     "no_speech_probability": float(getattr(seg, "no_speech_prob", 0.0)),
                     "words": words})
    return rows


def _diarize(path: Path, model_id: str, token: str | None) -> list[dict[str, Any]]:
    try:
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise RuntimeError("Speaker diarization backend missing. Install: pip install pyannote.audio") from exc
    auth = token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if not auth:
        raise RuntimeError("pyannote model requires HF_TOKEN; accept the model terms on Hugging Face first")
    pipeline = Pipeline.from_pretrained(model_id, token=auth)
    if pipeline is None:
        raise RuntimeError(f"Could not load diarization model: {model_id}")
    output = pipeline(str(path))
    annotation = getattr(output, "speaker_diarization", output)
    rows = []
    for segment, _, speaker in annotation.itertracks(yield_label=True):
        rows.append({"start": float(segment.start), "end": float(segment.end),
                     "speaker_id": str(speaker)})
    return rows


def _speaker_embeddings(path: Path, turns: list[dict[str, Any]], model_id: str,
                         min_duration: float = 1.0) -> dict[str, Any]:
    """Extract consent-neutral embeddings for within-project voice consistency.

    Embeddings are biometric-like data: caller must obtain speaker consent and
    keep them private. This function does not identify real-world people.
    """
    try:
        import numpy as np
        import soundfile as sf
        import torch
        import torchaudio.functional as AF
        from speechbrain.inference.speaker import EncoderClassifier
    except ImportError as exc:
        raise RuntimeError("Speaker embedding backend missing. Install SpeechBrain and torch") from exc
    classifier = EncoderClassifier.from_hparams(source=model_id, savedir=None)
    audio, sr = sf.read(str(path), always_2d=True, dtype="float32")
    mono = audio.mean(axis=1)
    vectors: dict[str, list[list[float]]] = {}
    for turn in turns:
        if turn["end"] - turn["start"] < min_duration:
            continue
        a, b = max(0, int(turn["start"] * sr)), min(len(mono), int(turn["end"] * sr))
        if b <= a:
            continue
        clip = torch.from_numpy(mono[a:b]).unsqueeze(0)
        if sr != 16000:
            clip = AF.resample(clip, orig_freq=sr, new_freq=16000)
        emb = classifier.encode_batch(clip).squeeze().detach().cpu().numpy().astype(float)
        vectors.setdefault(turn["speaker_id"], []).append(emb.tolist())
    profiles = {}
    for speaker, values in vectors.items():
        mean = np.asarray(values, dtype=np.float64).mean(axis=0)
        norm = np.linalg.norm(mean)
        if norm:
            mean = mean / norm
        profiles[speaker] = {"embedding": mean.tolist(), "sample_count": len(values),
                             "model": model_id, "use": "within-project voice consistency only"}
    return profiles


def _attach_speakers(transcript: list[dict[str, Any]], turns: list[dict[str, Any]]) -> None:
    for seg in transcript:
        best, overlap_best = None, 0.0
        for turn in turns:
            overlap = max(0.0, min(seg["end"], turn["end"]) - max(seg["start"], turn["start"]))
            if overlap > overlap_best:
                best, overlap_best = turn["speaker_id"], overlap
        seg["speaker_id"] = best
        seg["speaker_overlap_seconds"] = round(overlap_best, 4)


def _emotion_classify(path: Path, transcript: list[dict[str, Any]], model_id: str) -> list[dict[str, Any]]:
    """Optional user-selected HF audio classifier; language validity is model-specific."""
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise RuntimeError("Emotion backend missing. Install: pip install transformers torch") from exc
    import soundfile as sf
    import numpy as np
    audio, sr = sf.read(str(path), always_2d=True, dtype="float32")
    mono = audio.mean(axis=1)
    classifier = pipeline("audio-classification", model=model_id)
    output = []
    for seg in transcript:
        a, b = max(0, int(seg["start"] * sr)), min(len(mono), int(seg["end"] * sr))
        if b <= a:
            continue
        # Pass raw samples and sampling rate; HF audio-classification accepts this form.
        scores = classifier({"raw": mono[a:b], "sampling_rate": sr}, top_k=5)
        output.append({"start": seg["start"], "end": seg["end"],
                       "speaker_id": seg.get("speaker_id"), "scores": scores})
    return output


def analyze_vocal_file(input_path: str | Path, *, asr_model: str = "small",
                       language: str | None = "hi", device: str = "cpu",
                       compute_type: str = "int8", diarization: bool = True,
                       diarization_model: str = "pyannote/speaker-diarization-community-1",
                       hf_token: str | None = None, embeddings: bool = False,
                       embedding_model: str = "speechbrain/spkrec-ecapa-voxceleb",
                       emotion_model: str | None = None) -> dict[str, Any]:
    """Run selected neural vocal tasks and return a review-first JSON report."""
    path = _require_file(input_path)
    transcript = _transcribe(path, asr_model, language, device, compute_type)
    turns = _diarize(path, diarization_model, hf_token) if diarization else []
    if turns:
        _attach_speakers(transcript, turns)
    profiles = _speaker_embeddings(path, turns, embedding_model) if embeddings and turns else {}
    emotions = _emotion_classify(path, transcript, emotion_model) if emotion_model else []
    return {
        "schema_version": "1.0", "engine": "ASTRA Deep-Learning Vocal Intelligence",
        "input": str(path), "source_modified": False,
        "models": {"asr": asr_model, "diarization": diarization_model if diarization else None,
                   "speaker_embedding": embedding_model if embeddings else None,
                   "emotion": emotion_model},
        "transcript": transcript, "speaker_turns": turns,
        "speaker_profiles": profiles, "emotion_predictions": emotions,
        "quality_gates": {"human_transcript_review_required": True,
                           "speaker_assignment_review_required": bool(turns),
                           "emotion_is_not_ground_truth": bool(emotions),
                           "emotion_model_language_must_be_validated": bool(emotions),
                           "voice_identity_consent_required": bool(profiles)},
        "limitations": ["ASR and diarization can make errors, especially with overlap, music, accents and noisy audio.",
                        "Emotion labels are model-dependent and must not be treated as facts.",
                        "Speaker embeddings are not real-world identity recognition."],
    }


def save_vocal_report(report: dict[str, Any], output_path: str | Path) -> str:
    out = Path(output_path).expanduser().resolve()
    source = Path(report["input"]).resolve()
    if out == source:
        raise ValueError("Report path must not overwrite the source audio")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    return str(out)
