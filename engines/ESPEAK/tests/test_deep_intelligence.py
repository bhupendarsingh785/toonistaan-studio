import unittest, tempfile
from pathlib import Path
from hindi_understanding import analyze_story
from intelligence_agent import IntelligenceMemory
from browser_agent import _search
class DeepIntelligenceTests(unittest.TestCase):
 def test_character_and_emotion(self):
  x=analyze_story("आरव [भाव:खुश]: माँ, देखो!\nमाँ [भाव:गंभीर]: घर चलो।")
  self.assertEqual(len(x["characters"]),2)
  self.assertEqual(x["segments"][0]["emotion"]["primary"],"खुश")
 def test_ambiguous_relationship_not_guessed(self):
  x=analyze_story("आरव: मेरी माँ घर पर हैं।")
  self.assertEqual(x["relationship_mentions"][0]["target"],"UNRESOLVED")
 def test_explicit_age_tag_only(self):
  x=analyze_story("आरव [उम्र:बच्चा] [भाव:खुश]: मेरी माँ घर पर हैं।")
  self.assertEqual(x["characters"][0]["age_group"],"बच्चा")
 def test_incidental_age_word_not_assigned(self):
  x=analyze_story("आरव: वह बच्चा स्कूल गया।")
  self.assertEqual(x["characters"][0]["age_group"],"unknown")
 def test_search_provider_failures_are_isolated(self):
  class Offline:
   def get(self,*a,**k): raise RuntimeError("offline")
  self.assertEqual(_search("Hindi TTS",Offline(),5),[])
 def test_federated_search_collects_provider_results(self):
  class Response:
   def __init__(self,url): self.url=url; self.text='<a class="result__a" href="https://example.org/doc">Example documentation</a>'
   def raise_for_status(self): pass
   def json(self):
    if 'huggingface.co' in self.url: return [{'modelId':'org/hindi-tts'}]
    if 'api.github.com' in self.url: return {'items':[{'html_url':'https://github.com/org/hindi-tts','full_name':'org/hindi-tts','description':'Hindi TTS'}]}
    if 'wikipedia.org' in self.url: return ['q',['Hindi speech'],['desc'],['https://en.wikipedia.org/wiki/Speech']]
    return []
  class Online:
   def get(self,url,*a,**k): return Response(url)
  found=_search('Hindi TTS',Online(),12)
  self.assertGreaterEqual(len(found),4)
  self.assertTrue(any('huggingface.co' in u for u,_ in found))
  self.assertTrue(any('github.com' in u for u,_ in found))
 def test_search_provider_failures_are_isolated(self):
  class Offline:
   def get(self,*a,**k): raise RuntimeError('offline')
  self.assertEqual(_search('Hindi TTS',Offline(),5),[])
 def test_memory_is_persistent(self):
  with tempfile.TemporaryDirectory() as d:
   m=IntelligenceMemory(d); m.feedback("pronunciation","retroflex ण issue")
   self.assertEqual(m.status()["feedback"],1)
if __name__=="__main__": unittest.main()
