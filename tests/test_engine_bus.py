import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.engine_bus as bus


def _caps(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS", tmp_path / "bus")
    monkeypatch.setattr(bus, "registry_path", lambda: tmp_path / "bus" / "engines.json")
    return [
        bus.Capability(name="elevenlabs", emotions=["neutral", "dukh", "gussa"], speed=1.0, cost=1.0),
        bus.Capability(name="piper", emotions=["neutral"], speed=2.0, cost=0.0, offline=True),
        bus.Capability(name="espeak", emotions=["neutral"], speed=3.0, cost=0.0, offline=True),
    ]


def test_register_and_status(tmp_path, monkeypatch):
    _caps(tmp_path, monkeypatch)
    bus.register(bus.Capability(name="piper", offline=True, speed=2.0))
    st = bus.status()
    assert st["engines"] == 1 and st["list"][0]["name"] == "piper"


def test_split_script_reads_character_and_emotion():
    text = "दादी [dukh]: बेटा आ जा।\n[gussa] चुप रहो!\nबिना टैग की लाइन।"
    parts = bus.split_script(text)
    assert [p.character for p in parts] == ["दादी", "sutradhar", "sutradhar"]
    assert [p.emotion for p in parts] == ["dukh", "gussa", "neutral"]


def test_split_script_breaks_long_line():
    long_line = "यह एक लंबा वाक्य है। " * 30
    parts = bus.split_script(long_line, max_chars=100)
    assert len(parts) > 1 and all(len(p.text) <= 130 for p in parts)


def test_plan_keeps_one_voice_per_character(tmp_path, monkeypatch):
    caps = _caps(tmp_path, monkeypatch)
    text = "दादी: पहली लाइन।\nमाँ: दूसरी लाइन।\nदादी: तीसरी लाइन।"
    parts = bus.plan(text, caps)
    dadi_engines = {p.engine for p in parts if p.character == "दादी"}
    assert len(dadi_engines) == 1            # ek kirdaar = ek engine (awaaz nahi badalti)


def test_plan_sends_emotion_to_capable_engine(tmp_path, monkeypatch):
    caps = _caps(tmp_path, monkeypatch)
    parts = bus.plan("[dukh] बहुत तकलीफ़ है।", caps)
    assert parts[0].engine == "elevenlabs"    # dukh sirf elevenlabs kar sakta hai


def test_run_retries_on_next_engine_when_one_fails(tmp_path, monkeypatch):
    caps = _caps(tmp_path, monkeypatch)
    calls = []

    def renderer(engine, part, out):
        calls.append(engine)
        if engine == "elevenlabs":
            raise RuntimeError("key nahi")
        Path(out).write_bytes(b"x" * 4000)
        return True

    # dukh wali line → sarvam chuna jayega, woh fail hoga, phir doosra engine
    rep = bus.run("दादी [dukh]: लाइन एक।", str(tmp_path / "out"), renderer=renderer, caps=caps)
    assert rep["done"] == 1 and "elevenlabs" in calls and len(calls) > 1
    assert (tmp_path / "out" / "manifest.json").exists()


def test_run_marks_failure_when_no_engine_works(tmp_path, monkeypatch):
    caps = _caps(tmp_path, monkeypatch)
    rep = bus.run("दादी: लाइन।", str(tmp_path / "out"),
                  renderer=lambda e, p, o: False, caps=caps)
    assert rep["done"] == 0 and rep["failed"] == 1


def test_partial_progress_is_saved(tmp_path, monkeypatch):
    caps = _caps(tmp_path, monkeypatch)
    def renderer(engine, part, out):
        Path(out).write_bytes(b"y" * 4000)
        return True
    rep = bus.run("दादी: एक।\nमाँ: दो।", str(tmp_path / "out"), renderer=renderer, caps=caps)
    m = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert rep["done"] == 2 and m["done"] == 2 and len(m["parts"]) == 2


def test_default_four_engines(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS", tmp_path / "bus")
    monkeypatch.setattr(bus, "registry_path", lambda: tmp_path / "bus" / "engines.json")
    caps = bus.ensure_defaults()
    names = {c.name for c in caps}
    # chaar core engine + paanchva (sarvam) saathi — dono alag list
    assert set(bus.CORE_ENGINES) == {"edge", "elevenlabs", "piper", "espeak"}
    assert set(bus.CORE_ENGINES) <= names and "sarvam" in names


def test_engines_can_message_each_other(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS", tmp_path / "bus")
    monkeypatch.setattr(bus, "registry_path", lambda: tmp_path / "bus" / "engines.json")
    bus.ensure_defaults()
    bus.send("edge", "piper", "task", {"line": "बेटा आ जा", "emotion": "pyaar"})
    msgs = bus.inbox("piper")
    assert len(msgs) == 1 and msgs[0]["from"] == "edge" and msgs[0]["payload"]["emotion"] == "pyaar"


def test_broadcast_reaches_all_other_engines(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS", tmp_path / "bus")
    monkeypatch.setattr(bus, "registry_path", lambda: tmp_path / "bus" / "engines.json")
    bus.ensure_defaults()
    sent = bus.broadcast("edge", "info", {"story": "station"})
    assert len(sent) == 4          # baaki chaar (elevenlabs, piper, espeak, sarvam)
    assert all(bus.inbox(n) for n in ("elevenlabs", "piper", "espeak", "sarvam"))


def test_heartbeat_marks_engine_down(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS", tmp_path / "bus")
    monkeypatch.setattr(bus, "registry_path", lambda: tmp_path / "bus" / "engines.json")
    bus.ensure_defaults()
    bus.heartbeat("piper", healthy=False, note="binary nahi")
    caps = {c.name: c for c in bus.engines()}
    assert caps["piper"].healthy is False


def test_emotion_detected_when_no_tag(tmp_path, monkeypatch):
    caps = _caps(tmp_path, monkeypatch)
    parts = bus.plan("मुझे बहुत तकलीफ़ हो रही है, अब क्या करूँ...", caps)
    assert parts[0].emotion in ("dukh", "rona")


def test_fifth_engine_is_present_but_not_core(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS", tmp_path / "bus")
    monkeypatch.setattr(bus, "registry_path", lambda: tmp_path / "bus" / "engines.json")
    names = {c.name for c in bus.ensure_defaults()}
    assert bus.CORE_ENGINES == ["edge", "elevenlabs", "piper", "espeak"]
    assert "sarvam" in names and len(names) == 5      # chaar core + paanchva saathi


def test_error_is_recorded_and_credited_to_fixer(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS", tmp_path / "bus")
    monkeypatch.setattr(bus, "registry_path", lambda: tmp_path / "bus" / "engines.json")
    caps = _caps(tmp_path, monkeypatch)
    def renderer(engine, part, out):
        if engine == "elevenlabs":
            raise RuntimeError("key nahi")
        Path(out).write_bytes(b"z" * 4000); return True
    bus.run("दादी [dukh]: लाइन।", str(tmp_path / "out"), renderer=renderer, caps=caps)
    rep = bus.sudhaar_report()
    assert rep["total_errors"] >= 1
    assert rep["by_engine"].get("elevenlabs", 0) >= 1
    assert rep["fixed_by"]                                  # kisne sudhara, likha hai


def test_parallel_run_completes_all_parts(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS", tmp_path / "bus")
    monkeypatch.setattr(bus, "registry_path", lambda: tmp_path / "bus" / "engines.json")
    caps = _caps(tmp_path, monkeypatch)
    def renderer(engine, part, out):
        Path(out).write_bytes(b"p" * 4000); return True
    text = "\n".join(f"किरदार{i}: लाइन {i}।" for i in range(1, 9))
    rep = bus.run(text, str(tmp_path / "out"), renderer=renderer, caps=caps, workers=4)
    assert rep["done"] == 8 and rep["failed"] == 0 and rep["workers"] == 4
