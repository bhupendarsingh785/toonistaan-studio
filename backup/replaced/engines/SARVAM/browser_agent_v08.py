"""v0.8 independent deep research browser agent.
Federated discovery + dynamic browser extraction + one-hop relevant crawling.
Evidence is never treated as truth or auto-promoted into model training.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from urllib.parse import urlparse, urljoin, urldefrag, quote_plus, parse_qs, unquote
from urllib.robotparser import RobotFileParser
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re, time, os, requests, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from open_source_learning import start_svara_learning
from agent_cognition import plan_research_queries

UA='HindiVoiceIntelligenceResearchAgent/0.8 (+local user research; respects robots.txt)'
MAX_BYTES=5_000_000; MAX_TEXT=180_000
ENGINE_QUERY_AREAS={
 'sarvam':['Sarvam AI Hindi TTS official API documentation models capabilities','Sarvam Hindi pronunciation text normalization and prosody controls','Sarvam API latency reliability errors rate limits and fallback','Hindi neural speech naturalness expressive emotion speaker consistency benchmarks','Sarvam Hindi TTS independent evaluations licensing data privacy'],
 'edge':['official Edge TTS supported Hindi voices SSML limitations','Hindi phonology G2P pronunciation lexicon schwa deletion','Hindi expressive prosody emotion acting evaluation','Hindi ASR speaker diarization voice quality metrics','cinematic ambience foley story audio production'],
 'piper':['Piper Hindi ONNX voice models model cards licenses','Hindi G2P pronunciation lexicon schwa deletion corpus','Piper voice training phoneme data preparation validation','Hindi expressive TTS neural models CPU inference comparison','Hindi ASR diarization audio quality naturalness evaluation'],
 'elevenlabs':['ElevenLabs Hindi TTS official model audio tags text to dialogue API','Hindi emotion prosody expressive acting evaluation','Hindi pronunciation dictionary custom pronunciation API','Hindi character consistency long form speech evaluation','cinematic story sound design ambience foley audio mixing'],
 'espeak':['eSpeak NG Hindi phoneme dictionary phoneme rules','Hindi schwa deletion pronunciation lexicon G2P','Hindi intonation prosody formant synthesis limitations','Hindi speech intelligibility ASR evaluation speaker diarization','cinematic soundscape foley acoustic room simulation']}
QUALITY_DOMAINS=('huggingface.co','github.com','arxiv.org','aclanthology.org','ai4bharat.org','learn.microsoft.com','elevenlabs.io','github.io','piper.tts','crossref.org','wikipedia.org')
class Extractor(HTMLParser):
 def __init__(self): super().__init__(); self.parts=[]; self.links=[]; self.title=[]; self.skip=0; self.in_title=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag in {'script','style','noscript','svg','nav','footer','header','form','aside'}: self.skip+=1
  if tag=='title': self.in_title=True
  if tag=='a' and a.get('href'): self.links.append((a['href'],a.get('aria-label','')))
 def handle_endtag(self,tag):
  if tag in {'script','style','noscript','svg','nav','footer','header','form','aside'} and self.skip: self.skip-=1
  if tag=='title': self.in_title=False
 def handle_data(self,data):
  s=data.strip()
  if not s:return
  if self.in_title:self.title.append(s)
  if not self.skip:self.parts.append(s)
 def text(self):return re.sub(r'\s+',' ',' '.join(self.parts)).strip()
@dataclass
class Source:
 url:str; domain:str; title:str; text:str; sha256:str; relevance:float; fetched_at:str; status:str; provider:str='web'; quality:str='unknown'; links:list|None=None; reason:str=''

def _identity(root=None):
    """Engine ka apna naam padho (agent_identity.json) — report mein yahi naam jaata hai."""
    import json as _json
    from pathlib import Path as _P
    for base in (_P(root) if root else None, _P(__file__).resolve().parent):
        if base is None:
            continue
        f = base / "agent_identity.json"
        if f.is_file():
            try:
                return _json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {"agent_name": "", "engine": _P(root).name if root else "", "role": ""}

def utc():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def terms(q):return [x.casefold() for x in re.findall(r'[\w\u0900-\u097f]+',q) if len(x)>2]
def score(q,title,body):
 ts=set(terms(q)); content=(title+' '+body[:50000]).casefold()
 return round(sum(1 for t in ts if t in content)/max(1,len(ts)),4)
def quality(url):
 h=(urlparse(url).hostname or '').lower()
 if h.endswith(('huggingface.co','github.com','arxiv.org','aclanthology.org','learn.microsoft.com','elevenlabs.io')):return 'primary_or_project_source'
 if h.endswith(('crossref.org','semanticscholar.org')):return 'research_index'
 return 'secondary_or_general'
def robots_ok(url,s):
 p=urlparse(url); base=f'{p.scheme}://{p.netloc}/robots.txt'
 try:
  r=s.get(base,timeout=(4,8),headers={'User-Agent':UA})
  if r.status_code in (404,410):return True,'robots.txt absent'
  if r.status_code>=400:return False,f'robots HTTP {r.status_code}'
  rp=RobotFileParser();rp.parse(r.text.splitlines());ok=rp.can_fetch(UA,url)
  return ok,'allowed' if ok else 'disallowed by robots.txt'
 except Exception as e:return False,f'robots check failed: {type(e).__name__}'
def _add(out,seen,url,title,provider):
 if not url:return
 if url.startswith('//'):url='https:'+url
 p=urlparse(url)
 if p.scheme not in ('http','https') or not p.hostname:return
 if p.hostname in ('localhost','127.0.0.1','0.0.0.0'):return
 url=urldefrag(url)[0]
 if url not in seen:seen.add(url);out.append((url,title or '',provider))
def discover(q,s,limit=30):
 out=[];seen=set();errors=[]
 # Optional self-hosted SearXNG: keyless, multi-engine discovery. No hosted vendor/model dependency.
 searx=os.getenv('SEARXNG_URL','').strip().rstrip('/')
 if searx:
  try:
   r=s.get(searx+'/search',params={'q':q,'format':'json'},headers={'User-Agent':UA},timeout=(5,12));r.raise_for_status()
   for x in r.json().get('results',[])[:limit]:_add(out,seen,x.get('url'),x.get('title',''),'searxng')
  except Exception as e:errors.append({'provider':'searxng','error':f'{type(e).__name__}: {e}'})
 # DuckDuckGo HTML
 try:
  r=s.get('https://html.duckduckgo.com/html/',params={'q':q},headers={'User-Agent':UA},timeout=(4,9));r.raise_for_status()
  class L(HTMLParser):
   def __init__(self):super().__init__();self.rows=[];self.on=False;self.cur=None
   def handle_starttag(self,t,a):
    d=dict(a)
    if t=='a' and ('result__a' in d.get('class','') or 'result-link' in d.get('class','')):self.on=True;self.cur=[d.get('href',''),[]]
   def handle_data(self,d):
    if self.on and self.cur:self.cur[1].append(d)
   def handle_endtag(self,t):
    if t=='a' and self.on:
     if self.cur:self.rows.append((self.cur[0],''.join(self.cur[1])))
     self.cur=None;self.on=False
  p=L();p.feed(r.text)
  for u,t in p.rows:
   pp=urlparse(u)
   if pp.hostname and 'duckduckgo.com' in pp.hostname:
    u=unquote(parse_qs(pp.query).get('uddg',[''])[0]) or u
   _add(out,seen,u,t,'duckduckgo')
 except Exception as e:errors.append({'provider':'duckduckgo','error':f'{type(e).__name__}: {e}'})
 # Optional DDGS package fallback when DuckDuckGo HTML is blocked or returns no links.
 if not any(x[2]=='duckduckgo' for x in out):
  try:
   try: from ddgs import DDGS
   except ImportError: from duckduckgo_search import DDGS
   with DDGS() as ddgs:
    for x in ddgs.text(q,max_results=min(15,limit)):
     _add(out,seen,x.get('href') or x.get('url'),x.get('title',''),'ddgs')
  except Exception as e:errors.append({'provider':'ddgs_optional','error':f'{type(e).__name__}: {e}'})
 # Hugging Face model API
 try:
  r=s.get('https://huggingface.co/api/models',params={'search':q,'limit':min(15,limit),'sort':'downloads','direction':-1},headers={'User-Agent':UA},timeout=(4,9));r.raise_for_status()
  for x in r.json():
   mid=x.get('modelId') or x.get('id')
   if mid:_add(out,seen,'https://huggingface.co/'+mid,mid+' | model card','huggingface')
 except Exception as e:errors.append({'provider':'huggingface','error':f'{type(e).__name__}: {e}'})
 # GitHub repositories
 try:
  r=s.get('https://api.github.com/search/repositories',params={'q':q,'sort':'updated','per_page':min(15,limit)},headers={'User-Agent':UA,'Accept':'application/vnd.github+json'},timeout=(4,9));r.raise_for_status()
  for x in r.json().get('items',[]):_add(out,seen,x.get('html_url'),x.get('full_name','')+' | '+(x.get('description') or ''),'github')
 except Exception as e:errors.append({'provider':'github','error':f'{type(e).__name__}: {e}'})
 # Crossref paper index
 try:
  r=s.get('https://api.crossref.org/works',params={'query.bibliographic':q,'rows':min(10,limit),'select':'title,URL,author,published,DOI'},headers={'User-Agent':UA},timeout=(4,9));r.raise_for_status()
  for x in r.json().get('message',{}).get('items',[]):
   u=x.get('URL') or (('https://doi.org/'+x['DOI']) if x.get('DOI') else None); title=(x.get('title') or [''])[0]
   _add(out,seen,u,title+' | research paper','crossref')
 except Exception as e:errors.append({'provider':'crossref','error':f'{type(e).__name__}: {e}'})
 # arXiv Atom search
 try:
  r=s.get('https://export.arxiv.org/api/query',params={'search_query':'all:'+q,'start':0,'max_results':min(10,limit)},headers={'User-Agent':UA},timeout=(4,9));r.raise_for_status()
  root=ET.fromstring(r.text)
  ns={'a':'http://www.w3.org/2005/Atom'}
  for x in root.findall('a:entry',ns):
   u=x.findtext('a:id',default='',namespaces=ns);title=x.findtext('a:title',default='',namespaces=ns)
   _add(out,seen,u,title+' | arXiv paper','arxiv')
 except Exception as e:errors.append({'provider':'arxiv','error':f'{type(e).__name__}: {e}'})
 return out,errors
def fetch(url,s,q,use_browser=True,browser_context=None):
 p=urlparse(url);ok,why=robots_ok(url,s)
 if not ok:return Source(url,p.hostname or '', '', '', '',0,utc(),'skipped',reason=why)
 title='';body='';links=[];provider='http'
 if use_browser:
  try:
   if browser_context is not None:
    page=browser_context.new_page()
    try:
     resp=page.goto(url,wait_until='domcontentloaded',timeout=22000)
     if resp and resp.status>=400:raise RuntimeError(f'HTTP {resp.status}')
     title=page.title();body=page.locator('body').inner_text(timeout=10000)
     links=page.locator('a[href]').evaluate_all('(els)=>els.slice(0,250).map(a=>({href:a.href,text:(a.innerText||a.getAttribute("aria-label")||"").trim()}))')
     links=[(x.get('href',''),x.get('text','')) for x in links]
     provider='playwright_reused_context'
    finally: page.close()
   else:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
     browser=pw.chromium.launch(headless=True)
     try:
      context=browser.new_context(user_agent=UA,locale='hi-IN');page=context.new_page()
      resp=page.goto(url,wait_until='domcontentloaded',timeout=22000)
      if resp and resp.status>=400:raise RuntimeError(f'HTTP {resp.status}')
      title=page.title();body=page.locator('body').inner_text(timeout=10000)
      links=page.locator('a[href]').evaluate_all('(els)=>els.slice(0,250).map(a=>({href:a.href,text:(a.innerText||a.getAttribute("aria-label")||"").trim()}))')
      links=[(x.get('href',''),x.get('text','')) for x in links]
     finally:browser.close()
     provider='playwright_chromium'
  except ImportError:pass
  except Exception as e:provider='http_fallback_after_'+type(e).__name__
 if not body:
  r=s.get(url,headers={'User-Agent':UA},timeout=(5,12),stream=True);r.raise_for_status();ct=r.headers.get('content-type','').lower()
  if 'pdf' in ct or url.lower().endswith('.pdf'):
   raw=b''
   for ch in r.iter_content(65536):
    raw+=ch
    if len(raw)>MAX_BYTES:raise ValueError('PDF exceeds 5 MB safety cap')
   try:
    import fitz
    doc=fitz.open(stream=raw,filetype='pdf');body=' '.join(pg.get_text() for pg in doc);title=doc.metadata.get('title') or ''
   except ImportError:body='';provider='pdf_skipped_no_pymupdf'
  else:
   ct=r.headers.get('content-type','').lower()
   if not any(x in ct for x in ('text/html','text/plain','application/json','application/xml','text/xml')):return Source(url,p.hostname or '',title,'','',0,utc(),'skipped',reason='unsupported content type '+ct)
   chunks=[];n=0
   for ch in r.iter_content(65536):
    n+=len(ch)
    if n>MAX_BYTES:raise ValueError('page exceeds 5 MB safety cap')
    chunks.append(ch)
   raw=b''.join(chunks);txt=raw.decode(r.encoding or 'utf-8',errors='replace')
   if 'html' in ct:
    ex=Extractor();ex.feed(txt);title=title or ' '.join(ex.title);body=ex.text();links=[(urljoin(url,h),t) for h,t in ex.links]
   else:body=re.sub(r'\s+',' ',txt)
 body=re.sub(r'\s+',' ',body).strip()[:MAX_TEXT]
 digest=hashlib.sha256(body.encode()).hexdigest()
 return Source(url,p.hostname or '',title,body,digest,score(q,title,body),utc(),'collected',provider,quality(url),[{'url':u,'text':t[:180]} for u,t in links[:150]])
def research(query,root,max_pages=20,min_relevance=0.08,use_browser=True,engine=None):
 # Fire-and-forget: open-source learning cannot hold up this browser research run.
 start_svara_learning(root, engine or Path(root).name)
 if not isinstance(query,str) or not query.strip():raise ValueError('query cannot be empty')
 max_pages=max(1,min(int(max_pages),50));root=Path(root);rd=root/'research';inbox=root/'knowledge_inbox';rd.mkdir(parents=True,exist_ok=True);inbox.mkdir(parents=True,exist_ok=True)
 slug=(engine or root.name).lower(); areas=ENGINE_QUERY_AREAS.get(slug,ENGINE_QUERY_AREAS.get(root.name.lower(),[]))
 plan=plan_research_queries(query.strip(),slug,areas[:8],max_queries=8)
 queries=[query.strip()]+plan.get('queries',[])
 queries.extend([query.strip()+' official documentation specification',query.strip()+' Hindi research paper dataset',query.strip()+' model card benchmark evaluation',query.strip()+' counter evidence failure cases limitations',query.strip()+' GitHub issues bugs regression',query.strip()+' independent comparison CPU latency license'])
 queries.extend(areas[:6])
 # Stable de-duplication keeps the search breadth high without wasting provider calls.
 queries=list(dict.fromkeys(q.strip() for q in queries if q and q.strip()))[:max(4,min(10,max_pages*2))]
 candidates=[];search_errors=[]
 # Parallelize independent query discovery; each worker owns its own HTTP session.
 # Search workers never share the TTS rendering process or Playwright page objects.
 def _discover_one(q):
  session=requests.Session();session.headers.update({'User-Agent':UA})
  try:return q,*discover(q,session,limit=max(12,max_pages))
  finally:session.close()
 workers=max(2,min(6,int(os.getenv('RESEARCH_SEARCH_WORKERS','4'))))
 with ThreadPoolExecutor(max_workers=workers,thread_name_prefix='web-search') as pool:
  futures=[pool.submit(_discover_one,q) for q in queries]
  for future in as_completed(futures):
   try:
    q,rows,errs=future.result();candidates.extend(rows);search_errors.extend(errs)
   except Exception as exc:search_errors.append({'provider':'query_worker','error':f'{type(exc).__name__}: {exc}'})
 # Rank and diversify providers/domain; exact user query is strongest.
 s=requests.Session();s.headers.update({'User-Agent':UA})
 unique={}
 for u,t,p in candidates:
  if u not in unique:unique[u]=(u,t,p)
 candidates=list(unique.values())
 candidates.sort(key=lambda x:(quality(x[0])=='primary_or_project_source',score(query,x[1],'')),reverse=True)
 selected=[];domains={}
 for x in candidates:
  host=urlparse(x[0]).hostname or ''
  if domains.get(host,0)>=3:continue
  selected.append(x);domains[host]=domains.get(host,0)+1
  if len(selected)>=max_pages:break
 collected=[];errors=[];seen_hash=set();link_candidates=[]
 # Launch Chromium once per research batch, not once per source. HTTP remains the fallback.
 pw_manager=None; browser=None; browser_context=None
 if use_browser:
  try:
   from playwright.sync_api import sync_playwright
   pw_manager=sync_playwright();pw=pw_manager.start();browser=pw.chromium.launch(headless=True)
   browser_context=browser.new_context(user_agent=UA,locale='hi-IN',accept_downloads=False)
  except Exception as e:
   browser_context=None
   search_errors.append({'provider':'playwright','error':f'{type(e).__name__}: {e}','fallback':'bounded HTTP'})
 browser_enabled=bool(use_browser and browser_context is not None)
 for u,title,prov in selected:
  try:
   src=fetch(u,s,query,browser_enabled,browser_context)
   src.provider=prov+'+'+src.provider
   if src.status=='collected' and src.text and src.sha256 not in seen_hash:
    seen_hash.add(src.sha256)
    if src.relevance>=min_relevance or src.quality=='primary_or_project_source':collected.append(src)
    # one-hop links only from primary/project sources; relevant link labels are selected later
    if src.quality=='primary_or_project_source':
     for link in (src.links or []):
      label=(link.get('text') or '').casefold(); href=link.get('url','')
      if href and any(t in label for t in ['model','paper','documentation','dataset','benchmark','voice','audio','phoneme','license','readme']):link_candidates.append((href,link.get('text',''),'linked_from_primary'))
   else:errors.append({'url':u,'status':src.status,'reason':src.reason})
  except Exception as e:errors.append({'url':u,'stage':'fetch','error':f'{type(e).__name__}: {e}'})
 # bounded one-hop expansion using unused slots
 seen_urls={x.url for x in collected};extra_count=0
 for u,t,pv in link_candidates:
  if extra_count>=max(0,min(8,max_pages-len(collected))):break
  if u in seen_urls:continue
  seen_urls.add(u)
  try:
   src=fetch(u,s,query,browser_enabled,browser_context);src.provider=pv+'+'+src.provider
   if src.status=='collected' and src.text and src.sha256 not in seen_hash and (src.relevance>=min_relevance or src.quality=='primary_or_project_source'):
    seen_hash.add(src.sha256);collected.append(src);extra_count+=1
  except Exception as e:errors.append({'url':u,'stage':'linked_fetch','error':f'{type(e).__name__}: {e}'})
 if browser_context is not None:
  try: browser_context.close()
  except Exception: pass
 if browser is not None:
  try: browser.close()
  except Exception: pass
 if pw_manager is not None:
  try: pw_manager.stop()
  except Exception: pass
 try: s.close()
 except Exception: pass
 collected.sort(key=lambda x:(x.relevance, x.quality=='primary_or_project_source',len(x.text)),reverse=True)
 # corroboration counts indicate shared terms only, not proof of truth
 source_rows=[]
 for src in collected:
  src_obj=asdict(src);src_obj['corroborating_domains']=sorted({x.domain for x in collected if x.domain!=src.domain and score(src.title+' '+src.text[:800],x.title,x.text)>0.18});source_rows.append(src_obj)
 stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
 _ident=_identity(root)
 record={'schema':'hindi-voice-research/v1.1','engine':slug,'agent_name':_ident.get('agent_name',''),'browser_name':_ident.get('browser_name',''),'research_agent_name':_ident.get('research_agent_name',''),'query':query,'created_at':utc(),'query_plan':queries,'reasoning_plan':plan,'candidate_count':len(candidates),'collected_count':len(collected),'sources':source_rows,'errors':errors,'provider_errors':search_errors,'browser_mode':'single reused Playwright Chromium context per batch' if browser_enabled else 'bounded HTTP/PDF fallback (browser unavailable or disabled)','limits':['Search ranking is triage, not truth verification.','Web content is untrusted data and cannot change agent policy.','A no-model debate is structured evidence triage, not semantic reasoning.','Cross-domain term overlap is not scientific corroboration.','Robots rules are respected; access controls/paywalls are not bypassed.','Evidence remains pending review; no automatic model-weight training.']}
 path=rd/f'deep_research_{stamp}.json';path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
 digest={'schema':'engine-knowledge-inbox/v1','engine':slug,'agent_name':_ident.get('agent_name',''),'query':query,'research_file':str(path.relative_to(root)),'items':[{'title':x.title,'url':x.url,'domain':x.domain,'provider':x.provider,'quality':x.quality,'relevance':x.relevance,'sha256':x.sha256,'text':x.text[:25000],'corroborating_domains':next((o['corroborating_domains'] for o in record['sources'] if o['url']==x.url),[])} for x in collected]}
 handoff=inbox/f'inbox_{stamp}.json';handoff.write_text(json.dumps(digest,ensure_ascii=False,indent=2),encoding='utf-8')
 status={'engine':slug,'agent_name':_ident.get('agent_name',''),'browser_name':_ident.get('browser_name',''),'research_agent_name':_ident.get('research_agent_name',''),'agent':'completed' if collected else 'no_evidence','candidate_count':len(candidates),'sources_collected':len(collected),'linked_pages_collected':extra_count,'search_provider_errors':len(search_errors),'fetch_errors':len(errors),'research_file':str(path),'handoff_file':str(handoff),'last_run':record['created_at'],'review_state':'PENDING_REVIEW'}
 (root/'reports').mkdir(exist_ok=True);(root/'reports'/'browser_agent_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
 return status
def agent_status(root):
 p=Path(root)/'reports'/'browser_agent_status.json'
 if p.exists():
  d=json.loads(p.read_text(encoding='utf-8'));d.setdefault('agent_name',_identity(root).get('agent_name',''));return d
 return {'agent':'not_run_yet','engine':Path(root).name,'agent_name':_identity(root).get('agent_name','')}
