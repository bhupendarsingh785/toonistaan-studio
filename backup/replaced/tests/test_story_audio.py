import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.story_audio as sa


def test_story_has_characters_and_emotions():
    assert len(sa.STORY) >= 5
    for line in sa.STORY:
        assert line["who"] and line["bhaav"] and line["text"]


def test_two_characters_used():
    who = {l["who"] for l in sa.STORY}
    assert {"dadi", "bachcha"} <= who


def test_bed_assets_exist():
    for asset, _gain, _loop in sa.BED:
        assert (sa.LIB / asset).exists(), asset


def test_events_assets_exist():
    for _at, asset, _gain in sa.EVENTS:
        assert (sa.LIB / asset).exists(), asset


def test_single_mode_exists():
    assert hasattr(sa, "render_single")


def test_merge_lines_reduces_segments():
    merged = sa.merge_lines(sa.STORY)
    assert len(merged) < len(sa.STORY)
    assert all(m["who"] and m["text"] for m in merged)


def test_gap_is_small():
    import inspect
    src = inspect.getsource(sa.render_lines)
    assert "0.15" in src          # line ke beech ka gap chhota (ruka-ruka na lage)
