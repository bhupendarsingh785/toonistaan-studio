import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.world_scape as ws


def test_plan_detects_jungle_river_rain():
    p = ws.plan_scene("वह जंगल से गुजरा, पास में नदी बह रही थी, बारिश हो रही थी।")
    assert "jungle" in p["places"] and "nadi" in p["places"]
    assert "barish" in p["weather"]
    assert any(l["kind"] == "bed" for l in p["layers"])


def test_plan_detects_ground_and_props():
    p = ws.plan_scene("कीचड़ में कदम पड़े और दूर ट्रैक्टर गुजरा।")
    assert p["ground"] == "keechad" and "tractor" in p["props"]


def test_missing_assets_are_reported_not_hidden():
    p = ws.plan_scene("ट्रैक्टर आया।")   # library me tractor nahi hai
    assert p["missing"], "jo asset nahi hai wo 'missing' me aana chahiye"


def test_duck_curve_has_between_expression():
    c = ws.duck_curve([(1.0, 3.0), (5.0, 6.5)], -26)
    assert "between(t,1.00,3.00)" in c and "-26" in c


def test_duck_curve_without_dialogue_is_plain_volume():
    assert ws.duck_curve([], -24) == "volume=-24dB"


def test_build_writes_cues(tmp_path):
    rep = ws.build("जंगल में पत्ते खड़खड़ाए। नदी बह रही थी।", str(tmp_path), seconds=3)
    if not rep.get("ok"):
        import pytest; pytest.skip("ffmpeg asset nahi")
    assert Path(rep["cues"]).exists()
    cues = json.loads(Path(rep["cues"]).read_text())
    assert cues["seconds"] == 3 and cues["plan"]["places"]
