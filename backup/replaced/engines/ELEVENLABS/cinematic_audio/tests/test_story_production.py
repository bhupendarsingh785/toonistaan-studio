from astra_audio.story_production import prepare_story_audio


def test_prepare_story_audio_combines_world_and_action_and_story():
    script = """दृश्य 1: घना जंगल, रात
वह सूखे पत्तों पर धीरे चला और झाड़ियों से बाहर निकला।
दृश्य 2: पुरानी हवेली
उसने रस्सी खोली और खिड़की की ग्रिल पर बाँधी। फिर गाँठ कस दी।
वह खिड़की से बाहर निकला और रस्सी के सहारे नीचे उतरा।
"""
    report = prepare_story_audio(script, "test.txt")
    assert report["schema"] == "astra-story-audio-review-pack/v1"
    assert report["counts"]["scenes"] == 2
    assert report["counts"]["action_chains"] >= 1
    assert report["counts"]["physical_action_events"] >= 4
    assert report["stages"]["timeline_alignment"]["status"] == "blocked_needs_audio_alignment"
    assert report["policy"]["auto_asset_insertion"] is False


def test_prepare_story_audio_matches_action_tags_without_auto_insertion():
    script = "दृश्य 1: रात\nउसने रस्सी खोली और गाँठ कस दी।"
    catalog = {"assets": [
        {"asset_id": "rope01", "asset_name": "rope friction knot tightening", "tags": ["rope", "knot", "friction"]}
    ]}
    report = prepare_story_audio(script, "rope.txt", catalog)
    matching = report["stages"]["asset_matching"]["report"]
    assert matching is not None
    assert matching["matched_event_count"] >= 1
    assert matching["policy"]["never_auto_insert"] is True


def test_unknown_story_gets_generic_plan_and_no_fake_assets():
    report = prepare_story_audio("दृश्य 1: एक अनजान जगह\nवह चुपचाप बैठा रहा।")
    assert report["counts"]["physical_action_events"] == 0
    assert report["stages"]["asset_matching"]["status"] == "not_run_no_catalog"
