"""Context-aware Hindi performance planner. Rule-based baseline; never claims human-level emotion understanding."""
import re, json
from hindi_phonology import inspect_text
LEX={
'happy':['खुशी','खुश','बहुत अच्छा','वाह','शाबाश','कमाल','मिल गया','जीत गए','मुस्कुर','हँस','हंस','आनंद','धन्यवाद'],
'sad':['दुख','दुःख','उदास','अकेला','अकेली','खो दिया','मर गया','मर गई','आँसू','आंसू','रोने लगा','रो पड़ी','टूट गया','याद आ रही'],
'angry':['गुस्सा','क्रोध','नफरत','बर्दाश्त नहीं','चुप हो जाओ','धोखा','झूठ बोल','कितनी बार कहा'],
'fearful':['डर','भय','काँप','कांप','खतरा','बचाओ','कोई है','पीछे कोई','अंधेरा','आहट','सहमा'],
'surprised':['अचानक','यकीन नहीं','क्या सच','अरे बाप रे','हैरान','चौंक','अविश्वसनीय'],
'curious':['क्यों','कैसे','कहाँ','कहां','कौन','क्या हुआ','क्या होगा','जानना चाहता'],
'serious':['ध्यान से सुनो','यह जरूरी है','फैसला','सच बताओ','वादा','कसम','जिम्मेदारी']}
TAG={'खुश':'happy','प्रसन्न':'happy','उदास':'sad','दुखी':'sad','गुस्सा':'angry','क्रोधित':'angry','डरा':'fearful','डर':'fearful','हैरान':'surprised','जिज्ञासु':'curious','गंभीर':'serious','फुसफुस':'whisper','फुसफुसाहट':'whisper','जोर से':'shout','हँसी':'laughing','रोना':'crying','दुख':'sad'}

def _score(text):
    t=text.casefold(); scores={e:sum(1 for cue in cues if cue in t) for e,cues in LEX.items()}
    if '?' in text or '？' in text: scores['curious']+=1
    if '!' in text or '！' in text: scores['surprised']+=1
    if re.search(r'अरे|ओह|हाय|हे भगवान',text): scores['surprised']+=1
    best=max(scores,key=scores.get); val=scores[best]
    if val==0: return 'neutral',0.30,scores
    total=sum(scores.values()); lexical_total=sum(1 for cues in LEX.values() for cue in cues if cue in t)
    confidence=(min(.94,.48+val*.12+(val/total)*.22) if lexical_total else .40)
    return best,confidence,scores

def _explicit(line):
    m=re.search(r'\[भाव\s*:\s*([^\]]+)\]',line)
    return TAG.get(m.group(1).strip(),m.group(1).strip()) if m else None

def _delivery(emotion,text):
    tail=text.rstrip()[-1:] if text.strip() else ''
    base={'rate':'conversational','pitch':'natural','energy':'medium','articulation':'clear','pause_after_ms':0,'contour':'level'}
    styles={
      'happy':dict(rate='lively',pitch='slightly_up',energy='warm_medium_high',contour='rising_then_settle',pause_after_ms=180),
      'sad':dict(rate='slow',pitch='slightly_low',energy='soft',contour='falling_gentle',pause_after_ms=420),
      'angry':dict(rate='firm',pitch='firm_dynamic',energy='controlled_high',contour='sharp_fall',pause_after_ms=220),
      'fearful':dict(rate='uneven_careful',pitch='slightly_high',energy='tense_low',contour='unstable_then_fall',pause_after_ms=350),
      'surprised':dict(rate='quick_onset',pitch='up_then_down',energy='high_onset',contour='sharp_rise',pause_after_ms=260),
      'curious':dict(rate='measured',pitch='rising_question',energy='medium',contour='rising',pause_after_ms=250),
      'serious':dict(rate='measured_slow',pitch='stable_low',energy='firm_medium',contour='controlled_fall',pause_after_ms=300),
      'whisper':dict(rate='slow',pitch='low_soft',energy='very_low',contour='narrow',pause_after_ms=350),
      'shout':dict(rate='projected',pitch='dynamic',energy='high',contour='strong',pause_after_ms=250),
      'laughing':dict(rate='rhythmic',pitch='variable',energy='bright',contour='bouncy',pause_after_ms=180),
      'crying':dict(rate='broken_slow',pitch='unstable',energy='soft',contour='wavering_fall',pause_after_ms=500)}
    base.update(styles.get(emotion,{}))
    if tail in ('।','.'): base['pause_after_ms']=max(base['pause_after_ms'],300)
    elif tail in ('?','？'): base['pause_after_ms']=max(base['pause_after_ms'],280); base['contour']='question_rise'
    elif tail in ('!','！'): base['pause_after_ms']=max(base['pause_after_ms'],220)
    elif tail in ('…',): base['pause_after_ms']=max(base['pause_after_ms'],500)
    return base

def analyze_line(line, previous_emotion='neutral', persona=None):
    raw=line.strip(); m=re.match(r'^\s*([^:：\[]+?)\s*(?:\[भाव\s*:\s*([^\]]+)\])?\s*[:：]\s*(.*)$',raw)
    speaker=m.group(1).strip() if m else None; text=m.group(3).strip() if m else raw
    explicit=_explicit(raw); emotion=explicit
    if emotion is None: emotion,conf,scores=_score(text)
    else: conf=.99; scores={emotion:99}
    if previous_emotion in ('sad','fearful','angry') and (emotion=='neutral' or (emotion in ('curious','surprised') and conf<.60) or (previous_emotion=='fearful' and emotion=='curious' and text.rstrip().endswith('?'))):
        # A generic question marker or question word must not erase an established emotional scene.
        emotion=previous_emotion; conf=min(conf,.52)
    if persona and persona.get('delivery_notes') and emotion=='neutral': conf=.25
    plan=_delivery(emotion,text)
    phon=inspect_text(text)
    return {'speaker':speaker,'text':text,'emotion':emotion,'emotion_confidence':round(conf,2),
      'emotion_evidence':'explicit_script_tag' if explicit else 'context_lexicon_and_punctuation',
      'emotion_scores':scores,'delivery':plan,'phonology':phon,
      'speaker_persona':persona or {},'needs_review':conf<.55 or bool(any(w['unknown_symbols'] for w in phon['words']))}

def analyze_script(text, profiles=None):
    profiles=profiles or {}; rows=[]; previous={}
    for n,line in enumerate(text.splitlines(),1):
        if not line.strip(): continue
        if re.match(r'^\s*\[विराम:\d+ms\]\s*$',line):
            rows.append({'line':n,'kind':'pause','pause_after_ms':int(re.search(r'\d+',line).group())}); continue
        rough=re.match(r'^\s*([^:：\[]+?)\s*(?:\[भाव\s*:\s*[^\]]+\])?\s*[:：]',line)
        who=rough.group(1).strip() if rough else '__narrator__'
        persona=profiles.get(who,{})
        row=analyze_line(line,previous.get(who,'neutral'),persona); row['line']=n; row['kind']='speech'
        previous[who]=row['emotion']; rows.append(row)
    return {'version':'0.7','segments':rows,'summary':{'speech_segments':sum(r['kind']=='speech' for r in rows),'emotion_counts':{e:sum(1 for r in rows if r.get('emotion')==e) for e in ['neutral','happy','sad','angry','fearful','surprised','curious','serious','whisper','shout','laughing','crying']},'needs_review':sum(1 for r in rows if r.get('needs_review'))},'limits':['Emotion is inferred heuristically unless explicitly annotated.','Prosody directives are not guaranteed to be rendered by every TTS backend.','Natural acting requires a neural voice model that supports expressive conditioning.']}
