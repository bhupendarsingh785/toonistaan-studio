# Audio Read v2 — audio ko theek se padhna (21 Nov 2026)

Pehle wala system sirf "average" nikalta tha. Ab **kab, kya, kaun, kitni der** — sab.

## Kya naya hai
| Hissa | Kya batata hai |
|---|---|
| **SEGMENTS** | speech vs chupai ke hisse, har hisse ka time (0.7s–1.4s bol, 1.4–2.0 chup…) |
| **TURNS** | F0 se voice cluster — kaun bol raha hai (A bhaari / B halka), kab se kab tak, kitne Hz par |
| **EVENTS** | background ki awaazein: **kab** (sec), **kaisi** (thud/impact, hiss/noise, tonal) |
| **BED TIMELINE** | 5-5 second ke tukdon me background ka level aur flatness — kab tez hua |
| **SPEECH QUALITY** | SNR, clipping %, noise floor, pace (syllable/s), pause count/mean/max |
| **ENDING CONTOUR** | vakya ke aakhir me sur girta hai ya uthta (sawaal jaisa) |
| **CAST MATCH** | hamare kirdaaron me kaun sabse kareeb (Hz ke hisaab se) |

## Swag ke `arju111.mp3` ka poora padha hua
- **20 s** · RMS **-26.4 dBFS** · peak 0.26 · **clipping 0%** · SNR **23.3 dB** · noise floor -50.9 dB (saaf recording)
- **Bolne ka hissa 13.4 s**, chupai **5.7 s** — **9 pause** (औसत 0.63 s, sabse lamba 0.96 s)
- **Sur 118 Hz** (range 112–152, variability 9.3) → purush, bhaari; **narrator band (90–125)** me ✅
- **22 speech segments, 18 turns** — matlab bolne me **bahut chhote-chhote tukde** (0.2–0.9 s), yani ruk-ruk kar bolta hai
- **16 background events** (thud/impact type) — matlab recording me halke dhakke/table ki awaaz
- **Ending contour:** sur **upar uthta** (sawaal jaisa)

## Isse hamare liye seekh
1. Uski raftaar ~0.9 syllable/s — **dheemi**; hamare render se dheemi
2. Pause bahut (9 baar / 20 s) — hamare audio me isse **kam** pause rakhenge
3. Sur 118 Hz par **flat** (variability 9.3) — hamare me **temperature zyada** taaki jaan aaye
4. Background uski recording me **thud** hai, bed nahi — hum apne audio me bed **jaan-boojh kar** daalte hain

## Sach
- Ye sab **asli naap** hai (ffmpeg + numpy), andaza nahi.
- "A/B voice cluster" sirf F0 par hai — do logon ke sur bilkul same ho to woh alag nahi batayega.
- Event ka "type" (thud/hiss/tonal) **low vs high frequency energy** se guess hota hai.
