"""Character-aware rendering with sentence-level Hindi prosody planning."""
import os
import json, time
from pathlib import Path
from performance import plan_script
from prosody_intelligence import analyze_script
from tts_engine import render_segment
from audio_assembly import make_silence, assemble_wav
from character_voice import voice_shape

def load_voice_profiles(path):
    p=Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def map_profiles_by_name(profile_file):
    raw=load_voice_profiles(profile_file)
    return {v.get("name"):v for v in raw.values()}

def can_assemble(audio_parts, failures): return bool(audio_parts) and not failures

def render_story(text, config, output_dir, profile_file=None):
    outdir=Path(output_dir); outdir.mkdir(parents=True,exist_ok=True)
    profiles=map_profiles_by_name(profile_file) if profile_file else {}
    if not profiles:
        # profile file nahi di — to script scan se hi umar/ling le lo,
        # warna har kirdaar ek hi awaaz me bolta hai.
        try:
            from hindi_core import scan_script
            for c in scan_script(text).get("characters", []):
                profiles[c["name"]] = {"age_group": c.get("age_group","unspecified"),
                                       "voice_presentation": c.get("voice_presentation","unspecified")}
        except Exception:
            pass
    script_plan=plan_script(text)
    deep=analyze_script(text,profiles)
    deep_by_line={r['line']:r for r in deep['segments']}
    warnings=[]; failures=[]; audio_parts=[]; manifest=[]
    for idx,row in enumerate(script_plan,1):
        speaker=row.get('speaker'); profile=profiles.get(speaker,{})
        if speaker and not profile: warnings.append(f"Line {row['line']}: no verified voice profile for {speaker}; default engine voice will be used.")
        intelligence=deep_by_line.get(row['line'],{})
        planned_emotion=intelligence.get('emotion','neutral')
        delivery=intelligence.get('delivery',{})
        for event_index,event in enumerate(row.get('events',[]),1):
            if event['kind']=='pause':
                duration=event['duration_ms']
                if event.get('source')=='punctuation': duration=max(duration,int(delivery.get('pause_after_ms',duration)))
                pause=outdir/f"pause_{idx:04d}_{event_index:02d}.wav"; make_silence(pause,duration); audio_parts.append(str(pause))
                manifest.append({'line':row['line'],'speaker':speaker,'kind':'pause','duration_ms':duration}); continue
            txt=event['text']
            if not txt.strip(): continue
            chunk_cfg=dict(config); chunk_cfg['_stretch']=bool(event.get('stretch'))
            if profile:
                if profile.get('voice_id'): chunk_cfg['voice']=profile['voice_id']
                if profile.get('piper_model'): chunk_cfg['piper_model']=profile['piper_model']
                elif config.get('piper_models_by_presentation'):
                    # ek hi (mard) model se aurat ki awaaz banani padti thi — ab
                    # ling ke hisaab se alag model: female / male
                    pres = (profile.get('voice_presentation') or 'unspecified').lower()
                    mm = config['piper_models_by_presentation']
                    pick = mm.get(pres) or mm.get('unspecified')
                    if pick: chunk_cfg['piper_model'] = pick
                if profile.get('espeak_voice'): chunk_cfg['voice']=profile['espeak_voice']
                if profile.get('rate'): chunk_cfg['rate']=profile['rate']
            emotion=event.get('emotion','neutral')
            if emotion=='neutral' and planned_emotion!='neutral': emotion=planned_emotion
            chunk=outdir/f"chunk_{idx:04d}_{event_index:02d}.{ 'mp3' if config['adapter'] in ('elevenlabs','edge') else 'wav'}"
            try:
                path=render_segment(txt,chunk,chunk_cfg,emotion=emotion,stretch=event.get('stretch',False),prosody=delivery)
                # har kirdaar ka apna sur (ek hi model se bhi alag sune)
                try:
                    pitch, rate = voice_shape(profile)
                    if abs(pitch-1.0) > 0.02 or abs(rate-1.0) > 0.02:
                        path = _reshape(path, pitch, rate)
                except Exception as exc:
                    warnings.append(f"Line {row['line']}: voice shaping skip ({exc})")
                audio_parts.append(path)
                manifest.append({'line':row['line'],'speaker':speaker,'kind':'speech','text':txt,'emotion':emotion,
                  'emotion_confidence':intelligence.get('emotion_confidence'),'emotion_evidence':intelligence.get('emotion_evidence'),
                  'delivery_plan':delivery,'explicit_stretch':event.get('stretch',False),'audio':path})
            except Exception as exc:
                message=f"Line {row['line']} chunk {event_index} failed: {exc}"; warnings.append(message); failures.append(message)
                manifest.append({'line':row['line'],'speaker':speaker,'kind':'failed','error':str(exc)})
    result={'schema_version':'0.7','engine':config['title'],'generated_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
      'chunks':manifest,'warnings':warnings,'audio_assembly':'not_attempted','prosody_analysis':deep['summary'],
      'backend_capabilities_note': 'Prosody plan is passed to each adapter; actual audible emotion depends on backend/model support.'}
    if can_assemble(audio_parts,failures):
        try: result['final_audio']=assemble_wav(audio_parts,outdir/'story_final.wav'); result['audio_assembly']='success'
        except Exception as exc: result['audio_assembly']='failed_or_unavailable'; result['assembly_error']=str(exc)
    result['render_failures']=failures
    result['note']='A planner is not a neural acting model. Unsupported emotion controls remain unsupported; no realistic quality claim is made without listening evaluation.'
    (outdir/'render_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (outdir/'prosody_analysis.json').write_text(json.dumps(deep,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def _reshape(path, pitch, rate):
    """File ko us kirdaar ke sur/raftaar par le jao (ffmpeg, jagah par hi)."""
    import subprocess, shutil, tempfile
    ff = shutil.which("ffmpeg")
    if not ff:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return path
    tmp = str(path) + ".shape" + (".wav" if str(path).endswith(".wav") else ".mp3")
    af = f"aresample=44100,asetrate=44100*{pitch:.4f},aresample=44100,atempo={1/pitch:.4f}"
    if abs(rate - 1.0) > 0.02:
        af += f",atempo={rate:.4f}"
    r = subprocess.run([ff, "-loglevel", "error", "-y", "-i", str(path), "-filter:a", af, tmp],
                       capture_output=True)
    if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 1000:
        os.replace(tmp, str(path))
    elif os.path.exists(tmp):
        try: os.remove(tmp)
        except Exception: pass
    return path
