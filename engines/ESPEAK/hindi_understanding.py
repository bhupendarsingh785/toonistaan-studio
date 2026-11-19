"""Conservative Hindi story understanding: entities, speaker map, emotion, relations and ambiguity."""
from __future__ import annotations
import re, json, unicodedata, hashlib
from pathlib import Path

EMOTION_LEXICON={
 'happy':['खुश','प्रसन्न','मुस्कुर','हँस','हंस','वाह','शाबाश','अद्भुत'],
 'sad':['उदास','दुखी','रोया','रोई','आँसू','आंसू','विलाप','टूट गया'],
 'angry':['गुस्सा','क्रोध','चिल्ला','नफरत','चुप रहो','बर्दाश्त'],
 'fearful':['डर','भय','काँप','कांप','घबर','खौफ'],
 'surprised':['अचानक','चौंक','हैरान','क्या!','अरे!'],
 'curious':['क्यों','कैसे','कहाँ','कहां','क्या हुआ','जानना'],
 'whisper':['फुसफुस','धीरे से','कान में'],
 'shout':['चिल्ला','जोर से','ज़ोर से'],
 'laughing':['हँसते हुए','हंसते हुए','ठहाका'],
 'crying':['रोते हुए','सिसक','बिलख']}
AGE_HINTS={'शिशु':'infant','बच्चा':'child','बच्ची':'child','तीन साल':'toddler','3 साल':'toddler','किशोर':'teen','किशोरी':'teen','युवा':'young_adult','बुजुर्ग':'elderly','बूढ़े':'elderly','बूढ़ी':'elderly','दादी':'elderly','दादा':'elderly','नानी':'elderly','नाना':'elderly'}
RELATIONS={'माँ':'mother','माता':'mother','पिता':'father','बाप':'father','बेटा':'son','बेटी':'daughter','भाई':'brother','बहन':'sister','पति':'husband','पत्नी':'wife','दोस्त':'friend','मित्र':'friend','दादी':'grandmother','दादा':'grandfather','नानी':'grandmother','नाना':'grandfather'}
PLACE_MARKERS=['में','पर','से','तक','के पास','की ओर','गाँव','गांव','शहर','घर','स्कूल','मंदिर','बाज़ार','बाजार','जंगल','नदी','पहाड़','पहाड']

def _id(s): return hashlib.sha1(s.casefold().encode()).hexdigest()[:12]
def _norm(s): return unicodedata.normalize('NFC',s.replace('\ufeff','')).strip()
def _emotion(text):
    explicit=re.search(r'\[भाव\s*:\s*([^\]]+)\]',text)
    if explicit: return {'primary':explicit.group(1).strip(),'confidence':'explicit','evidence':'script_markup'}
    low=text.casefold(); hits=[]
    for emotion,words in EMOTION_LEXICON.items():
        matched=[w for w in words if w in low]
        if matched: hits.append((len(matched),emotion,matched))
    if not hits: return {'primary':'neutral','secondary':[],'confidence':'low','evidence':'no_clear_lexical_cue'}
    hits.sort(reverse=True)
    return {'primary':hits[0][1],'secondary':[x[1] for x in hits[1:]],'confidence':'heuristic','matched':hits[0][2]}

def analyze_story(text):
    text=_norm(text); chars={}; segments=[]; places=[]; relations=[]; names=[]; warnings=[]
    lines=text.splitlines()
    # Names introduced by common narrative patterns; speaker labels are strongest evidence.
    for no,line in enumerate(lines,1):
        m=re.match(r'^\s*([\w\u0900-\u097f ._-]{1,40}?)\s*(?:\[[^]]+\]\s*)*\s*[:：]\s*(.*)$',line)
        speaker=m.group(1).strip() if m else None; utterance=m.group(2).strip() if m else line.strip()
        if not utterance: continue
        if speaker:
            c=chars.setdefault(speaker,{'id':_id(speaker),'name':speaker,'dialogue_lines':[],'age_group':'unknown','role':'unknown','voice_presentation':'unknown','relations':[],'voice_profile':'UNASSIGNED','evidence':[]})
            c['dialogue_lines'].append(no); c['evidence'].append({'line':no,'kind':'explicit_speaker_label'})
        # Age/gender/role are assigned only from explicit speaker metadata, never from incidental dialogue words.
        if speaker:
            age_tag=re.search(r'\[उम्र\s*:\s*([^]]+)\]',line)
            role_tag=re.search(r'\[भूमिका\s*:\s*([^]]+)\]',line)
            gender_tag=re.search(r'\[लिंग\s*:\s*([^]]+)\]',line)
            if age_tag:
                chars[speaker]['age_group']=age_tag.group(1).strip(); chars[speaker]['evidence'].append({'line':no,'kind':'explicit_age_tag'})
            if role_tag:
                chars[speaker]['role']=role_tag.group(1).strip(); chars[speaker]['evidence'].append({'line':no,'kind':'explicit_role_tag'})
            if gender_tag:
                chars[speaker]['voice_presentation']=gender_tag.group(1).strip(); chars[speaker]['evidence'].append({'line':no,'kind':'explicit_gender_tag'})
        for token,relation in RELATIONS.items():
            if token in utterance:
                relations.append({'line':no,'speaker':speaker,'relation_term':token,'relation':relation,'target':'UNRESOLVED','confidence':'lexical_only'})
        # Conservative place candidates: proper nouns after common Hindi location prepositions.
        for pat in [r'(?:गाँव|गांव|शहर|कस्बे|जिले|राज्य|देश)\s+([\u0900-\u097fA-Za-z][\u0900-\u097fA-Za-z -]{1,30})',r'([\u0900-\u097fA-Za-z][\u0900-\u097fA-Za-z -]{1,25})\s+(?:के जंगल|की नदी|के मंदिर|के घर)']:
            for x in re.findall(pat,utterance): places.append({'name':x.strip(),'line':no,'confidence':'candidate'})
        # Named person introductions, clearly marked only as candidates.
        for x in re.findall(r'(?:नाम है|जिसका नाम|नाम का|नाम की)\s+([\u0900-\u097f]{2,20})',utterance): names.append({'name':x,'line':no,'confidence':'candidate'})
        segments.append({'line':no,'speaker':speaker,'text':utterance,'emotion':_emotion(line),'delivery':'dialogue' if speaker else 'narration','character_id':chars[speaker]['id'] if speaker else None})
    # Deduplicate candidates without pretending ambiguous entities are resolved.
    def dedup(rows,key):
        seen=set(); out=[]
        for r in rows:
            k=(r[key].casefold(),r['line'])
            if k not in seen: seen.add(k); out.append(r)
        return out
    places=dedup(places,'name'); names=dedup(names,'name')
    if not chars: warnings.append('स्पष्ट speaker labels नहीं मिले; speaker attribution विश्वसनीय रूप से संभव नहीं।')
    if any(r['target']=='UNRESOLVED' for r in relations): warnings.append('रिश्ते के शब्द मिले, लेकिन किस पात्र से संबंध है यह स्पष्ट नहीं; अनुमान नहीं लगाया गया।')
    warnings += ['भावना पहचान नियम-आधारित अनुमान है; अंतिम अभिनय के लिए संदर्भ/मानवीय समीक्षा आवश्यक है।','उम्र, लिंग, नाम और स्थान केवल स्पष्ट पाठ-साक्ष्य पर निर्धारित किए जाएँ; अस्पष्टता को unknown रखा गया है।']
    return {'schema_version':'0.6','characters':list(chars.values()),'segments':segments,'candidate_names':names,'candidate_places':places,'relationship_mentions':relations,'warnings':warnings}

def save_analysis(text, path):
    result=analyze_story(text); Path(path).parent.mkdir(parents=True,exist_ok=True); Path(path).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); return result
