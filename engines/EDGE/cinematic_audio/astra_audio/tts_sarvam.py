"""Sarvam Bulbul REST TTS adapter with per-character voice continuity.

No API key is bundled. This adapter follows Sarvam's documented REST
contract and can be exercised with a mocked transport for offline tests.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable
import base64, hashlib, io, json, os, re, tempfile, urllib.error, urllib.request
import soundfile as sf
import numpy as np
from scipy import signal
from .io import save_json_atomic, save_wav
from .story_intelligence import _scene_heading, _speaker_line

API_URL = "https://api.sarvam.ai/text-to-speech"
SUPPORTED_LANGUAGES = {"hi-IN","bn-IN","ta-IN","te-IN","kn-IN","ml-IN","mr-IN","gu-IN","pa-IN","od-IN","en-IN"}
# bulbul:v2 Sarvam ne deprecated kar diya (20 Nov 2026) — use mat karo
SUPPORTED_MODELS = {"bulbul:v3","bulbul:v4-flash"}

class SarvamTTS:
    def __init__(self, api_key: str | None = None, model: str = "bulbul:v4-flash",
                 language_code: str = "hi-IN", timeout: int = 120,
                 transport: Callable[[dict], dict] | None = None):
        self.api_key = api_key or os.environ.get("SARVAM_API_KEY")
        self.model = model
        self.language_code = language_code
        self.timeout = int(timeout)
        self.transport = transport
        if model not in SUPPORTED_MODELS:
            raise ValueError(f"Unsupported Sarvam model: {model}")
        if language_code not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language_code: {language_code}")
        if not 5 <= self.timeout <= 600:
            raise ValueError("timeout must be 5..600 seconds")

    def _request(self, payload: dict) -> dict:
        if self.transport is not None:
            return self.transport(payload)
        if not self.api_key:
            raise RuntimeError("SARVAM_API_KEY is not set; no API request was made")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            API_URL, data=body, method="POST",
            headers={"api-subscription-key": self.api_key,
                     "Content-Type": "application/json", "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(32 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as exc:
            detail = exc.read(4000).decode("utf-8", "replace")
            raise RuntimeError(f"Sarvam TTS HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Sarvam TTS connection failed: {exc}") from exc
        if len(raw) > 32 * 1024 * 1024:
            raise RuntimeError("Sarvam TTS response exceeded 32 MiB safety limit")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Sarvam TTS returned invalid JSON") from exc

    def synthesize(self, text: str, speaker: str, output_path: str | Path,
                   pace: float = 1.0, temperature: float = 0.6,
                   sample_rate: int = 48000) -> dict:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("TTS text must be non-empty")
        if len(text) > 2500:
            raise ValueError("Bulbul v3/v4 supports up to 2500 characters per request; split at sentence boundaries")
        if not isinstance(speaker, str) or not speaker.strip():
            raise ValueError("An explicit provider speaker ID is required")
        pace = float(pace); temperature = float(temperature)
        if not 0.5 <= pace <= 2.0:
            raise ValueError("Bulbul v3/v4 pace must be 0.5..2.0")
        if not 0.01 <= temperature <= 1.0:
            raise ValueError("temperature must be 0.01..1.0")
        if sample_rate not in {8000,16000,22050,24000,32000,44100,48000}:
            raise ValueError("Unsupported Sarvam REST sample rate")
        out = Path(output_path).resolve()
        if out.exists():
            raise FileExistsError(f"Refusing to overwrite existing TTS output: {out}")
        payload = {
            "text": text, "model": self.model, "language_code": self.language_code,
            "speaker": speaker, "pace": pace, "temperature": temperature,
            "speech_sample_rate": sample_rate, "output_audio_codec": "wav",
        }
        response = self._request(payload)
        audios = response.get("audios") if isinstance(response, dict) else None
        if not isinstance(audios, list) or len(audios) != 1 or not isinstance(audios[0], str):
            raise RuntimeError("Sarvam TTS response must contain exactly one base64 audio item")
        try:
            audio_bytes = base64.b64decode(audios[0], validate=True)
        except Exception as exc:
            raise RuntimeError("Sarvam TTS returned invalid base64 audio") from exc
        if len(audio_bytes) < 44 or not audio_bytes.startswith(b"RIFF") or b"WAVE" not in audio_bytes[:16]:
            raise RuntimeError("Sarvam TTS did not return a valid WAV container")
        try:
            info = sf.info(io.BytesIO(audio_bytes))
        except Exception as exc:
            raise RuntimeError("Sarvam TTS WAV failed audio metadata validation") from exc
        if info.frames <= 0 or info.channels not in (1,2) or info.samplerate <= 0:
            raise RuntimeError("Sarvam TTS WAV has unsupported or empty audio metadata")
        out.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{out.stem}.", suffix=".wav.tmp", dir=str(out.parent))
        os.close(fd)
        try:
            with open(tmp_name, "wb") as f:
                f.write(audio_bytes); f.flush(); os.fsync(f.fileno())
            os.replace(tmp_name, out)
        except Exception:
            try: os.unlink(tmp_name)
            except FileNotFoundError: pass
            raise
        return {
            "output": str(out), "request_id": response.get("request_id"),
            "speaker": speaker, "model": self.model, "language_code": self.language_code,
            "duration_seconds": round(info.frames/info.samplerate, 4),
            "sample_rate": info.samplerate, "channels": info.channels,
            "sha256": hashlib.sha256(audio_bytes).hexdigest(),
            "provider": "sarvam_bulbul_rest", "source_text_modified": False,
        }

def split_tts_text(text: str, max_chars: int = 2400) -> list[str]:
    """Split long speech at sentence/whitespace boundaries without dropping text."""
    text = re.sub(r"\s+", " ", str(text)).strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[।!?])\s+", text)
    chunks, current = [], ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            words = sentence.split(" ")
            for word in words:
                if len(word) > max_chars:
                    raise ValueError("A single unbroken token exceeds the TTS request limit")
                if current and len(current)+1+len(word) > max_chars:
                    chunks.append(current); current = word
                else:
                    current = (current+" "+word).strip()
            continue
        candidate = (current+" "+sentence).strip()
        if current and len(candidate) > max_chars:
            chunks.append(current); current = sentence
        else:
            current = candidate
    if current: chunks.append(current)
    if "".join(chunks).replace(" ","") != text.replace(" ",""):
        raise RuntimeError("Internal TTS chunking validation failed")
    return chunks

def extract_script_segments(script_path: str | Path) -> list[dict]:
    path = Path(script_path)
    text = path.read_text(encoding="utf-8-sig")
    segments = []
    scene_no = 0
    scene_id = "scene_001"
    for line_no, raw in enumerate(text.replace("\r\n","\n").replace("\r","\n").split("\n"),1):
        line = raw.strip()
        if not line:
            continue
        if _scene_heading(line):
            scene_no += 1
            scene_id = f"scene_{scene_no:03d}"
            continue
        if re.match(r"(?i)^(?:SFX|BGM|MUSIC|ध्वनि|संगीत)\s*[:：]", line):
            continue
        speaker = _speaker_line(line)
        if speaker:
            name, speech = speaker
            segments.append({"segment_id": f"line_{line_no:05d}", "source_line": line_no,
                             "scene_id": scene_id, "speaker_name": name, "text": speech})
        else:
            segments.append({"segment_id": f"line_{line_no:05d}", "source_line": line_no,
                             "scene_id": scene_id, "speaker_name": "वाचक", "text": line})
    return segments

def synthesize_script(script_path: str | Path, voice_map: dict, output_dir: str | Path,
                      api_key: str | None = None,
                      transport: Callable[[dict], dict] | None = None) -> dict:
    """Generate per-line WAV clips and a sequential multi-character dialogue mix."""
    if not isinstance(voice_map, dict):
        raise ValueError("voice_map must be a JSON object")
    model = voice_map.get("model", "bulbul:v4-flash")
    language = voice_map.get("language_code", "hi-IN")
    speakers = voice_map.get("speakers", {})
    default = voice_map.get("default_speaker")
    if not isinstance(speakers, dict):
        raise ValueError("voice_map.speakers must be an object")
    outdir = Path(output_dir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_path = outdir/"tts-manifest.json"
    dialogue_path = outdir/"dialogue-mix.wav"
    if manifest_path.exists() or dialogue_path.exists():
        raise FileExistsError("Refusing to overwrite existing TTS manifest/dialogue mix")
    client = SarvamTTS(api_key=api_key, model=model, language_code=language,
                       timeout=int(voice_map.get("timeout_seconds",120)), transport=transport)
    segments = extract_script_segments(script_path)
    if not segments:
        raise ValueError("No narration/dialogue segments were found in the script")
    pace_default = float(voice_map.get("pace",1.0))
    temp_default = float(voice_map.get("temperature",0.65))
    sample_rate = int(voice_map.get("sample_rate",48000))
    generated = []
    created_files = []
    try:
        for segment in segments:
            speaker_id = speakers.get(segment["speaker_name"], default)
            if not speaker_id:
                raise ValueError(f"No voice ID configured for character/narrator '{segment['speaker_name']}'")
            parts = split_tts_text(segment["text"])
            for part_no, part in enumerate(parts,1):
                name = f"{segment['segment_id']}_part_{part_no:02d}.wav"
                result = client.synthesize(part, speaker_id, outdir/name,
                    pace=float(voice_map.get("pace_by_speaker",{}).get(segment["speaker_name"],pace_default)),
                    temperature=temp_default, sample_rate=sample_rate)
                created_files.append(Path(result["output"]))
                generated.append({**segment, "part":part_no, "text":part,
                                  "provider_speaker":speaker_id, **result})
        # Assemble a sequential dialogue/narration master and a line timing map.
        pause_ms = int(voice_map.get("pause_ms",250))
        scene_pause_ms = int(voice_map.get("scene_pause_ms",750))
        memory_budget_mb = int(voice_map.get("memory_budget_mb",512))
        if not 0 <= pause_ms <= 5000 or not 0 <= scene_pause_ms <= 10000:
            raise ValueError("pause_ms/scene_pause_ms are outside safe limits")
        decoded = []
        channels = 1
        total_frames = 0
        previous_scene = None
        for item in generated:
            data, sr = sf.read(item["output"], always_2d=True, dtype="float32")
            if sr != sample_rate:
                g = __import__("math").gcd(int(sr), int(sample_rate))
                data = signal.resample_poly(data, sample_rate//g, sr//g, axis=0).astype(np.float32)
            if data.shape[1] not in (1,2):
                raise ValueError(f"Unsupported TTS channel count in {item['output']}")
            channels = max(channels, data.shape[1])
            gap_ms = 0 if previous_scene is None else (
                scene_pause_ms if item["scene_id"] != previous_scene else pause_ms)
            gap_frames = int(sample_rate*gap_ms/1000)
            total_frames += gap_frames + len(data)
            decoded.append((item,data,gap_frames))
            previous_scene = item["scene_id"]
        estimated_mb = total_frames*channels*4/1024/1024
        if estimated_mb > memory_budget_mb:
            raise MemoryError(f"Dialogue assembly needs about {estimated_mb:.1f} MiB; above {memory_budget_mb} MiB budget")
        chunks = []
        timeline = []
        cursor = 0
        for item,data,gap_frames in decoded:
            if gap_frames:
                chunks.append(np.zeros((gap_frames,channels),dtype=np.float32))
                cursor += gap_frames
            if data.shape[1] == 1 and channels == 2:
                data = np.repeat(data,2,axis=1)
            elif data.shape[1] == 1 and channels == 1:
                pass
            start_frame = cursor
            chunks.append(data)
            cursor += len(data)
            timeline.append({
                "segment_id":item["segment_id"], "source_line":item["source_line"],
                "scene_id":item["scene_id"], "speaker_name":item["speaker_name"],
                "provider_speaker":item["speaker"], "start_seconds":round(start_frame/sample_rate,4),
                "end_seconds":round(cursor/sample_rate,4), "clip_path":item["output"],
            })
        dialogue = np.concatenate(chunks,axis=0)
        save_wav(dialogue_path,dialogue,sample_rate)
        manifest = {
            "schema": "astra-sarvam-tts-manifest/v1",
            "provider": "sarvam_bulbul_rest", "model": model, "language_code": language,
            "segment_count": len(segments), "clip_count": len(generated),
            "clips": generated,
            "dialogue_mix_path": str(dialogue_path),
            "dialogue_duration_seconds": round(len(dialogue)/sample_rate,4),
            "timeline": timeline,
            "voice_continuity": {name: speakers.get(name,default) for name in sorted({s["speaker_name"] for s in segments})},
            "source_script_modified": False,
            "notes": ["One provider voice ID is reused for each speaker across all their lines.",
                      "Dialogue mix is assembled in script order with configured pauses; it is not word-level forced alignment.",
                      "SFX/BGM lines are not synthesized; their timeline still needs explicit cue approvals/placement.",
                      "Expressive performance is limited by the selected provider voice and its supported controls."],
        }
        save_json_atomic(manifest_path,manifest)
        created_files.append(manifest_path)
        return manifest
    except Exception:
        # Remove only files created during this invocation, allowing a clean retry.
        for created in created_files:
            try:
                Path(created).unlink(missing_ok=True)
            except OSError:
                pass
        try:
            dialogue_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
def make_workflow_adapter(voice_map: dict, output_dir: str | Path,
                          transport: Callable[[dict], dict] | None = None):
    """Return an AudioWorkflow-compatible voice_generation stage adapter."""
    def adapter(context: dict) -> dict:
        script_path = context.get("story_script_path") or context.get("script_path")
        if not script_path:
            raise ValueError("voice_generation requires story_script_path in workflow context")
        return synthesize_script(script_path, voice_map, output_dir, transport=transport)
    return adapter
