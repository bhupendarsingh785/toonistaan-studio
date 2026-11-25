"""Hindi Devanagari orthography/phonology inspection (rule-based, transparent, no fake IPA)."""
import unicodedata, re
VOWELS=set('अआइईउऊऋॠऌएऐओऔ')
CONSONANTS=set('कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहळक़ख़ग़ज़ड़ढ़फ़')
MATRAS=set('ािीुूृॄॢेैोौ')
MARKS=set('\u0900\u0901\u0902\u0903\u093c\u094d')
NASAL={'ं':'anusvara','ँ':'chandrabindu','ः':'visarga'}
ASPIRATED=set('खघछझठढथधफभ')
RETROFLEX=set('टठडढणष')

def graphemes(text):
    out=[]; cur=''
    for ch in unicodedata.normalize('NFC',text):
        if not cur: cur=ch
        elif unicodedata.combining(ch) or ch in MARKS or cur.endswith('्') or ch=='़': cur+=ch
        else: out.append(cur); cur=ch
    if cur: out.append(cur)
    return out

def inspect_word(word):
    gs=graphemes(word); aksharas=[]; current=''
    for g in gs:
        if g.isspace(): continue
        if current and current.endswith('्'):
            current+=g
        else:
            if current: aksharas.append(current)
            current=g
    if current: aksharas.append(current)
    vowels=[]; consonants=[]; matras=[]; nasal=[]; aspirated=[]; conjuncts=[]; unknown=[]
    for i,g in enumerate(aksharas):
        has_vowel=False; has_matra=False; has_halant='्' in g
        for ch in g:
            if ch in VOWELS: vowels.append({'symbol':ch,'type':'independent_vowel'}); has_vowel=True
            elif ch in MATRAS: matras.append(ch); vowels.append({'symbol':ch,'type':'matra'}); has_vowel=True; has_matra=True
            elif ch in CONSONANTS:
                consonants.append(ch)
                if ch in ASPIRATED: aspirated.append(ch)
            elif ch in NASAL: nasal.append(NASAL[ch])
            elif ch in ('्','़'): pass
            elif unicodedata.category(ch).startswith(('P','M')): pass
            elif ch.isdigit() or ch.isascii() or ch in '।॥': pass
            else: unknown.append(ch)
        # A consonant akshara without a matra/halant usually carries an inherent schwa.
        # This is an orthographic estimate only; Hindi schwa deletion remains contextual.
        if any(c in CONSONANTS for c in g) and not has_vowel and not has_halant:
            vowels.append({'symbol':'अ (inherent)','type':'inherent_schwa_estimate'})
        if '्' in g and len([c for c in g if c in CONSONANTS])>1: conjuncts.append(g)
    return {'word':word,'aksharas':aksharas,'syllable_nuclei_estimate':len(vowels),
      'vowel_symbols':vowels,'consonants':consonants,'matras':matras,'nasal_features':nasal,
      'aspirated_consonants':aspirated,'conjunct_clusters':conjuncts,'unknown_symbols':unknown,
      'schwa_note':'Hindi schwa deletion is context-sensitive; this scanner does not guess the spoken form.'}

def inspect_text(text):
    words=re.findall(r'[\u0900-\u097f]+|[A-Za-z]+|\d+',unicodedata.normalize('NFC',text))
    return {'script':'Devanagari/Hinglish mixed' if re.search(r'[A-Za-z]',text) else 'Devanagari or other',
      'words':[inspect_word(w) for w in words], 'counts':{'words':len(words),'aksharas':sum(len(inspect_word(w)['aksharas']) for w in words)},
      'limitations':['Orthographic scanner is not a trained G2P model.','Schwa deletion, dialect, loanword pronunciation and prosodic phrasing require context and native-speaker validation.']}
