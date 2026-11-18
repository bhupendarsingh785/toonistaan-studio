from __future__ import annotations
from pathlib import Path
import shutil, subprocess, os, tempfile, json
import numpy as np
import soundfile as sf

SUPPORTED_NATIVE = {".wav", ".flac", ".ogg", ".aiff", ".aif"}

def probe_audio(path: str | Path) -> dict:
    """Read audio metadata without decoding the full waveform where supported."""
    path = Path(path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path)
    try:
        info = sf.info(str(path))
        if info.frames <= 0 or info.samplerate <= 0 or info.channels <= 0:
            raise ValueError(f"Audio metadata is empty or invalid: {path}")
        return {"frames": int(info.frames), "sample_rate": int(info.samplerate),
                "channels": int(info.channels), "duration_seconds": float(info.duration),
                "probe": "soundfile"}
    except Exception as soundfile_error:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise RuntimeError(
                f"Cannot safely preflight audio metadata for {path}; install FFprobe or convert this file to WAV/FLAC."
            ) from soundfile_error
        cmd = [ffprobe, "-v", "error", "-select_streams", "a:0",
               "-show_entries", "stream=sample_rate,channels,duration",
               "-of", "json", str(path)]
        try:
            proc = subprocess.run(cmd, capture_output=True, check=False, timeout=30)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("FFprobe metadata scan exceeded 30 seconds") from exc
        if proc.returncode:
            raise RuntimeError("FFprobe could not read audio metadata: " +
                               proc.stderr.decode("utf-8", "replace")[:300])
        try:
            streams = json.loads(proc.stdout.decode("utf-8")).get("streams", [])
            stream = streams[0]
            sr = int(stream["sample_rate"]); channels = int(stream["channels"])
            duration = float(stream["duration"])
            frames = int(round(sr * duration))
        except Exception as exc:
            raise RuntimeError(f"FFprobe returned incomplete audio metadata for {path}") from exc
        if frames <= 0 or sr <= 0 or channels <= 0 or not np.isfinite(duration):
            raise ValueError(f"Audio metadata is empty or invalid: {path}")
        return {"frames": frames, "sample_rate": sr, "channels": channels,
                "duration_seconds": duration, "probe": "ffprobe"}

def load_audio(path: str | Path):
    path = Path(path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() in SUPPORTED_NATIVE:
        data, sr = sf.read(str(path), always_2d=True, dtype="float32")
        if not np.isfinite(data).all():
            raise ValueError(f"Decoded audio contains NaN or infinite samples: {path}")
        return data, int(sr), "soundfile"
    if path.suffix.lower() in {".mp3", ".m4a", ".aac", ".mp4"}:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("MP3/M4A input needs FFmpeg. Convert to WAV or install FFmpeg.")
        cmd = [ffmpeg, "-v", "error", "-i", str(path), "-f", "wav",
               "-acodec", "pcm_f32le", "-"]
        try:
            proc = subprocess.run(cmd, capture_output=True, check=False, timeout=300)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("FFmpeg decode exceeded the 300-second safety timeout") from exc
        if proc.returncode:
            raise RuntimeError("FFmpeg decode failed: " + proc.stderr.decode("utf-8", "replace")[:500])
        import io
        data, sr = sf.read(io.BytesIO(proc.stdout), always_2d=True, dtype="float32")
        if not np.isfinite(data).all():
            raise ValueError(f"Decoded audio contains NaN or infinite samples: {path}")
        return data, int(sr), "ffmpeg"
    raise ValueError(f"Unsupported audio extension: {path.suffix}")

def save_wav(path: str | Path, data: np.ndarray, sr: int):
    """Atomically write PCM-24 WAV. Reject invalid samples instead of hiding them."""
    path = Path(path)
    if int(sr) <= 0:
        raise ValueError("Sample rate must be positive")
    data = np.asarray(data, dtype=np.float32)
    if data.ndim != 2 or data.shape[0] == 0 or data.shape[1] == 0:
        raise ValueError("Audio must be a non-empty 2D frames-by-channels array")
    if not np.isfinite(data).all():
        raise ValueError("Refusing to write audio containing NaN or infinite samples")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".wav.tmp", dir=str(path.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        sf.write(str(tmp), data, int(sr), format="WAV", subtype="PCM_24")
        # Replace only after the complete temporary WAV has been flushed successfully.
        os.replace(str(tmp), str(path))
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        finally:
            raise
    return path


def save_json_atomic(path: str | Path, payload: dict):
    """Write a UTF-8 JSON document atomically in the destination directory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".json.tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    return path
