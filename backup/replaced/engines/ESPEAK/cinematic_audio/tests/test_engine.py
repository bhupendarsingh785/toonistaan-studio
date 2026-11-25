import tempfile, unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from astra_audio.analyzer import analyze_audio
from astra_audio.processor import process_audio, ProcessingOptions
from astra_audio.io import save_wav, save_json_atomic, load_audio

class EngineTests(unittest.TestCase):
    def test_analyze_and_keep_original(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"input.wav"; out=Path(d)/"clean.wav"
            sr=16000; t=np.arange(sr)/sr
            x=(0.15*np.sin(2*np.pi*440*t)).astype(np.float32)
            sf.write(src,x,sr)
            a=analyze_audio(src)
            self.assertEqual(a["sample_rate"],sr)
            r=process_audio(src,out,ProcessingOptions(normalize_peak_dbfs=-1))
            self.assertTrue(out.exists()); self.assertTrue(src.exists())
            self.assertFalse(r["preservation_policy"]["original_overwritten"])
    def test_invalid_noise_profile(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"input.wav"; out=Path(d)/"clean.wav"
            sf.write(src,np.zeros(16000,dtype=np.float32),16000)
            with self.assertRaises(ValueError):
                process_audio(src,out,ProcessingOptions(denoise_strength=.4))
    def test_profile_denoise_requires_noise_only_interval_and_runs(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"input.wav"; out=Path(d)/"clean.wav"
            sr=16000; rng=np.random.default_rng(4)
            noise=(0.008*rng.normal(size=sr)).astype(np.float32)
            t=np.arange(sr)/sr
            tone=(0.12*np.sin(2*np.pi*440*t)).astype(np.float32)
            x=np.concatenate([noise, tone+noise]).astype(np.float32)
            sf.write(src,x,sr)
            r=process_audio(src,out,ProcessingOptions(
                noise_start_seconds=0.1, noise_end_seconds=1.5, denoise_strength=.25, asset_profile="speech"))
            self.assertTrue(out.exists())
            self.assertIn("quality_gate",r)
            self.assertTrue(r["preservation_policy"]["original_overwritten"] is False)
    def test_non_speech_denoise_blocked_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"input.wav"; out=Path(d)/"clean.wav"
            sr=16000; rng=np.random.default_rng(5)
            x=(0.01*rng.normal(size=sr*2)).astype(np.float32)
            sf.write(src,x,sr)
            with self.assertRaisesRegex(ValueError,"Automatic denoise is blocked"):
                process_audio(src,out,ProcessingOptions(
                    noise_start_seconds=0.1, noise_end_seconds=1.5,
                    denoise_strength=.2, asset_profile="music"))
    def test_unknown_profile_denoise_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"input.wav"; out=Path(d)/"clean.wav"
            sf.write(src,np.zeros(32000,dtype=np.float32),16000)
            with self.assertRaisesRegex(ValueError,"Automatic denoise is blocked"):
                process_audio(src,out,ProcessingOptions(
                    noise_start_seconds=0.1, noise_end_seconds=1.5,
                    denoise_strength=.2))
    def test_no_implicit_denoise(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"input.wav"; out=Path(d)/"clean.wav"
            sf.write(src,np.zeros(16000,dtype=np.float32),16000)
            r=process_audio(src,out,ProcessingOptions())
            self.assertNotIn("no_processing_applied",r["review_flags"])

    def test_process_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"source.wav"
            sf.write(p,np.zeros(16000,dtype="float32"),16000)
            before=p.read_bytes()
            with self.assertRaises(ValueError):
                process_audio(p,p,ProcessingOptions())
            self.assertEqual(before,p.read_bytes())

    def test_process_does_not_overwrite_existing_derivative_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"source.wav"; out=Path(d)/"processed.wav"
            sf.write(src,np.ones(16000,dtype="float32")*.1,16000)
            out.write_bytes(b"previous derivative")
            before=out.read_bytes()
            with self.assertRaises(FileExistsError):
                process_audio(src,out,ProcessingOptions())
            self.assertEqual(before,out.read_bytes())
            process_audio(src,out,ProcessingOptions(),overwrite=True)

    def test_wav_writer_rejects_nonfinite_without_touching_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"out.wav"
            p.write_bytes(b"keep this file")
            before=p.read_bytes()
            x=np.zeros((100,1),dtype="float32"); x[5,0]=np.nan
            with self.assertRaises(ValueError): save_wav(p,x,16000)
            self.assertEqual(before,p.read_bytes())

    def test_atomic_json_rejects_nan_and_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"report.json"; p.write_text('{"keep":true}',encoding="utf-8")
            before=p.read_bytes()
            with self.assertRaises(ValueError): save_json_atomic(p,{"bad":float("nan")})
            self.assertEqual(before,p.read_bytes())
            save_json_atomic(p,{"ok":1})
            self.assertEqual(__import__("json").loads(p.read_text()),{"ok":1})

    def test_audio_loader_rejects_nonfinite_float_wav(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"nan.wav"
            x=np.zeros(100,dtype="float32"); x[3]=np.nan
            sf.write(p,x,16000,subtype="FLOAT")
            with self.assertRaises(ValueError): load_audio(p)

if __name__=="__main__": unittest.main()
