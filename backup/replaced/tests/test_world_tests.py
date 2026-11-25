import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.world_tests as wtst
import tools.test_matrix as tm


def test_matrix_cases_include_all_methods():
    cases = tm.make_cases(10, seed=1)
    methods = {c["method"] for c in cases}
    assert {"combinatorial", "boundary", "chaos"} <= methods
    assert len(cases) == 10 + len(tm.BOUNDARY) + 4


def test_boundary_lengths_present():
    cases = tm.make_cases(0, seed=1)
    kinds = {c["kind"] for c in cases}
    for n in tm.BOUNDARY:
        assert f"len{n}" in kinds


def test_mutation_rejects_broken_audio(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"RIFF" + b"\x00" * 400)
    import tools.render_cache as rc
    assert rc._usable(bad) is False


def test_world_tests_has_six_methods():
    for name in ("differential", "soak", "pairwise", "mutation_lite",
                 "regression", "risk_based"):
        assert hasattr(wtst, name)


def test_piper_does_not_print_traceback():
    """Piper fail hone par log me traceback ka dher nahi aana chahiye."""
    src = (Path(__file__).resolve().parent.parent / "tools" / "voice_provider.py").read_text(encoding="utf-8")
    assert 'print("PIPER_FAIL"' not in src
