from pathlib import Path
import base64, io, json
import numpy as np
import soundfile as sf
import pytest
from astra_audio.tts_sarvam import SarvamTTS, split_tts_text, synthesize_script, extract_script_segments, make_workflow_adapter

def _fake_wav_b64():
    sr=22050
    t=np.arange(sr//5,dtype=np.float32)/sr
    buf=io.BytesIO()
    sf.write(buf,0.08*np.sin(2*np.pi*440*t),sr,format="WAV",subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode()

def test_sarvam_adapter_validates_payload_and_writes_wav(tmp_path):
    calls=[]
    audio=_fake_wav_b64()
    def transport(payload):
        calls.append(payload)
        return {"request_id":"mock-123","audios":[audio]}
    client=SarvamTTS(model="bulbul:v4-flash",language_code="hi-IN",transport=transport)
    result=client.synthesize("नमस्ते भारत","priya_hi_narration",tmp_path/"line.wav")
    assert result["request_id"]=="mock-123"
    assert result["sample_rate"]==22050
    assert calls[0]["speaker"]=="priya_hi_narration"
    assert calls[0]["speech_sample_rate"]==48000
    assert (tmp_path/"line.wav").is_file()

def test_sarvam_adapter_refuses_overwrite_and_bad_controls(tmp_path):
    client=SarvamTTS(transport=lambda p: {"audios":[_fake_wav_b64()]})
    out=tmp_path/"line.wav"
    client.synthesize("hello","shubh",out)
    with pytest.raises(FileExistsError):
        client.synthesize("hello","shubh",out)
    with pytest.raises(ValueError):
        client.synthesize("hello","shubh",tmp_path/"bad.wav",pace=2.5)

def test_sarvam_adapter_requires_key_when_real_transport_used(monkeypatch,tmp_path):
    monkeypatch.delenv("SARVAM_API_KEY",raising=False)
    client=SarvamTTS(api_key=None)
    with pytest.raises(RuntimeError,match="SARVAM_API_KEY"):
        client.synthesize("hello","shubh",tmp_path/"no-key.wav")

def test_split_tts_text_preserves_text_and_limit():
    text=("यह एक वाक्य है। "*300)
    chunks=split_tts_text(text, max_chars=250)
    assert len(chunks)>1
    assert all(len(c)<=250 for c in chunks)
    assert "".join(chunks).replace(" ","")==text.replace(" ","")

def test_script_tts_keeps_one_voice_id_per_character(tmp_path):
    script=tmp_path/"story.txt"
    script.write_text("दृश्य 1: गाँव\nवाचक: सुबह हो गई।\nगौरी: नमस्ते।\nSFX: घंटी बजे।\nगौरी: चलो।\nमोहन: हाँ।\n",encoding="utf-8")
    segments=extract_script_segments(script)
    assert [x["speaker_name"] for x in segments]==["वाचक","गौरी","गौरी","मोहन"]
    calls=[]
    audio=_fake_wav_b64()
    def transport(payload):
        calls.append(payload)
        return {"request_id":str(len(calls)),"audios":[audio]}
    voices={"model":"bulbul:v4-flash","language_code":"hi-IN",
            "speakers":{"वाचक":"shubh_hi_narration","गौरी":"priya_hi_narration","मोहन":"ashutosh_hi_narration"}}
    manifest=synthesize_script(script,voices,tmp_path/"tts",transport=transport)
    assert manifest["clip_count"]==4
    assert manifest["voice_continuity"]["गौरी"]=="priya_hi_narration"
    assert [c["speaker"] for c in calls].count("priya_hi_narration")==2
    assert (tmp_path/"tts"/"tts-manifest.json").is_file()
    assert (tmp_path/"tts"/"dialogue-mix.wav").is_file()
    assert len(manifest["timeline"]) == 4
    assert manifest["timeline"][0]["start_seconds"] == 0
    assert manifest["timeline"][1]["start_seconds"] > manifest["timeline"][0]["end_seconds"]


def test_sarvam_voice_adapter_integrates_with_audio_workflow(tmp_path):
    from astra_audio.workflow import AudioWorkflow
    script=tmp_path/"story.txt"
    script.write_text("वाचक: नमस्ते।\\n",encoding="utf-8")
    calls=[]
    voice_map={"model":"bulbul:v3","language_code":"hi-IN","speakers":{"वाचक":"shubh"}}
    adapter=make_workflow_adapter(voice_map,tmp_path/"workflow-tts",
        transport=lambda payload: (calls.append(payload) or {"audios":[_fake_wav_b64()]}))
    workflow=AudioWorkflow()
    workflow.register("voice_generation",adapter)
    # Adapter can be called directly as the stage contract; full workflow still
    # correctly refuses to run until every other production stage is connected.
    result=adapter({"story_script_path":str(script)})
    assert result["clip_count"]==1
    assert calls[0]["speaker"]=="shubh"


def test_sarvam_script_generation_rolls_back_partial_clips_on_failure(tmp_path):
    script=tmp_path/"story.txt"
    script.write_text("वाचक: पहली पंक्ति।\nगौरी: दूसरी पंक्ति।\n",encoding="utf-8")
    count={"n":0}
    def transport(payload):
        count["n"]+=1
        if count["n"]==2:
            raise RuntimeError("mock quota failure")
        return {"audios":[_fake_wav_b64()]}
    voices={"model":"bulbul:v3","language_code":"hi-IN",
            "speakers":{"वाचक":"shubh","गौरी":"priya"}}
    out=tmp_path/"failed-tts"
    with pytest.raises(RuntimeError,match="quota"):
        synthesize_script(script,voices,out,transport=transport)
    assert not list(out.glob("*.wav"))
    assert not (out/"tts-manifest.json").exists()
