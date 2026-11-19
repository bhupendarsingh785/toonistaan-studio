import json, tempfile, unittest
from pathlib import Path
from astra_audio.story_intelligence import analyze_script_text, analyze_script_file, build_reviewable_mix_spec

SAMPLE = """दृश्य 1: गाँव की सुबह
राम: आज मौसम कितना शांत है।
सीता: हाँ, लेकिन बाहर कुछ आहट हुई।
दरवाजा धीरे से खुला। पक्षी चहचहा रहे थे।

दृश्य 2: पुरानी हवेली
राम: मुझे डर लग रहा है।
अचानक तेज बारिश शुरू हो गई और वह दौड़ पड़ा।
"""

class StoryIntelligenceTests(unittest.TestCase):
    def test_scene_character_and_event_extraction(self):
        r=analyze_script_text(SAMPLE,"sample.txt")
        self.assertEqual(r["scene_count"],2)
        self.assertEqual({c["name"] for c in r["characters"]},{"राम","सीता"})
        self.assertEqual(r["summary"]["narration_line_count"],0)
        self.assertIn("voice_continuity_rule",r["characters"][0])
        events=[c["event"] for s in r["scenes"] for c in s["sound_cues"] if c["cue_type"]=="sound_event"]
        self.assertIn("door",events)
        self.assertIn("animal_bird",events)
        self.assertIn("rain",events)
        self.assertIn("footsteps",events)
    def test_empty_and_oversized_rejected(self):
        with self.assertRaises(ValueError): analyze_script_text("   ")
        with self.assertRaises(ValueError): analyze_script_text("x"*(2_000_001))
    def test_scene_heading_and_dialogue_robust_to_blank_lines(self):
        r=analyze_script_text("SCENE 1 - INT. ROOM\nAsha: Hello\n\nSCENE 2 - EXT. ROAD\nAsha: Run!")
        self.assertEqual(r["scene_count"],2)
        self.assertEqual(r["characters"][0]["dialogue_lines"],2)
    def test_narrator_lines_are_separated_from_characters(self):
        r=analyze_script_text("दृश्य 1\nवाचक: रात गहरी हो चुकी थी।\nमोहन: कौन है?")
        self.assertEqual(r["summary"]["narration_line_count"],1)
        self.assertEqual([c["name"] for c in r["characters"]],["मोहन"])
    def test_review_spec_never_claims_render_ready(self):
        r=analyze_script_text(SAMPLE)
        spec=build_reviewable_mix_spec(r,{"narration":"voice.wav"})
        self.assertTrue(spec["review_required"])
        self.assertEqual(spec["tracks"][0]["role"],"narration")
        self.assertIn("must be aligned",spec["warning"])
    def test_invalid_role_and_values_rejected(self):
        r=analyze_script_text(SAMPLE)
        with self.assertRaises(ValueError): build_reviewable_mix_spec(r,{"voice":"x.wav"})
        with self.assertRaises(ValueError): build_reviewable_mix_spec(r,{},48000,1.5)
    def test_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"story.txt"; p.write_text(SAMPLE,encoding="utf-8")
            out=Path(d)/"report.json"
            r=analyze_script_file(p,out)
            self.assertTrue(out.exists())
            self.assertEqual(json.loads(out.read_text())["script_sha256"],r["script_sha256"])

    def test_sound_event_coverage_and_english_word_boundaries(self):
        r=analyze_script_text("दृश्य 1\nपत्तों की सरसराहट सुनाई दी। चूड़ियाँ खनकीं। मंदिर की घंटियाँ बजीं।\nHe carefully opened the box.")
        events=[c["event"] for s in r["scenes"] for c in s["sound_cues"] if c["cue_type"]=="sound_event"]
        self.assertIn("foliage",events)
        self.assertIn("clothing_jewellery",events)
        self.assertIn("bell_chime",events)
        self.assertNotIn("vehicle",events)

    def test_production_labels_are_not_misread_as_character_names(self):
        r=analyze_script_text("दृश्य 1\nस्थान: पुरानी हवेली\nSFX: दरवाजा खुलता है\nराम: अंदर कोई है?")
        self.assertEqual([c["name"] for c in r["characters"]],["राम"])

    def test_explicit_scene_timecodes_are_parsed_and_propagated(self):
        r=analyze_script_text("दृश्य 1 @ 00:00:05.500\nराम: चलो।\nदृश्य 2 [00:00:12]\nसीता: आ गई।")
        self.assertAlmostEqual(r["scenes"][0]["start_time_seconds"],5.5)
        self.assertEqual(r["scenes"][1]["start_time_seconds"],12.0)
        spec=build_reviewable_mix_spec(r,{"narration":"voice.wav"})
        self.assertEqual(spec["scenes"][0]["start_seconds"],5.5)
        self.assertEqual(spec["scenes"][0]["end_seconds"],12.0)
        self.assertEqual(spec["scenes"][0]["timing_status"],"START_AND_END_FROM_EXPLICIT_ADJACENT_MARKERS")
        self.assertTrue(spec["review_required"])

    def test_conch_is_separate_from_bells_and_crying_is_detected(self):
        r=analyze_script_text("दृश्य 1: मंदिर\nSFX: शंख बजा और घंटियाँ गूँजीं।\nदृश्य 2: कमरा\nगौरी: माँ की याद में वह सिसकने लगी।")
        cues=[c["event"] for s in r["scenes"] for c in s["sound_cues"] if c["cue_type"]=="sound_event"]
        self.assertIn("conch",cues)
        self.assertIn("bell_chime",cues)
        self.assertIn("crying_sobbing",cues)

    def test_scene_environment_candidates_are_reported(self):
        r=analyze_script_text("दृश्य 1: गाँव का मंदिर\nवाचक: गाँव के मंदिर में आरती शुरू हुई।\nदृश्य 2: पुरानी हवेली\nमोहन: यह हवेली बहुत पुरानी है।")
        labels=[{x["environment"] for x in s["environment_candidates"]} for s in r["scenes"]]
        self.assertIn("village",labels[0])
        self.assertIn("temple",labels[0])
        self.assertNotIn("forest",labels[0])
        self.assertIn("old_mansion",labels[1])
        self.assertEqual(r["summary"]["environment_candidate_count"],sum(map(len,[s["environment_candidates"] for s in r["scenes"]])))

if __name__=="__main__": unittest.main()
