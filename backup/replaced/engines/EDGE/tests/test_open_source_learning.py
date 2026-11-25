import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import open_source_learning as osl

class OpenSourceLearningTests(unittest.TestCase):
    def test_sources_include_svara_and_independent_alternatives(self):
        ids={x["id"] for x in osl.SOURCES}
        self.assertIn("svara_model_card",ids)
        self.assertIn("ai4bharat_indic_tts",ids)
        self.assertIn("ai4bharat_indic_parler",ids)
    def test_svara_is_not_runtime_dependency(self):
        for item in osl.SOURCES:
            self.assertNotIn("model-00001",item["url"])
        self.assertTrue(all("runtime_dependency" not in x for x in osl.SOURCES))
    def test_html_extraction_removes_script(self):
        got=osl._extract('<html><script>secret()</script><body>हिंदी आवाज़</body></html>','text/html')
        self.assertIn('हिंदी आवाज़',got); self.assertNotIn('secret',got)
    def test_nonblocking_detached_worker_launch(self):
        with tempfile.TemporaryDirectory() as td, patch.object(osl.subprocess,'Popen') as popen:
            result=osl.start_svara_learning(Path(td), 'unit-engine')
            self.assertEqual(result['state'],'queued_background')
            self.assertFalse(result['runtime_dependency']); popen.assert_called_once()
            self.assertIn('--worker',popen.call_args.args[0])
            self.assertTrue((Path(td)/'reports'/'open_source_learning_status.json').exists())

    def test_svara_renderer_is_explicitly_rejected(self):
        from tts_engine import render_segment
        with self.assertRaisesRegex(RuntimeError, "research-only"):
            render_segment("नमस्ते", Path("unused.wav"), {"adapter":"edge", "expressive_backend":"svara"})

    def test_status_default(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(osl.learning_status(td)['state'],'not_started')

if __name__=='__main__': unittest.main()
