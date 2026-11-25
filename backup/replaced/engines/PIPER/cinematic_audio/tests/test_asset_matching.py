import json
from pathlib import Path
import pytest
from astra_audio.asset_matching import match_assets, make_workflow_adapter

ROOT = Path(__file__).resolve().parents[1]

def test_matches_shankh_without_confusing_bell():
    catalog = [
        {"asset_name":"temple_conch.mp3","description":"शंख की ध्वनि","suggested_profile":"sfx"},
        {"asset_name":"temple_bell.mp3","description":"मंदिर की घंटी","suggested_profile":"sfx"},
    ]
    report = match_assets([{"event_id":"e1","event_type":"conch","text":"शंख बजा"}], catalog)
    names = [x["asset_name"] for x in report["results"][0]["candidates"]]
    assert names[0] == "temple_conch.mp3"
    assert report["results"][0]["auto_inserted"] is False

def test_unknown_license_never_commercial_auto_eligible():
    catalog = [{"asset_name":"crying_girl.mp3","description":"लड़की के रोने की आवाज़",
                "license_status":"unknown_requires_verification"}]
    report = match_assets([{"event_type":"crying_sobbing","text":"वह रोने लगी"}], catalog)
    assert report["results"][0]["candidates"]
    assert report["results"][0]["candidates"][0]["eligible_for_commercial_auto_use"] is False
    assert report["results"][0]["candidates"][0]["decision"] == "human_review_required"

def test_license_and_audition_both_required():
    catalog = [{"asset_name":"rain.wav","description":"rain ambience","license_status":"CC0","approval_status":"approved"}]
    report = match_assets([{"event_type":"rain","text":"बारिश शुरू हुई"}], catalog)
    assert report["results"][0]["candidates"][0]["eligible_for_commercial_auto_use"] is True

def test_no_guess_when_no_match():
    report = match_assets([{"event_type":"spaceship_laser","text":"अंतरिक्ष यान"}], [])
    assert report["results"][0]["status"] == "no_confident_candidate"
    assert report["matched_event_count"] == 0

def test_bad_catalog_and_parameters_rejected():
    with pytest.raises(ValueError):
        match_assets([], {"assets":"not a list"})
    with pytest.raises(ValueError):
        match_assets([], [], min_score=2)


def test_bell_event_does_not_match_conch_mentioned_in_same_line():
    catalog = [
        {"asset_name":"temple_conch.mp3","description":"शंख की ध्वनि"},
        {"asset_name":"temple_bell.mp3","description":"मंदिर की घंटी"},
    ]
    report = match_assets([{"event_type":"bell_chime","text":"मंदिर की घंटियाँ और शंख की ध्वनि"}], catalog)
    names = [x["asset_name"] for x in report["results"][0]["candidates"]]
    assert "temple_bell.mp3" in names
    assert "temple_conch.mp3" not in names


def test_asset_matcher_workflow_adapter_consumes_story_understanding_output():
    catalog = [{"asset_name":"temple_conch.mp3","description":"शंख की ध्वनि"}]
    analysis = {"scenes":[{"scene_id":"s1","sound_cues":[
        {"cue_id":"c1","cue_type":"sound_event","event":"conch","text_excerpt":"शंख बजा"}
    ]}]}
    adapter = make_workflow_adapter(catalog)
    result = adapter({"story_understanding":analysis})
    assert result["event_count"] == 1
    assert result["results"][0]["event_id"] == "c1"

def test_asset_matcher_workflow_adapter_fails_closed_without_story_analysis():
    adapter = make_workflow_adapter([])
    with pytest.raises(ValueError, match="story_analysis"):
        adapter({})


def test_peacock_cry_is_not_misclassified_as_human_sobbing():
    catalog = [{"asset_name":"cry-of-a-peacock.mp3","description":"मोर की आवाज़",
                "filename_category_hints":["peacock"]}]
    report = match_assets([{"event_type":"crying_sobbing","text":"धीमा सिसकना"}], catalog)
    assert report["results"][0]["candidates"] == []
