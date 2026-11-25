import unittest, tempfile, json
from pathlib import Path
from system_watchdog import health_report
class WatchdogTests(unittest.TestCase):
 def test_health_report_is_engine_scoped_and_saved(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td); (root/"reports").mkdir(); (root/"research").mkdir(); (root/"knowledge_inbox").mkdir(); (root/"memory").mkdir(); (root/"output").mkdir()
   for n in ["app.py","browser_agent.py","hindi_core.py","tts_engine.py","dialogue_renderer.py","error_memory.py"]: (root/n).write_text("",encoding="utf-8")
   result=health_report(root,{"adapter":"edge"})
   self.assertTrue((root/"reports"/"system_health.json").exists()); self.assertEqual(result["engine"],root.name)
if __name__=="__main__": unittest.main()
