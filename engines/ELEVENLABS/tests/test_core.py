
import unittest, tempfile, json
from pathlib import Path
from hindi_core import normalize_hindi, scan_script, language_diagnostics
from character_voice import make_profiles
from model_registry import inspect_model_file
from error_memory import ErrorLedger
from quality_lab import blank_report, evaluate
from browser_research import clean_html_text

class CoreTests(unittest.TestCase):
 def test_unicode_nfc(self):
  self.assertEqual(normalize_hindi("नमस्ते"),"नमस्ते")
 def test_dialogue_and_narration(self):
  r=scan_script("वाचक: कहानी शुरू हुई।\nसीमा: नमस्ते।")
  self.assertEqual(len(r["characters"]),2)
  self.assertEqual(r["segments"][1]["speaker"],"सीमा")
 def test_roman_hindi_warning(self):
  self.assertFalse(language_diagnostics("namaste bhai")["likely_hindi_or_devanagari"])
 def test_profile_not_claim_verified(self):
  r=scan_script("आरव: नमस्ते")
  p=make_profiles(r)
  self.assertFalse(next(iter(p.values()))["verified_voice_match"])
 def test_model_unknown_until_verified(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"x.onnx"; p.write_bytes(b"test")
   self.assertFalse(inspect_model_file(p)["verified"])
 def test_error_reopen(self):
  with tempfile.TemporaryDirectory() as td:
   l=ErrorLedger(Path(td)/"errors.json")
   f=l.add("bad hindi","symptom","cause","fix","prevent","test")
   l.close(f,"test passed")
   l.add("bad hindi","symptom","cause","fix","prevent","test")
   self.assertEqual(l.release_blockers()[0]["status"],"REOPENED")
 def test_browser_removes_script_and_collapses_whitespace(self):
  cleaned=clean_html_text("<html><script>SECRET()</script><p>नमस्ते</p></html>")
  self.assertNotIn("SECRET",cleaned)
  self.assertIn("नमस्ते",cleaned)
 def test_quality_never_auto_pass(self):
  r=blank_report("test","1")
  self.assertNotEqual(evaluate(r,[])["status"],"PASS")
if __name__=="__main__": unittest.main()
