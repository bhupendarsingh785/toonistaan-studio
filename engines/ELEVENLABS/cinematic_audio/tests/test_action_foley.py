from astra_audio.action_foley import analyze_action_chains
from astra_audio.soundscape_planner import plan_soundscape

def test_rope_window_descent_chain_extracts_explicit_steps():
    text = """दृश्य 1: रात
उसने रस्सी खोली और खिड़की की ग्रिल पर बाँधी।
उसने रस्सी में गाँठ लगाकर कस दी और खींचकर जाँचा।
वह खिड़की से बाहर निकला और रस्सी के सहारे नीचे उतरा।
नीचे पहुँचकर उसने रस्सी छोड़ दी।
"""
    result = analyze_action_chains(text)
    events = [e["action"] for c in result["action_chains"] for e in c["events"]]
    assert "rope_uncoil" in events
    assert "rope_wrap_anchor" in events
    assert "knot_tighten" in events
    assert "anchor_test" in events
    assert "window_exit" in events
    assert "rope_descend" in events
    assert "rope_release" in events
    assert result["safety_and_realism"]["no_auto_asset_insertion"] is True

def test_reverse_climb_and_window_entry():
    text = "वह रस्सी पकड़कर ऊपर चढ़ा और खिड़की से अंदर कूदा।"
    events = [e["action"] for c in analyze_action_chains(text)["action_chains"] for e in c["events"]]
    assert "rope_climb" in events
    assert "jump_window_in" in events

def test_soundscape_includes_action_chains_per_scene():
    result = plan_soundscape("दृश्य 1: जंगल\nवह सूखे पत्तों पर चला और झाड़ियों से बाहर निकला।")
    assert result["action_chain_count"] >= 1
    assert result["scenes"][0]["action_chains"]
    assert result["audio_rendered"] is False if "audio_rendered" in result else True

def test_no_invented_rope_cues_when_not_in_story():
    result = analyze_action_chains("वह कमरे में बैठकर किताब पढ़ रहा था।")
    assert result["event_count"] == 0
