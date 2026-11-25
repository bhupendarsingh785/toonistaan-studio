"""Evidence-grounded multi-role cognition for the independent Hindi voice agents.

Supports any OpenAI-compatible local or remote chat-completions endpoint (Ollama,
LM Studio, vLLM, compatible hosted providers). No endpoint is mandatory. When no
model is configured, it emits a transparent extractive/offline report and never
pretends that heuristics are deep reasoning or neural learning.
"""
from __future__ import annotations
import json, os, re, hashlib, time
from pathlib import Path
from urllib.parse import urlparse
import requests

def _load_dotenv():
    env_path=Path(__file__).resolve().parent/'.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1); os.environ.setdefault(k.strip(),v.strip().strip('\"').strip("'"))
_load_dotenv()

ROLE_PROMPTS = {
 "research_analyst": "You are the research analyst. Extract only claims explicitly supported by the supplied source excerpts. For every claim give source_ids and short evidence quotes. Separate facts, author claims, limitations, and unknowns. Do not infer unsupported facts.",
 "domain_expert": "You are a critical Hindi speech/TTS domain specialist. Explain technical implications for the specified engine, Hindi phonology, pronunciation, prosody, emotion, speaker consistency, audio QA, CPU constraints and maintainability. Distinguish direct evidence from inference. Identify concrete experiments.",
 "skeptic": "You are an adversarial reviewer. Challenge the analyst and expert. Find contradictions, missing baselines, weak evidence, licensing uncertainty, stale information, confounders, benchmark leakage, deployment assumptions and failure cases. Do not be agreeable by default.",
 "decision_judge": "You are an evidence judge and engineering lead. Reconcile the debate. Cite source_ids for factual claims. Assign confidence only when evidence supports it. Output actionable, testable proposals with acceptance criteria, rollback plan and dependencies. Never approve unverified code execution, model training, production changes or license assumptions."
}
ENGINE_SPECIALIZATION = {'EDGE': 'EDGE specialization: evaluate Microsoft Edge neural/cloud TTS availability, Hindi voice selection, documented controls, network fallback, latency, service limits and output consistency. Do not assume local model training is possible.', 'PIPER': 'PIPER specialization: evaluate local neural TTS, VITS/Piper checkpoint compatibility, phonemization, ONNX runtime, training metadata, speaker identity, CPU/RAM latency and reproducible fine-tuning.', 'ESPEAK': 'ESPEAK specialization: evaluate eSpeak NG formant synthesis, Hindi phoneme rules, schwa deletion, dictionary overrides, intonation/rhythm and intelligibility. Do not propose neural-weight training for this formant engine.', 'ELEVENLABS': 'ELEVENLABS specialization: evaluate hosted API capabilities, Hindi multilingual pronunciation, voice settings, latency/cost/quotas, audio tags, long-form character consistency and API failure handling. Do not assume model weights are locally trainable.', 'SARVAM': 'SARVAM specialization: evaluate Indian-language speech models, Hindi pronunciation, documented API/model capabilities, deployment limits, data provenance and measurable voice quality.'}


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

def _config():
    base=os.getenv('AGENT_LLM_BASE_URL','').strip().rstrip('/')
    model=os.getenv('AGENT_LLM_MODEL','').strip()
    key=os.getenv('AGENT_LLM_API_KEY','').strip()
    timeout=int(os.getenv('AGENT_LLM_TIMEOUT','75'))
    return {'base_url':base,'model':model,'api_key':key,'timeout':max(10,min(timeout,240))}

def backend_status():
    c=_config(); base=c['base_url']; model=c['model']; reachable=None; installed=None; detected=[]
    if '127.0.0.1:11434' in base or 'localhost:11434' in base:
        try:
            api='http://127.0.0.1:11434/api/tags'
            r=requests.get(api,timeout=1.2); r.raise_for_status()
            detected=[x.get('name','') for x in r.json().get('models',[]) if x.get('name')]
            reachable=True; installed=any(x.casefold()==model.casefold() or (':' not in model and x.split(':')[0].casefold()==model.casefold()) for x in detected)
        except Exception: reachable=False; installed=False
    configured=bool(base and model) and (installed if installed is not None else True)
    return {'configured':configured,'provider_mode':'openai-compatible','base_url':base or None,'model':model or None,
            'local_server_reachable':reachable,'installed_local_models':detected,
            'default_local_endpoint':'http://127.0.0.1:11434/v1','api_key_present':bool(c['api_key']),
            'recommended_open_model':None, 'setup_command':None,
            'note':'WEB_FIRST mode: no model is selected or required. Any OpenAI-compatible reasoning endpoint is optional and must be configured explicitly by the operator.'}

def _chat(system, user, cfg=None):
    cfg=cfg or _config()
    if not (cfg['base_url'] and cfg['model']):
        raise RuntimeError('No AGENT_LLM_BASE_URL and AGENT_LLM_MODEL configured')
    if ('127.0.0.1:11434' in cfg['base_url'] or 'localhost:11434' in cfg['base_url']) and not backend_status().get('configured'):
        raise RuntimeError('Configured local reasoning endpoint is not ready; web-first research does not require it.')
    url=cfg['base_url']
    if not url.endswith('/chat/completions'):
        url += '/chat/completions'
    headers={'Content-Type':'application/json'}
    if cfg['api_key']: headers['Authorization']='Bearer '+cfg['api_key']
    payload={'model':cfg['model'],'temperature':0.15,'messages':[{'role':'system','content':system},{'role':'user','content':user}]}
    r=requests.post(url,headers=headers,json=payload,timeout=cfg['timeout'])
    r.raise_for_status(); data=r.json()
    return data['choices'][0]['message']['content']

def _json_from_text(raw):
    s=raw.strip()
    if s.startswith('```'):
        s=re.sub(r'^```(?:json)?\s*|\s*```$','',s,flags=re.I)
    try:return json.loads(s)
    except Exception:
        m=re.search(r'\{.*\}',s,re.S)
        if m:
            try:return json.loads(m.group(0))
            except Exception:pass
    return {'raw_text':raw,'parse_warning':'Model response was not valid JSON; retained verbatim.'}

def plan_research_queries(query, engine, seed_topics=None, max_queries=8):
    """Use a configured model to decompose a research goal; safe fallback is explicit."""
    seed=list(seed_topics or [])
    prompt={'goal':query,'engine':engine,'seed_topics':seed,
            'return_schema':{'queries':['specific independent search query'], 'questions':['testable research question'], 'risks':['potential blind spot']}}
    try:
        if not backend_status().get('configured'): raise RuntimeError('Local model not ready or endpoint not configured')
        raw=_chat('You design rigorous web-research plans for Hindi speech technology. Return JSON only. Create diverse, non-duplicate queries spanning primary docs, papers, datasets, benchmarks, implementation and failure analysis. Do not assume the product is capable.',json.dumps(prompt,ensure_ascii=False))
        obj=_json_from_text(raw); queries=obj.get('queries',[]) if isinstance(obj,dict) else []
        clean=[]
        for q in queries:
            if isinstance(q,str) and q.strip() and q.strip().casefold()!=query.strip().casefold() and q.strip() not in clean: clean.append(q.strip()[:240])
        return {'mode':'model_planned','queries':clean[:max_queries],'questions':obj.get('questions',[]) if isinstance(obj,dict) else [],'risks':obj.get('risks',[]) if isinstance(obj,dict) else []}
    except Exception as e:
        # Model-free query planning: deliberately diverse search angles, not a claim of semantic reasoning.
        angles = [
            'official documentation specification architecture',
            'peer reviewed research paper systematic evaluation',
            'open source GitHub implementation issues pull requests',
            'benchmark dataset baseline ablation reproducibility',
            'failure cases limitations negative results known bugs',
            'independent comparison alternatives tradeoffs',
            'license commercial use model data provenance',
            'Hindi phonology pronunciation prosody emotion long form',
            'CPU memory latency offline deployment mobile constraints',
            'security prompt injection browser agent untrusted pages',
            'maintainer roadmap changelog release notes',
            'real world user reports regression tests'
        ]
        queries=[f'{query} {a}' for a in angles]
        return {'mode':'web_first_model_free_plan','queries':queries[:max_queries],
                'questions':['What evidence supports the main claim?', 'Which independent source contradicts it?',
                  'What fails in real deployments?', 'What measurable test would falsify the claim?',
                  'What is the license and data provenance?', 'What can be learned without adopting the dependency?'],
                'risks':[f'No reasoning model configured ({type(e).__name__}); this is structured query planning, not semantic model reasoning.']}

def _sentences(text):
    parts=re.split(r'(?<=[.!?।])\s+|\n+',text or '')
    return [re.sub(r'\s+',' ',p).strip() for p in parts if len(p.strip())>55]

def offline_evidence_analysis(query, engine, sources, prior_lessons=None):
    """Model-free evidence triage and adversarial review. Not a substitute for semantic LLM reasoning."""
    rows=[]; domains=set(); terms_by_source=[]; candidate_claims=[]
    negations={'not','no','never','cannot','cant','unable','without','fails','failure','limited','unsupported','नहीं','नही','असमर्थ','सीमित','विफल'}
    for i,src in enumerate(sources,1):
        txt=src.get('text','') or ''
        domain=src.get('domain') or urlparse(src.get('url','')).hostname or ''
        if domain: domains.add(domain.casefold())
        sentences=_sentences(txt)
        rows.append({'source_id':f'S{i}','title':src.get('title',''),'url':src.get('url',''),
            'domain':domain,'quality':src.get('quality','unknown'),'sha256':src.get('sha256',''),
            'candidate_sentences':sentences[:12],'source_length':len(txt),'status':'EXTRACTED_NOT_VERIFIED'})
        for sent in sentences[:30]:
            toks=set(re.findall(r'[a-z0-9\u0900-\u097f]+',sent.casefold()))
            if len(toks)>=7:
                candidate_claims.append({'source_id':f'S{i}','domain':domain,'text':sent,'tokens':toks,
                                         'negated':bool(toks & negations)})
    # Find possible agreement / disagreement by lexical overlap. These are leads, not semantic entailment.
    comparisons=[]; used=set()
    for i,a in enumerate(candidate_claims):
        for j in range(i+1,len(candidate_claims)):
            b=candidate_claims[j]
            if a['domain'] and a['domain']==b['domain']: continue
            inter=a['tokens'] & b['tokens']; union=a['tokens'] | b['tokens']
            sim=len(inter)/max(1,len(union))
            if sim>=0.24 and (a['negated'] != b['negated'] or sim>=0.38):
                key=(a['source_id'],b['source_id'],a['text'][:80],b['text'][:80])
                if key in used: continue
                used.add(key)
                comparisons.append({'source_a':a['source_id'],'source_b':b['source_id'],
                    'domain_a':a['domain'],'domain_b':b['domain'],'lexical_overlap':round(sim,3),
                    'possible_conflict':a['negated'] != b['negated'],
                    'statement_a':a['text'],'statement_b':b['text'],
                    'status':'HUMAN_OR_MODEL_REVIEW_REQUIRED'})
                if len(comparisons)>=40: break
        if len(comparisons)>=40: break
    primary=sum(1 for x in rows if x['quality'] in ('primary_or_project_source','primary','official'))
    followups=[query+' counter evidence criticism failure cases',query+' independent replication benchmark results',
      query+' official license dataset provenance limitations',query+' issue tracker bugs regression performance',
      query+' Hindi real user evaluation pronunciation emotion naturalness']
    debate={
      'research_analyst':{'task':'Evidence inventory','source_count':len(rows),'independent_domains':len(domains),
        'candidate_claim_count':len(candidate_claims),'claims':'Candidate sentences only; not verified facts.'},
      'domain_expert':{'task':'Domain implications','observations':['Check whether each claim maps to the specific TTS engine and Hindi use case.',
        'Separate text normalization, phonology, prosody, speaker identity, acoustic quality and runtime performance.',
        'Require held-out audio tests; repository stars and model-card claims are not quality proof.'],
        'status':'RULE_BASED_REVIEW_NOT_SEMANTIC_REASONING'},
      'skeptic':{'task':'Adversarial review','possible_conflicts':comparisons,
        'challenges':['Are the sources independent or repeating the same upstream claim?',
          'Is the evidence current and reproducible?', 'Are limitations and negative results represented?',
          'Does the license cover both code and model/data assets?',
          'Does the claim hold for Hindi, not merely English or another language?'],
        'status':'LEXICAL_CONFLICT_CANDIDATES_REQUIRE_VERIFICATION'},
      'decision_judge':{'task':'Conservative decision','decision':'INSUFFICIENT_FOR_AUTOMATIC_ADOPTION',
        'reason':'Model-free analysis can organize and challenge evidence but cannot reliably understand nuanced meaning or infer causality.',
        'proposals':[{'title':'Run independent source triangulation','source_ids':[x['source_id'] for x in rows[:8]],
          'acceptance_criteria':['At least two genuinely independent sources for high-impact claims',
            'Primary documentation or paper checked', 'Contradictions resolved or explicitly left unknown'],
          'rollback_plan':'Keep the current engine configuration unchanged until tests pass.'}],
        'promotion_policy':'PROPOSAL_ONLY'}
    }
    return {'schema':'agent-cognition-report/v1.1','engine':engine,'agent_name':_identity().get('agent_name',''),'query':query,
      'mode':'web_first_structured_adversarial_review','model_used':False,
      'warning':'No model selected. This is deterministic evidence organization and adversarial triage, not human-level semantic reasoning or deep learning.',
      'evidence_inventory':rows,'debate':debate,'possible_cross_source_conflicts':comparisons,
      'independent_domain_count':len(domains),'primary_source_count':primary,
      'follow_up_queries':followups,'decisions':debate['decision_judge']['proposals'],
      'prior_lessons_for_review':list(prior_lessons or []),
      'next_actions':['Fetch counter-evidence and independent sources.',
        'Verify claims against original papers, official docs and issue trackers.',
        'Convert accepted claims into engine-specific regression/audio tests.',
        'Keep all production changes gated behind measured tests and rollback.']}

def analyze_sources(query, engine, sources, out_dir=None, prior_lessons=None):
    """Four-role serial debate over bounded source evidence; decisions remain proposals."""
    sources=list(sources or [])
    if not sources:
        report={'schema':'agent-cognition-report/v1','engine':engine,'query':query,'mode':'no_evidence','model_used':False,
                'warning':'No source text was collected; no conclusion is possible.','evidence_inventory':[],'debate':None,'decisions':[]}
    elif not backend_status().get('configured'):
        report=offline_evidence_analysis(query,engine,sources,prior_lessons=prior_lessons)
    else:
        # Bound prompt size and preserve source IDs/provenance.
        evidence=[]
        for i,s in enumerate(sources[:12],1):
            evidence.append({'source_id':f'S{i}','title':s.get('title',''),'url':s.get('url',''),
                'domain':s.get('domain',''),'quality':s.get('quality','unknown'),'sha256':s.get('sha256',''),
                'text':(s.get('text') or '')[:10000]})
        ctx=json.dumps({'goal':query,'engine':engine,'engine_specialization':ENGINE_SPECIALIZATION.get(str(engine).upper(),'Hindi speech technology'),
            'sources':evidence,'prior_lessons_unverified':list(prior_lessons or [])},ensure_ascii=False)
        debate={}; previous=''
        try:
            for role in ('research_analyst','domain_expert','skeptic','decision_judge'):
                user=ctx if not previous else ctx+'\n\nPrevious role outputs (treat as hypotheses to critique, not truth):\n'+previous[-14000:]
                raw=_chat(ROLE_PROMPTS[role]+' Engine-specific focus: '+ENGINE_SPECIALIZATION.get(str(engine).upper(),'Hindi speech technology')+' Treat prior lessons as hypotheses, not facts. Return valid JSON only. Include source_ids for every factual assertion. If unsupported, mark unknown.',user)
                obj=_json_from_text(raw)
                if not isinstance(obj,dict) or 'raw_text' in obj or 'parse_warning' in obj:
                    raise ValueError(f'{role} returned invalid structured JSON')
                debate[role]=obj
                previous+=f'\n{role}: '+json.dumps(obj,ensure_ascii=False)
            proposals=debate.get('decision_judge',{}).get('proposals',[])
            if not isinstance(proposals,list): proposals=[]
            allowed_ids={x['source_id'] for x in evidence}
            safe_proposals=[]
            for proposal in proposals:
                if not isinstance(proposal,dict): continue
                refs=proposal.get('source_ids',[])
                criteria=proposal.get('acceptance_criteria',[])
                if not isinstance(refs,list) or any(ref not in allowed_ids for ref in refs): continue
                if not isinstance(criteria,list) or not criteria: continue
                safe_proposals.append(proposal)
            report={'schema':'agent-cognition-report/v1','engine':engine,'query':query,'mode':'four_role_model_debate',
                    'model_used':True,'model':_config()['model'],'source_count':len(evidence),'debate':debate,
                    'decisions':safe_proposals,
                    'promotion_policy':'PROPOSAL_ONLY: no auto code execution, no production mutation, no model-weight training.'}
        except Exception as exc:
            report=offline_evidence_analysis(query,engine,sources,prior_lessons=prior_lessons)
            report['mode']='model_unavailable_fallback'
            report['model_used']=False
            report['model_failure']=f'{type(exc).__name__}: {exc}'
            report['warning']='Configured reasoning backend failed or returned invalid output. Fell back to transparent model-free evidence triage; no deep reasoning is claimed.'
    if out_dir:
        out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
        stamp=time.strftime('%Y%m%d-%H%M%S',time.gmtime())
        path=out/f'cognition_{stamp}.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        report['report_file']=str(path)
    if isinstance(report, dict):
        report.setdefault('agent_name', _identity().get('agent_name',''))
    return report

def load_sources(research_file):
    data=json.loads(Path(research_file).read_text(encoding='utf-8'))
    return data.get('sources',[])
