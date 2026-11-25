
import unittest, tempfile, json
from pathlib import Path
from performance import parse_performance_line, plan_script
from dialogue_renderer import map_profiles_by_name, can_assemble
from audio_assembly import make_silence
from tts_engine import CAPABILITIES

class PerformanceTests(unittest.TestCase):
 def test_speaker_and_emotion(self):
  x=parse_performance_line("आरव [भाव:खुश]: अरे वाह!")
  self.assertEqual(x["speaker"],"आरव")
  self.assertEqual(x["emotion"],"happy")
 def test_only_marked_word_stretched(self):
  x=parse_performance_line("रवि: यह [खींचें:नहीं] हो सकता!")
  stretched=[e["text"] for e in x["events"] if e.get("stretch")]
  self.assertEqual(stretched,["नहीं"])
 def test_unmarked_words_not_stretched(self):
  x=parse_performance_line("रवि: यह बहुत अच्छा है।")
  self.assertFalse(any(e.get("stretch") for e in x["events"]))
 def test_explicit_pause_bounded(self):
  x=parse_performance_line("रवि: रुको [विराम:500ms] फिर चलो")
  p=[e["duration_ms"] for e in x["events"] if e["kind"]=="pause"]
  self.assertIn(500,p)
 def test_pause_capped(self):
  x=parse_performance_line("रवि: रुको [विराम:9999ms] चलो")
  p=[e["duration_ms"] for e in x["events"] if e["kind"]=="pause"]
  self.assertIn(2000,p)
 def test_profiles_name_map(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"p.json"; p.write_text(json.dumps({"id":{"name":"सीमा","voice_id":"v1"}}),encoding="utf-8")
   self.assertEqual(map_profiles_by_name(p)["सीमा"]["voice_id"],"v1")
 def test_capabilities_are_not_fabricated(self):
  self.assertIn("not supported",CAPABILITIES["piper"]["emotion_control"])
 def test_optional_warning_does_not_block_audio_assembly(self):
  self.assertTrue(can_assemble(["speech.wav"], []))
 def test_real_render_failure_blocks_assembly(self):
  self.assertFalse(can_assemble(["speech.wav"], ["synthesis failed"]))
 def test_blank_line(self):
  self.assertEqual(parse_performance_line(" ")["kind"],"blank")
 def test_plan_preserves_line_numbers(self):
  p=plan_script("रवि: नमस्ते\n\nसीमा: नमस्ते")
  self.assertEqual([x["line"] for x in p],[1,3])
 def test_silence_wav(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"s.wav"; make_silence(p,100)
   self.assertTrue(p.exists() and p.stat().st_size>100)
if __name__=="__main__": unittest.main()
