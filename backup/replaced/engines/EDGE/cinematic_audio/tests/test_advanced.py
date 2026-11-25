import tempfile, unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from astra_audio.analyzer import analyze_audio
from astra_audio.acoustic_map import build_acoustic_map
from astra_audio.audit import audit_folder

class AdvancedTests(unittest.TestCase):
    def test_deep_metrics_and_timeline(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"stereo.wav"
            sr=16000; t=np.arange(sr*2)/sr
            x=np.column_stack([.1*np.sin(2*np.pi*440*t),.08*np.sin(2*np.pi*660*t)]).astype("float32")
            sf.write(p,x,sr)
            r=analyze_audio(p)
            self.assertIn("approx_true_peak_dbfs",r)
            self.assertIn("stereo_correlation",r)
            self.assertGreaterEqual(len(r["timeline_1s"]),2)
            self.assertIn("spectral",r)
    def test_acoustic_map_is_not_semantic(self):
        sr=8000
        x=np.concatenate([np.zeros(sr//2),.2*np.sin(2*np.pi*440*np.arange(sr//2)/sr)]).astype("float32")
        m=build_acoustic_map(x,sr,.25)
        self.assertFalse(m["semantic_labels_performed"])
        self.assertGreaterEqual(len(m["frames"]),3)
    def test_batch_audit_hash_and_non_destructive(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"tone.wav"; sf.write(p,np.zeros(8000,dtype="float32"),8000)
            before=p.read_bytes()
            r=audit_folder(d,Path(d)/"report.json")
            self.assertEqual(r["analyzed_count"],1)
            self.assertEqual(before,p.read_bytes())
            self.assertEqual(len(r["assets"][0]["sha256"]),64)
    def test_invalid_acoustic_window(self):
        with self.assertRaises(ValueError):
            build_acoustic_map(np.zeros(100),0,.5)

if __name__=="__main__": unittest.main()
