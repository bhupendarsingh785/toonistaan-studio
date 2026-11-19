import unittest
from pathlib import Path
from hindi_phonology import inspect_word, inspect_text
from prosody_intelligence import analyze_line, analyze_script
class TestHindiProsodyV07(unittest.TestCase):
 def test_vowel_and_matra(self):
  x=inspect_word('कहानी'); self.assertGreaterEqual(x['syllable_nuclei_estimate'],3)
 def test_nasalization(self):
  x=inspect_word('माँ'); self.assertTrue(x['nasal_features'])
 def test_conjunct(self):
  x=inspect_word('प्रेम'); self.assertTrue(x['conjunct_clusters'])
 def test_explicit_emotion(self):
  x=analyze_line('सीमा [भाव:उदास]: मैं तुम्हें याद कर रही हूँ।'); self.assertEqual(x['emotion'],'sad')
 def test_contextual_question(self):
  x=analyze_line('तुम यहाँ इतनी रात को क्यों आए?'); self.assertEqual(x['emotion'],'curious')
 def test_character_continuity(self):
  x=analyze_script('माँ: मुझे बहुत डर लग रहा है।\nमाँ: बाहर कौन है?'); self.assertEqual(x['segments'][1]['emotion'],'fearful')
 def test_separate_characters(self):
  x=analyze_script('राम: वाह!\nसीता: मुझे दुख हो रहा है।'); self.assertNotEqual(x['segments'][0]['emotion'],x['segments'][1]['emotion'])
 def test_review_ambiguous(self):
  x=analyze_line('वह वहाँ गया।'); self.assertTrue(x['needs_review'])
if __name__=='__main__': unittest.main()

class TestProsodyAdapterIntegration(unittest.TestCase):
 def test_delivery_targets_exist(self):
  x=analyze_line('माँ: मुझे बहुत डर लग रहा है।'); self.assertIn('rate',x['delivery']); self.assertIn('contour',x['delivery'])

class TestRenderPipelineIntegration(unittest.TestCase):
 def test_deep_prosody_reaches_tts_adapter(self):
  import tempfile
  from unittest.mock import patch
  from dialogue_renderer import render_story
  calls=[]
  def fake_render(text,out,config,emotion='neutral',stretch=False,prosody=None):
   calls.append({'text':text,'emotion':emotion,'prosody':prosody})
   from pathlib import Path
   Path(out).write_bytes(b'x'*200)
   return str(out)
  with tempfile.TemporaryDirectory() as td:
   with patch('dialogue_renderer.render_segment',side_effect=fake_render), patch('dialogue_renderer.assemble_wav',return_value=str(Path(td)/'final.wav')):
    render_story('माँ: मुझे बहुत डर लग रहा है।',{'adapter':'edge','title':'test'},td)
  self.assertTrue(calls)
  self.assertEqual(calls[0]['emotion'],'fearful')
  self.assertIn('contour',calls[0]['prosody'])
