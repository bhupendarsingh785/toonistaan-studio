"""Persistent, evidence-grounded evolution loop for one ASTRA engine agent.

This is software-level continual improvement: retrieval, adaptive task selection,
feedback, and measured reflection. It does not claim to train model weights.
"""
from __future__ import annotations
import math, re, sqlite3, time, hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

TOKEN_RE = re.compile(r"[a-z0-9_]+|[\u0900-\u097f]+", re.I)


def _tokens(text: str) -> set[str]:
    return {x.casefold() for x in TOKEN_RE.findall(text or "") if len(x) > 1}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AgentEvolution:
    """One engine's private experience store and adaptive research policy."""
    def __init__(self, engine_root):
        self.root = Path(engine_root)
        self.db = self.root / "memory" / "intelligence_memory.sqlite3"
        self.db.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS agent_experiences(
              id INTEGER PRIMARY KEY, created TEXT NOT NULL, topic_key TEXT NOT NULL,
              topic TEXT NOT NULL, outcome TEXT NOT NULL, reward REAL NOT NULL,
              sources_count INTEGER NOT NULL DEFAULT 0, domains_count INTEGER NOT NULL DEFAULT 0,
              primary_count INTEGER NOT NULL DEFAULT 0, cognition_mode TEXT,
              summary TEXT, error TEXT);
            CREATE INDEX IF NOT EXISTS idx_agent_exp_topic ON agent_experiences(topic_key, id DESC);
            CREATE TABLE IF NOT EXISTS agent_lessons(
              id INTEGER PRIMARY KEY, created TEXT NOT NULL, topic_key TEXT NOT NULL,
              lesson TEXT NOT NULL, evidence_refs TEXT, status TEXT NOT NULL DEFAULT 'PROPOSED');
            CREATE TABLE IF NOT EXISTS agent_policy(
              key TEXT PRIMARY KEY, value REAL NOT NULL, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS agent_feedback_events(
              id INTEGER PRIMARY KEY, created TEXT NOT NULL, category TEXT NOT NULL,
              issue TEXT NOT NULL, severity TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'user');
            """)

    def connect(self):
        con = sqlite3.connect(self.db, timeout=20)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=20000")
        con.execute("PRAGMA journal_mode=WAL")
        return con

    @staticmethod
    def topic_key(topic: str) -> str:
        return hashlib.sha256(" ".join((topic or "").casefold().split()).encode()).hexdigest()[:24]

    def status(self):
        with self.connect() as con:
            return {
                "experiences": con.execute("SELECT COUNT(*) FROM agent_experiences").fetchone()[0],
                "lessons_proposed": con.execute("SELECT COUNT(*) FROM agent_lessons WHERE status='PROPOSED'").fetchone()[0],
                "feedback_events": con.execute("SELECT COUNT(*) FROM agent_feedback_events").fetchone()[0],
                "policy_parameters": con.execute("SELECT COUNT(*) FROM agent_policy").fetchone()[0],
                "learning_mode": "persistent retrieval + feedback-weighted adaptive planning + outcome reflection",
                "weights_updated": False,
            }

    def add_feedback(self, category, issue, severity="medium", source="user"):
        category, issue = str(category).strip(), str(issue).strip()
        if not category or not issue:
            raise ValueError("category and issue must be non-empty")
        if severity not in {"low", "medium", "high", "critical"}:
            raise ValueError("severity must be low, medium, high, or critical")
        with self.connect() as con:
            con.execute("INSERT INTO agent_feedback_events(created,category,issue,severity,source) VALUES(?,?,?,?,?)",
                        (_now(), category[:120], issue[:2000], severity, source[:40]))

    def rank_topics(self, topics, feedback_rows=(), limit=3):
        """Rank tasks using novelty, overdue value, feedback match and measured yield."""
        now = time.time()
        with self.connect() as con:
            rows = con.execute("""SELECT topic_key, COUNT(*) n, AVG(reward) avg_reward,
                MAX(created) last_seen, SUM(CASE WHEN outcome='NO_EVIDENCE' THEN 1 ELSE 0 END) no_evidence
                FROM agent_experiences GROUP BY topic_key""").fetchall()
        hist = {r['topic_key']: r for r in rows}
        fb = [(str(x.get('category','')) + ' ' + str(x.get('issue','')), str(x.get('severity','medium')))
              for x in feedback_rows]
        ranked=[]
        for topic in topics:
            key=self.topic_key(topic); row=hist.get(key)
            attempts=int(row['n']) if row else 0
            avg=float(row['avg_reward']) if row else 0.5
            age_days=365.0
            if row and row['last_seen']:
                try: age_days=max(0.0,(now-datetime.fromisoformat(row['last_seen']).timestamp())/86400)
                except Exception: age_days=0.0
            novelty=1.0/math.sqrt(1+attempts)
            overdue=min(1.0,age_days/14.0)
            reward_signal=avg if attempts else 0.5
            topic_tokens=_tokens(topic)
            feedback_score=0.0
            matched=[]
            for text,severity in fb:
                overlap=len(topic_tokens & _tokens(text))/max(1,len(topic_tokens | _tokens(text)))
                if overlap >= 0.08:
                    weight={'low':0.5,'medium':1.0,'high':1.5,'critical':2.0}.get(severity,1.0)
                    feedback_score=max(feedback_score, overlap*weight)
                    matched.append(text[:180])
            # Low-yield tasks are not permanently discarded; they receive a modest retry penalty.
            score=0.38*novelty+0.20*overdue+0.22*reward_signal+0.20*min(1.0,feedback_score)
            ranked.append({"topic":topic,"score":round(score,5),"attempts":attempts,
                           "historical_reward":round(avg,3) if attempts else None,
                           "novelty":round(novelty,3),"overdue":round(overdue,3),
                           "feedback_match":bool(matched),"matched_feedback":matched[:2]})
        ranked.sort(key=lambda x:(x['feedback_match'],x['score'],x['topic']),reverse=True)
        return ranked[:max(1,int(limit))]

    def retrieve_evidence(self, query, limit=5):
        """Retrieve relevant prior evidence as untrusted context, never as verified truth."""
        q=_tokens(query)
        if not q:
            return []
        with self.connect() as con:
            # AgentEvolution may be used before IntelligenceMemory initializes the
            # research-evidence schema. An empty store is a valid cold-start state.
            exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='evidence'").fetchone()
            if not exists:
                return []
            rows=con.execute("SELECT sha,url,domain,title,text,relevance,collected,review_status FROM evidence ORDER BY id DESC LIMIT 1500").fetchall()
        scored=[]
        for row in rows:
            body=(row['title'] or '')+' '+(row['text'] or '')
            toks=_tokens(body)
            if not toks: continue
            overlap=len(q & toks)/max(1,len(q))
            if overlap <= 0: continue
            score=0.75*overlap+0.25*max(0.0,min(1.0,float(row['relevance'] or 0)))
            scored.append((score,row))
        scored.sort(key=lambda x:x[0],reverse=True)
        out=[]
        for score,row in scored[:max(1,int(limit))]:
            out.append({"sha256":row['sha'],"url":row['url'],"domain":row['domain'],
                        "title":row['title'],"text":(row['text'] or '')[:8000],
                        "relevance":score,"quality":"historical_unverified",
                        "memory_review_status":row['review_status'],"memory_origin":"prior_engine_experience"})
        return out

    def retrieve_lessons(self, query, limit=5):
        q=_tokens(query)
        with self.connect() as con:
            rows=con.execute("SELECT topic_key,lesson,evidence_refs,created,status FROM agent_lessons WHERE status IN ('PROPOSED','ACCEPTED') ORDER BY id DESC LIMIT 500").fetchall()
        scored=[]
        for row in rows:
            overlap=len(q & _tokens(row['lesson']))/max(1,len(q))
            if overlap>0:
                scored.append((overlap,row))
        scored.sort(key=lambda x:x[0],reverse=True)
        return [{"lesson":r['lesson'],"evidence_refs":r['evidence_refs'],"status":r['status'] if 'status' in r.keys() else 'PROPOSED',"origin":"prior_reflection_unverified"} for _,r in scored[:max(1,int(limit))]]

    def reflect(self, topic, report=None, cognition=None, error=None):
        report=report or {}; cognition=cognition or {}
        sources=report.get('sources') or []
        collected=[s for s in sources if s.get('status')=='collected' or s.get('text')]
        domains={s.get('domain') for s in collected if s.get('domain')}
        primary=sum(1 for s in collected if s.get('quality') in ('primary_or_project_source','primary','official'))
        count=int(report.get('sources_collected',len(collected)) or 0)
        mode=cognition.get('mode','not_run')
        if error:
            outcome='FAILED'; reward=0.0
        elif count <= 0:
            outcome='NO_EVIDENCE'; reward=0.12
        else:
            outcome='COMPLETED'
            reward=min(1.0,0.25+0.10*min(count,5)+0.08*min(len(domains),4)+0.12*bool(primary)+0.08*(mode=='four_role_model_debate'))
        summary=f"sources={count}; domains={len(domains)}; primary={primary}; cognition={mode}"
        with self.connect() as con:
            con.execute("INSERT INTO agent_experiences(created,topic_key,topic,outcome,reward,sources_count,domains_count,primary_count,cognition_mode,summary,error) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (_now(),self.topic_key(topic),topic,outcome,reward,count,len(domains),primary,mode,summary,str(error)[:1000] if error else None))
            if error:
                lesson=f"Retry after resolving {type(error).__name__}; preserve the failure trace and add a regression test."
                con.execute("INSERT INTO agent_lessons(created,topic_key,lesson,evidence_refs) VALUES(?,?,?,?)",
                            (_now(),self.topic_key(topic),lesson,"[]"))
            elif count == 0:
                lesson="Broaden discovery with alternate terms and independent indexes; record provider failures; do not infer absence from one search pass."
                con.execute("INSERT INTO agent_lessons(created,topic_key,lesson,evidence_refs) VALUES(?,?,?,?)",
                            (_now(),self.topic_key(topic),lesson,"[]"))
        return {"outcome":outcome,"reward":round(reward,3),"sources":count,"domains":len(domains),"primary_sources":primary,"lesson_created":bool(error or count==0)}


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); root.mkdir(exist_ok=True)
        # Create compatible evidence table used by the production memory store.
        con=sqlite3.connect(root/'memory'/'intelligence_memory.sqlite3') if (root/'memory').exists() else None
        if con: con.close()
        from contextlib import closing
        (root/'memory').mkdir(exist_ok=True)
        con=sqlite3.connect(root/'memory'/'intelligence_memory.sqlite3')
        con.execute("CREATE TABLE evidence(id INTEGER PRIMARY KEY, sha TEXT, url TEXT, domain TEXT, title TEXT, text TEXT, relevance REAL, collected TEXT, review_status TEXT)")
        con.execute("INSERT INTO evidence(sha,url,domain,title,text,relevance,collected,review_status) VALUES(?,?,?,?,?,?,?,?)",
                    ('a'*64,'https://example.org','example.org','Hindi TTS','Hindi pronunciation prosody and Piper training',0.8,_now(),'PENDING'))
        con.commit(); con.close()
        agent=AgentEvolution(root)
        agent.add_feedback('pronunciation','Hindi pronunciation error in difficult words','critical')
        plan=agent.rank_topics(['Hindi pronunciation lexicon','generic CPU benchmark'],[{'category':'pronunciation','issue':'Hindi pronunciation error','severity':'critical'}],2)
        assert plan[0]['feedback_match']
        mem=agent.retrieve_evidence('Hindi pronunciation Piper',2)
        assert mem and mem[0]['memory_origin']=='prior_engine_experience'
        outcome=agent.reflect('Hindi pronunciation lexicon',{'sources_collected':2,'sources':[{'status':'collected','domain':'a.org','quality':'official'},{'status':'collected','domain':'b.org'}]},{'mode':'offline'})
        assert outcome['outcome']=='COMPLETED' and agent.status()['experiences']==1
        return {'passed':True,'checks':5,'status':agent.status()}
