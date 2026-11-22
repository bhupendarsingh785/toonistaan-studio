import wave, subprocess, numpy as np, json
from piper import PiperVoice
from piper.config import SynthesisConfig
from imageio_ffmpeg import get_ffmpeg_exe
from faster_whisper import WhisperModel
FF=get_ffmpeg_exe()
v=PiperVoice.load("voices/hi_IN-pratham-medium.onnx", config_path="voices/hi_IN-pratham-medium.onnx.json")
m=WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=1, download_root="/scratch/work/whisper")
def say(t):
    with wave.open("/tmp/p.wav","wb") as w:
        v.synthesize_wav(t, w, syn_config=SynthesisConfig(length_scale=1.0))
    r=subprocess.run([FF,"-v","quiet","-i","/tmp/p.wav","-f","f32le","-ac","1","-ar","16000","-"],capture_output=True)
    x=np.frombuffer(r.stdout,dtype=np.float32).copy()
    s,_=m.transcribe(x, language="hi", vad_filter=False, condition_on_previous_text=False)
    return " ".join(a.text.strip() for a in s)
cases={"बारिश":["बारिश","बारीश"],"ठंडक":["ठंडक","ठण्डक"],"गाँव":["गाँव","गांव"],
       "देखो":["देखो","देखो!"],"कितनी":["कितनी","कितनी।"],"खुशबू":["खुशबू","खुशबु"]}
out={}
for k,cs in cases.items():
    out[k]=[{"cand":c,"heard":say(c)} for c in cs]
    print(k, "|", out[k])
json.dump(out, open("/scratch/work/pronounce_dict_test.json","w"), ensure_ascii=False, indent=1)
