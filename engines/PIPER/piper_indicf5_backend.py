"""Optional IndicF5 reference-voice backend for the Piper project.

This is an opt-in neural backend adapter, NOT a Piper ONNX model.
It leaves the existing Piper renderer untouched. Model weights are downloaded
by the user after accepting the upstream model terms.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

MODEL_ID = "ai4bharat/IndicF5"
DEFAULT_SAMPLE_RATE = 24000


CHARACTER_ALIASES = {
    # engine ke naam (Devanagari) -> profile ke naam
    "वाचक": "narrator", "आरव": "arav", "माँ": "mother", "मां": "mother",
    "दादी": "grandmother", "दादा": "grandfather", "बेटा": "son", "बेटी": "daughter",
    "भूत": "ghost", "चुड़ैल": "witch", "सूत्रधार": "narrator",
}


class VoiceProfileError(ValueError):
    pass


def normalize_hindi_text(text: str) -> str:
    """Unicode-normalize and clean spacing without rewriting Hindi words."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *([,;:!?।॥]) *", r"\1 ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def apply_pronunciation_overrides(text: str, overrides: dict[str, str] | None) -> tuple[str, list[dict[str, str]]]:
    """Apply only explicitly configured whole-word pronunciations."""
    if not overrides:
        return text, []
    spoken = text
    audit = []
    for source in sorted(overrides, key=len, reverse=True):
        target = overrides[source]
        if not source or not isinstance(target, str) or not target.strip():
            raise VoiceProfileError("pronunciation override keys/values must be non-empty strings")
        pattern = rf"(?<![\w]){re.escape(source)}(?![\w])"
        spoken, count = re.subn(pattern, lambda _m: target, spoken)
        if count:
            audit.append({"written": source, "spoken_as": target, "count": str(count)})
    return spoken, audit


def split_hindi_text(text: str, max_chars: int = 180) -> list[str]:
    """Split at sentence/phrase boundaries; never split inside a whitespace token."""
    if max_chars < 40:
        raise ValueError("max_chars must be at least 40")
    text = normalize_hindi_text(text)
    if len(text) <= max_chars:
        return [text]
    # Keep punctuation with its preceding phrase.
    pieces = re.split(r"(?<=[।!?;])\s+|(?<=,)\s+", text)
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if not piece:
            continue
        if len(piece) > max_chars:
            words = piece.split()
            for word in words:
                # ek hi "word" max_chars se lamba ho (bina space wali lambi line) —
                # use tukdon me todo, warna 400 akshar ka chunk model ko chala jata hai
                if len(word) > max_chars:
                    while len(word) > max_chars:
                        if current:
                            chunks.append(current); current = ""
                        chunks.append(word[:max_chars])
                        word = word[max_chars:]
                    if word:
                        current = word
                    continue
                if current and len(current) + 1 + len(word) > max_chars:
                    chunks.append(current)
                    current = word
                elif not current:
                    current = word
                else:
                    current += " " + word
            continue
        candidate = f"{current} {piece}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def load_voice_profile(profile_path: str | Path, character: str, emotion: str = "neutral") -> tuple[dict[str, Any], str, str, str]:
    character = CHARACTER_ALIASES.get(str(character).strip(), str(character).strip())
    path = Path(profile_path)
    if not path.is_file():
        raise VoiceProfileError(f"voice profile file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    characters = data.get("characters", {})
    if character not in characters:
        raise VoiceProfileError(f"unknown character '{character}' in {path}")
    profile = characters[character]
    refs = profile.get("references", {})
    selected = refs.get(emotion) or refs.get("neutral")
    selected_emotion = emotion if refs.get(emotion) else "neutral"
    if not selected:
        raise VoiceProfileError(f"character '{character}' needs a '{emotion}' or 'neutral' reference")
    audio_path = Path(selected.get("audio", ""))
    if not audio_path.is_absolute():
        audio_path = path.parent / audio_path
    if not audio_path.is_file():
        raise VoiceProfileError(f"reference audio not found for {character}/{selected_emotion}: {audio_path}")
    transcript = selected.get("text", "").strip()
    if not transcript:
        raise VoiceProfileError(f"reference transcript missing for {character}/{selected_emotion}")
    try:
        import soundfile as sf
        info = sf.info(str(audio_path))
        if info.duration < 2.0:
            raise VoiceProfileError(f"reference audio must be at least 2 seconds: {audio_path}")
        if info.channels > 2:
            raise VoiceProfileError("reference audio must be mono or stereo")
    except ImportError as exc:
        raise RuntimeError("soundfile is required to validate reference audio") from exc
    return profile, selected_emotion, str(audio_path), transcript


@dataclass
class RenderResult:
    output_path: str
    chunks: int
    sample_rate: int
    character: str
    requested_emotion: str
    used_emotion: str
    pronunciation_changes: list[dict[str, str]]
    warnings: list[str]


class IndicF5Backend:
    """Lazy-loaded IndicF5 renderer with per-character, per-emotion reference clips."""

    def __init__(self, model_id: str = MODEL_ID, device: str = "auto",
                 model_loader: Callable[[str, str], Any] | None = None):
        self.model_id = model_id
        self.device = device
        self._model = None
        self._model_loader = model_loader

    def _load(self):
        if self._model is not None:
            return self._model
        if self._model_loader:
            self._model = self._model_loader(self.model_id, self.device)
            return self._model
        try:
            import torch
            from transformers import AutoModel
        except ImportError as exc:
            raise RuntimeError(
                "Install IndicF5 dependencies in a separate environment: "
                "pip install torch transformers soundfile"
            ) from exc
        chosen = self.device
        if chosen == "auto":
            chosen = "cuda" if torch.cuda.is_available() else "cpu"
        # Official model card uses trust_remote_code=True.
        self._model = AutoModel.from_pretrained(self.model_id, trust_remote_code=True)
        if hasattr(self._model, "to"):
            self._model = self._model.to(chosen)
        if hasattr(self._model, "eval"):
            self._model.eval()
        return self._model

    def render(self, text: str, profile_path: str | Path, character: str,
               emotion: str, output_path: str | Path, max_chars: int = 180) -> RenderResult:
        import soundfile as sf

        clean = normalize_hindi_text(text)
        profile, used_emotion, ref_audio, ref_text = load_voice_profile(profile_path, character, emotion)
        spoken_text, audit = apply_pronunciation_overrides(clean, profile.get("pronunciation_overrides", {}))
        chunks = split_hindi_text(spoken_text, max_chars=max_chars)
        model = self._load()
        waveforms = []
        for chunk in chunks:
            audio = model(chunk, ref_audio_path=ref_audio, ref_text=ref_text)
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu().numpy()
            raw = np.asarray(audio)
            if raw.dtype == np.int16:
                arr = raw.astype(np.float32) / 32768.0
            else:
                arr = raw.astype(np.float32)
            arr = arr.squeeze()
            if arr.ndim != 1 or arr.size == 0:
                raise RuntimeError("IndicF5 returned empty or non-mono audio")
            if not np.isfinite(arr).all():
                raise RuntimeError("IndicF5 returned NaN/Inf audio samples")
            waveforms.append(arr)
        sr = int(getattr(getattr(model, "config", None), "sampling_rate", DEFAULT_SAMPLE_RATE))
        # Short phrase boundary only; no aggressive silence insertion.
        gap = np.zeros(int(sr * 0.075), dtype=np.float32)
        joined = []
        for i, arr in enumerate(waveforms):
            if i:
                joined.append(gap)
            joined.append(arr)
        final_audio = np.concatenate(joined)
        peak = float(np.max(np.abs(final_audio))) if final_audio.size else 0.0
        if peak > 0.999:
            final_audio = final_audio * (0.98 / peak)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out), final_audio, sr, subtype="PCM_16")
        warnings = []
        if used_emotion != emotion:
            warnings.append(f"No '{emotion}' reference for {character}; neutral reference used.")
        warnings.append("Emotion is guided by the supplied reference recording; it is not guaranteed by a text label.")
        return RenderResult(str(out), len(chunks), sr, character, emotion, used_emotion, audit, warnings)
