
"""Optional audio diagnostics and speech-recognition adapters."""
from pathlib import Path
import json
def inspect_audio(path):
    p=Path(path)
    if not p.is_file(): raise FileNotFoundError(path)
    result={"path":str(p.resolve()),"size_bytes":p.stat().st_size,"duration_seconds":None,
            "sample_rate":None,"channels":None,"rms":None,"peak":None,
            "optional_dependencies_missing":[]}
    try:
        import soundfile as sf
        import numpy as np
        data,sr=sf.read(str(p),always_2d=True)
        result["sample_rate"]=int(sr); result["channels"]=int(data.shape[1])
        result["duration_seconds"]=round(len(data)/sr,3)
        result["rms"]=round(float(np.sqrt(np.mean(data.astype("float64")**2))),6)
        result["peak"]=round(float(np.max(np.abs(data))),6)
        result["clipping_detected"]=bool(result["peak"]>=0.999)
    except ImportError:
        result["optional_dependencies_missing"].append("soundfile,numpy")
    except Exception as e:
        result["audio_read_error"]=str(e)
    return result

def transcribe_with_faster_whisper(path, model_size="small"):
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError("Install optional extra: pip install faster-whisper") from e
    model=WhisperModel(model_size,device="cpu",compute_type="int8")
    segments,info=model.transcribe(str(path),language="hi",vad_filter=True)
    rows=[{"start":s.start,"end":s.end,"text":s.text} for s in segments]
    return {"language":info.language,"language_probability":info.language_probability,"segments":rows}
