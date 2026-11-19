"""Narrative-aware cinematic soundstage: smooth spatial automation + existing story mixer.

This is deterministic DSP over user-supplied stems. Scene labels/timings must be reviewed;
no claim of automatic semantic source recognition is made.
"""
from __future__ import annotations
import json, math, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, resample_poly
from math import gcd
from .story_mix import mix_story
from .io import save_json_atomic

SCHEMA = "astra-cinematic-soundstage/v1"
MOODS = {"neutral","peaceful","tense","action","sad","fear","horror","romantic","joy","wonder","epic","mystery","devotional","comedy","grief","calm"}

def _finite(v, name, lo=None, hi=None):
    try: x=float(v)
    except (TypeError,ValueError) as e: raise ValueError(f"{name} must be numeric") from e
    if not math.isfinite(x) or (lo is not None and x<lo) or (hi is not None and x>hi): raise ValueError(f"{name} outside allowed range")
    return x

def _curve(points, duration, sr, default, key, lo, hi):
    if not points: return np.full(int(math.ceil(duration*sr)), default, np.float32)
    clean=[]
    for p in points:
        t=_finite(p.get("time_seconds"),"keyframe time",0,duration)
        v=_finite(p.get(key,default),key,lo,hi); clean.append((t,v))
    clean.sort()
    if len({t for t,_ in clean}) != len(clean): raise ValueError(f"Duplicate keyframe times for {key}")
    if clean[0][0] > 0: clean.insert(0,(0.0,default))
    n=int(math.ceil(duration*sr)); times=np.arange(n,dtype=np.float64)/sr
    return np.interp(times,[p[0] for p in clean],[p[1] for p in clean]).astype(np.float32)

def _smooth(x, sr, attack=.08, release=.35):
    out=np.empty_like(x,dtype=np.float32); prev=float(x[0]) if len(x) else 0
    aa=math.exp(-1/max(1,sr*attack)); ar=math.exp(-1/max(1,sr*release))
    for i,v in enumerate(x):
        c=aa if v>prev else ar; prev=c*prev+(1-c)*float(v); out[i]=prev
    return out

def _resample(x, src, dst):
    if src==dst:return x
    g=gcd(src,dst); return resample_poly(x,dst//g,src//g,axis=0).astype(np.float32)

def _spatialize(x, sr, track, target_sr):
    x=_resample(x,sr,target_sr); n=len(x); dur=n/target_sr
    if x.ndim==1:x=x[:,None]
    if x.shape[1]>2: raise ValueError("Soundstage supports mono/stereo stems only")
    frames=track.get("automation",[])
    if not isinstance(frames,list): raise ValueError("automation must be an array")
    distance=_smooth(_curve(frames,dur,target_sr,_finite(track.get("distance_m",8),"distance_m",0.2,500),"distance_m",0.2,500),target_sr)
    pan=_smooth(_curve(frames,dur,target_sr,_finite(track.get("pan",0),"pan",-1,1),"pan",-1,1),target_sr)
    gain=_smooth(_curve(frames,dur,target_sr,_finite(track.get("gain_db",0),"gain_db",-36,12),"gain_db",-36,12),target_sr)
    # Physically-inspired, intentionally conservative distance model; user can override attenuation.
    ref=_finite(track.get("reference_distance_m",2),"reference_distance_m",0.2,50)
    attenuation=20*np.log10(np.maximum(ref/distance,0.02))
    attenuation=np.clip(attenuation,-30,6)
    gain_lin=10**((gain+attenuation)/20)
    # Distance and occlusion soften high frequencies; no hard noise gate.
    occlusion=_finite(track.get("occlusion",0),"occlusion",0,1)
    mean_dist=float(np.median(distance))
    cutoff=float(np.clip(16000/(1+0.035*max(0,mean_dist-ref))*(1-0.72*occlusion),1200,18000))
    cutoff=min(cutoff,target_sr/2-100)
    if cutoff < target_sr/2-100:
        sos=butter(2,cutoff,btype="lowpass",fs=target_sr,output="sos")
        x=sosfiltfilt(sos,x,axis=0).astype(np.float32)
    if x.shape[1]==1:
        mono=x[:,0]
        left=np.sqrt((1-pan)/2); right=np.sqrt((1+pan)/2)
        x=np.column_stack((mono*left,mono*right)).astype(np.float32)
    else:
        # Constant-power balance pan retains stereo width.
        left=np.sqrt((1-np.maximum(pan,0))); right=np.sqrt((1+np.minimum(pan,0)))
        x[:,0]*=left; x[:,1]*=right
    x*=gain_lin[:,None]
    return x.astype(np.float32), {"median_distance_m":round(float(np.median(distance)),2),"pan_range":[round(float(np.min(pan)),2),round(float(np.max(pan)),2)],"distance_filter_cutoff_hz":round(cutoff),"occlusion":occlusion}

def render_soundstage(spec_path, output_path, report_path=None, overwrite=False):
    spec_path=Path(spec_path).resolve()
    spec=json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec,dict) or spec.get("schema")!=SCHEMA: raise ValueError(f"Expected {SCHEMA} JSON")
    tracks=spec.get("tracks")
    if not isinstance(tracks,list) or not tracks or len(tracks)>32: raise ValueError("tracks must contain 1..32 stems")
    scenes=spec.get("scenes",[])
    for s in scenes:
        if s.get("mood","neutral") not in MOODS: raise ValueError(f"Unsupported mood: {s.get('mood')}")
    target_sr=int(spec.get("sample_rate",48000))
    if not 8000<=target_sr<=96000: raise ValueError("sample_rate must be 8000..96000")
    out=Path(output_path).resolve(); report=Path(report_path).resolve() if report_path else None
    if out.exists() and not overwrite: raise FileExistsError(out)
    if report and report.exists() and not overwrite: raise FileExistsError(report)
    if out==spec_path or (report and report in {spec_path,out}): raise ValueError("Output/report must not overwrite input spec")
    source_paths=set()
    for t in tracks:
        src=Path(t["path"]); src=(spec_path.parent/src).resolve() if not src.is_absolute() else src.resolve()
        source_paths.add(src)
    if out in source_paths or (report and report in source_paths): raise ValueError("Output/report must not overwrite any source audio stem")
    tempdir=Path(tempfile.mkdtemp(prefix="astra-soundstage-"))
    prepared=[]; track_reports=[]
    try:
        for i,t in enumerate(tracks):
            src=Path(t["path"]); src=(spec_path.parent/src).resolve() if not src.is_absolute() else src.resolve()
            if not src.is_file(): raise FileNotFoundError(src)
            x,sr=sf.read(str(src),dtype="float32",always_2d=True)
            if not len(x) or sr<8000: raise ValueError(f"Invalid audio stem: {src}")
            y,spatial=_spatialize(x,sr,t,target_sr)
            staged=tempdir/f"track_{i:02d}.wav"; sf.write(staged,y,target_sr,subtype="PCM_24")
            item={k:v for k,v in t.items() if k not in {"automation","distance_m","pan","occlusion","reference_distance_m"}}
            item["path"]=str(staged); prepared.append(item)
            track_reports.append({"name":t.get("name",src.name),"source":str(src),"role":t.get("role","ambience"),**spatial,"source_modified":False})
        mix_spec={"tracks":prepared,"scenes":scenes,"sample_rate":target_sr,"creativity":spec.get("creativity",0.5),"ducking":spec.get("ducking",{"music_db":7,"ambience_db":3}),"memory_budget_mb":spec.get("memory_budget_mb",768)}
        staged_spec=tempdir/"mix-spec.json"; staged_spec.write_text(json.dumps(mix_spec,ensure_ascii=False),encoding="utf-8")
        result=mix_story(staged_spec,out,report,overwrite=overwrite)
        result["schema"]="astra-cinematic-soundstage-report/v1"
        result["spatial_tracks"]=track_reports
        result["scene_moods_supported"]=sorted(MOODS)
        result["limitations"]=["Scene timing and mood labels must be checked against the story.","Distance/pan are DSP approximations, not binaural HRTF rendering.","No source-identity recognition or sound generation is performed.","Human listening review is required before release."]
        if report: save_json_atomic(report,result)
        return result
    finally:
        import shutil; shutil.rmtree(tempdir,ignore_errors=True)
