# Galti report — kahani-2

Engine **espeak** · 8 line · 126 akshar · PASS 6/8
Pakki galti: pehle 2 (CER 0.016) → sudhaar ke baad **2** (CER 0.016)
Sudhri lines: 2 · samay 1.7 s (audio 22.6 s)

## Line-war

| # | Kaun | Galti (pehle) | Sudhaar | Nateeja |
|---|---|---|---|---|
| 1 | narrator | जल्दी: ल्दी→ल्दि (matra-lambai, shak); नदी: दी→दि (matra-lambai, shak); की: की→कि (matra-lambai, shak) | — | ✓ |
| 2 | narrator | पानी: नी→नि (matra-lambai, shak) | — | ✓ |
| 3 | narrator | अपनी: नी→नि (matra-lambai, shak); खोली: ली→लि (matra-lambai, shak) | — | ✓ |
| 4 | dadi | — | — | ✓ |
| 5 | narrator | — | — | ✓ |
| 6 | raju | दादी: दी→दि (matra-lambai, shak); की: की→कि (matra-lambai, shak); कहानी: नी→नि (matra-lambai, shak); क्षत्रिय: क्ष→छ (sanyukt); की: की→कि (matra-lambai, shak) | uchcharan:क्ष ANSULJHA (engine kamzor — doosra engine aazmao) | ✗ क्ष |
| 7 | narrator | दादी: दी→दि (matra-lambai, shak); विशेष: ष→श (ushm); कहानी: नी→नि (matra-lambai, shak) · raftaar 13.89≠11.13; chamak 2226≠1787 | raftaar:rate 0.80, chamak:-1.3dB, uchcharan:ष ANSULJHA (engine kamzor — doosra engine aazmao) | ✗ ष |
| 8 | narrator | — · chamak 2363≠1787 | — | ✓ |

## Galti-bahi (yaad: kaun sa akshar kamzor)

### espeak/dadi

Lines: 3 · akshar bole: 41

**Sabse kamzor akshar (pakki galti):**

| Akshar | Ban jaata hai | Kism | Galti / bola | Shabd |
|---|---|---|---|---|
| खा | का | महाप्राण (ख/घ/छ/झ/ठ/ढ/थ/ध/फ/भ की 'ह' साँस) | 3/6 | खा, खाओ, खाना |

**Kism-war:** महाप्राण 3

**Kaunsa sudhaar kaam aaya:**

- महाप्राण: h-spell 3/3

**Pichhli kahaniyan (CER, pakki galti):** 0.111/3 → 0.000/0

### espeak/narrator

Lines: 13 · akshar bole: 210

**Sabse kamzor akshar (pakki galti):**

| Akshar | Ban jaata hai | Kism | Galti / bola | Shabd |
|---|---|---|---|---|
| षा | शा | ऊष्म (श/ष/स) | 1/1 | भाषा |
| ढ़ा | डा | ड़/ढ़ (उत्क्षिप्त — जीभ का झटका) | 1/1 | पढ़ाई |
| ष | श | ऊष्म (श/ष/स) | 1/1 | विशेष |

**Kism-war:** मात्रा छोटी/लंबी 12 · ऊष्म 2 · नुक़्ता 1 · ड़/ढ़ 1

**Kaunsa sudhaar kaam aaya:**

- मात्रा छोटी/लंबी: matra-swap 0/3
- नुक़्ता: nukta-decomp 1/1
- ऊष्म: viraam 0/1, dheema 0/1, viraam+dheema 0/1
- ड़/ढ़: nukta-decomp 1/1

**Pichhli kahaniyan (CER, pakki galti):** 0.017/2 → 0.011/1

### espeak/raju

Lines: 2 · akshar bole: 34

**Sabse kamzor akshar (pakki galti):**

| Akshar | Ban jaata hai | Kism | Galti / bola | Shabd |
|---|---|---|---|---|
| क्ष | छ | संयुक्त अक्षर (क्ष, त्र, ज्ञ, ्) | 2/2 | क्षत्रिय, क्षमा |

**Kism-war:** मात्रा छोटी/लंबी 5 · संयुक्त अक्षर 2

**Kaunsa sudhaar kaam aaya:**

- संयुक्त अक्षर: sanyukt-alt 0/2, viraam 0/1, dheema 0/1

**Pichhli kahaniyan (CER, pakki galti):** 0.071/1 → 0.050/1

## Shabdkosh (seekhi likhai — agli baar render se pehle lagegi)

- `espeak/dadi`: **खाना** → bulwao **क्हाना** (mahapraan, tareeka h-spell)
- `espeak/dadi`: **खा** → bulwao **क्हा** (mahapraan, tareeka h-spell)
- `espeak/dadi`: **खाओ** → bulwao **क्हाओ** (mahapraan, tareeka h-spell)
- `espeak/narrator`: **ज़मीन** → bulwao **ज़मीन** (nukta, tareeka nukta-decomp)
- `espeak/narrator`: **पढ़ाई** → bulwao **पढ़ाई** (nukta-flap, tareeka nukta-decomp)