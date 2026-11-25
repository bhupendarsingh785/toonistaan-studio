import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf

from piper_indicf5_backend import (
    normalize_hindi_text, apply_pronunciation_overrides, split_hindi_text,
    load_voice_profile, IndicF5Backend, VoiceProfileError
)


class FakeModel:
    class config:
        sampling_rate = 24000
    def __call__(self, text, ref_audio_path, ref_text):
        assert text.strip()
        assert Path(ref_audio_path).is_file()
        assert ref_text.strip()
        return np.sin(np.linspace(0, 20, 2400)).astype(np.float32)


class FakeInt16Model(FakeModel):
    def __call__(self, text, ref_audio_path, ref_text):
        return np.array([0, 16384, -16384, 0], dtype=np.int16)


class IndicF5AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ref = self.root / "voice.wav"
        sf.write(self.ref, np.zeros(24000*3, dtype=np.float32), 24000)
        self.profile = self.root / "profiles.json"
        self.profile.write_text(json.dumps({"characters":{"A":{
            "references":{"neutral":{"audio":"voice.wav","text":"नमस्ते, मैं आपकी आवाज़ का नमूना हूँ।"}},
            "pronunciation_overrides":{"क्षमा":"क्शमा"}
        }}}), encoding="utf-8")
    def tearDown(self):
        self.tmp.cleanup()

    def test_unicode_normalization_and_spaces(self):
        self.assertEqual(normalize_hindi_text(" नमस्\u200bते   भारत "), "नमस्ते भारत")
    def test_empty_text_rejected(self):
        with self.assertRaises(ValueError): normalize_hindi_text(" ")
    def test_explicit_override_only(self):
        out, audit = apply_pronunciation_overrides("क्षमा करें", {"क्षमा":"क्शमा"})
        self.assertEqual(out, "क्शमा करें")
        self.assertEqual(audit[0]["count"], "1")
    def test_no_override_does_not_rewrite(self):
        self.assertEqual(apply_pronunciation_overrides("भारत", None)[0], "भारत")
    def test_chunking_no_token_split(self):
        chunks = split_hindi_text(("यह एक लंबा वाक्य है। " * 30), 80)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c.strip() for c in chunks))
    def test_min_chunk_limit(self):
        with self.assertRaises(ValueError): split_hindi_text("हिंदी", 10)
    def test_profile_reference_resolves(self):
        profile, emo, audio, transcript = load_voice_profile(self.profile, "A", "happy")
        self.assertEqual(emo, "neutral")
        self.assertEqual(transcript, "नमस्ते, मैं आपकी आवाज़ का नमूना हूँ।")
        self.assertTrue(Path(audio).exists())

    def test_exact_emotion_reference_selected(self):
        data=json.loads(self.profile.read_text())
        data["characters"]["A"]["references"]["sad"]={"audio":"voice.wav","text":"दुखी नमूना।"}
        self.profile.write_text(json.dumps(data),encoding="utf-8")
        _profile, emo, _audio, transcript = load_voice_profile(self.profile,"A","sad")
        self.assertEqual(emo,"sad")
        self.assertEqual(transcript,"दुखी नमूना।")
    def test_unknown_character_rejected(self):
        with self.assertRaises(VoiceProfileError): load_voice_profile(self.profile, "B")
    def test_missing_reference_audio_rejected(self):
        data=json.loads(self.profile.read_text())
        data["characters"]["A"]["references"]["neutral"]["audio"]="missing.wav"
        self.profile.write_text(json.dumps(data))
        with self.assertRaises(VoiceProfileError): load_voice_profile(self.profile, "A")
    def test_neural_render_writes_wav(self):
        backend=IndicF5Backend(model_loader=lambda _id,_dev: FakeModel())
        out=self.root/"out.wav"
        result=backend.render("क्षमा करें। यह परीक्षण है।", self.profile, "A", "happy", out)
        self.assertTrue(out.exists())
        info=sf.info(out)
        self.assertEqual(info.samplerate, 24000)
        self.assertEqual(result.used_emotion, "neutral")
        self.assertTrue(result.warnings)
        self.assertEqual(result.pronunciation_changes[0]["written"], "क्षमा")
    def test_int16_audio_is_scaled_to_float_range(self):
        backend=IndicF5Backend(model_loader=lambda _id,_dev: FakeInt16Model())
        out=self.root/"int16.wav"
        backend.render("नमस्ते।", self.profile, "A", "neutral", out)
        audio, _sr = sf.read(out)
        self.assertLessEqual(float(np.max(np.abs(audio))), 0.51)

    def test_model_cached(self):
        calls=[]
        backend=IndicF5Backend(model_loader=lambda _id,_dev: calls.append(1) or FakeModel())
        backend._load(); backend._load()
        self.assertEqual(len(calls),1)


if __name__ == "__main__":
    unittest.main()
