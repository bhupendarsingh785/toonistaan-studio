#!/usr/bin/env python3
"""ASTRA Voice Clone — kisi ki bhi awaaz copy karke poori script usi awaaz me.

Kaam kaise hota hai (3 step):
  1) enroll  — 5-15 second ki recording + uska exact transcript + ijazat (consent)
  2) speak   — script ki har line us awaaz me banti hai
  3) mix     — lines jod kar ek file (background ke saath, agar chahiye)

Backends (jo machine par chale, wahi use hoga):
  indicf5  — free, reference audio + transcript se cloning (GPU chahiye)
  xtts     — Coqui XTTS-v2 (GPU/CPU, dheema par chalta hai)
  piper    — cloning NAHI karta (sirf fallback; saaf-saaf batata hai)

Ijazat (consent) lazmi:
  Bina consent ke enroll nahi hota. Ye guard jaan-boojh kar rakha hai —
  kisi ki awaaz uski permission ke bina copy karna galat hai.

Commands:
  python tools/voice_clone.py backends
  python tools/voice_clone.py enroll --name dadi --audio dadi.wav --transcript "..." --consent
  python tools/voice_clone.py voices
  python tools/voice_clone.py speak --name dadi --script story.txt --out output/dadi/
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import re
import hashlib
import time
import threading
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICES = ROOT / "voices"          # cloned voices yahan rehti hain
OUT = ROOT / "output"

# XTTS is expensive to initialise. Keep one model instance per process/device.
_XTTS_MODEL_CACHE: dict[tuple[str, str], object] = {}
_XTTS_CACHE_LOCK = threading.RLock()
_XTTS_INFER_LOCK = threading.RLock()

def _atomic_json(path: Path, payload: dict) -> None:
    """Write manifests/profile metadata atomically to survive process interruption."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


class ConsentMissing(PermissionError):
    pass


@dataclass
class Voice:
    name: str
    audio: str
    transcript: str
    consent: bool
    backend: str = "indicf5"
    note: str = ""
    emotion_refs: dict = field(default_factory=dict)
    render_emotion: str = "neutral"


# ------------------------------------------------------------------ backends
def backend_status() -> list[dict]:
    """Report dependency readiness honestly; never equate imports with verified inference."""
    try:
        from tools.preflight import report
        pre = report()
    except Exception as exc:
        return [{"name":"indicf5","ready":False,"why":f"preflight failed: {exc}"},
                {"name":"xtts","ready":False,"why":f"preflight failed: {exc}"},
                {"name":"piper","ready":False,"why":"Piper is not a voice-cloning backend"}]
    i=pre["backends"]["indicf5"]; x=pre["backends"]["xtts"]
    # 'ready' means enough local dependencies and credentials for an attempted render,
    # not that model access or audio quality has been verified.
    return [
      {"name":"indicf5","ready":bool(i["dependencies_present"] and i["token_present"]),"why":i["status"]+"; model download/access/inference still unverified"},
      {"name":"xtts","ready":bool(x["dependencies_present"]),"why":x["status"]+"; model download/Hindi inference still unverified"},
      {"name":"piper","ready":False,"why":"Piper does not perform voice cloning"}]


def pick_backend() -> str | None:
    for b in backend_status():
        if b["ready"] and b["name"] != "piper":
            return b["name"]
    return None


# ------------------------------------------------------------------ voices
def reference_quality(path: str) -> dict:
    """Reference ki jaanch: lambai + bolne ka hissa (mera v3 gate)."""
    from tools import voice_extract as ve
    import numpy as _np
    x = ve._load(path, 16000)
    dur = len(x) / 16000
    w = int(0.05 * 16000)
    rms = _np.array([_np.sqrt((x[i:i + w] ** 2).mean())
                     for i in range(0, max(1, len(x) - w), w)])
    floor = float(_np.percentile(rms, 10)) if len(rms) else 0.0
    thr = max(0.01, float(_np.median(rms)) * 0.5) if len(rms) else 0.01
    talk = float((rms > thr).mean()) if len(rms) else 0.0
    ok = dur >= 3.0 and talk >= 0.25
    why = []
    if dur < 3.0:
        why.append(f"bahut chhoti ({dur:.1f}s, kam se kam 3s)")
    if talk < 0.25:
        why.append(f"bolne ka hissa kam ({talk*100:.0f}%)")
    return {"duration_sec": round(dur, 2), "talk_ratio": round(talk, 2),
            "noise_floor": round(floor, 4), "ok": ok, "why": "; ".join(why)}


def _voice_dir(name: str) -> Path:
    """Resolve a profile name safely; never allow traversal or symlink escape."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name) or name in {".", ".."}:
        raise ValueError("Voice name invalid: use 1-64 letters, digits, dot, underscore or hyphen.")
    root = VOICES.resolve()
    target = (root / name).resolve()
    if target.parent != root:
        raise ValueError("Voice profile path escapes voices directory.")
    return target


def _normalise_reference(src: Path, dest: Path) -> None:
    """Decode any supported input and write a verified mono PCM WAV."""
    try:
        import soundfile as sf
        import numpy as np
        # FFmpeg decodes WAV/MP3/M4A/FLAC and media containers consistently.
        try:
            from tools.voice_extract import _ff
            ffmpeg = _ff()
        except Exception:
            ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = [ffmpeg, "-nostdin", "-v", "error", "-y", "-i", str(src), "-vn",
               "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(dest)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            raise ValueError("Reference audio decode failed: " + (proc.stderr or "unknown ffmpeg error")[-300:])
        audio, sr = sf.read(str(dest), dtype="float32", always_2d=True)
        if audio.size == 0 or sr < 8000 or not np.isfinite(audio).all():
            raise ValueError("Audio empty, invalid sample rate, or non-finite samples.")
        mono = audio.mean(axis=1)
        peak = float(np.max(np.abs(mono)))
        if peak < 1e-5: raise ValueError("Reference audio silent/near-silent hai.")
        if peak > 0.999: mono = mono * (0.98 / peak)
        sf.write(str(dest), mono, int(sr), subtype="PCM_16", format="WAV")
        check, check_sr = sf.read(str(dest), dtype="float32")
        if check.size == 0 or check_sr != sr: raise ValueError("Reference WAV verification failed.")
    except ImportError as exc:
        raise RuntimeError("soundfile aur numpy required: pip install soundfile numpy") from exc


def enroll_from_media(name: str, media: str, consent: bool, seconds: float = 12.0,
                      transcript: str = "", backend: str = "") -> Voice:
    """Video/audio se awaaz nikaal kar enroll — extract + clean + (transcript)."""
    from tools import voice_extract as ve
    if not consent:
        raise ConsentMissing(
            "Ijazat ke bina enroll nahi hoga. --consent do (awaaz uski hi ho ya likhit permission ho).")
    d = _voice_dir(name); d.mkdir(parents=True, exist_ok=True)
    meta = ve.run(media, str(d), seconds=seconds, do_clean=True)
    text = (transcript or meta.get("transcript") or "").strip()
    if not text:
        chosen = backend or pick_backend()
        xtts_ready = any(b["name"] == "xtts" and b["ready"] for b in backend_status())
        if chosen == "indicf5" or not xtts_ready:
            raise ValueError(
                "transcript nahi mila — indicf5 ke liye zaroori; "
                "bina transcript sirf xtts chal sakta hai (pip install TTS)")
    extracted = Path(meta["reference"])
    q = reference_quality(str(extracted)) if extracted.is_file() else {"ok": False, "why": "file nahi mili"}
    if not q["ok"]:
        if os.environ.get("ASTRA_STRICT_REF") == "1":
            raise ValueError(f"nikala hua reference theek nahi: {q.get('why','')} — lamba clip do")
        print(f"[warn] nikala hua reference kamzor: {q.get('why','')}")
    if not extracted.is_file():
        raise FileNotFoundError(f"Extracted reference audio missing: {extracted}")
    # Extraction output is normalized too; never trust its extension/header alone.
    normalized_tmp = d / "reference.normalized.wav"
    _normalise_reference(extracted, normalized_tmp)
    os.replace(normalized_tmp, d / "reference.wav")
    v = Voice(name=name, audio=str(d / "reference.wav"), transcript=text, consent=True,
              backend=backend or (pick_backend() or "piper"),
              note=f"media se nikaala: {os.path.basename(media)} ({meta['duration_sec']}s)")
    from tools.consent import record_consent
    record_consent(d, name)
    _atomic_json(d / "voice.json", v.__dict__)
    return v


def enroll(name: str, audio: str, transcript: str, consent: bool, backend: str = "") -> Voice:
    if not consent:
        raise ConsentMissing(
            "Ijazat ke bina enroll nahi hoga. --consent do (aur yaad rakho: "
            "awaaz uski hi honi chahiye ya likhit permission ho).")
    src = Path(audio)
    if not src.exists():
        raise FileNotFoundError(f"recording nahi mili: {audio}")
    transcript = (transcript or "").strip()
    if not transcript:
        chosen = backend or pick_backend()
        xtts_ready = any(b["name"] == "xtts" and b["ready"] for b in backend_status())
        if chosen == "indicf5" or not xtts_ready:
            raise ValueError(
                "transcript khali hai — indicf5 ke liye zaroori hai; "
                "bina transcript sirf xtts chal sakta hai (pip install TTS)")
    q = reference_quality(str(src))
    if not q["ok"]:
        if os.environ.get("ASTRA_STRICT_REF") == "1":
            raise ValueError(f"reference theek nahi: {q['why']} — saaf 3-15 second ki recording do")
        print(f"[warn] reference kamzor: {q['why']} (ASTRA_STRICT_REF=1 se block ho jayega)")
    d = _voice_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    _normalise_reference(src, d / "reference.wav")
    v = Voice(name=name, audio=str(d / "reference.wav"), transcript=transcript.strip(),
              consent=True, backend=backend or (pick_backend() or "piper"),
              note=f"consent: user ne di; quality: {q['talk_ratio']*100:.0f}% bolna, {q['duration_sec']}s")
    from tools.consent import record_consent
    record_consent(d, name)
    _atomic_json(d / "voice.json", v.__dict__)
    return v


def list_voices() -> list[Voice]:
    out = []
    if not VOICES.exists():
        return out
    for d in sorted(VOICES.iterdir()):
        f = d / "voice.json"
        if f.exists():
            try:
                voice = Voice(**json.loads(f.read_text(encoding="utf-8")))
                try:
                    from tools.consent import assert_consent_active
                    assert_consent_active(d)
                    voice.note = (voice.note + " | consent=active").strip(" |")
                except Exception:
                    voice.consent = False
                    voice.note = (voice.note + " | consent=blocked").strip(" |")
                out.append(voice)
            except Exception:
                continue
    return out


def load_voice(name: str) -> Voice:
    from tools.consent import assert_consent_active
    profile_dir = _voice_dir(name)
    assert_consent_active(profile_dir)
    f = _voice_dir(name) / "voice.json"
    if not f.exists():
        raise FileNotFoundError(f"voice nahi mili: {name} (pehle enroll karo)")
    return Voice(**json.loads(f.read_text(encoding="utf-8")))


# ------------------------------------------------------------------ render
def clear_backend_cache() -> None:
    """Release cached backend instances (useful for controlled shutdown/tests)."""
    _XTTS_MODEL_CACHE.clear()


def _get_xtts_model(device: str = "cpu"):
    """Load XTTS once per process/device instead of once per script chunk."""
    key = ("xtts_v2", device)
    with _XTTS_CACHE_LOCK:
        if key not in _XTTS_MODEL_CACHE:
            try:
                from TTS.api import TTS
            except Exception as exc:
                raise RuntimeError("XTTS package load nahi hua; install/check TTS") from exc
            model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
            if hasattr(model, "to"):
                model = model.to(device)
            _XTTS_MODEL_CACHE[key] = model
        return _XTTS_MODEL_CACHE[key]


def _canonical_emotion(emotion: str) -> str:
    aliases = {"dukh":"sad", "pain":"pain", "sad":"sad", "khushi":"happy", "happy":"happy",
              "gussa":"angry", "anger":"angry", "angry":"angry", "dar":"fear", "fear":"fear",
              "pyaar":"warm", "love":"warm", "warm":"warm", "hasai":"laugh", "hasi":"laugh",
              "laugh":"laugh", "rona":"cry", "cry":"cry", "whisper":"whisper", "shout":"shout",
              "surprise":"surprise", "ashcharya":"surprise", "calm":"calm", "excited":"excited",
              "neutral":"neutral"}
    return aliases.get((emotion or "neutral").strip().lower(), "neutral")


def add_emotion_reference(name: str, emotion: str, audio: str, transcript: str,
                          consent: bool, same_speaker_confirmed: bool) -> dict:
    """Register a consented, same-speaker emotional prompt for reference-conditioned IndicF5."""
    if not consent:
        raise ConsentMissing("Emotion sample add karne ke liye speaker ki explicit permission zaroori hai.")
    if not same_speaker_confirmed:
        raise ValueError("same speaker confirm karein: emotion sample enrolled speaker ki hi awaaz honi chahiye.")
    canonical = _canonical_emotion(emotion)
    if canonical == "neutral":
        raise ValueError("Neutral sample ke liye base enrollment audio use hota hai.")
    if not transcript or not transcript.strip():
        raise ValueError("Emotion reference ka exact transcript zaroori hai.")
    profile = _voice_dir(name)
    from tools.consent import assert_consent_active
    assert_consent_active(profile)
    meta_path = profile / "voice.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"Voice profile nahi mili: {name}")
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    refs = dict(payload.get("emotion_refs") or {})
    refs_dir = profile / "emotion_refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    target = refs_dir / f"{canonical}.wav"
    tmp = refs_dir / f"{canonical}.normalized.wav"
    _normalise_reference(Path(audio), tmp)
    import soundfile as sf
    info = sf.info(str(tmp))
    if info.frames / info.samplerate < 2.0:
        tmp.unlink(missing_ok=True)
        raise ValueError("Emotion reference kam-se-kam 2 seconds ka hona chahiye.")
    os.replace(tmp, target)
    refs[canonical] = {"audio": str(target), "transcript": transcript.strip(),
                       "speaker_same_as_profile_attested": True,
                       "emotion_reference_storage_consent_attested": True,
                       "registered_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    payload["emotion_refs"] = refs
    _atomic_json(meta_path, payload)
    return {"voice": name, "emotion": canonical, "audio": str(target),
            "conditioning": "reference_audio_conditioning; model response must be evaluated, not guaranteed"}


def _render_line(backend: str, voice: Voice, text: str, out: Path) -> bool:
    """Render a line. IndicF5 may use same-speaker emotion prompt; XTTS has no guaranteed emotion control."""
    out.parent.mkdir(parents=True, exist_ok=True)
    canonical = _canonical_emotion(getattr(voice, "render_emotion", "neutral"))
    selected_audio, selected_text = voice.audio, voice.transcript
    emotion_ref = (voice.emotion_refs or {}).get(canonical)
    if backend == "indicf5" and emotion_ref:
        candidate = Path(emotion_ref.get("audio", "")).resolve()
        profile_root = _voice_dir(voice.name).resolve()
        try:
            candidate.relative_to(profile_root)
        except ValueError as exc:
            raise ValueError("Emotion reference path profile directory se bahar hai; blocked.") from exc
        if candidate.is_file() and emotion_ref.get("transcript", "").strip():
            selected_audio, selected_text = str(candidate), emotion_ref["transcript"]
    if backend == "indicf5":
        cmd = [sys.executable, str(ROOT / "indicf5_fix_v1" / "indicf5_render.py"),
               "--text", text, "--ref-audio", selected_audio, "--ref-text", selected_text,
               "--out", str(out), "--device", os.environ.get("CLONE_DEVICE", "cpu")]
        timeout = int(os.environ.get("ASTRA_TTS_TIMEOUT_SEC", "600"))
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=max(30, timeout))
        except subprocess.TimeoutExpired:
            if out.exists(): out.unlink()
            print("  indicf5 fail: generation timeout")
            return False
        if r.returncode != 0:
            print("  indicf5 fail:", (r.stderr or r.stdout).strip()[-160:])
            return False
        return out.exists() and out.stat().st_size > 1000
    if backend == "xtts":
        try:
            device = os.environ.get("CLONE_DEVICE", "cpu")
            tts = _get_xtts_model(device)
            with _XTTS_INFER_LOCK:
                tts.tts_to_file(text=text, speaker_wav=voice.audio, language="hi", file_path=str(out))
            return out.exists() and out.stat().st_size > 1000
        except Exception as exc:
            print("  xtts fail:", f"{type(exc).__name__}: {exc}"[-200:])
            return False
    return False


EMOTIONS = ("neutral", "dukh", "khushi", "gussa", "dar", "pyaar", "hasai", "rona")


def parse_line(line: str) -> tuple[str, str]:
    """Line se bhaav nikalo: '[dukh] बेटा...' ya 'दादी [gussa]: ...'"""
    import re
    m = re.search(r"\[(" + "|".join(EMOTIONS) + r")\]", line)
    if not m:
        return "neutral", line.strip()
    emo = m.group(1)
    text = (line[:m.start()] + line[m.end():]).strip()
    text = re.sub(r"^[:\-\s]+", "", text)      # bacha hua colon hatao
    # "दादी : बेटा..." jaisa speaker prefix hatao (chhota naam hi)
    text = re.sub(r"^[^:\n]{1,20}:\s*", "", text)
    return emo, text


def _wav_info(path: Path) -> tuple[int, int]:
    """Validate decodable, non-empty, finite, audible WAV data (not just its header)."""
    import soundfile as sf
    import numpy as np
    info = sf.info(str(path))
    if info.frames <= 0 or info.samplerate < 8000 or info.channels <= 0:
        raise ValueError("Generated audio invalid/empty or sample rate too low")
    peak = 0.0
    with sf.SoundFile(str(path), mode="r") as audio:
        while True:
            block = audio.read(65536, dtype="float32", always_2d=True)
            if len(block) == 0:
                break
            if not np.isfinite(block).all():
                raise ValueError("Generated audio contains NaN/Inf samples")
            peak = max(peak, float(np.max(np.abs(block))))
    if peak < 1e-5:
        raise ValueError("Generated audio is silent/near-silent")
    if info.frames / info.samplerate < 0.02:
        raise ValueError("Generated audio is too short to be valid speech")
    return int(info.samplerate), int(info.frames)


def _stitch_wavs(files: list[Path], destination: Path, gap_ms: int = 100) -> dict:
    """Stream chunks into one master WAV; avoids loading multi-hour stories into RAM."""
    import soundfile as sf
    import numpy as np
    if not files: raise ValueError("No successful chunks to stitch")
    first = sf.info(str(files[0]))
    target_sr, channels = int(first.samplerate), int(first.channels)
    if first.frames <= 0 or target_sr <= 0: raise ValueError("First chunk is invalid")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.stem + '.partial.wav')
    total_frames = 0
    silence = np.zeros((max(0, int(target_sr * max(0, gap_ms) / 1000)), channels), dtype=np.float32)
    try:
        with sf.SoundFile(str(temp), mode='w', samplerate=target_sr, channels=channels, subtype='PCM_16', format='WAV') as out:
            for index, path in enumerate(files):
                info = sf.info(str(path))
                if info.samplerate != target_sr or info.channels != channels or info.frames <= 0:
                    raise ValueError(f"Chunk format mismatch or empty: {path.name}")
                with sf.SoundFile(str(path), mode='r') as inp:
                    while True:
                        block = inp.read(65536, dtype='float32', always_2d=True)
                        if len(block) == 0: break
                        if not np.isfinite(block).all(): raise ValueError(f"Non-finite audio samples: {path.name}")
                        out.write(block); total_frames += len(block)
                if index < len(files)-1 and len(silence):
                    out.write(silence); total_frames += len(silence)
        check = sf.info(str(temp))
        if check.frames != total_frames or check.samplerate != target_sr:
            raise RuntimeError("Final master WAV verification failed")
        os.replace(temp, destination)
    finally:
        if temp.exists(): temp.unlink()
    return {"master": str(destination), "sample_rate": target_sr,
            "duration_sec": round(total_frames/target_sr, 3), "chunks": len(files), "gap_ms": gap_ms}


def _voice_fingerprint(voice: Voice) -> str:
    """Bind resume state to the actual enrolled reference and transcript."""
    h = hashlib.sha256()
    h.update(voice.transcript.encode("utf-8"))
    h.update(voice.backend.encode("utf-8"))
    profile_root = _voice_dir(voice.name).resolve()
    ref = Path(voice.audio).resolve()
    try:
        ref.relative_to(profile_root)
    except ValueError as exc:
        raise ValueError("Base voice reference profile directory se bahar hai; blocked.") from exc
    if not ref.is_file():
        raise FileNotFoundError(f"Voice reference audio missing: {ref}")
    with ref.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    # Emotion prompt changes alter IndicF5 conditioning, so they must invalidate resume.
    for emotion, item in sorted((voice.emotion_refs or {}).items()):
        h.update(str(emotion).encode("utf-8"))
        h.update(str(item.get("transcript", "")).encode("utf-8"))
        candidate = Path(item.get("audio", "")).resolve()
        try:
            candidate.relative_to(profile_root)
        except ValueError as exc:
            raise ValueError(f"Emotion reference escapes voice profile: {emotion}") from exc
        if not candidate.is_file():
            raise FileNotFoundError(f"Emotion reference missing: {emotion}: {candidate}")
        with candidate.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
    return h.hexdigest()


def speak(name: str, script_path: str, out_dir: str, retries: int = 1,
          max_chars: int = 220, resume: bool = True, stitch: bool = True,
          stitch_gap_ms: int = 0) -> dict:
    """Crash-resilient long-form generation with manifest, retries and master WAV."""
    from tools.script_pipeline import prepare_script
    if not isinstance(retries, int) or retries < 0 or retries > 10:
        raise ValueError("retries 0 se 10 ke beech hona chahiye")
    if not isinstance(max_chars, int) or max_chars < 40 or max_chars > 2000:
        raise ValueError("max_chars 40 se 2000 ke beech hona chahiye")
    if not isinstance(stitch_gap_ms, int) or not 0 <= stitch_gap_ms <= 5000:
        raise ValueError("stitch_gap_ms 0 se 5000 ke beech hona chahiye")
    script_file = Path(script_path)
    if not script_file.is_file(): raise FileNotFoundError(script_path)
    source = script_file.read_text(encoding="utf-8-sig")
    chunks = prepare_script(source, max_chars=max_chars)
    if not chunks: raise ValueError("Script mein bolne layak text nahi mila.")
    v = load_voice(name)
    status = {b["name"]: b for b in backend_status()}
    backend = v.backend if status.get(v.backend, {}).get("ready") else pick_backend()
    if not backend: raise RuntimeError("Koi cloning backend ready nahi; Piper voice cloning nahi karta.")
    # Do not silently synthesize all dialogue in one voice when speaker labels differ.
    speakers = sorted({x["speaker"] for x in chunks if x["speaker"] not in ("default", name)})
    if speakers:
        raise ValueError("Multiple speaker labels detected but speaker-to-voice mapping is not configured: " + ", ".join(speakers))
    od = Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    voice_digest = _voice_fingerprint(v)
    manifest_path = od / "generation_manifest.json"
    manifest = {"schema_version": 3, "voice": name, "voice_sha256": voice_digest, "backend": backend, "script_sha256": digest,
                "started_at": time.time(), "max_chars": max_chars, "items": [], "status": "running"}
    if resume and manifest_path.is_file():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (old.get("script_sha256") == digest and old.get("voice") == name
                    and old.get("voice_sha256") == voice_digest and old.get("backend") == backend
                    and old.get("max_chars") == max_chars and old.get("schema_version") == 3):
                manifest = old
        except Exception: pass
    prior = {int(x["sequence"]): x for x in manifest.get("items", []) if "sequence" in x}
    rows, successful_files = [], []
    for item in chunks:
        i = item["sequence"]; target = od / f"{i:05d}_{item['emotion']}.wav"
        old = prior.get(i)
        same_chunk = bool(old and all(old.get(k) == item.get(k) for k in ("sequence", "speaker", "emotion", "text", "chunk")))
        if resume and same_chunk and old.get("status") == "ok" and target.is_file():
            try:
                _wav_info(target)
                from tools.audio_qa import inspect_wav
                cached_qa = inspect_wav(target)
                if not cached_qa["pass"]:
                    raise ValueError("cached chunk failed audio QA")
                rows.append(old); successful_files.append(target); continue
            except Exception:
                # Corrupt or degraded cached chunks are regenerated, never silently reused.
                pass
        error = None; ok = False; qa = None
        for attempt in range(retries + 1):
            try:
                v.render_emotion = item.get("emotion", "neutral")
                ok = bool(_render_line(backend, v, item["text"], target))
                if ok:
                    _wav_info(target)
                    from tools.audio_qa import inspect_wav
                    qa = inspect_wav(target)
                    if not qa["pass"]:
                        raise ValueError("Audio QA rejected output: " + ", ".join(qa["warnings"]))
                    break
                error = "backend returned failure or output missing"
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            if target.exists(): target.unlink()
        row = {**item, "file": str(target) if ok else None, "status": "ok" if ok else "failed",
               "attempts": attempt + 1, "error": None if ok else error,
               "qa": qa if ok else None}
        rows.append(row)
        if ok: successful_files.append(target)
        manifest.update(items=rows, updated_at=time.time())
        _atomic_json(manifest_path, manifest)
        print(("ok  " if ok else "FAIL"), i, f"[{item['emotion']}]", item["text"][:42])
    failed = [x for x in rows if x.get("status") != "ok"]
    master = None
    master_path = od / "master.wav"
    # Never leave an old successful master looking current after a failed new run.
    if failed and master_path.exists():
        master_path.unlink()
    if stitch and not failed and successful_files:
        master = _stitch_wavs(successful_files, master_path, gap_ms=stitch_gap_ms)
    elif master_path.exists():
        master_path.unlink()
    manifest.update(status="completed" if not failed else "partial_failure", items=rows,
                    completed_at=time.time(), master=master, voice_sha256=voice_digest)
    _atomic_json(manifest_path, manifest)
    return {"voice": name, "backend": backend, "ok": len(successful_files), "failed": len(failed),
            "out": str(od), "manifest": str(manifest_path), "master": master, "lines": rows}


def cmd_backends() -> int:
    for b in backend_status():
        print(f"{'[READY]' if b['ready'] else '[ --  ]'} {b['name']:9s} {b['why']}")
    print(f"\nChuna jayega: {pick_backend() or 'koi nahi (cloning ke liye indicf5 ya xtts chahiye)'}")
    return 0


def cmd_audit() -> int:
    rows = []
    for v in list_voices():
        rows.append({"voice": v.name, "consent": v.consent, "backend": v.backend,
                     "transcript": bool(v.transcript),
                     "refs": len(getattr(v, "emotion_references", {}) or {})})
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0 if all(r["consent"] for r in rows) else 1


def cmd_voices() -> int:
    vs = list_voices()
    if not vs:
        print("koi voice enroll nahi hui")
        return 0
    for v in vs:
        print(f"{v.name:12s} backend={v.backend:9s} consent={'haan' if v.consent else 'NAHI'} "
              f"| {v.transcript[:40]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ASTRA voice clone (consent ke saath)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backends"); sub.add_parser("voices")
    sub.add_parser("audit")
    rv = sub.add_parser("revoke", help="voice profile ki permission revoke karo")
    rv.add_argument("--name", required=True)
    rv.add_argument("--reason", default="speaker_request")
    er = sub.add_parser("add-emotion-reference", help="same-speaker emotional reference sample register karein")
    er.add_argument("--name", required=True); er.add_argument("--emotion", required=True)
    er.add_argument("--audio", required=True); er.add_argument("--transcript", required=True)
    er.add_argument("--consent", action="store_true")
    er.add_argument("--same-speaker-confirmed", action="store_true")
    e = sub.add_parser("enroll")
    e.add_argument("--name", required=True); e.add_argument("--audio", required=True)
    e.add_argument("--transcript", required=True); e.add_argument("--consent", action="store_true")
    e.add_argument("--backend", default="")
    e.add_argument("--from-media", default="", help="video ya audio file (mp4/mp3/wav)")
    e.add_argument("--seconds", type=float, default=12.0)
    s = sub.add_parser("speak")
    s.add_argument("--name", required=True); s.add_argument("--script", required=True)
    s.add_argument("--out", default=str(OUT / "clone"))
    s.add_argument("--retries", type=int, default=1)
    s.add_argument("--max-chars", type=int, default=220)
    s.add_argument("--no-resume", action="store_true")
    s.add_argument("--no-stitch", action="store_true")
    s.add_argument("--stitch-gap-ms", type=int, default=0, help="chunk boundaries par extra silence; default 0")
    a = ap.parse_args()
    if a.cmd == "backends":
        return cmd_backends()
    if a.cmd == "audit":
        return cmd_audit()
    if a.cmd == "voices":
        return cmd_voices()
    if a.cmd == "revoke":
        try:
            from tools.consent import revoke_consent
            revoke_consent(_voice_dir(a.name), a.reason)
            print(f"[OK] {a.name}: consent revoked; future generation blocked")
            return 0
        except Exception as exc:
            print(f"[x] {type(exc).__name__}: {exc}")
            return 1
    if a.cmd == "add-emotion-reference":
        try:
            result = add_emotion_reference(a.name, a.emotion, a.audio, a.transcript,
                                           a.consent, a.same_speaker_confirmed)
            print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
        except Exception as exc:
            print(f"[x] {type(exc).__name__}: {exc}"); return 1
    if a.cmd == "enroll":
        try:
            if a.from_media:
                v = enroll_from_media(a.name, a.from_media, a.consent, a.seconds,
                                      a.transcript or "", a.backend)
            else:
                v = enroll(a.name, a.audio, a.transcript, a.consent, a.backend)
            print(json.dumps(v.__dict__, ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            print(f"[x] {type(exc).__name__}: {exc}")
            return 1
    rep = speak(a.name, a.script, a.out, retries=max(0, a.retries), max_chars=a.max_chars, resume=not a.no_resume, stitch=not a.no_stitch, stitch_gap_ms=a.stitch_gap_ms)
    print(json.dumps({k: rep[k] for k in ("voice", "backend", "ok", "failed", "out", "manifest", "master")},
                     ensure_ascii=False, indent=2))
    return 0 if rep["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
