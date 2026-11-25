"""Engine-local autonomous research, evidence memory and continual-improvement loop.
This is adaptive software memory/planning, NOT neural-weight training.
"""
from __future__ import annotations
import json, sqlite3, time, hashlib, re
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from browser_agent_v08 import research as browser_research
from agent_cognition import analyze_sources, load_sources, backend_status
from open_source_learning import load_open_source_records
from youtube_research import research_youtube
from agent_evolution import AgentEvolution

ENGINE_TOPICS = {
 "sarvam": ["Sarvam AI Hindi TTS API documentation and model capabilities", "Sarvam Hindi pronunciation, text normalization and prosody controls", "Sarvam Hindi expressive speech and speaker consistency evaluation", "Sarvam API reliability latency limits and error handling", "Hindi speech quality benchmarks and independent user evaluations"],
 "edge": ["Hindi phonemization and pronunciation normalization", "Hindi prosody punctuation pauses and natural speaking rate", "speaker diarization and character attribution for Hindi dialogue", "Hindi emotion recognition and expressive speech evaluation", "Edge TTS supported Hindi voices and documented controls", "Hindi conversational turn-taking disfluency reduction natural speech","Hindi child elderly character voice representation ethical synthesis","Hindi room acoustics ambience Foley and spatial audio sound design","Hindi phoneme alignment ASR CER WER MOS evaluation"],
 "piper": ["Hindi Piper ONNX voice models and model cards", "Hindi grapheme to phoneme and pronunciation lexicons", "Piper voice training data preparation and evaluation", "Hindi long-form speech prosody and chunk boundary artifacts", "speaker diarization and Hindi speech quality metrics"],
 "elevenlabs": ["ElevenLabs Hindi multilingual voice capabilities and audio tags", "Hindi dialogue speaker assignment and text-to-dialogue controls", "Hindi pronunciation dictionaries and phonetic correction", "Hindi expressive speech evaluation and long-form consistency", "ElevenLabs API model limits and voice settings documentation"],
 "espeak": ["eSpeak NG Hindi phoneme rules and dictionary development", "Hindi schwa deletion and pronunciation lexicon", "Hindi prosody and intonation rules for formant synthesis", "eSpeak NG voice variants and documented parameters", "Hindi speech intelligibility and pronunciation evaluation"]
}

class IntelligenceMemory:
    def __init__(self, root):
        self.root=Path(root); self.db=self.root/"memory"/"intelligence_memory.sqlite3"
        self.db.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, started TEXT, topic TEXT, status TEXT, summary TEXT);
            CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY, sha TEXT UNIQUE, url TEXT, domain TEXT, title TEXT, text TEXT, relevance REAL, collected TEXT, review_status TEXT DEFAULT 'PENDING');
            CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY, created TEXT, category TEXT, issue TEXT, severity TEXT, status TEXT DEFAULT 'OPEN');
            CREATE TABLE IF NOT EXISTS learned_rules(id INTEGER PRIMARY KEY, created TEXT, rule TEXT, rationale TEXT, evidence_sha TEXT, status TEXT DEFAULT 'PROPOSED');
            CREATE TABLE IF NOT EXISTS metrics(key TEXT PRIMARY KEY, value TEXT, updated TEXT);
            CREATE TABLE IF NOT EXISTS agent_analyses(id INTEGER PRIMARY KEY, created TEXT, topic TEXT, mode TEXT, report_path TEXT, summary TEXT);
            CREATE TABLE IF NOT EXISTS improvement_proposals(id INTEGER PRIMARY KEY, created TEXT, topic TEXT, proposal TEXT, status TEXT DEFAULT 'PROPOSED', evidence TEXT);""")
    def connect(self):
        c=sqlite3.connect(self.db); c.row_factory=sqlite3.Row; return c
    @contextmanager
    def connection(self):
        c=self.connect()
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback(); raise
        finally:
            c.close()
    def add_run(self,topic,status,summary):
        with self.connection() as c: c.execute("INSERT INTO runs(started,topic,status,summary) VALUES(?,?,?,?)",(utc(),topic,status,summary))
    def ingest(self, inbox_file):
        data=json.loads(Path(inbox_file).read_text(encoding='utf-8')); count=0
        items=data.get('items') or data.get('sources') or []
        with self.connection() as c:
            for x in items:
                text=x.get('text',''); sha=x.get('sha256') or hashlib.sha256(text.encode()).hexdigest()
                cur=c.execute("INSERT OR IGNORE INTO evidence(sha,url,domain,title,text,relevance,collected) VALUES(?,?,?,?,?,?,?)",(sha,x.get('url'),x.get('domain'),x.get('title'),text,float(x.get('relevance',0)),utc()))
                count += max(0,cur.rowcount)
        return count
    def feedback(self,category,issue,severity='medium'):
        with self.connection() as c: c.execute("INSERT INTO feedback(created,category,issue,severity) VALUES(?,?,?,?)",(utc(),category,issue,severity))
        AgentEvolution(self.root).add_feedback(category,issue,severity)
    def status(self):
        with self.connection() as c:
            out={t:c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ['runs','evidence','feedback','learned_rules','agent_analyses','improvement_proposals']}
            out['pending_evidence']=c.execute("SELECT COUNT(*) FROM evidence WHERE review_status='PENDING'").fetchone()[0]
            out['open_feedback']=c.execute("SELECT COUNT(*) FROM feedback WHERE status='OPEN'").fetchone()[0]
            return out
    def plan(self, engine, limit=3):
        topics=list(ENGINE_TOPICS.get(engine,ENGINE_TOPICS['edge']))
        with self.connection() as c:
            recent=[r['topic'] for r in c.execute('SELECT topic FROM runs ORDER BY id DESC LIMIT 12')]
            open_feedback=[dict(r) for r in c.execute("SELECT category,issue FROM feedback WHERE status='OPEN' ORDER BY id DESC LIMIT 8")]
        # Adaptive planning uses private experience, novelty, overdue topics and feedback.
        ranked=AgentEvolution(self.root).rank_topics(topics,open_feedback,limit)
        self.last_plan=ranked
        return [row['topic'] for row in ranked]

def utc(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

def run_cycle(root, engine, max_pages=8, topic_limit=2, youtube=False):
    root=Path(root); mem=IntelligenceMemory(root); evolution=AgentEvolution(root)
    tasks=mem.plan(engine,topic_limit); plan_details=getattr(mem,'last_plan',[]); results=[]
    for topic in tasks:
        try:
            report=browser_research(topic,root,max_pages=max_pages)
            inbox=report.get('handoff_file')
            added=mem.ingest(inbox) if inbox and Path(inbox).exists() else 0
            youtube_result=None
            if youtube:
                try:
                    youtube_result=research_youtube(topic,root,limit=3)
                except Exception as exc:
                    youtube_result={"error":f"{type(exc).__name__}: {exc}","videos_found":0}
            cognitive=None
            if report.get('research_file') and Path(report['research_file']).exists():
                raw_sources=load_sources(report['research_file'])
                open_sources=load_open_source_records(root)
                historical=evolution.retrieve_evidence(topic,limit=4)
                seen={x.get('sha256') for x in raw_sources}
                raw_sources.extend(x for x in open_sources+historical if x.get('sha256') not in seen)
                prior_lessons=evolution.retrieve_lessons(topic,limit=5)
                # Historical evidence and lessons are explicitly marked unverified hypotheses.
                cognitive=analyze_sources(topic,engine,raw_sources,root/'reports'/'cognition',prior_lessons=prior_lessons)
                with mem.connection() as c:
                    c.execute("INSERT INTO agent_analyses(created,topic,mode,report_path,summary) VALUES(?,?,?,?,?)",
                        (utc(),topic,cognitive.get('mode','unknown'),cognitive.get('report_file',''),json.dumps(cognitive.get('decisions',[])[:4],ensure_ascii=False)[:4000]))
                    proposals=cognitive.get('decisions',[])
                    if isinstance(proposals,list):
                        for proposal in proposals[:20]:
                            c.execute("INSERT INTO improvement_proposals(created,topic,proposal,evidence) VALUES(?,?,?,?)",
                                (utc(),topic,json.dumps(proposal,ensure_ascii=False)[:5000],json.dumps(proposal.get('source_ids',[]) if isinstance(proposal,dict) else [],ensure_ascii=False)))
            summary=f"candidate sources={report.get('sources_collected',0)}; evidence rows added={added}; cognition={cognitive.get('mode') if cognitive else 'not_run'}"
            mem.add_run(topic,'COMPLETED' if report.get('sources_collected',0)>0 else 'NO_EVIDENCE',summary)
            reflection=evolution.reflect(topic,report,cognitive)
            results.append({'topic':topic,'status':'COMPLETED' if report.get('sources_collected',0)>0 else 'NO_EVIDENCE',
                'adaptive_plan':next((x for x in plan_details if x.get('topic')==topic),{}),'reflection':reflection,
                'youtube':({'videos_found':youtube_result.get('videos_found',0),'videos_with_captions':youtube_result.get('videos_with_captions',0),'error':youtube_result.get('error')} if youtube_result else {'enabled':False}),'report':report,'evidence_added':added,'cognition':cognitive})
        except Exception as e:
            mem.add_run(topic,'FAILED',f'{type(e).__name__}: {e}')
            reflection=evolution.reflect(topic,{}, {},error=e)
            results.append({'topic':topic,'status':'FAILED','error':f'{type(e).__name__}: {e}','reflection':reflection})
    status={'engine':engine,'cycle_at':utc(),'tasks':results,'memory':mem.status(),
            'agent_evolution':evolution.status(),'adaptive_plan':plan_details,
            'learning_mode':'persistent evidence + four-role model debate when a compatible model is configured; offline mode is extractive only; no neural weights are changed',
            'reasoning_backend':backend_status(),
            'open_source_background_records_available':len(load_open_source_records(root)),
            'safety':'new evidence remains PENDING review; no source is auto-promoted to model training'}
    (root/'reports').mkdir(exist_ok=True)
    (root/'reports'/'intelligence_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    return status

def autopilot(root,engine,cycles=1,interval_seconds=3600,max_pages=8,topic_limit=2,youtube=False):
    """Foreground loop. cycles=None means continuous until Ctrl+C; no hidden daemon."""
    out=[]; index=0
    try:
        while cycles is None or index < max(1,cycles):
            out.append(run_cycle(root,engine,max_pages,topic_limit,youtube=youtube)); index += 1
            if cycles is None or index < cycles: time.sleep(max(30,interval_seconds))
    except KeyboardInterrupt:
        pass
    return {'engine':engine,'cycles':len(out),'results':out,'note':'foreground process; keep device awake and process running for scheduled cycles'}
