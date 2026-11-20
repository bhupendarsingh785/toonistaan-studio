#!/usr/bin/env python3
"""Evaluate an ASTRA generation manifest with objective audio QA and optional ASR.
ASR scores measure text intelligibility, not speaker identity or emotional realism.
"""
from __future__ import annotations
import argparse, json, re, unicodedata
from pathlib import Path
from tools.audio_qa import inspect_wav

def _norm(s: str) -> str:
    s=unicodedata.normalize('NFC',s).lower()
    s=re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return " ".join(s.split())

def _edit_distance(a: list[str], b: list[str]) -> int:
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        cur=[i]
        for j,y in enumerate(b,1):
            cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=cur
    return prev[-1]

def text_scores(reference: str, hypothesis: str) -> dict:
    r=_norm(reference); h=_norm(hypothesis)
    rw=r.split(); hw=h.split()
    wer=_edit_distance(rw,hw)/max(1,len(rw))
    rc=list(r.replace(' ','')); hc=list(h.replace(' ',''))
    cer=_edit_distance(rc,hc)/max(1,len(rc))
    return {"wer":round(wer,5),"cer":round(cer,5),"reference_words":len(rw),"hypothesis_words":len(hw)}

def evaluate(manifest_path: str, asr_model: str | None = None, device: str = 'cpu') -> dict:
    mp=Path(manifest_path)
    m=json.loads(mp.read_text(encoding='utf-8'))
    rows=[x for x in m.get('items',[]) if x.get('status')=='ok' and x.get('file')]
    if not rows: raise ValueError('Manifest mein successful audio chunks nahi mile')
    asr=None
    if asr_model:
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            raise RuntimeError('ASR evaluation ke liye faster-whisper install karein') from exc
        asr=WhisperModel(asr_model,device=device,compute_type='int8' if device=='cpu' else 'float16')
    results=[]; failures=[]
    for row in rows:
        wav=Path(row['file'])
        if not wav.is_absolute(): wav=mp.parent/wav
        try:
            qa=inspect_wav(wav)
            item={"sequence":row.get('sequence'),"file":str(wav),"audio_qa":qa}
            if asr is not None:
                segments,_=asr.transcribe(str(wav),language='hi',vad_filter=True)
                hyp=' '.join(seg.text for seg in segments)
                item['asr_text']=hyp
                item['text_scores']=text_scores(row.get('text',''),hyp)
            results.append(item)
        except Exception as exc:
            failures.append({"sequence":row.get('sequence'),"file":str(wav),"error":f"{type(exc).__name__}: {exc}"})
    qa_pass=sum(1 for x in results if x['audio_qa']['pass'])
    score_rows=[x['text_scores'] for x in results if 'text_scores' in x]
    summary={"manifest":str(mp),"chunks_total":len(rows),"chunks_evaluated":len(results),
             "chunks_failed":len(failures),"audio_qa_pass":qa_pass,
             "audio_qa_fail":len(results)-qa_pass,"asr_enabled":asr is not None,
             "mean_wer":round(sum(x['wer'] for x in score_rows)/len(score_rows),5) if score_rows else None,
             "mean_cer":round(sum(x['cer'] for x in score_rows)/len(score_rows),5) if score_rows else None,
             "limitations":"No speaker-identity verification or human emotion/naturalness rating is performed."}
    return {"summary":summary,"chunks":results,"failures":failures}

def main() -> int:
    ap=argparse.ArgumentParser(description='ASTRA generation quality evaluator')
    ap.add_argument('--manifest',required=True); ap.add_argument('--out',required=True)
    ap.add_argument('--asr-model',default=None,help='Optional faster-whisper model, e.g. small')
    ap.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    a=ap.parse_args()
    try:
        report=evaluate(a.manifest,a.asr_model,a.device)
        Path(a.out).parent.mkdir(parents=True,exist_ok=True)
        Path(a.out).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report['summary'],ensure_ascii=False,indent=2))
        return 0 if report['summary']['chunks_failed']==0 and report['summary']['audio_qa_fail']==0 else 2
    except Exception as exc:
        print(f'[FAIL] {type(exc).__name__}: {exc}')
        return 1
if __name__=='__main__': raise SystemExit(main())
