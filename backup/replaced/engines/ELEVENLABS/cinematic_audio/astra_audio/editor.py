"""Non-destructive AI-assisted audio editing primitives for ASTRA.

DSP edits run locally. Optional stem separation uses the `audio-separator` package
(ONNX/MDX/VR/BS-Roformer/Demucs models). No source file is ever overwritten.
"""
from __future__ import annotations
import json, math, shutil, subprocess
from pathlib import Path
from typing import Any
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt
from .io import load_audio

SUPPORTED = {'.wav', '.flac', '.ogg', '.aiff', '.aif', '.mp3', '.m4a'}


def _read(path: str | Path):
    p=Path(path).expanduser().resolve()
    if not p.is_file() or p.suffix.lower() not in SUPPORTED:
        raise ValueError(f'Unsupported or missing audio file: {p}')
    x,sr,_decoder=load_audio(p)
    if not len(x) or sr < 8000: raise ValueError('Audio is empty or sample rate is invalid')
    return x,sr,p


def _write(path: str | Path, x: np.ndarray, sr: int, overwrite=False):
    p=Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists() and not overwrite: raise FileExistsError(f'Refusing to overwrite: {p}')
    x=np.asarray(x,dtype=np.float32)
    if x.ndim==1: x=x[:,None]
    if not np.isfinite(x).all(): raise ValueError('Audio contains NaN/Inf')
    peak=float(np.max(np.abs(x))) if x.size else 0
    if peak>1.0: x=x/peak*0.999
    tmp=p.with_name(p.stem+'.tmp'+p.suffix)
    sf.write(str(tmp),x,sr,subtype='PCM_24' if p.suffix.lower()=='.wav' else 'PCM_16')
    tmp.replace(p)
    return str(p)


def inspect_audio(path: str | Path) -> dict:
    x,sr,p=_read(path); mono=x.mean(axis=1)
    rms=float(np.sqrt(np.mean(mono**2)))
    peak=float(np.max(np.abs(x)))
    result={'path':str(p),'duration_seconds':len(x)/sr,'sample_rate':sr,'channels':x.shape[1],
            'peak_dbfs':20*math.log10(max(peak,1e-12)),'rms_dbfs':20*math.log10(max(rms,1e-12)),
            'clipped_samples':int(np.sum(np.abs(x)>=0.9999)),'silence_ratio':float(np.mean(np.abs(mono)<1e-4))}
    try:
        import librosa
        tempo,beats=librosa.beat.beat_track(y=mono,sr=sr,units='time')
        result.update({'estimated_bpm':float(np.asarray(tempo).reshape(-1)[0]),
                       'beat_times_seconds':np.asarray(beats[:500]).astype(float).tolist(),
                       'beat_estimation':'librosa_onset_beat_tracker'})
    except Exception as e: result['beat_estimation_note']=f'librosa unavailable or failed: {type(e).__name__}'
    return result


def cut_audio(source, output, start_seconds:float, end_seconds:float, overwrite=False):
    x,sr,_=_read(source)
    if start_seconds<0 or end_seconds<=start_seconds or end_seconds>len(x)/sr+1e-6: raise ValueError('Invalid cut range')
    a=int(round(start_seconds*sr)); b=min(len(x),int(round(end_seconds*sr)))
    return _write(output,x[a:b],sr,overwrite), {'start_seconds':start_seconds,'end_seconds':end_seconds,'duration_seconds':(b-a)/sr}


def _resample_channels(x, src_sr, dst_sr):
    if src_sr==dst_sr:return x
    from scipy.signal import resample_poly
    from math import gcd
    g=gcd(src_sr,dst_sr)
    return resample_poly(x,dst_sr//g,src_sr//g,axis=0).astype(np.float32)


def join_audio(sources, output, crossfade_seconds=2.0, match_loudness=True, beat_align=False, overwrite=False):
    if len(sources)<2: raise ValueError('At least two source tracks are required')
    items=[_read(s) for s in sources]; sr=max(v[1] for v in items)
    arr=[_resample_channels(v[0],v[1],sr) for v in items]
    ch=max(a.shape[1] for a in arr)
    arr=[np.repeat(a, ch,axis=1) if a.shape[1]==1 and ch>1 else a for a in arr]
    if any(a.shape[1]!=ch for a in arr): raise ValueError('Incompatible channel layouts')
    if match_loudness:
        target=np.median([np.sqrt(np.mean(a*a)) for a in arr]); target=max(float(target),1e-5)
        arr=[a*min(4.0,target/max(float(np.sqrt(np.mean(a*a))),1e-5)) for a in arr]
    result=arr[0]; seams=[]
    for idx,nxt in enumerate(arr[1:],1):
        overlap=min(int(crossfade_seconds*sr),len(result)//3,len(nxt)//3)
        if overlap<1:
            result=np.concatenate([result,nxt]); seams.append({'track':idx,'crossfade_seconds':0.0}); continue
        # Optional beat-aware crossfade: snap overlap to nearest beat interval when beat estimate exists.
        if beat_align:
            try:
                import librosa
                y=result.mean(axis=1); tempo,beats=librosa.beat.beat_track(y=y,sr=sr,units='samples')
                if len(beats)>1:
                    beat_len=float(np.median(np.diff(beats)))
                    candidates=[int(beat_len*k) for k in range(1,9)]
                    valid=[c for c in candidates if 0.25*sr<=c<=min(len(result)//3,len(nxt)//3)]
                    if valid: overlap=min(valid,key=lambda c:abs(c-overlap))
            except Exception: pass
        fade=np.linspace(0,1,overlap,dtype=np.float32)[:,None]
        # Equal-power crossfade, stable for correlated and uncorrelated audio.
        left=np.cos(fade*np.pi/2); right=np.sin(fade*np.pi/2)
        blended=result[-overlap:]*left+nxt[:overlap]*right
        result=np.concatenate([result[:-overlap],blended,nxt[overlap:]])
        seams.append({'track':idx,'crossfade_seconds':overlap/sr,'method':'equal_power','beat_align_requested':beat_align})
    out=_write(output,result,sr,overwrite)
    return out,{'duration_seconds':len(result)/sr,'sample_rate':sr,'tracks':len(arr),'seams':seams,
                'source_files_modified':False,'loudness_matched':match_loudness}


def apply_effects(source, output, gain_db=0.0, speed=1.0, pitch_semitones=0.0,
                  lowpass_hz=None, highpass_hz=None, fade_in_seconds=0.0, fade_out_seconds=0.0, overwrite=False):
    x,sr,_=_read(source)
    if not 0.25<=speed<=4: raise ValueError('speed must be 0.25..4')
    if abs(pitch_semitones)>12: raise ValueError('pitch shift limited to +/-12 semitones')
    if pitch_semitones:
        try:
            import librosa
            y=np.stack([librosa.effects.pitch_shift(x[:,c],sr=sr,n_steps=pitch_semitones) for c in range(x.shape[1])],axis=1)
            x=y.astype(np.float32)
        except Exception as e: raise RuntimeError('Pitch shift needs librosa; install librosa') from e
    if speed!=1:
        from scipy.signal import resample
        new_len=max(1,int(round(len(x)/speed)))
        x=resample(x,new_len,axis=0).astype(np.float32)
    if highpass_hz or lowpass_hz:
        lo=highpass_hz or 20; hi=lowpass_hz or sr/2-100
        if not 0<lo<hi<sr/2: raise ValueError('Invalid filter frequencies')
        x=sosfiltfilt(butter(4,[lo,hi],btype='bandpass',fs=sr,output='sos'),x,axis=0).astype(np.float32)
    x*=10**(gain_db/20)
    fi=min(len(x),int(fade_in_seconds*sr)); fo=min(len(x),int(fade_out_seconds*sr))
    if fade_in_seconds<0 or fade_out_seconds<0: raise ValueError('Fade durations cannot be negative')
    if fi: x[:fi]*=np.linspace(0,1,fi,dtype=np.float32)[:,None]
    if fo: x[-fo:]*=np.linspace(1,0,fo,dtype=np.float32)[:,None]
    return _write(output,x,sr,overwrite),{'gain_db':gain_db,'speed':speed,'pitch_semitones':pitch_semitones,
        'highpass_hz':highpass_hz,'lowpass_hz':lowpass_hz,'source_files_modified':False}


def separate_stems(source, output_dir, model_filename='model_bs_roformer_ep_317_sdr_12.9755.ckpt'):
    """Optional deep-learning separation. Requires audio-separator and model download/cache."""
    _,_,src=_read(source); out=Path(output_dir).resolve()
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f'Refusing to write stem separation into a non-empty directory: {out}')
    out.mkdir(parents=True,exist_ok=True)
    try: from audio_separator.separator import Separator
    except Exception as e: raise RuntimeError('Install optional dependency: pip install "audio-separator[cpu]" (or its GPU extra)') from e
    sep=Separator(output_dir=str(out),output_format='WAV',output_single_stem=None)
    sep.load_model(model_filename=model_filename)
    files=sep.separate(str(src))
    return {'source':str(src),'output_dir':str(out),'model':model_filename,
            'generated_files':[str(out/f) for f in files],'source_files_modified':False,
            'warning':'Stem separation can leak artefacts; audition stems before publishing.'}


def replace_vocals_with_hindi(source, hindi_vocal, output, instrumental_stem=None,
                              separator_model='model_bs_roformer_ep_317_sdr_12.9755.ckpt',
                              vocal_gain_db=-2.0, crossfade_ms=40, overwrite=False):
    """Separate source vocals, then replace with a user-supplied/generated Hindi vocal WAV.

    This does NOT translate lyrics or synthesize singing. Provide the Hindi vocal recording.
    """
    source_path=Path(source).expanduser().resolve()
    vocal_path=Path(hindi_vocal).expanduser().resolve()
    output_path=Path(output).expanduser().resolve()
    instrumental_path=Path(instrumental_stem).expanduser().resolve() if instrumental_stem else None
    protected={source_path,vocal_path}
    if instrumental_path is not None: protected.add(instrumental_path)
    if output_path in protected:
        raise ValueError('Output must not overwrite source, Hindi vocal, or instrumental input')
    temp=None
    if instrumental_stem is None:
        temp=output_path.parent/(output_path.stem+'_stems')
        info=separate_stems(source,temp,separator_model)
        candidates=[Path(p) for p in info['generated_files'] if 'instrumental' in Path(p).stem.lower()]
        if not candidates: raise RuntimeError('Separator did not return an instrumental stem; inspect its output files')
        instrumental_stem=candidates[0]
    bg,sr,_=_read(instrumental_stem); vox,vsr,_=_read(hindi_vocal)
    vox=_resample_channels(vox,vsr,sr)
    if vox.shape[1]==1 and bg.shape[1]==2: vox=np.repeat(vox,2,axis=1)
    if vox.shape[1]!=bg.shape[1]: raise ValueError('Hindi vocal and instrumental channel layouts differ')
    # Match vocal length to available instrumental with high-quality time stretch, not sample-rate pitch change.
    ratio=len(bg)/max(1,len(vox))
    if not 0.5<=ratio<=2.0:
        raise ValueError('Hindi vocal duration differs by more than 2x; prepare a closer-length vocal stem instead of silently truncating it')
    if abs(ratio-1)>0.005:
        try:
            import librosa
            vox=np.stack([librosa.effects.time_stretch(vox[:,c],rate=1/ratio) for c in range(vox.shape[1])],axis=1)
        except Exception as e:
            raise RuntimeError('Duration matching needs librosa time-stretch; install librosa instead of using a pitch-changing fallback') from e
    if not math.isfinite(float(vocal_gain_db)) or not math.isfinite(float(crossfade_ms)) or crossfade_ms<0:
        raise ValueError('vocal_gain_db and non-negative crossfade_ms must be finite numbers')
    n=min(len(bg),len(vox)); bg=bg[:n]; vox=vox[:n]
    vox*=10**(vocal_gain_db/20)
    # Tiny edge fades prevent clicks; retain the instrumental bed.
    f=min(n//2,int(sr*crossfade_ms/1000))
    if f: vox[:f]*=np.linspace(0,1,f)[:,None]; vox[-f:]*=np.linspace(1,0,f)[:,None]
    out=_write(output,bg+vox,sr,overwrite)
    return out,{'duration_seconds':n/sr,'instrumental_stem':str(instrumental_stem),'hindi_vocal':str(Path(hindi_vocal).resolve()),
        'vocal_gain_db':vocal_gain_db,'source_files_modified':False,
        'limitation':'Lyrics translation and singing generation are not performed; Hindi vocal must be supplied. Original song timing/pitch fit may need manual review.'}


def execute_project(project_json, output_dir, overwrite=False):
    """Run an explicit edit decision list (EDL); every operation creates a new file."""
    data=json.loads(Path(project_json).read_text(encoding='utf-8'))
    ops=data.get('operations')
    if not isinstance(ops,list) or not ops: raise ValueError('Project requires a non-empty operations list')
    root=Path(output_dir).resolve(); root.mkdir(parents=True,exist_ok=True); results=[]
    for i,op in enumerate(ops,1):
        kind=op.get('type'); dest=root/f'{i:03d}_{kind}.wav'
        if kind=='cut': result,meta=cut_audio(op['source'],dest,float(op['start']),float(op['end']),overwrite)
        elif kind=='join': result,meta=join_audio(op['sources'],dest,float(op.get('crossfade_seconds',2)),bool(op.get('match_loudness',True)),bool(op.get('beat_align',False)),overwrite)
        elif kind=='effects': result,meta=apply_effects(op['source'],dest,**{k:v for k,v in op.items() if k in {'gain_db','speed','pitch_semitones','lowpass_hz','highpass_hz','fade_in_seconds','fade_out_seconds'}},overwrite=overwrite)
        elif kind=='separate': meta=separate_stems(op['source'],root/f'{i:03d}_stems',op.get('model_filename','model_bs_roformer_ep_317_sdr_12.9755.ckpt')); result=meta['generated_files']
        else: raise ValueError(f'Unsupported edit operation: {kind}')
        results.append({'operation':kind,'output':result,'details':meta})
    report={'operations':results,'source_files_modified':False,'project_file':str(Path(project_json).resolve())}
    report_path=root/'edit-report.json'
    if report_path.exists() and not overwrite: raise FileExistsError(report_path)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
