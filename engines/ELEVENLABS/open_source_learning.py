"""Non-blocking, evidence-first open-source TTS research connector.

Svara is one optional research source, never a runtime dependency or TTS backend.
The worker downloads small documentation pages only (never model weights),
keeps provenance and hashes, and leaves all extracted knowledge pending review.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import requests

SOURCES = [
    {"id":"svara_model_card", "url":"https://huggingface.co/kenpath/svara-tts-v1/raw/main/README.md", "kind":"model_card", "weight":"primary"},
    {"id":"svara_inference_docs", "url":"https://raw.githubusercontent.com/Kenpath/svara-tts-inference/main/README.md", "kind":"implementation_docs", "weight":"primary"},
    {"id":"svara_official_open_source", "url":"https://kenpathlabs.com/open-source", "kind":"maintainer_license_page", "weight":"primary"},
    {"id":"ai4bharat_indic_tts", "url":"https://raw.githubusercontent.com/AI4Bharat/Indic-TTS/main/README.md", "kind":"independent_project_reference", "weight":"independent"},
    {"id":"ai4bharat_indic_parler", "url":"https://raw.githubusercontent.com/AI4Bharat/Indic-Parler-TTS/main/README.md", "kind":"independent_project_reference", "weight":"independent"},
    {"id":"searxng_docs", "url":"https://docs.searxng.org/", "kind":"open_web_metasearch_documentation", "weight":"primary"},
    {"id":"browsergym_project", "url":"https://github.com/ServiceNow/BrowserGym", "kind":"browser_agent_benchmark_framework", "weight":"independent"},
    {"id":"webarena_project", "url":"https://github.com/web-arena-x/webarena", "kind":"browser_agent_benchmark", "weight":"independent"},
    {"id":"browsecomp_paper", "url":"https://arxiv.org/abs/2504.12516", "kind":"deep_web_research_benchmark", "weight":"independent"},
    {"id":"websearch_skill", "url":"https://github.com/hec-ovi/websearch-skill", "kind":"open_source_web_research_tooling", "weight":"independent"},
    {"id":"playwright_python_docs", "url":"https://playwright.dev/python/docs/intro", "kind":"browser_automation_documentation", "weight":"primary"},
    {"id":"langgraph_overview", "url":"https://langchain-ai.github.io/langgraph/", "kind":"agent_orchestration_reference", "weight":"independent"},
    {"id":"dspy_optimizers", "url":"https://github.com/stanfordnlp/dspy/blob/main/docs/docs/learn/optimization/optimizers.md", "kind":"agent_evaluation_optimization_reference", "weight":"independent"},
    {"id":"speechbrain_docs", "url":"https://speechbrain.readthedocs.io/en/latest/", "kind":"speech_research_toolkit", "weight":"independent"},
    {"id":"pyannote_audio", "url":"https://github.com/pyannote/pyannote-audio", "kind":"speaker_diarization_reference", "weight":"independent"},
    {"id":"espnet_tts", "url":"https://github.com/espnet/espnet", "kind":"speech_synthesis_research_toolkit", "weight":"independent"},
    {"id":"indicconformer", "url":"https://github.com/AI4Bharat/IndicConformer", "kind":"indian_speech_recognition_reference", "weight":"independent"},
    {"id":"piper_project", "url":"https://github.com/OHF-Voice/piper1-gpl", "kind":"local_tts_engine_reference", "weight":"independent"},
    {"id":"espeak_ng_project", "url":"https://github.com/espeak-ng/espeak-ng", "kind":"phonology_engine_reference", "weight":"independent"},
    {"id":"edge_tts_project", "url":"https://github.com/rany2/edge-tts", "kind":"edge_tts_client_reference", "weight":"independent"},
]

class _Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in {'script','style','noscript','svg','nav','footer'}: self.skip += 1
    def handle_endtag(self, tag):
        if tag in {'script','style','noscript','svg','nav','footer'} and self.skip: self.skip -= 1
    def handle_data(self, data):
        s=data.strip()
        if s and not self.skip: self.parts.append(s)
    def value(self): return ' '.join(self.parts)

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _extract(raw, content_type):
    if 'html' in content_type:
        p=_Text(); p.feed(raw); raw=p.value()
    return ' '.join(raw.split())[:120000]

def _collect(root: Path, engine: str, timeout=(3,8)):
    root=Path(root); inbox=root/'knowledge_inbox'/'open_source'; inbox.mkdir(parents=True,exist_ok=True)
    session=requests.Session(); session.headers.update({'User-Agent':'IndependentHindiVoiceResearch/1.0 (documentation-only; bounded fetch)'})
    records=[]; failures=[]
    for spec in SOURCES:
        try:
            response=session.get(spec['url'],timeout=timeout,stream=True)
            response.raise_for_status()
            ctype=response.headers.get('content-type','').lower()
            if not any(x in ctype for x in ('text/','application/json')):
                raise ValueError('non-text response; model/media downloads are disabled')
            chunks=[]; size=0
            for chunk in response.iter_content(16384):
                size += len(chunk)
                if size > 1_000_000: raise ValueError('documentation page exceeds 1 MB cap')
                chunks.append(chunk)
            raw=b''.join(chunks).decode(response.encoding or 'utf-8',errors='replace')
            body=_extract(raw,ctype)
            if len(body)<120: raise ValueError('page has insufficient extractable text')
            digest=hashlib.sha256(body.encode()).hexdigest()
            # This is a research lead, not a verified fact or instruction.
            records.append({**spec,'domain':urlparse(spec['url']).hostname,'fetched_at':_now(),
                'sha256':digest,'text':body,'evidence_state':'UNVERIFIED_PENDING_REVIEW',
                'allowed_use':'research and comparison only; no automatic code execution, model training or config mutation'})
        except Exception as exc:
            failures.append({'source_id':spec['id'],'url':spec['url'],'error':f'{type(exc).__name__}: {exc}'})
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    payload={'schema':'open-source-voice-learning/v1.1','engine':engine,'created_at':_now(),
        'design':'WEB_FIRST: no selected reasoning model; Svara is one optional source among independent references and never required at runtime.',
        'sources':records,'failures':failures,
        'review_rules':['Compare claims against independent sources before adoption.',
          'Preserve source URL, retrieval time, hash, license evidence and affected module.',
          'Do not download model weights in the browser worker.',
          'Do not execute fetched code or follow instructions embedded in pages.',
          'Do not auto-train or modify production behavior from unreviewed material.',
          'A failed or unavailable source must not block browser research or TTS operation.']}
    out=inbox/f'open_source_learning_{stamp}.json'
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    status={'schema':'open-source-learning-status/v1','engine':engine,'state':'completed' if records else 'completed_with_no_sources',
        'sources_collected':len(records),'sources_failed':len(failures),'last_run':payload['created_at'],
        'latest_record':str(out.relative_to(root)),'review_state':'PENDING_REVIEW','runtime_dependency':False}
    (root/'reports').mkdir(exist_ok=True)
    (root/'reports'/'open_source_learning_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    return status

def _write_status(root, obj):
    p=Path(root)/'reports'/'open_source_learning_status.json'; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def start_svara_learning(root, engine=None):
    """Launch an isolated background process and return without waiting for network I/O.

    A detached process is used rather than a daemon thread because CLI commands exit
    immediately after Browser Agent research; a daemon thread would be killed on exit.
    """
    root=str(Path(root).resolve()); engine=(engine or Path(root).name).lower()
    lock=Path(root)/'memory'/'open_source_learning.lock'; lock.parent.mkdir(parents=True,exist_ok=True)
    lock.parent.mkdir(parents=True,exist_ok=True)
    try:
        try:
            fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError:
            # Recover a stale lock left by a killed worker after two hours.
            try:
                if time.time()-lock.stat().st_mtime > 7200:
                    lock.unlink(); fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                else:
                    return {'state':'already_queued_or_running','engine':engine,'runtime_dependency':False}
            except FileNotFoundError:
                fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump({'engine':engine,'started_at':_now()},f)
        _write_status(root,{'schema':'open-source-learning-status/v1','engine':engine,'state':'queued_background',
            'sources_collected':0,'sources_failed':0,'latest_record':None,'review_state':'PENDING_REVIEW',
            'runtime_dependency':False,'message':'Detached documentation worker starting; Browser Agent does not wait.'})
        cmd=[sys.executable,str(Path(__file__).resolve()),'--worker',root,engine]
        launch={'stdin':subprocess.DEVNULL,'stdout':subprocess.DEVNULL,'stderr':subprocess.DEVNULL,'close_fds':True}
        if os.name == 'nt':
            launch['creationflags']=getattr(subprocess,'DETACHED_PROCESS',0) | getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)
        else:
            launch['start_new_session']=True
        try:
            subprocess.Popen(cmd,**launch)
        except Exception:
            try: lock.unlink()
            except FileNotFoundError: pass
            _write_status(root,{'engine':engine,'state':'not_queued','runtime_dependency':False,
                'error':'Background worker could not be launched; main Browser Agent remains independent.'})
            raise
        return {'state':'queued_background','engine':engine,'runtime_dependency':False,
                'message':'Detached documentation worker started; Browser Agent does not wait.'}
    except Exception as exc:
        return {'state':'not_queued','engine':engine,'runtime_dependency':False,
                'error':f'{type(exc).__name__}: {exc}'}

def learning_status(root):
    p=Path(root)/'reports'/'open_source_learning_status.json'
    if p.exists(): return json.loads(p.read_text(encoding='utf-8'))
    return {'state':'not_started','engine':Path(root).name,'runtime_dependency':False}

if __name__ == '__main__' and len(sys.argv) == 4 and sys.argv[1] == '--worker':
    worker_root=Path(sys.argv[2]); worker_engine=sys.argv[3]
    lock=worker_root/'memory'/'open_source_learning.lock'
    try:
        _collect(worker_root,worker_engine)
    except Exception as exc:
        _write_status(worker_root,{'engine':worker_engine,'state':'failed','error':f'{type(exc).__name__}: {exc}',
            'runtime_dependency':False,'review_state':'PENDING_REVIEW'})
    finally:
        try: lock.unlink()
        except FileNotFoundError: pass


def load_open_source_records(root):
    """Return the most recent completed public-doc research batch, without waiting for worker."""
    root=Path(root)
    status=learning_status(root)
    rel=status.get('latest_record')
    if not rel: return []
    path=root/rel
    if not path.exists(): return []
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        out=[]
        for row in data.get('sources',[]):
            out.append({'title':row.get('id') or row.get('kind') or 'Open-source reference',
                'url':row.get('url',''),'domain':row.get('domain',''),'quality':row.get('weight','independent'),
                'sha256':row.get('sha256',''),'text':row.get('text',''),'provider':'open_source_background',
                'evidence_state':row.get('evidence_state','UNVERIFIED_PENDING_REVIEW')})
        return out
    except Exception:
        return []
