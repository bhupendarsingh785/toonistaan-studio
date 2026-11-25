import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))
sys.path.insert(0, str(ROOT / "astra"))
sys.path.insert(0, str(ROOT / "tools"))

import sfx_extra
from story_check import _line_parts


class AudioRegressionTests(unittest.TestCase):
    def test_hindi_walking_phrase_detects_footsteps(self):
        self.assertIn("footsteps", sfx_extra.detect_smart("वह धीरे-धीरे आगे चला।", "room"))

    def test_entering_room_detects_footsteps(self):
        self.assertIn("footsteps", sfx_extra.detect_smart("राम कमरे में दाखिल हुआ।", "room"))

    def test_door_open_and_close_are_distinguished(self):
        self.assertIn("gate_open", sfx_extra.detect_smart("दरवाजा धीरे से खुला।", "room"))
        self.assertIn("gate_close", sfx_extra.detect_smart("दरवाजा बंद हो गया।", "room"))

    def test_story_check_accepts_both_line_shapes(self):
        self.assertEqual(_line_parts("कहानी की पंक्ति"), ("madhur", "कहानी की पंक्ति", None))
        self.assertEqual(_line_parts(["swara", "नमस्ते", "happy"]), ("swara", "नमस्ते", "happy"))


if __name__ == "__main__":
    unittest.main()
