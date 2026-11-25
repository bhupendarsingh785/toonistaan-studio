import json
import numpy as np
import soundfile as sf
import pytest
from astra_audio.soundstage import render_soundstage, SCHEMA

def test_soundstage_renders_spatial_tracks_and_keeps_sources(tmp_path):
    sr=16000; t=np.arange(sr*3)/sr
    paths=[]
    for i,f in enumerate([180,440]):
        p=tmp_path/f"s{i}.wav"; sf.write(p,(0.08*np.sin(2*np.pi*f*t)).astype('float32'),sr); paths.append(p)
    spec={"schema":SCHEMA,"sample_rate":sr,"tracks":[
        {"name":"voice","path":str(paths[0]),"role":"narration","distance_m":1},
        {"name":"train","path":str(paths[1]),"role":"sfx","distance_m":80,"automation":[
            {"time_seconds":0,"distance_m":80,"pan":-0.8,"gain_db":-12},
            {"time_seconds":2,"distance_m":5,"pan":0.8,"gain_db":0}]}],
        "scenes":[{"start_seconds":0,"end_seconds":3,"mood":"wonder","intensity":0.5}]}
    sp=tmp_path/'spec.json'; sp.write_text(json.dumps(spec))
    out=tmp_path/'out.wav'; rep=tmp_path/'report.json'
    result=render_soundstage(sp,out,rep)
    audio,sr2=sf.read(out,always_2d=True)
    assert sr2==sr and audio.shape[1]==2 and len(audio)==sr*3
    assert result['track_count']==2 and len(result['spatial_tracks'])==2
    assert all(p.exists() for p in paths)
    assert json.loads(rep.read_text())['schema']=='astra-cinematic-soundstage-report/v1'

def test_soundstage_rejects_bad_pan(tmp_path):
    p=tmp_path/'s.wav'; sf.write(p,np.zeros(16000,dtype='float32'),16000)
    spec={"schema":SCHEMA,"sample_rate":16000,"tracks":[{"path":str(p),"role":"sfx","pan":2}]}
    sp=tmp_path/'s.json'; sp.write_text(json.dumps(spec))
    with pytest.raises(ValueError): render_soundstage(sp,tmp_path/'out.wav')
