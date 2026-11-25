import json, tempfile, unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from unittest.mock import patch
from astra_audio.story_mix import mix_story, _activity_envelope, _scene_gain_curve

class StoryMixTests(unittest.TestCase):
    def test_story_mix_levels_tracks_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); sr=16000; n=sr*4
            t=np.arange(n)/sr
            voice=np.zeros(n,dtype=np.float32)
            voice[:sr*2]=0.10*np.sin(2*np.pi*180*t[:sr*2])
            music=(0.08*np.sin(2*np.pi*440*t)).astype("float32")
            vp=d/"voice.wav"; mp=d/"music.wav"
            sf.write(vp,voice,sr); sf.write(mp,music,sr)
            before_v=vp.read_bytes(); before_m=mp.read_bytes()
            spec={"creativity":0.7,"tracks":[
                {"path":str(vp),"role":"narration"},
                {"path":str(mp),"role":"music","gain_db":-1}
            ],"scenes":[{"start_seconds":0,"end_seconds":4,"mood":"tense","intensity":0.8}]}
            sp=d/"mix.json"; sp.write_text(json.dumps(spec),encoding="utf-8")
            out=d/"story.wav"; report=d/"report.json"
            r=mix_story(sp,out,report)
            y,ysr=sf.read(out)
            self.assertEqual(ysr,sr)
            self.assertEqual(r["track_count"],2)
            self.assertTrue(r["dialogue_driven_ducking_enabled"])
            self.assertLessEqual(float(np.max(np.abs(y))),0.951)
            self.assertEqual(before_v,vp.read_bytes())
            self.assertEqual(before_m,mp.read_bytes())
            self.assertTrue(report.exists())
    def test_ducking_activity_envelope(self):
        sr=1000
        x=np.zeros((1000,1),dtype=np.float32)
        x[:500,0]=0.3
        env=_activity_envelope(x,sr,20)
        self.assertGreater(float(np.max(env)),0.8)
        self.assertLess(float(np.mean(env[800:])),0.1)
    def test_mood_curve_is_modest_and_creativity_scales(self):
        n=1000; sr=1000
        low=_scene_gain_curve(n,sr,[{"start_seconds":0,"end_seconds":1,"mood":"action","intensity":1}], "sfx",0.2)
        high=_scene_gain_curve(n,sr,[{"start_seconds":0,"end_seconds":1,"mood":"action","intensity":1}], "sfx",1.0)
        self.assertGreater(float(np.mean(high)),float(np.mean(low)))
        self.assertLess(float(np.max(high)),1.3)

    def test_sfx_cue_offset_and_fade_in(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); sr=8000
            x=np.ones(sr,dtype="float32")*0.1
            src=d/"impact.wav"; sf.write(src,x,sr)
            spec={"creativity":0,"tracks":[
                {"path":str(src),"role":"sfx","start_seconds":1.0,"fade_in_ms":100}
            ]}
            sp=d/"spec.json"; sp.write_text(json.dumps(spec))
            out=d/"mix.wav"; mix_story(sp,out)
            y,_=sf.read(out)
            self.assertEqual(len(y),sr*2)
            self.assertLess(float(np.max(np.abs(y[:int(.9*sr)]))),1e-6)
            self.assertLess(float(np.max(np.abs(y[int(1.01*sr):int(1.05*sr)]))),
                            float(np.max(np.abs(y[int(1.8*sr):]))))


    def test_output_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/"source.wav"; sf.write(src,np.ones(8000,dtype="float32")*.1,8000)
            spec=d/"spec.json"; spec.write_text(json.dumps({"tracks":[{"path":str(src),"role":"sfx"}]}))
            before=src.read_bytes()
            with self.assertRaises(ValueError):
                mix_story(spec,src)
            self.assertEqual(before,src.read_bytes())


    def test_invalid_sample_rate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/"source.wav"; sf.write(src,np.zeros(8000,dtype="float32"),8000)
            spec=d/"spec.json"; spec.write_text(json.dumps({"sample_rate":100,"tracks":[{"path":str(src),"role":"sfx"}]}))
            with self.assertRaises(ValueError): mix_story(spec,d/"out.wav")

    def test_invalid_role_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); sr=8000
            a=d/"a.wav"; sf.write(a,np.zeros(8000,dtype="float32"),sr)
            sp=d/"spec.json"; sp.write_text(json.dumps({"tracks":[{"path":str(a),"role":"alien"}]}))
            with self.assertRaises(ValueError): mix_story(sp,d/"out.wav")

    def test_review_only_spec_cannot_be_rendered(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/"voice.wav"; sf.write(src,np.ones(8000,dtype="float32")*.1,8000)
            spec=d/"review.json"
            spec.write_text(json.dumps({"schema":"astra-story-mix-spec-review/v1","review_required":True,
                                        "tracks":[{"path":str(src),"role":"narration"}]}))
            out=d/"out.wav"
            with self.assertRaises(ValueError): mix_story(spec,out)
            self.assertFalse(out.exists())

    def test_report_cannot_overwrite_input_or_audio_output(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/"voice.wav"; sf.write(src,np.ones(8000,dtype="float32")*.1,8000)
            spec=d/"spec.json"; spec.write_text(json.dumps({"tracks":[{"path":str(src),"role":"narration"}]}))
            before=src.read_bytes()
            with self.assertRaises(ValueError): mix_story(spec,d/"out.wav",src)
            self.assertEqual(before,src.read_bytes())
            with self.assertRaises(ValueError): mix_story(spec,d/"same.wav",d/"same.wav")

    def test_existing_output_is_not_overwritten_without_explicit_permission(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/"voice.wav"; sf.write(src,np.ones(8000,dtype="float32")*.1,8000)
            spec=d/"spec.json"; spec.write_text(json.dumps({"tracks":[{"path":str(src),"role":"narration"}]}))
            out=d/"out.wav"; out.write_bytes(b"previous valuable output")
            with self.assertRaises(FileExistsError): mix_story(spec,out)
            self.assertEqual(out.read_bytes(),b"previous valuable output")
            mix_story(spec,out,overwrite=True)

    def test_nonfinite_mix_controls_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/"voice.wav"; sf.write(src,np.ones(8000,dtype="float32")*.1,8000)
            spec=d/"spec.json"; spec.write_text(json.dumps({"creativity":float("nan"),
                "tracks":[{"path":str(src),"role":"narration"}]}))
            with self.assertRaises(ValueError): mix_story(spec,d/"out.wav")

    def test_report_path_cannot_overwrite_mix_spec(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/"voice.wav"; sf.write(src,np.ones(8000,dtype="float32")*.1,8000)
            spec=d/"spec.json"; spec.write_text(json.dumps({"tracks":[{"path":str(src),"role":"narration"}]}))
            before=spec.read_bytes()
            with self.assertRaises(ValueError): mix_story(spec,d/"out.wav",spec)
            self.assertEqual(before,spec.read_bytes())

    def test_antiphase_stereo_voice_still_triggers_activity(self):
        sr=1000
        x=np.zeros((1000,2),dtype=np.float32)
        wave=0.2*np.sin(2*np.pi*100*np.arange(500)/sr)
        x[:500,0]=wave; x[:500,1]=-wave
        env=_activity_envelope(x,sr,20)
        self.assertGreater(float(np.max(env)),0.8)

    def test_scene_end_beyond_render_is_safely_clamped(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/"voice.wav"; sf.write(src,np.ones(8000,dtype="float32")*.1,8000)
            spec=d/"spec.json"; spec.write_text(json.dumps({"tracks":[{"path":str(src),"role":"narration"}],
                "scenes":[{"start_seconds":0,"end_seconds":5,"mood":"neutral","intensity":0.5}]}))
            out=d/"out.wav"
            r=mix_story(spec,out)
            self.assertEqual(r["duration_seconds"],1.0)
    def test_scene_start_after_render_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/"voice.wav"; sf.write(src,np.ones(8000,dtype="float32")*.1,8000)
            spec=d/"spec.json"; spec.write_text(json.dumps({"tracks":[{"path":str(src),"role":"narration"}],
                "scenes":[{"start_seconds":2,"end_seconds":3,"mood":"neutral","intensity":0.5}]}))
            with self.assertRaises(ValueError): mix_story(spec,d/"out.wav")

    def test_memory_preflight_runs_before_waveform_decode(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/"large.wav"; src.write_bytes(b"placeholder")
            spec=d/"spec.json"; spec.write_text(json.dumps({"memory_budget_mb":128,
                "tracks":[{"path":str(src),"role":"ambience"}]}))
            fake_info={"frames":100_000_000,"sample_rate":48000,"channels":2,"duration_seconds":2083.3}
            with patch("astra_audio.story_mix.probe_audio",return_value=fake_info), \
                 patch("astra_audio.story_mix.load_audio") as decoder:
                with self.assertRaises(MemoryError): mix_story(spec,d/"out.wav")
                decoder.assert_not_called()

    def test_multichannel_audio_is_not_silently_padded(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/"surround.wav"
            sf.write(src,np.zeros((8000,3),dtype="float32"),8000)
            spec=d/"spec.json"; spec.write_text(json.dumps({"tracks":[{"path":str(src),"role":"ambience"}]}))
            with self.assertRaisesRegex(ValueError,"mono/stereo only"):
                mix_story(spec,d/"out.wav")

if __name__=="__main__": unittest.main()
