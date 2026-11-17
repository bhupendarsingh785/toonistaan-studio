import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))
from world_engine import plan_world

class WorldEngineTests(unittest.TestCase):
    def test_explicit_movement_persists_until_stop(self):
        story = {"scenes": [{"env": "village", "lines": [
            ["ram", "राम धीरे-धीरे चलने लगा।"],
            ["ram", "वह पुराने घर की ओर देखता रहा।"],
            ["ram", "फिर वह अचानक रुक गया।"]
        ]}]}
        cues = plan_world(story, [[1.0, 1.0, 1.0]])["scenes"][0]["cues"]
        self.assertTrue(any(c["type"] == "state_start" and c["asset"] == "footsteps" for c in cues))
        self.assertTrue(any(c["type"] == "state_continue" for c in cues))
        self.assertTrue(any(c["type"] == "state_stop" for c in cues))

    def test_vehicle_pass_is_action_not_object_mention(self):
        mention = {"scenes": [{"env": "street", "lines": [["n", "वह मोटरसाइकिल देख रहा था।"]]}]}
        action = {"scenes": [{"env": "street", "lines": [["n", "मोटरसाइकिल उसके पास से गुज़र गई।"]]}]}
        self.assertFalse(any(c.get("event") == "vehicle_pass" for c in plan_world(mention)["scenes"][0]["cues"]))
        self.assertTrue(any(c.get("event") == "vehicle_pass" for c in plan_world(action)["scenes"][0]["cues"]))

    def test_bangles_only_when_explicitly_described(self):
        story = {"scenes": [{"env": "room", "lines": [["n", "उसकी चूड़ियाँ हल्के से खनक उठीं।"]]}]}
        self.assertTrue(any(c.get("asset") == "bangles" for c in plan_world(story)["scenes"][0]["cues"]))

    def test_actual_durations_remove_estimate_flag(self):
        story = {"scenes": [{"env": "room", "lines": [["n", "नमस्ते।"]]}]}
        line = plan_world(story, [[3.25]])["scenes"][0]["lines"][0]
        self.assertEqual(line["end"] - line["start"], 3.25)
        self.assertFalse(line["duration_estimated"])

    def test_movement_state_is_tracked_per_character(self):
        story = {"scenes": [{"env": "street", "lines": [
            ["ram", "राम धीरे-धीरे चलने लगा।"],
            ["sita", "सीता आगे बढ़ी।"],
            ["ram", "राम रुक गया।"],
            ["sita", "सीता सड़क पर देखती रही।"],
            ["sita", "सीता भी रुक गई।"]
        ]}]}
        cues = plan_world(story, [[1.0, 1.0, 1.0, 1.0, 1.0]])["scenes"][0]["cues"]
        ram = [c for c in cues if c.get("type") == "state_start" and c.get("speaker") == "ram"]
        sita = [c for c in cues if c.get("type") == "state_start" and c.get("speaker") == "sita"]
        self.assertEqual(len(ram), 1)
        self.assertEqual(len(sita), 1)
        self.assertLess(ram[0]["end"], sita[0]["end"])
        self.assertGreater(sita[0]["end"], ram[0]["end"])

    def test_unknown_environment_is_neutral(self):
        story = {"scenes": [{"env": "mars", "lines": [["n", "वह खड़ा रहा।"]]}]}
        result = plan_world(story)
        self.assertEqual(result["scenes"][0]["env"], "neutral")
        self.assertEqual(result["scenes"][0]["cues"], [])

if __name__ == "__main__":
    unittest.main()
