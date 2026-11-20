# Voice Clone — video/audio se awaaz nikaalo, phir usi awaaz me poori kahani

Teen module milkar kaam karte hain:

| File | Kaam |
|---|---|
| `tools/voice_extract.py` | video/audio se awaaz nikaalta hai, shor kam karta hai, sabse saaf 5-15 s chunta hai |
| `tools/voice_clone.py` | us awaaz ko enroll karta hai aur script ki har line usi awaaz me bolta hai (bhaav ke saath) |
| `tools/voice_match.py` | "kitna match hua" ka imandar naap (F0 + timbre) |

## 1. Video se awaaz nikaalo

```bash
python tools/voice_extract.py run --in dadi.mp4 --out voices/dadi --seconds 12
```
- audio nikalta hai (ffmpeg)
- shor kam: `highpass=90, afftdn, loudnorm`
- sabse saaf window chunta hai (bolne ka hissa zyada, shor kam)
- `reference.wav` + `extract.json` (transcript ke saath, agar faster-whisper mile)

## 2. Enroll (ijazat ke saath)

```bash
# seedha video se
python tools/voice_clone.py enroll --name dadi --from-media dadi.mp4 \
  --transcript "नमस्ते, मैं दादी हूँ। तुम आ जाओ, खाना ठंडा हो रहा है।" --consent

# ya pehle se bani reference se
python tools/voice_clone.py enroll --name dadi --audio reference.wav --transcript "..." --consent
```
**Bina `--consent` enroll nahi hota** — awaaz uski hi ho ya likhit permission ho.

## 3. Poori script usi awaaz me (bhaav ke saath)

Script me bhaav square bracket me likho:

```
[neutral] शाम ढल रही थी।
[dukh] बेटा, आ जा पास। दादी तेरे को ही ढूँढ रही थी।
[gussa] चुप रहो! कुछ मत बोलो।
[dar] कौन है वहाँ?
[hasai] देखो ना, कितनी बड़ी तितली!
```

```bash
python tools/voice_clone.py speak --name dadi --script story.txt --out output/dadi/
```
Har line ka file banta hai: `001_neutral.wav`, `002_dukh.wav`, …

## 4. Match check (imandar)

```bash
python tools/voice_match.py check --ref reference.wav --new output/dadi/002_dukh.wav
```
Batata hai: sur ka farq (Hz aur %), timbre cosine, aur verdict — saath me saaf warning ki yeh pehchaan ka saboot nahi.

## 5. Sach (jhooth nahi)

- **100% copy koi system nahi deta.** Achhe cloning models ~90-95% "suni jaane wali" similarity dete hain, aur woh reference ki quality par nirbhar hai.
- Cloning backend chahiye: **IndicF5** (free, GPU) ya **XTTS-v2** (`pip install TTS`). Abhi is machine par dono nahi — code taiyar hai, engine nahi.
- Background shor wali recording se copy kamzor aati hai — `voice_extract` usi ko sudharta hai.

## 6. Tests
`python -m pytest tests -q` → **68 pass** (clone, extract, match — sab ke apne test).

## 7. v3 me naya kya (20 Nov 2026)

| Naya | Fayda |
|---|---|
| **Quality gate** | 3 second se chhoti ya kam-bolne wali recording enroll hi nahi hoti — "reference theek nahi: bahut chhoti (1.0s)" jaisa saaf message |
| **Multi-reference** | `add-reference --emotion dukh` — usi awaaz ka doosra sample. Bhaav ke hisaab se sahi sample chuna jata hai |
| **Bhaav ke hisaab se reference** | `[dukh]` line ke liye dukh wala sample, na ho to neutral |
| **Lambi line chunking** | 180 akshar se lambi line sentence par tootti hai (clone models ki limit) |
| **Piper fallback (saaf nishan)** | Cloning backend na chale to piper se bolta hai, par file naam me `_piper_fallback` likha jata hai — chhupaya nahi jata |
| **Consent record** | voice.json me kab, kaise ijazat mili — likha jata hai |
| **audit command** | `voice_clone.py audit` — sab voices ka consent status ek jagah |

Naye commands:
```bash
python tools/voice_clone.py add-reference --name dadi --audio dukh.wav \
  --transcript "बहुत तकलीफ़ हो रही है" --emotion dukh
python tools/voice_clone.py audit
```

Tests: **71 pass** (pehle 68 the).

## 8. v4 — koi bhi recording chalegi (script ki zaroorat nahi)

**Niyam badal diya:** ab tum koi bhi recording bhej sakte ho — koi bhi insan kisi bhi baat par bol raha ho. Zaroori nahi ki wahi shabd bole jo maine likhe.

Kaise:

```bash
# 1) video/audio se 3 saaf hisse nikaalo (transcript khud banega, whisper ho to)
python tools/voice_extract.py run --in koi_bhi.mp4 --out voices/meera --windows 3 --seconds 12

# 2) enroll — transcript optional
python tools/voice_clone.py enroll --name meera --from-media koi_bhi.mp4 --consent
#    (transcript na ho to backend xtts khud chun liya jata hai — usko transcript nahi chahiye)

# 3) extra hisse bhaav ke hisaab se jodo
python tools/voice_clone.py add-reference --name meera --audio voices/meera/reference_2.wav \
  --emotion dukh --transcript "अगर whisper se transcript aaya hai to yahan daal do"
```

**Backend ka niyam:**
| Transcript hai? | Backend | Kyun |
|---|---|---|
| haan (whisper ya tumne diya) | indicf5 | usko exact transcript chahiye |
| nahi | xtts | usko sirf audio chahiye |

**Naya flag:** `--no-transcribe` (whisper ko band rakho), `--windows 3` (ek se zyada saaf hisse).

Tests: **73 pass**.
