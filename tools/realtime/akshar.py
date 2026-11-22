"""
Akshar — Hindi ko akshar (syllable cluster) me todna, do line ka akshar-akshar milaan, aur galti ki kism batana.

Kyun: WER sirf "shabd galat" batata hai. Humein chahiye: KAUN SA AKSHAR, KYA BANA, KIS KISM KI GALTI.
  "खाना" sunai diya "काना"  ->  akshar 'खा' -> 'का'  ·  kism: mahapraan (ख ka 'h' wala hissa gaya)
  "ज़मीन" -> "जमीन"         ->  'ज़' -> 'ज'      ·  kism: nukta
  "दीदी" -> "दिदी"          ->  'दी' -> 'दि'     ·  kism: matra-lambai (ii -> i)

Kisms (Hindi naam, kyunki report Arjun padhega):
  mahapraan   aspiration: क/ख ग/घ च/छ ज/झ ट/ठ ड/ढ त/थ द/ध प/फ ब/भ
  ghosh       voicing:    क/ग च/ज ट/ड त/द प/ब ...
  murdhanya   retroflex vs dental: ट/त ठ/थ ड/द ढ/ध ण/न ड़/र
  ushm        sibilant:   श/ष/स
  nukta       ज़/ज फ़/फ क़/क ख़/ख ग़/ग ड़/ड ढ़/ढ
  va-ba       व/ब
  matra-lambai ि/ी ु/ू
  matra       koi aur matra badli (े/ै, ो/ौ, ा/ ...)
  schwa       'a' ki galti: matra ka aana/jaana (कमला vs कम्ला)
  anunasik    ं / ँ / न् / म्
  sanyukt     sanyukt akshar tootna/judna (क्ष, ज्ञ, त्र, ् )
  vyanjan     koi aur vyanjan badla
  chhoota     akshar gayab (deletion)
  faltu       akshar zyada (insertion)
"""
from __future__ import annotations
import re, unicodedata

# ---------------------------------------------------------------- Unicode basics
VIRAMA, NUKTA, ANUSVARA, CHANDRA, VISARGA = "्", "़", "ं", "ँ", "ः"
ZWJ, ZWNJ = "‍", "‌"
PRECOMP_NUKTA = {"क़": "क", "ख़": "ख", "ग़": "ग", "ज़": "ज", "ड़": "ड", "ढ़": "ढ", "फ़": "फ", "य़": "य"}

def is_cons(c): return "क" <= c <= "ह" or c in PRECOMP_NUKTA
def is_matra(c): return "ा" <= c <= "ौ" or c in ("ॢ", "ॣ", "ॕ", "ॖ", "ॗ")
def is_vowel(c): return "ऄ" <= c <= "औ" or c in ("ॠ", "ॡ")
def is_mod(c): return c in (ANUSVARA, CHANDRA, VISARGA)

# Likhne ke fark (bolne ki galti nahi): ASR in roopon me likhta hai — dono taraf ek jaise karo
SPELL_VARIANTS = [(r"यी(?=\s|$)", "ई"), (r"ये(?=\s|$)", "ए"), (r"(?<=[ि-ौ])य(?=े)", ""), ("हुये", "हुए"), ("लिये", "लिए"),
                  ("गयी", "गई"), ("नयी", "नई"), ("आयी", "आई"), ("चाहिये", "चाहिए"), ("किये", "किए"), ("दिये", "दिए")]

def normalize(text, keep_nukta=True, nasal_equiv=True, variants=True):
    """NFC, precomposed nukta -> base+nukta (ek hi roop), ZWJ/ZWNJ hatao, viraam/punctuation hatao.
    nasal_equiv: ँ aur ं ko ek maano (ASR aksar ं likhta hai). variants: गयी=गई, हुये=हुए..."""
    t = unicodedata.normalize("NFC", text)
    if nasal_equiv: t = t.replace(CHANDRA, ANUSVARA)
    if variants:
        for a, b in SPELL_VARIANTS: t = re.sub(a, b, t)
    out = []
    for c in t:
        if c in PRECOMP_NUKTA: out.append(PRECOMP_NUKTA[c] + (NUKTA if keep_nukta else ""))
        elif c in (ZWJ, ZWNJ): continue
        elif c == NUKTA and not keep_nukta: continue
        else: out.append(c)
    t = "".join(out)
    t = re.sub(r"[।॥,.!?;:\"'“”‘’()\[\]{}\-–—…|]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def split_akshar(word):
    """Akshar (grapheme cluster): vyanjan(+nukta)(+्+vyanjan...)(+matra)(+ं/ँ/ः)  ya  svar(+ं/ँ)."""
    out, i, n = [], 0, len(word)
    while i < n:
        c = word[i]
        if is_cons(c):
            j = i + 1
            if j < n and word[j] == NUKTA: j += 1
            while j + 1 < n and word[j] == VIRAMA and is_cons(word[j + 1]):
                j += 2
                if j < n and word[j] == NUKTA: j += 1
            if j < n and word[j] == VIRAMA: j += 1            # aakhri halant (विद्वान्)
            if j < n and is_matra(word[j]): j += 1
            while j < n and is_mod(word[j]): j += 1
            out.append(word[i:j]); i = j
        elif is_vowel(c):
            j = i + 1
            while j < n and is_mod(word[j]): j += 1
            out.append(word[i:j]); i = j
        else:
            out.append(c); i += 1
    return out

def tokens(text, keep_nukta=True, nasal_equiv=True):
    """Line -> [(akshar, shabd_index)] ; shabd ke beech koi token nahi (alignment shabd-aware rehta hai)."""
    toks = []
    for wi, w in enumerate(normalize(text, keep_nukta, nasal_equiv).split()):
        for a in split_akshar(w): toks.append((a, wi))
    return toks

# ---------------------------------------------------------------- phonetic features (vyanjan)
#                 place, voiced, aspirated
F = {}
for row, place in (("कखगघङ", "kanth"), ("चछजझञ", "talu"), ("टठडढण", "murdha"), ("तथदधन", "dant"), ("पफबभम", "oshth")):
    for k, (vo, asp) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1), (1, 0)]):
        F[row[k]] = (place, vo, asp, "nasal" if k == 4 else "stop")
for c, f in {"य": ("talu", 1, 0, "semi"), "र": ("murdha", 1, 0, "liquid"), "ल": ("dant", 1, 0, "liquid"), "व": ("oshth", 1, 0, "semi"),
             "श": ("talu", 0, 0, "ushm"), "ष": ("murdha", 0, 0, "ushm"), "स": ("dant", 0, 0, "ushm"), "ह": ("kanth", 1, 1, "ushm")}.items():
    F[c] = f
MURDHA_DANT = {frozenset(p) for p in (("ट", "त"), ("ठ", "थ"), ("ड", "द"), ("ढ", "ध"), ("ण", "न"))}
LONG_PAIRS = {frozenset(p) for p in (("ि", "ी"), ("ु", "ू"))}

def parts(ak):
    """Akshar -> (consonants list, nukta flags, matra, nasal mod, svar)."""
    cons, nuk, matra, mod, vow = [], [], "", "", ""
    i = 0
    while i < len(ak):
        c = ak[i]
        if is_cons(c):
            cons.append(c); nuk.append(i + 1 < len(ak) and ak[i + 1] == NUKTA)
        elif is_matra(c): matra = c
        elif is_mod(c): mod += c
        elif is_vowel(c): vow = c
        i += 1
    halant_end = ak.endswith(VIRAMA)
    return cons, nuk, matra, mod, vow, halant_end

def classify(exp, got):
    """Do akshar ka fark -> kism (Hindi naam) + chhota samjhaav."""
    if got is None: return "chhoota", f"'{exp}' bola hi nahi gaya"
    if exp is None: return "faltu", f"'{got}' zyada bola gaya"
    ce, ne, me, de, ve, he = parts(exp); cg, ng, mg, dg, vg, hg = parts(got)
    if ve or vg:
        if ve and vg and ve != vg: return "matra", f"svar '{ve}' ki jagah '{vg}'"
        if bool(ve) != bool(vg): return "vyanjan", f"'{exp}' ki jagah '{got}'"
    if len(ce) != len(cg): return "sanyukt", f"sanyukt akshar '{exp}' -> '{got}'"
    for a, b, na, nb in zip(ce, cg, ne, ng):
        if a == b and na != nb: return ("nukta-flap" if a in "डढ" else "nukta"), f"'{a}{'़' if na else ''}' ki jagah '{b}{'़' if nb else ''}' (nukta)"
        if na and not nb and a in "डढ" and b in "डढ":
            return "nukta-flap", f"'{a}़' (jeebh ka jhatka/flap) ki jagah '{b}'"
        if a != b:
            fa, fb = F.get(a), F.get(b)
            if frozenset((a, b)) == frozenset(("व", "ब")): return "va-ba", "व/ब ka fark"
            if frozenset((a, b)) in MURDHA_DANT: return "murdhanya", f"'{a}' -> '{b}' (jeebh ki jagah: murdha/dant)"
            if fa and fb and fa[3] == "ushm" and fb[3] == "ushm" and "ह" not in (a, b): return "ushm", f"'{a}' -> '{b}' (श/ष/स)"
            if fa and fb and fa[0] == fb[0] and fa[3] == fb[3] == "stop":
                if fa[1] == fb[1] and fa[2] != fb[2]: return "mahapraan", f"'{a}' -> '{b}' ({'saans (h) gayi' if fa[2] else 'saans zyada'})"
                if fa[2] == fb[2] and fa[1] != fb[1]: return "ghosh", f"'{a}' -> '{b}' (ghosh/aghosh)"
                return "mahapraan", f"'{a}' -> '{b}' (ghosh aur saans dono badle)"
            return "vyanjan", f"'{a}' -> '{b}'"
    if me != mg:
        if me and mg and frozenset((me, mg)) in LONG_PAIRS: return "matra-lambai", f"matra '{me}' -> '{mg}' (chhoti/lambi)"
        if not me or not mg: return "schwa", f"matra {'gayi' if me else 'aa gayi'}: '{exp}' -> '{got}'"
        return "matra", f"matra '{me}' -> '{mg}'"
    if de != dg or he != hg:
        return "anunasik" if (ANUSVARA in de + dg or CHANDRA in de + dg) else "schwa", f"'{exp}' -> '{got}'"
    return "vyanjan", f"'{exp}' -> '{got}'"

def _sub_cost(a, b):
    if a == b: return 0.0
    ca, _, ma, *_ = parts(a); cb, _, mb, *_ = parts(b)
    if ca and ca == cb: return 0.5          # sirf matra/nukta/anunasik ka fark
    return 1.0

def align(expected, heard, keep_nukta=True, nasal_equiv=True):
    """Akshar-level Levenshtein; shabd ki seema ka dhyan. Returns ops list [(exp_tok, heard_tok)]."""
    E, H = tokens(expected, keep_nukta, nasal_equiv), tokens(heard, keep_nukta, nasal_equiv)
    n, m = len(E), len(H)
    D = [[0.0] * (m + 1) for _ in range(n + 1)]; B = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1): D[i][0], B[i][0] = i, "d"
    for j in range(1, m + 1): D[0][j], B[0][j] = j, "i"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c = _sub_cost(E[i - 1][0], H[j - 1][0])
            opts = [(D[i - 1][j - 1] + c, "s"), (D[i - 1][j] + 1, "d"), (D[i][j - 1] + 1, "i")]
            D[i][j], B[i][j] = min(opts)
    ops, i, j = [], n, m
    while i > 0 or j > 0:
        b = B[i][j]
        if b == "s": ops.append((E[i - 1], H[j - 1])); i, j = i - 1, j - 1
        elif b == "d": ops.append((E[i - 1], None)); i -= 1
        else: ops.append((None, H[j - 1])); j -= 1
    return ops[::-1], E, H

# Pakki galti (hard) = line dobara banao. Shak (soft) = darj karo, line mat roko (ASR ki likhai bhi ho sakti hai).
SEVERITY = {"nukta": "soft", "matra-lambai": "soft", "anunasik": "soft", "va-ba": "soft"}

def _merge_schwa(ops):
    """कमला -> कम्ला: ('म','म्ला') + ('ला',None) = ek galti: 'म' ka 'अ' gaya (schwa)."""
    out, k = [], 0
    while k < len(ops):
        e, h = ops[k]
        if e and h and k + 1 < len(ops) and ops[k + 1][0] and ops[k + 1][1] is None:
            nxt = ops[k + 1][0][0]
            if h[0] == e[0] + VIRAMA + nxt:
                out.append((e, (e[0] + VIRAMA, h[1]), "schwa")); out.append((ops[k + 1][0], ops[k + 1][0], None)); k += 2; continue
        out.append((e, h, None)); k += 1
    return out

def compare(expected, heard, keep_nukta=True, nasal_equiv=True):
    """Poori jaanch: akshar galtiyan (hard/soft) + CER + shabd jinme galti."""
    ops, E, H = align(expected, heard, keep_nukta, nasal_equiv)
    words = normalize(expected, keep_nukta, nasal_equiv).split()
    errs = []; last_w = 0
    for e, h, forced in _merge_schwa(ops):
        if e is not None: last_w = e[1]
        ea, ha = (e[0] if e else None), (h[0] if h else None)
        if ea == ha: continue
        kind, why = (forced, f"'{ea}' ka 'अ' gayab (jaise {ha}…)") if forced else classify(ea, ha)
        w = words[last_w] if words else ""
        errs.append({"word": w, "word_i": last_w, "expected": ea, "heard": ha, "kind": kind, "why": why,
                     "severity": SEVERITY.get(kind, "hard")})
    hard = [e for e in errs if e["severity"] == "hard"]
    cer = len(hard) / max(1, len(E))
    bad_words = sorted({e["word_i"] for e in hard})
    return {"cer": round(cer, 3), "cer_all": round(len(errs) / max(1, len(E)), 3), "akshar": len(E), "errors": errs,
            "hard": len(hard), "soft": len(errs) - len(hard),
            "bad_words": [words[i] for i in bad_words if i < len(words)], "wer": round(len(bad_words) / max(1, len(words)), 3)}

KIND_HINDI = {
    "mahapraan": "महाप्राण (ख/घ/छ/झ/ठ/ढ/थ/ध/फ/भ की 'ह' साँस)", "ghosh": "घोष/अघोष (क/ग, त/द…)",
    "murdhanya": "मूर्धन्य/दंत्य (ट/त, ड/द, ण/न)", "ushm": "ऊष्म (श/ष/स)", "nukta": "नुक़्ता (ज़/फ़/क़/ख़/ग़/ड़/ढ़)",
    "va-ba": "व/ब", "matra-lambai": "मात्रा छोटी/लंबी (ि/ी, ु/ू)", "matra": "मात्रा", "schwa": "'अ' (स्वर का आना/जाना)",
    "anunasik": "अनुनासिक (ं/ँ)", "nukta-flap": "ड़/ढ़ (उत्क्षिप्त — जीभ का झटका)", "sanyukt": "संयुक्त अक्षर (क्ष, त्र, ज्ञ, ्)", "vyanjan": "व्यंजन बदला",
    "chhoota": "अक्षर छूटा", "faltu": "अक्षर ज़्यादा",
}


LONG_MATRA = set("ाीूेैोौ")
def matra_units(text):
    """Hindi chhand ki laghu-guru ginti: chhota svar = 1, lamba svar / ं / ः / sanyukt se pehle = 2.
    Raftaar naapne ke liye akshar se behtar (alag vaakyon me phailav aadha)."""
    u = 0
    for w in normalize(text).split():
        aks = split_akshar(w)
        for k, a in enumerate(aks):
            guru = (any(c in LONG_MATRA for c in a) or ANUSVARA in a or VISARGA in a
                    or any(c in "आईऊएऐओऔ" for c in a) or (k + 1 < len(aks) and VIRAMA in aks[k + 1][:3]))
            u += 2 if guru else 1
    return u
