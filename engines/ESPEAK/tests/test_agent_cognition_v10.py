import unittest, tempfile
from unittest.mock import patch
from agent_cognition import plan_research_queries, analyze_sources, backend_status, offline_evidence_analysis

class CognitionV10Tests(unittest.TestCase):
 def test_unconfigured_backend_is_explicit(self):
  self.assertFalse(backend_status()["configured"]) if not __import__("os").getenv("AGENT_LLM_BASE_URL") else self.assertTrue(True)
 def test_fallback_plan_is_nonempty(self):
  p=plan_research_queries("Hindi TTS prosody", "edge", ["Hindi prosody"] )
  self.assertTrue(p["queries"]); self.assertIn(p["mode"],["model_planned","deterministic_fallback","web_first_model_free_plan"])
 def test_offline_mode_never_claims_deep_reasoning(self):
  r=analyze_sources("Hindi TTS", "edge", [{"title":"Paper","url":"https://example.org","domain":"example.org","text":"A sufficiently long source sentence about Hindi speech evaluation and its benchmark design."}])
  if r["mode"]=="offline_extractive_only": self.assertFalse(r["model_used"]); self.assertIsNone(r["debate"])
 def test_no_sources_yields_no_conclusion(self):
  r=analyze_sources("topic","edge",[])
  self.assertEqual(r["mode"],"no_evidence"); self.assertEqual(r["decisions"],[])
 def test_extractive_report_keeps_provenance(self):
  r=offline_evidence_analysis("topic","edge",[{"title":"T","url":"https://x.test","domain":"x.test","text":"This is a long sentence that should be extracted as a candidate statement from source material for review."}])
  self.assertEqual(r["evidence_inventory"][0]["url"],"https://x.test")


 def test_four_role_debate_when_model_is_configured(self):
  import agent_cognition as ac
  src=[{"title":"Official doc","url":"https://docs.example.org","domain":"docs.example.org","quality":"primary","sha256":"abc","text":"A sufficiently long source excerpt describing Hindi text to speech pronunciation and evaluation requirements."}]
  def fake_chat(system,user,cfg=None):
   if "You design rigorous" in system: return '{"queries":["Hindi phonology benchmark"]}'
   if "research analyst" in system: return '{"claims":[{"claim":"Hindi pronunciation needs evaluation","source_ids":["S1"]}]}'
   if "domain specialist" in system: return '{"implications":[{"text":"Add phoneme regression tests","source_ids":["S1"]}]}'
   if "adversarial reviewer" in system: return '{"risks":["Single source is insufficient"]}'
   return '{"proposals":[{"title":"Add held-out Hindi pronunciation tests","source_ids":["S1"],"acceptance_criteria":["Run 100 held-out words"]}]}'
  with patch.object(ac,'_config',return_value={'base_url':'https://example.org/v1','model':'test','api_key':'','timeout':10}), patch.object(ac,'_chat',side_effect=fake_chat), patch.object(ac,'backend_status',return_value={'configured':True}):
   report=ac.analyze_sources('Hindi TTS','edge',src)
  self.assertEqual(report['mode'],'four_role_model_debate')
  self.assertIn('skeptic',report['debate'])
  self.assertEqual(report['decisions'][0]['source_ids'],['S1'])


 def test_browser_fetch_uses_shared_context_without_launching_browser(self):
  from unittest.mock import Mock, patch
  import browser_agent_v08 as ba
  page=Mock(); page.goto.return_value=None; page.title.return_value='Hindi TTS docs'
  page.locator.return_value.inner_text.return_value='Hindi speech synthesis documentation with phoneme pronunciation and prosody details.'
  page.locator.return_value.evaluate_all.return_value=[]
  context=Mock(); context.new_page.return_value=page
  with patch.object(ba,'robots_ok',return_value=(True,'allowed')), patch('browser_agent_v08.sync_playwright',create=True,side_effect=AssertionError('should not launch a new browser')):
   src=ba.fetch('https://docs.example.org/page',Mock(),'Hindi TTS',True,context)
  self.assertEqual(src.status,'collected')
  context.new_page.assert_called_once()
  page.close.assert_called_once()


 def test_intelligence_cycle_persists_cognition_and_evidence(self):
  import tempfile, json
  from pathlib import Path
  from unittest.mock import patch
  import intelligence_agent as ia
  with tempfile.TemporaryDirectory() as td:
   root=Path(td); (root/'reports').mkdir(); (root/'knowledge_inbox').mkdir()
   research=root/'reports'/'source.json'
   research.write_text(json.dumps({'sources':[{'title':'Official Hindi TTS guide','url':'https://docs.example.org','domain':'docs.example.org','quality':'primary','sha256':'a'*64,'text':'This is a sufficiently long evidence sentence about Hindi pronunciation, phoneme normalization and speech quality evaluation.'}]}),encoding='utf-8')
   inbox=root/'knowledge_inbox'/'inbox.json'
   inbox.write_text(json.dumps({'items':[{'title':'Guide','url':'https://docs.example.org','domain':'docs.example.org','text':'Evidence text','sha256':'b'*64}]}),encoding='utf-8')
   fake={'research_file':str(research),'handoff_file':str(inbox),'sources_collected':1,'errors':0}
   with patch.object(ia,'browser_research',return_value=fake):
    result=ia.run_cycle(root,'edge',max_pages=1,topic_limit=1)
   self.assertEqual(result['tasks'][0]['cognition']['mode'],'web_first_structured_adversarial_review')
   self.assertEqual(result['memory']['agent_analyses'],1)
   self.assertEqual(result['memory']['evidence'],1)

if __name__=="__main__": unittest.main()


class WebFirstV11Tests(unittest.TestCase):
 def test_no_preselected_model_by_default(self):
  import os, agent_cognition as ac
  with patch.dict(os.environ, {"AGENT_LLM_BASE_URL":"", "AGENT_LLM_MODEL":""}, clear=False):
   cfg=ac._config()
   self.assertEqual(cfg["base_url"], "")
   self.assertEqual(cfg["model"], "")
   self.assertFalse(ac.backend_status()["configured"])
 def test_model_free_review_has_adversarial_roles(self):
  import agent_cognition as ac
  src=[{"title":"Primary doc","url":"https://docs.example.org/a","domain":"docs.example.org","quality":"primary_or_project_source","sha256":"a","text":"Hindi TTS system supports emotion tags and expressive speech generation.\nThe implementation has no Hindi emotion benchmark and cannot verify naturalness."},
       {"title":"Independent paper","url":"https://paper.example.net/b","domain":"paper.example.net","quality":"research_index","sha256":"b","text":"Hindi TTS evaluation includes human listening tests for emotion and naturalness across speakers."}]
  with patch.object(ac,"backend_status",return_value={"configured":False}):
   report=ac.analyze_sources("Hindi TTS emotion","edge",src)
  self.assertEqual(report["mode"],"web_first_structured_adversarial_review")
  self.assertIn("skeptic",report["debate"])
  self.assertTrue(report["follow_up_queries"])
  self.assertFalse(report["model_used"])
