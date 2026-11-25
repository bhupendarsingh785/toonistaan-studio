import unittest, tempfile, json
from pathlib import Path
from browser_agent_v08 import terms, score, quality
from prosody_intelligence import analyze_line, analyze_script
from hindi_phonology import inspect_text
class V08Tests(unittest.TestCase):
 def test_query_tokenization_hindi(self): self.assertIn("हिंदी",terms("हिंदी उच्चारण research"))
 def test_score_relevance(self): self.assertGreater(score("Hindi TTS","Hindi TTS model","Hindi TTS model for speech"),0.4)
 def test_primary_source_quality(self): self.assertEqual(quality("https://huggingface.co/model"),"primary_or_project_source")
 def test_question_punctuation(self): self.assertEqual(analyze_line("तुम कहाँ जा रहे हो?")["delivery"]["contour"],"question_rise")
 def test_explicit_angry(self): self.assertEqual(analyze_line("राम [भाव:गुस्सा]: बस करो!")["emotion"],"angry")
 def test_character_profiles_stay_separate(self):
  x=analyze_script("राम: मैं आ गया।\nसीता: तुम देर से आए।"); self.assertEqual(x["summary"]["speech_segments"],2)
 def test_hindi_text_has_words(self): self.assertGreater(inspect_text("कहानी की आवाज़")["counts"]["words"],0)
 def test_svara_bridge_emotion_tag_and_character_voice(self):
  from unittest.mock import patch, Mock
  from svara_bridge import render
  fake=Mock(); fake.content=b"x"*200; fake.raise_for_status.return_value=None
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/"voice.mp3"
   cfg={"svara_base_url":"http://127.0.0.1:8080/v1","svara_model":"svara-tts-v1","svara_voice":"hi_female"}
   profile={"svara_voice":"hi_male"}
   with patch("svara_bridge.requests.post",return_value=fake) as post:
    render("मुझे बहुत गुस्सा आ रहा है।",out,cfg,profile,"angry")
   self.assertTrue(out.exists())
   args=post.call_args
   self.assertEqual(args.args[0],"http://127.0.0.1:8080/v1/audio/speech")
   self.assertEqual(args.kwargs["json"]["voice"],"hi_male")
   self.assertTrue(args.kwargs["json"]["input"].endswith("<anger>"))
 def test_scene_analyzer_extracts_tagged_characters(self):
  from cinematic_audio.astra_audio.story_intelligence import analyze_script_text
  x=analyze_script_text("आरव [भाव:डर]: मुझे यहाँ डर लग रहा है।\nमाँ [भाव:गंभीर]: मेरे पास रहो।")
  self.assertEqual({c["name"] for c in x["characters"]},{"आरव","माँ"})
 def test_research_handoff_is_engine_local(self):
  from unittest.mock import patch
  from browser_agent_v08 import research, Source
  with tempfile.TemporaryDirectory() as td:
   candidate=("https://huggingface.co/example/model","Example Hindi model","huggingface")
   src=Source(candidate[0],"huggingface.co","Example Hindi model","Hindi TTS model card with Hindi pronunciation and expressive speech.","a"*64,1.0,"2026-11-18T00:00:00Z","collected","mock","primary_or_project_source",[])
   with patch("browser_agent_v08.start_svara_learning",return_value={"state":"mocked"}), patch("browser_agent_v08.discover",return_value=([candidate],[])), patch("browser_agent_v08.fetch",return_value=src):
    status=research("Hindi TTS",td,max_pages=1,use_browser=False,engine="elevenlabs")
   self.assertEqual(status["sources_collected"],1)
   self.assertTrue(Path(status["handoff_file"]).exists())
   data=json.loads(Path(status["handoff_file"]).read_text(encoding="utf-8"))
   self.assertEqual(data["engine"],"elevenlabs")
   self.assertEqual(len(data["items"]),1)

if __name__=="__main__": unittest.main()
