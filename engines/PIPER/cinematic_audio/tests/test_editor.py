import tempfile, unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from astra_audio.editor import cut_audio, join_audio, apply_effects, inspect_audio, execute_project

class EditorTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.root=Path(self.t.name); sr=24000
  t=np.arange(sr*3)/sr
  self.a=self.root/'a.wav'; self.b=self.root/'b.wav'
  sf.write(self.a,(.2*np.sin(2*np.pi*220*t)).astype('float32'),sr)
  sf.write(self.b,(.2*np.sin(2*np.pi*330*t)).astype('float32'),sr)
 def tearDown(self): self.t.cleanup()
 def test_cut_non_destructive(self):
  before=self.a.read_bytes(); out,meta=cut_audio(self.a,self.root/'cut.wav',.5,1.5)
  x,sr=sf.read(out); self.assertAlmostEqual(len(x)/sr,1,places=3); self.assertEqual(before,self.a.read_bytes())
 def test_join_crossfade(self):
  out,meta=join_audio([self.a,self.b],self.root/'join.wav',.4)
  x,sr=sf.read(out); self.assertAlmostEqual(len(x)/sr,5.6,places=2); self.assertEqual(len(meta['seams']),1)
 def test_effects(self):
  out,meta=apply_effects(self.a,self.root/'fx.wav',gain_db=-3,fade_in_seconds=.1)
  x,sr=sf.read(out); self.assertEqual(sr,24000); self.assertTrue(np.max(np.abs(x))<.3)
 def test_inspect(self):
  r=inspect_audio(self.a); self.assertAlmostEqual(r['duration_seconds'],3,places=2); self.assertEqual(r['channels'],1)
 def test_project_edl(self):
  p=self.root/'project.json'; p.write_text('{"operations":[{"type":"cut","source":"'+str(self.a)+'","start":0.2,"end":1.2}]}')
  r=execute_project(p,self.root/'out'); self.assertEqual(len(r['operations']),1); self.assertTrue((self.root/'out'/'edit-report.json').exists())
if __name__=='__main__': unittest.main()

def test_editor_rejects_vocal_output_overwriting_input(tmp_path):
  import numpy as np, soundfile as sf
  from astra_audio.editor import replace_vocals_with_hindi
  source=tmp_path/'song.wav'; vocal=tmp_path/'hindi.wav'
  sf.write(source,np.zeros((4800,2),dtype=np.float32),48000)
  sf.write(vocal,np.zeros((4800,2),dtype=np.float32),48000)
  try:
    replace_vocals_with_hindi(source,vocal,source,instrumental_stem=source)
  except ValueError as e:
    assert 'overwrite' in str(e)
  else:
    raise AssertionError('Should refuse to overwrite an input file')


def test_editor_rejects_extreme_vocal_duration_mismatch(tmp_path):
  import numpy as np, soundfile as sf
  from astra_audio.editor import replace_vocals_with_hindi
  bg=tmp_path/'instrumental.wav'; vocal=tmp_path/'hindi.wav'
  sf.write(bg,np.zeros((48000,2),dtype=np.float32),48000)
  sf.write(vocal,np.zeros((12000,2),dtype=np.float32),48000)
  try:
    replace_vocals_with_hindi(bg,vocal,tmp_path/'out.wav',instrumental_stem=bg)
  except ValueError as e:
    assert 'more than 2x' in str(e)
  else:
    raise AssertionError('Should reject an extreme duration mismatch')
