import sys, json, numpy as np, soundfile as sf
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.voice_clone as vc


def test_enroll_needs_consent(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = tmp_path / "a.wav"; sf.write(str(audio), np.sin(np.arange(24000)*2*np.pi*220/24000).astype("float32")*0.2, 24000)
    try:
        vc.enroll("dadi", str(audio), "नमस्ते", consent=False)
        assert False, "ConsentMissing aana chahiye tha"
    except vc.ConsentMissing as exc:
        assert "Ijazat" in str(exc)


def test_enroll_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = tmp_path / "a.wav"; sf.write(str(audio), np.sin(np.arange(24000)*2*np.pi*220/24000).astype("float32")*0.2, 24000)
    v = vc.enroll("dadi", str(audio), " नमस्ते, मैं दादी हूँ। ", consent=True, backend="indicf5")
    assert v.consent and v.transcript == "नमस्ते, मैं दादी हूँ।"
    vs = vc.list_voices()
    assert len(vs) == 1 and vs[0].name == "dadi"
    assert (tmp_path / "voices" / "dadi" / "reference.wav").exists()


def test_enroll_rejects_empty_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = tmp_path / "a.wav"; sf.write(str(audio), np.zeros(100, dtype="float32"), 24000)
    try:
        vc.enroll("x", str(audio), "   ", consent=True)
        assert False
    except ValueError as exc:
        assert "transcript" in str(exc)


def test_speak_reports_backend_and_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = tmp_path / "a.wav"; sf.write(str(audio), np.sin(np.arange(24000)*2*np.pi*220/24000).astype("float32")*0.2, 24000)
    vc.enroll("dadi", str(audio), "नमस्ते", consent=True, backend="indicf5")
    script = tmp_path / "s.txt"; script.write_text("पहली लाइन\nदूसरी लाइन\n", encoding="utf-8")
    monkeypatch.setattr(vc, "backend_status", lambda: [{"name": "indicf5", "ready": True, "why": ""}])
    calls = []

    def fake_render(backend, voice, text, out):
        calls.append(text); sf.write(str(out), np.ones(2400, dtype="float32") * 0.05, 24000); return True

    monkeypatch.setattr(vc, "_render_line", fake_render)
    rep = vc.speak("dadi", str(script), str(tmp_path / "out"))
    assert rep["ok"] == 2 and rep["failed"] == 0
    assert rep["backend"] == "indicf5"
    assert calls == ["पहली लाइन", "दूसरी लाइन"]


def test_no_backend_means_failure_not_fake_success(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = tmp_path / "a.wav"; sf.write(str(audio), np.sin(np.arange(24000)*2*np.pi*220/24000).astype("float32")*0.2, 24000)
    vc.enroll("dadi", str(audio), "नमस्ते", consent=True, backend="indicf5")
    script = tmp_path / "s.txt"; script.write_text("लाइन\n", encoding="utf-8")
    monkeypatch.setattr(vc, "backend_status", lambda: [{"name": "indicf5", "ready": False, "why": ""}])
    monkeypatch.setattr(vc, "pick_backend", lambda: None)
    try:
        vc.speak("dadi", str(script), str(tmp_path / "out"))
        assert False
    except RuntimeError as exc:
        assert "backend" in str(exc)


def test_parse_line_emotion_tag_forms():
    assert vc.parse_line("[dukh] बेटा, आ जा पास।") == ("dukh", "बेटा, आ जा पास।")
    assert vc.parse_line("दादी [gussa]: चुप रहो!") == ("gussa", "चुप रहो!")
    assert vc.parse_line("बिना भाव") == ("neutral", "बिना भाव")


def test_enroll_from_media_uses_extract(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    media = tmp_path / "clip.mp4"; media.write_bytes(b"x" * 100)
    ref = tmp_path / "voices" / "dadi" / "reference.wav"

    def fake_run(src, out_dir, seconds=12.0, do_clean=True):
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        sf.write(str(ref), np.ones(12000, dtype="float32") * 0.1, 16000)
        return {"reference": str(ref), "duration_sec": 11.0, "transcript": "नमस्ते मैं दादी हूँ"}

    monkeypatch.setattr("tools.voice_extract.run", fake_run)
    v = vc.enroll_from_media("dadi", str(media), consent=True, backend="indicf5")
    assert v.transcript == "नमस्ते मैं दादी हूँ"
    assert "media se nikaala" in v.note
    assert ref.exists()
    extracted, sample_rate = sf.read(str(ref))
    assert sample_rate == 24000 and extracted.size == 18000


def test_enroll_from_media_needs_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    media = tmp_path / "clip.mp4"; media.write_bytes(b"x")
    monkeypatch.setattr("tools.voice_extract.run",
                        lambda *a, **k: {"reference": str(tmp_path / "r.wav"), "duration_sec": 5, "transcript": ""})
    try:
        vc.enroll_from_media("x", str(media), consent=True)
        assert False
    except ValueError as exc:
        assert "transcript" in str(exc)

def test_voice_name_path_traversal_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, 'VOICES', tmp_path / 'voices')
    for bad in ('../escape', '..', '/tmp/x', 'a/b'):
        try:
            vc._voice_dir(bad)
            assert False, f'{bad} should be rejected'
        except ValueError:
            pass

def test_reference_audio_is_normalised_to_wav(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, 'VOICES', tmp_path / 'voices')
    audio = tmp_path / 'a.wav'
    sf.write(str(audio), np.ones(8000, dtype='float32') * 0.2, 16000)
    voice = vc.enroll('safe_name', str(audio), 'नमस्ते', consent=True)
    data, sr = sf.read(voice.audio)
    assert sr == 24000 and data.size == 12000

def test_empty_script_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, 'VOICES', tmp_path / 'voices')
    audio = tmp_path / 'a.wav'; sf.write(str(audio), np.ones(8000, dtype='float32')*.2, 16000)
    vc.enroll('dadi', str(audio), 'नमस्ते', consent=True, backend='indicf5')
    script = tmp_path / 'empty.txt'; script.write_text('# comment only', encoding='utf-8')
    try:
        vc.speak('dadi', str(script), str(tmp_path / 'out'))
        assert False
    except ValueError as exc:
        assert 'text' in str(exc)

def test_long_form_manifest_and_master_wav(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, 'VOICES', tmp_path / 'voices')
    audio = tmp_path / 'ref.wav'; sf.write(str(audio), np.ones(8000, dtype='float32')*.1, 24000)
    vc.enroll('narrator', str(audio), 'यह एक नमूना है।', consent=True, backend='indicf5')
    script = tmp_path / 'story.txt'; script.write_text('पहला वाक्य।\nदूसरा वाक्य।', encoding='utf-8')
    monkeypatch.setattr(vc, 'backend_status', lambda: [{'name':'indicf5','ready':True,'why':''}])
    def fake_render(backend, voice, text, out):
        sf.write(str(out), np.ones(2400, dtype='float32')*.03, 24000); return True
    monkeypatch.setattr(vc, '_render_line', fake_render)
    out = tmp_path / 'long'
    report = vc.speak('narrator', str(script), str(out))
    assert report['ok'] == 2 and report['failed'] == 0
    assert Path(report['master']['master']).is_file()
    manifest = json.loads((out/'generation_manifest.json').read_text(encoding='utf-8'))
    assert manifest['status'] == 'completed' and len(manifest['items']) == 2

def test_revoked_voice_listed_as_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, 'VOICES', tmp_path / 'voices')
    audio = tmp_path / 'ref.wav'; sf.write(str(audio), np.ones(8000, dtype='float32')*.1, 24000)
    vc.enroll('revoked', str(audio), 'नमस्ते', consent=True)
    from tools.consent import revoke_consent
    revoke_consent(tmp_path/'voices'/'revoked')
    voices = vc.list_voices()
    assert len(voices) == 1 and voices[0].consent is False and 'consent=blocked' in voices[0].note


def test_xtts_model_cached_once_per_process(monkeypatch):
    import types
    calls = []
    class FakeTTS:
        def __init__(self, model_name):
            calls.append(model_name)
        def to(self, device):
            return self
    api = types.ModuleType('TTS.api'); api.TTS = FakeTTS
    pkg = types.ModuleType('TTS'); pkg.__path__ = []
    monkeypatch.setitem(sys.modules, 'TTS', pkg)
    monkeypatch.setitem(sys.modules, 'TTS.api', api)
    vc.clear_backend_cache()
    first = vc._get_xtts_model('cpu')
    second = vc._get_xtts_model('cpu')
    assert first is second and len(calls) == 1
    vc.clear_backend_cache()


def test_resume_invalidated_when_reference_audio_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, 'VOICES', tmp_path / 'voices')
    audio = tmp_path / 'ref.wav'; sf.write(str(audio), np.ones(8000, dtype='float32')*.1, 24000)
    vc.enroll('narrator', str(audio), 'नमस्ते', consent=True, backend='indicf5')
    script = tmp_path / 'story.txt'; script.write_text('एक वाक्य।', encoding='utf-8')
    monkeypatch.setattr(vc, 'backend_status', lambda: [{'name':'indicf5','ready':True,'why':''}])
    calls = []
    def fake_render(backend, voice, text, out):
        calls.append(text); sf.write(str(out), np.ones(2400, dtype='float32')*.03, 24000); return True
    monkeypatch.setattr(vc, '_render_line', fake_render)
    out = tmp_path / 'long'
    vc.speak('narrator', str(script), str(out))
    # Re-enrol same profile name with different reference audio: resume must not reuse old chunks.
    audio2 = tmp_path / 'ref2.wav'; sf.write(str(audio2), np.ones(8000, dtype='float32')*.2, 24000)
    vc.enroll('narrator', str(audio2), 'नमस्ते', consent=True, backend='indicf5')
    vc.speak('narrator', str(script), str(out), resume=True)
    assert len(calls) == 2


def test_multi_speaker_script_is_not_silently_rendered_as_one_voice(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, 'VOICES', tmp_path / 'voices')
    audio = tmp_path / 'ref.wav'; sf.write(str(audio), np.ones(8000, dtype='float32')*.1, 24000)
    vc.enroll('narrator', str(audio), 'नमस्ते', consent=True, backend='indicf5')
    script = tmp_path / 'dialogue.txt'; script.write_text('दादी: नमस्ते।\nबेटा: प्रणाम।', encoding='utf-8')
    monkeypatch.setattr(vc, 'backend_status', lambda: [{'name':'indicf5','ready':True,'why':''}])
    try:
        vc.speak('narrator', str(script), str(tmp_path / 'out'))
        assert False, 'speaker mapping missing should fail explicitly'
    except ValueError as exc:
        assert 'Multiple speaker labels' in str(exc)


def test_resume_does_not_reuse_chunk_when_pipeline_text_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, 'VOICES', tmp_path / 'voices')
    audio = tmp_path / 'ref.wav'; sf.write(str(audio), np.ones(8000, dtype='float32')*.1, 24000)
    vc.enroll('narrator', str(audio), 'नमस्ते', consent=True, backend='indicf5')
    script = tmp_path / 'story.txt'; script.write_text('एक वाक्य।', encoding='utf-8')
    monkeypatch.setattr(vc, 'backend_status', lambda: [{'name':'indicf5','ready':True,'why':''}])
    calls = []
    def fake_render(backend, voice, text, out):
        calls.append(text); sf.write(str(out), np.ones(2400, dtype='float32')*.03, 24000); return True
    monkeypatch.setattr(vc, '_render_line', fake_render)
    out = tmp_path / 'long'
    vc.speak('narrator', str(script), str(out))
    # Simulate a parser/pipeline change while source script and voice remain the same.
    original = vc.prepare_script if hasattr(vc, 'prepare_script') else None
    import tools.script_pipeline as sp
    monkeypatch.setattr(sp, 'prepare_script', lambda *a, **k: [{
        'sequence': 1, 'speaker': 'default', 'emotion': 'sad', 'text': 'badla hua chunk', 'chunk': 1
    }])
    vc.speak('narrator', str(script), str(out), resume=True)
    assert calls == ['एक वाक्य।', 'badla hua chunk']


def test_generated_wav_rejects_silence_and_nan(tmp_path):
    silent = tmp_path / 'silent.wav'; sf.write(str(silent), np.zeros(2400, dtype='float32'), 24000)
    try:
        vc._wav_info(silent)
        assert False, 'silent WAV reject hona chahiye'
    except ValueError as exc:
        assert 'silent' in str(exc).lower()
    invalid = tmp_path / 'nan.wav'; sf.write(str(invalid), np.array([float('nan')] * 2400, dtype='float32'), 24000, subtype='FLOAT')
    try:
        vc._wav_info(invalid)
        assert False, 'NaN WAV reject hona chahiye'
    except ValueError as exc:
        assert 'NaN' in str(exc) or 'Inf' in str(exc)


def test_invalid_generation_limits_fail_before_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, 'VOICES', tmp_path / 'voices')
    audio = tmp_path / 'ref.wav'; sf.write(str(audio), np.ones(8000, dtype='float32')*.1, 24000)
    vc.enroll('narrator', str(audio), 'नमस्ते', consent=True, backend='indicf5')
    script = tmp_path / 'story.txt'; script.write_text('एक वाक्य।', encoding='utf-8')
    for kwargs in ({'retries': 11}, {'max_chars': 20}, {'max_chars': 3000}):
        try:
            vc.speak('narrator', str(script), str(tmp_path / 'out'), **kwargs)
            assert False
        except ValueError:
            pass


def test_reference_quality_gate_warns_and_strict_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "VOICES", tmp_path / "voices")
    audio = tmp_path / "short.wav"
    sf.write(str(audio), np.sin(np.arange(24000)*2*np.pi*220/24000).astype("float32")*0.2, 24000)
    # default: warning, enroll chalta hai
    v = vc.enroll("kamzor", str(audio), "नमस्ते", consent=True, backend="indicf5")
    assert v.consent
    # strict mode: block
    monkeypatch.setenv("ASTRA_STRICT_REF", "1")
    try:
        vc.enroll("kamzor2", str(audio), "नमस्ते", consent=True, backend="indicf5")
        assert False, "strict mode me block hona chahiye"
    except ValueError as exc:
        assert "chhoti" in str(exc)


def test_multi_window_extract_helper():
    from tools import voice_extract as ve
    sr = 24000
    loud = 0.3*np.sin(2*np.pi*180*np.arange(int(4*sr))/sr).astype(np.float32)
    quiet = np.zeros(int(2*sr), dtype=np.float32)
    wins = ve.best_windows(np.concatenate([loud, quiet, loud]), sr, 3.0, 2)
    assert len(wins) == 2 and abs(wins[0][0] - wins[1][0]) >= 3.0
