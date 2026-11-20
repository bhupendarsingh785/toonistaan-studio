import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.engine_router as r


def test_parse_story_named_and_narrator():
    lines = r.parse_story("दादी: बेटा आ जा।\nबारिश हो रही थी।")
    assert lines[0] == ("दादी", "बेटा आ जा।")
    assert lines[1] == ("vachak", "बारिश हो रही थी।")


def test_parse_story_ignores_comments_and_blanks():
    assert r.parse_story("# note\n\n  \n") == []


def test_choose_engine_first_ready_wins():
    first, rest = r.choose_engine("dadi", ready=["edge", "piper", "espeak"])
    assert first == "edge" and rest == ["piper", "espeak"]


def test_choose_engine_none_ready():
    first, rest = r.choose_engine("dadi", ready=[])
    assert first is None and rest == []


def test_status_covers_all_four_plus_sarvam():
    names = [s.name for s in r.engine_status()]
    assert names == r.ORDER
    assert set(["edge", "piper", "espeak", "elevenlabs"]).issubset(set(names))


def test_plan_uses_ready_engine_for_every_line(monkeypatch):
    monkeypatch.setattr(r, "ready_engines", lambda: ["piper"])
    plans = r.build_plan("दादी: बेटा आ जा।\nमाँ: खाना खा ले।")
    assert all(p.engine == "piper" for p in plans)
    assert [p.character for p in plans] == ["दादी", "माँ"]


def test_plan_marks_none_when_nothing_ready(monkeypatch):
    monkeypatch.setattr(r, "ready_engines", lambda: [])
    plans = r.build_plan("दादी: बेटा आ जा।")
    assert plans[0].engine == "NONE"


def test_render_line_falls_back_on_failure(monkeypatch, tmp_path):
    calls = []

    def fake(engine, text, character, out):
        calls.append(engine)
        if engine == "sarvam":
            raise RuntimeError("key nahi")
        Path(out).write_bytes(b"x" * 5000)
        return True

    monkeypatch.setattr(r, "_call_provider", fake)
    def fake_guarded(eng, text, ch, out, bhaav=""):
        calls.append(eng)
        return (eng != "sarvam"), {"cached": False, "engine": eng}
    monkeypatch.setattr(r, "_guarded", fake_guarded)
    ok, log = r.render_line("बेटा आ जा।", "दादी", tmp_path / "a.wav",
                            "sarvam", ["piper", "espeak"])
    assert ok is True
    assert calls == ["sarvam", "piper"]
    assert [x["ok"] for x in log] == [False, True]


def test_render_line_reports_all_failures(monkeypatch, tmp_path):
    def fake(engine, text, character, out):
        raise RuntimeError("band")

    monkeypatch.setattr(r, "_call_provider", fake)
    monkeypatch.setattr(r, "_guarded", lambda eng, text, ch, out, bhaav="": (False, {"cached": False, "engine": eng}))
    ok, log = r.render_line("x", "दादी", tmp_path / "a.wav", "piper", ["espeak"])
    assert ok is False
    assert len(log) == 2 and not any(x["ok"] for x in log)


def test_render_story_counts_and_reports(monkeypatch, tmp_path):
    def fake(engine, text, character, out):
        Path(out).write_bytes(b"x" * 5000)
        return True

    monkeypatch.setattr(r, "_call_provider", fake)
    monkeypatch.setattr(r, "_guarded", lambda eng, text, ch, out, bhaav="": (True, {"cached": False, "engine": eng}))
    monkeypatch.setattr(r, "ready_engines", lambda: ["piper"])
    rep = r.render_story("दादी: बेटा आ जा।\nमाँ: खाना खा ले।", tmp_path)
    assert rep["lines"] == 2 and rep["ok"] == 2
    assert [x["character"] for x in rep["results"]] == ["दादी", "माँ"]


def test_problems_lists_only_not_ready(monkeypatch):
    monkeypatch.setattr(r, "engine_status", lambda: [
        r.EngineState("edge", False, "binary missing: edge-tts"),
        r.EngineState("piper", True, "tayyar"),
    ])
    items = r.problems()
    assert len(items) == 1 and items[0]["engine"] == "edge"
    assert "pip install edge-tts" in items[0]["hal"]


def test_problems_empty_when_all_ready(monkeypatch):
    monkeypatch.setattr(r, "engine_status", lambda: [r.EngineState("piper", True, "tayyar")])
    assert r.problems() == []


def test_parallel_render_keeps_order(monkeypatch, tmp_path):
    monkeypatch.setattr(r, "ready_engines", lambda: ["piper"])
    monkeypatch.setattr(r, "_guarded", lambda eng, text, ch, out, bhaav="": (True, {"cached": False, "engine": eng}))
    rep = r.render_story_parallel("दादी: एक।\nमाँ: दो।\nलड़का: तीन।", tmp_path, workers=3)
    assert rep["ok"] == 3 and [x["n"] for x in rep["results"]] == [1, 2, 3]
    assert [x["character"] for x in rep["results"]] == ["दादी", "माँ", "लड़का"]


def test_bench_reports_timings(monkeypatch, tmp_path):
    import tools.engine_bench as eb
    import tools.engine_router as _er
    monkeypatch.setattr(_er, "render_line", lambda *a, **k: (True, [{"engine": "piper", "ok": True, "note": "banaya"}]))
    rows = eb.bench("नमस्ते दादी", ["piper"])
    assert rows[0]["ok"] is True and rows[0]["first_sec"] >= 0
