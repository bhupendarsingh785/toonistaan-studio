import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.teacher_student as ts


def test_plan_counts_calls():
    p = ts.plan(12)
    assert p["api_calls"] == 12 and p["emotions"] == len(ts.LINES)


def test_learn_needs_meta(tmp_path, monkeypatch):
    monkeypatch.setattr(ts, "DATA", tmp_path / "none")
    assert ts.learn()["ok"] is False


def test_learn_from_synthetic_meta(tmp_path, monkeypatch):
    rows = [
        {"emotion": "neutral", "hz": 150, "dur": 2.0, "cps": 20, "rms": 0.1},
        {"emotion": "gussa", "hz": 165, "dur": 1.6, "cps": 25, "rms": 0.14},
        {"emotion": "dukh", "hz": 135, "dur": 2.6, "cps": 15, "rms": 0.08},
    ]
    meta = tmp_path / "m.json"
    meta.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    monkeypatch.setattr(ts, "LEARNED", tmp_path / "learned.json")
    rep = ts.learn(meta)
    assert rep["ok"] and rep["emotions"] == 3
    st = json.loads((tmp_path / "learned.json").read_text())["style"]
    assert st["gussa"]["pitch"] > 1 and st["gussa"]["pace"] > 1     # tez + uncha
    assert st["dukh"]["pitch"] < 1 and st["dukh"]["pace"] < 1       # dheema + neecha


def test_provider_prefers_learned(tmp_path, monkeypatch):
    import tools.voice_provider as vp
    monkeypatch.setattr(vp, "_LEARNED_CACHE", {"gussa": {"pitch": 1.2, "pace": 1.4,
                                                         "energy": 1.3, "gap_ms": 90}})
    st = vp._bhaav_style("gussa")
    assert st["pace"] == 1.4 and st.get("source") == "learned"
