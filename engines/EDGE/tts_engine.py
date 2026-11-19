
"""TTS adapters with explicit per-character voice routing and capability limits."""
import os, shutil, subprocess, asyncio
from pathlib import Path

CAPABILITIES = {
 "edge": {"voice_selection":True,"emotion_control":"not guaranteed by edge-tts adapter","word_level_stretch":"segment-level rate approximation","offline":False},
 "piper":{"voice_selection":"per-character ONNX model path","emotion_control":"not supported by standard Piper CLI","word_level_stretch":"segment-level length scale","offline":True},
 "elevenlabs":{"voice_selection":True,"emotion_control":"model-dependent audio tags","word_level_stretch":"segment-level speed setting when supported","offline":False},
 "espeak":{"voice_selection":"installed eSpeak voices","emotion_control":"limited rate/pitch only; not natural acting","word_level_stretch":"segment-level slower rate","offline":True}
}

def _slow_rate(value):
    try:
        n=int(str(value).replace("%","").replace("+",""))
    except Exception:n=0
    return f"{min(0,n-18):+d}%"

def render_segment(text, out_path, config, profile=None, emotion="neutral", stretch=False, prosody=None):
    adapter=config["adapter"]; out=Path(out_path); out.parent.mkdir(parents=True,exist_ok=True)
    prosody=prosody or {}
    voice=(profile or {}).get("voice_id") or config.get("voice")
    if config.get("expressive_backend") == "svara":
        raise RuntimeError("Svara is configured as a research-only source in this build; it is not a production TTS backend. Set expressive_backend='native'.")
    if adapter=="edge":
        try: import edge_tts
        except ImportError as e: raise RuntimeError("Install edge-tts in this engine's environment.") from e
        voice=voice or "hi-IN-SwaraNeural"
        rate=_slow_rate(config.get("rate","+0%")) if stretch else config.get("rate","+0%")
        rate_map={'slow':'-12%','measured_slow':'-8%','measured':'-3%','lively':'+5%','quick_onset':'+7%','firm':'+0%','uneven_careful':'-5%','projected':'+4%','conversational':'+0%'}
        pitch_map={'slightly_up':'+5Hz','slightly_low':'-4Hz','low_soft':'-8Hz','rising_question':'+4Hz','dynamic':'+7Hz','up_then_down':'+6Hz'}
        if not stretch: rate=rate_map.get(prosody.get('rate'),rate)
        pitch=pitch_map.get(prosody.get('pitch'),'+0Hz')
        async def go():
            await edge_tts.Communicate(text,voice,rate=rate,pitch=pitch,volume=config.get("volume","+0%")).save(str(out))
        asyncio.run(go())
    elif adapter=="piper":
        exe=config.get("piper_executable") or shutil.which("piper")
        model=(profile or {}).get("piper_model") or config.get("piper_model")
        if not exe or not model or not Path(model).exists():
            raise RuntimeError("Piper requires a valid local Hindi ONNX voice model. No model is bundled.")
        cmd=[exe,"--model",model,"--output_file",str(out)]
        if stretch: cmd += ["--length-scale","1.18"]
        else:
            scale={'slow':'1.10','measured_slow':'1.07','measured':'1.03','lively':'0.96','quick_onset':'0.94','conversational':'1.00'}.get(prosody.get('rate'))
            if scale: cmd += ["--length-scale",scale]
        subprocess.run(cmd,input=text,text=True,check=True,timeout=120)
    elif adapter=="elevenlabs":
        import requests
        key=os.getenv("ELEVENLABS_API_KEY")
        voice=(profile or {}).get("voice_id") or os.getenv("ELEVENLABS_VOICE_ID") or config.get("voice")
        if not key or not voice: raise RuntimeError("ElevenLabs disabled: supply your API key and per-character voice IDs; usage may be billable.")
        model=config.get("model_id","eleven_v4")
        prompt=text
        tag={"happy":"[excited] ","sad":"[sad] ","angry":"[angry] ","fearful":"[afraid] ",
             "whisper":"[whispers] ","laughing":"[laughs] ","crying":"[crying] ","surprised":"[surprised] ","curious":"[curious] ",
             "serious":"[serious] ","shout":"[shouts] "}.get(emotion,"")
        if model in ("eleven_v4","eleven_v4_turbo"):
            prompt=tag+prompt
        settings={"stability":float(config.get("stability",0.55)),
                  "similarity_boost":float(config.get("similarity_boost",0.75)),
                  "use_speaker_boost":bool(config.get("use_speaker_boost",True))}
        if model not in ("eleven_v4","eleven_v4_turbo"):
            settings["style"]=float(config.get("style",0.15))
            settings["speed"]=float(config.get("stretch_speed",0.82) if stretch else config.get("speed",1.0))
        r=requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            headers={"xi-api-key":key,"Content-Type":"application/json","Accept":"audio/mpeg"},
            json={"text":prompt,"model_id":model,"voice_settings":settings},timeout=90)
        r.raise_for_status(); out=out.with_suffix(".mp3"); out.write_bytes(r.content)
    elif adapter=="espeak":
        exe=config.get("espeak_executable") or shutil.which("espeak-ng") or shutil.which("espeak")
        if not exe: raise RuntimeError("Install eSpeak NG; binary not found.")
        rate=int(config.get("espeak_rate",155)); pitch=50; amplitude=100
        if stretch: rate=max(90,int(rate*0.82))
        rate_delta={'slow':-18,'measured_slow':-12,'measured':-5,'lively':8,'quick_onset':12,'projected':5}.get(prosody.get('rate'),0)
        rate=max(85,min(230,rate+rate_delta))
        pitch_delta={'slightly_up':8,'slightly_low':-6,'low_soft':-12,'rising_question':6,'dynamic':10,'up_then_down':8}.get(prosody.get('pitch'),0)
        pitch=max(0,min(99,pitch+pitch_delta))
        if prosody.get('energy') in ('soft','very_low','tense_low'): amplitude=78
        elif prosody.get('energy') in ('high','controlled_high','bright'): amplitude=112
        v=(profile or {}).get("espeak_voice") or config.get("voice","hi")
        subprocess.run([exe,"-v",v,"-s",str(rate),"-p",str(pitch),"-a",str(amplitude),"-w",str(out),text],check=True,timeout=120)
    else: raise ValueError("Unknown adapter.")
    if not out.exists() or out.stat().st_size<100:
        raise RuntimeError("Renderer did not create a valid audio file.")
    return str(out)
