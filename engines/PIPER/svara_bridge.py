"""Optional Svara-TTS expressive Hindi neural backend bridge.
Uses the documented OpenAI-compatible /v1/audio/speech endpoint.
Disabled unless config.expressive_backend == 'svara'.
"""
from pathlib import Path
import requests

TAGS={"happy":"<happy>","sad":"<sad>","angry":"<anger>","fearful":"<fear>"}

def render(text, out_path, config, profile=None, emotion="neutral", timeout=180):
    base=(config.get("svara_base_url") or "http://127.0.0.1:8080/v1").rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    model=config.get("svara_model") or "svara-tts-v1"
    voice=(profile or {}).get("svara_voice") or config.get("svara_voice") or "hi_female"
    tag=TAGS.get(emotion)
    prompt=text.rstrip()
    if tag and tag not in prompt:
        prompt=f"{prompt} {tag}"
    out=Path(out_path);out.parent.mkdir(parents=True,exist_ok=True)
    fmt="wav" if out.suffix.lower()==".wav" else "mp3"
    payload={"model":model,"input":prompt,"voice":voice,"response_format":fmt}
    try:
        response=requests.post(base+"/audio/speech",json=payload,timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Svara expressive backend unavailable at {base}: {exc}. Start the Svara inference server or set expressive_backend='native'.") from exc
    if not response.content or len(response.content)<100:
        raise RuntimeError("Svara API returned an empty or implausibly small audio response")
    out.write_bytes(response.content)
    return str(out)
