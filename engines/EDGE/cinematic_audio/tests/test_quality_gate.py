import tempfile, unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
from astra_audio.quality_check import quality_check, _chunked_true_peak

class QualityGateTests(unittest.TestCase):
    def test_clean_audio_passes_and_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"clean.wav"
            sr=16000
            t=np.arange(sr*2)/sr
            sf.write(p,(0.2*np.sin(2*np.pi*440*t)).astype("float32"),sr)
            before=p.read_bytes()
            r=quality_check(p,Path(d)/"report.json")
            self.assertEqual(r["status"],"PASS")
            self.assertLessEqual(r["sample_peak_dbfs"],-1.0)
            self.assertEqual(before,p.read_bytes())
    def test_clipping_and_silence_are_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.wav"
            x=np.zeros(16000,dtype="float32")
            x[100:1000]=1.0
            sf.write(p,x,16000,subtype="PCM_24")
            r=quality_check(p)
            self.assertEqual(r["status"],"REVIEW")
            self.assertGreater(r["near_full_scale_sample_count"],0)
            self.assertTrue(r["warnings"])
    def test_stereo_phase_warning(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"phase.wav"
            x=np.sin(np.arange(16000)*0.1).astype("float32")
            sf.write(p,np.column_stack([x,-x]),16000)
            r=quality_check(p)
            self.assertEqual(r["status"],"REVIEW")
            self.assertLess(r["stereo_correlation"],-0.99)

    def test_report_path_cannot_overwrite_audio(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"input.wav"
            sf.write(p,np.zeros(16000,dtype="float32"),16000)
            before=p.read_bytes()
            with self.assertRaises(ValueError):
                quality_check(p,p)
            self.assertEqual(before,p.read_bytes())

    def test_chunked_true_peak_matches_whole_file_estimate(self):
        rng=np.random.default_rng(4)
        x=(rng.standard_normal((48000*2,2))*0.1).astype("float32")
        full=float(np.max(np.abs(signal.resample_poly(x.astype("float64"),4,1,axis=0))))
        chunked=_chunked_true_peak(x,4,chunk_seconds=0.4,sample_rate=48000)
        self.assertLess(abs(full-chunked),1e-6)

if __name__=="__main__": unittest.main()
