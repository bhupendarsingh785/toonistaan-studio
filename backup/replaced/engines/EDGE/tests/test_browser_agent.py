import unittest, tempfile, json
from pathlib import Path
from browser_agent import _score, agent_status
class BrowserAgentTests(unittest.TestCase):
 def test_relevance_score(self): self.assertGreater(_score("Hindi TTS model", "Hindi speech model", "TTS voice model"), 0)
 def test_empty_query_score(self): self.assertEqual(_score("", "anything", "anything"), 0)
 def test_status_before_first_run(self):
  with tempfile.TemporaryDirectory() as td: self.assertEqual(agent_status(td)["agent"], "not_run_yet")
if __name__ == "__main__": unittest.main()
