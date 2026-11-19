"""Autonomous, engine-local web research agent.

Searches the public web, selects relevant sources, respects robots.txt, extracts
text, deduplicates evidence, writes a research corpus and hands a compact digest
into this engine's own knowledge inbox. No cross-engine imports or shared stores.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from urllib.parse import urlparse, urljoin, urldefrag, quote_plus, parse_qs, unquote
from urllib.robotparser import RobotFileParser
from html.parser import HTMLParser
from pathlib import Path
import hashlib, json, re, time
import requests

UA = "IndependentHindiVoiceResearchAgent/0.6 (+respect robots.txt; contact: local-user)"
MAX_BYTES = 3_000_000
MAX_TEXT = 120_000
SEARCH_DIAGNOSTICS = []

class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form"}
    def __init__(self):
        super().__init__(); self.parts=[]; self.links=[]; self.title=[]; self._skip=0; self._title=False
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag in self.SKIP: self._skip += 1
        if tag == "title": self._title=True
        if tag == "a" and attrs.get("href"):
            self.links.append((attrs["href"], ""))
    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip: self._skip -= 1
        if tag == "title": self._title=False
    def handle_data(self, data):
        s=data.strip()
        if not s: return
        if self._title: self.title.append(s)
        if not self._skip: self.parts.append(s)
    def text(self): return re.sub(r"\s+", " ", " ".join(self.parts)).strip()

@dataclass
class Source:
    url: str; domain: str; title: str; text: str; sha256: str
    relevance: float; fetched_at: str; status: str; reason: str = ""

def _robots(url, session):
    p=urlparse(url); robots=f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        r=session.get(robots,timeout=(5,10),headers={"User-Agent":UA})
        if r.status_code in (404, 410): return True, robots, "robots.txt absent (no published rules)"
        if r.status_code >= 400: return False, robots, f"robots.txt HTTP {r.status_code}"
        rp=RobotFileParser(); rp.parse(r.text.splitlines())
        ok=rp.can_fetch(UA,url)
        return ok,robots,"allowed" if ok else "disallowed"
    except requests.RequestException as e:
        return False,robots,f"robots check failed: {type(e).__name__}"

def _terms(q):
    return [x.lower() for x in re.findall(r"[\w\u0900-\u097f]+",q) if len(x)>2]

def _score(q, title, text):
    terms=_terms(q)
    if not terms: return 0.0
    t=(title+" "+text[:25000]).lower()
    hits=sum(1 for x in terms if x in t)
    return round(hits/len(set(terms)),3)

def _search(query, session, limit=12):
    """Federated public discovery: DDG HTML + Hugging Face + GitHub + Wikipedia.
    Provider failure is isolated; a blocked provider does not erase other results.
    """
    global SEARCH_DIAGNOSTICS
    out=[]; seen=set()
    def add(url,title):
        if not url: return
        p=urlparse(url)
        if p.scheme not in ("http","https") or not p.hostname: return
        if p.hostname in ("localhost", "127.0.0.1", "0.0.0.0"): return
        url=urldefrag(url)[0]
        if url not in seen:
            seen.add(url); out.append((url,(title or "").strip()))
    # DuckDuckGo web search
    try:
        url="https://html.duckduckgo.com/html/?q="+quote_plus(query)
        r=session.get(url,headers={"User-Agent":UA},timeout=(8,18)); r.raise_for_status()
        class Links(HTMLParser):
            def __init__(self): super().__init__(); self.items=[]; self.capture=False; self.cur=None
            def handle_starttag(self,tag,attrs):
                a=dict(attrs)
                if tag=='a' and ('result__a' in a.get('class','') or 'result-link' in a.get('class','')):
                    self.capture=True; self.cur=[a.get('href',''),[]]
            def handle_data(self,d):
                if self.capture and self.cur: self.cur[1].append(d)
            def handle_endtag(self,tag):
                if tag=='a' and self.capture:
                    if self.cur and self.cur[0]: self.items.append((self.cur[0],''.join(self.cur[1])))
                    self.cur=None; self.capture=False
        lp=Links(); lp.feed(r.text)
        for href,title in lp.items:
            if href.startswith('//'): href='https:'+href
            if href.startswith('/'): href='https://duckduckgo.com'+href
            pp=urlparse(href)
            if pp.hostname and 'duckduckgo.com' in pp.hostname:
                target=parse_qs(pp.query).get('uddg',[''])[0]
                if target: href=unquote(target)
            add(href,title)
    except Exception as exc:
        SEARCH_DIAGNOSTICS.append({'provider':'duckduckgo','error':f'{type(exc).__name__}: {exc}'})
    # Hugging Face public model catalogue (metadata only; no model download).
    try:
        r=session.get('https://huggingface.co/api/models',params={'search':query,'limit':min(10,limit),'sort':'downloads','direction':-1},headers={'User-Agent':UA},timeout=(6,15)); r.raise_for_status()
        for item in r.json():
            mid=item.get('modelId') or item.get('id')
            if mid: add('https://huggingface.co/'+mid,mid+' | Hugging Face model card')
    except Exception as exc:
        SEARCH_DIAGNOSTICS.append({'provider':'huggingface','error':f'{type(exc).__name__}: {exc}'})
    # GitHub repository search. Unauthenticated API has rate limits; failures are recorded by the caller's general search diagnostics.
    try:
        r=session.get('https://api.github.com/search/repositories',params={'q':query,'sort':'updated','per_page':min(10,limit)},headers={'User-Agent':UA,'Accept':'application/vnd.github+json'},timeout=(6,15)); r.raise_for_status()
        for item in r.json().get('items',[]): add(item.get('html_url'),item.get('full_name','')+' | '+(item.get('description') or 'GitHub repository'))
    except Exception as exc:
        SEARCH_DIAGNOSTICS.append({'provider':'github','error':f'{type(exc).__name__}: {exc}'})
    # Wikipedia's public search API adds general-language background references.
    try:
        r=session.get('https://en.wikipedia.org/w/api.php',params={'action':'opensearch','search':query,'limit':min(8,limit),'namespace':0,'format':'json'},headers={'User-Agent':UA},timeout=(6,15)); r.raise_for_status()
        data=r.json()
        for title,url in zip(data[1],data[3]): add(url,title+' | Wikipedia')
    except Exception as exc:
        SEARCH_DIAGNOSTICS.append({'provider':'wikipedia','error':f'{type(exc).__name__}: {exc}'})
    return out[:limit]

def _fetch(url, session, query):
    p=urlparse(url)
    if p.scheme not in ("http","https") or not p.hostname: raise ValueError("unsafe URL")
    allowed, robots, why=_robots(url,session)
    if not allowed: return Source(url,p.hostname,"","","",0,"", "skipped",f"{why}: {robots}")
    title=""; text=""; ctype=""
    # Use a headless Chromium browser for JavaScript-rendered pages when available.
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            try:
                page=browser.new_page(user_agent=UA)
                response=page.goto(url,wait_until="domcontentloaded",timeout=25000)
                if response is not None and response.status >= 400:
                    raise RuntimeError(f"browser HTTP {response.status}")
                title=page.title(); text=page.locator("body").inner_text(timeout=10000)
            finally:
                browser.close()
        ctype="text/html; rendered by Playwright"
    except ImportError:
        pass
    except Exception as browser_error:
        browser_note=f"Playwright fallback: {type(browser_error).__name__}: {browser_error}"
    # Bounded HTTP fallback keeps the collector useful on lightweight machines.
    if not text:
        r=session.get(url,headers={"User-Agent":UA},timeout=(8,25),stream=True)
        r.raise_for_status(); ctype=r.headers.get("content-type","").lower()
        if not any(x in ctype for x in ("text/html","text/plain","application/json","application/xml","text/xml")):
            return Source(url,p.hostname,"","","",0,"", "skipped",f"unsupported content type: {ctype}")
        chunks=[]; size=0
        for chunk in r.iter_content(65536):
            size+=len(chunk)
            if size>MAX_BYTES: raise ValueError("source exceeds 3 MB limit")
            chunks.append(chunk)
        raw=b''.join(chunks); enc=r.encoding or 'utf-8'; body=raw.decode(enc,errors='replace')
        if 'html' in ctype:
            ex=_TextExtractor(); ex.feed(body); text=ex.text(); title=' '.join(ex.title)
        else: text=re.sub(r"\s+"," ",body).strip()
    text=text[:MAX_TEXT]
    return Source(url,p.hostname,title,text,hashlib.sha256(text.encode()).hexdigest(),_score(query,title,text),
                  time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),"collected")

def research(query, root, max_pages=12, min_relevance=0.12, use_browser=True):
    if not query.strip(): raise ValueError("research query cannot be empty")
    root=Path(root); research_dir=root/"research"; inbox=root/"knowledge_inbox"
    research_dir.mkdir(parents=True,exist_ok=True); inbox.mkdir(parents=True,exist_ok=True)
    global SEARCH_DIAGNOSTICS
    SEARCH_DIAGNOSTICS=[]
    session=requests.Session(); queries=[query, query+" official documentation", query+" Hindi model card benchmark", query+" GitHub open source", query+" research paper dataset"]
    candidates=[]; errors=[]
    for q in queries:
        try: candidates.extend(_search(q,session,limit=max(5,max_pages)))
        except Exception as e: errors.append({"stage":"search","query":q,"error":str(e)})
    dedup={}
    for url,title in candidates: dedup.setdefault(url,(url,title))
    candidates=list(dedup.values())[:max_pages*2]
    sources=[]; hashes=set()
    for url,search_title in candidates:
        try:
            src=_fetch(url,session,query)
            if src.status!="collected": sources.append(asdict(src)); continue
            if src.sha256 in hashes: continue
            hashes.add(src.sha256)
            if not src.title: src.title=search_title
            if src.relevance>=min_relevance and len(src.text)>180:
                sources.append(asdict(src))
            if sum(1 for x in sources if x.get('status')=='collected')>=max_pages: break
        except Exception as e: errors.append({"stage":"fetch","url":url,"error":str(e)})
    collected=[s for s in sources if s.get('status')=='collected']
    collected.sort(key=lambda x:(x['relevance'],len(x['text'])),reverse=True)
    stamp=time.strftime('%Y%m%d-%H%M%S',time.gmtime())
    record={"engine":root.name,"query":query,"created_at":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            "search_queries":queries,"candidate_count":len(candidates),"collected_count":len(collected),
            "sources":sources,"errors":errors,"search_provider_errors":SEARCH_DIAGNOSTICS,
            "quality_note":"Relevance is lexical triage, not proof of truth. Cross-source corroboration and human review remain required."}
    path=research_dir/f"agent_research_{stamp}.json"; path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    # Engine-local handoff: a compact, traceable digest for downstream model/voice research modules.
    digest={"research_file":str(path.relative_to(root)),"engine":root.name,"query":query,
            "items":[{"title":s['title'],"url":s['url'],"domain":s['domain'],"relevance":s['relevance'],
                      "sha256":s['sha256'],"text":s['text'][:18000]} for s in collected]}
    inbox_path=inbox/f"inbox_{stamp}.json"; inbox_path.write_text(json.dumps(digest,ensure_ascii=False,indent=2),encoding='utf-8')
    status={"engine":root.name,"agent":"active","search_candidates":len(candidates),"sources_collected":len(collected),
            "errors":len(errors),"research_file":str(path),"handoff_file":str(inbox_path),
            "last_run":record['created_at'],"next_action":"Review source evidence; ingest only approved claims into engine-specific knowledge."}
    (root/"reports").mkdir(exist_ok=True); (root/"reports"/"browser_agent_status.json").write_text(json.dumps(status,indent=2),encoding='utf-8')
    return status

def agent_status(root):
    p=Path(root)/"reports"/"browser_agent_status.json"
    if not p.exists(): return {"agent":"not_run_yet","engine":Path(root).name}
    return json.loads(p.read_text(encoding='utf-8'))
