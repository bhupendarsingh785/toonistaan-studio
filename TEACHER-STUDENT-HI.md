# ElevenLabs se seekhne wala system — haan, ban sakta hai (imaandari se)

## Sach: kya milta hai, kya nahi
| Cheez | Mil sakta hai? |
|---|---|
| Unki awaaz ka **style** (kis bhaav me kitna sur/raftaar/zor/rukna) | ✅ **haan** — naap kar |
| Har line ka audio (dataset) | ✅ haan — API se |
| Unke settings ka asar (stability/style/speed) | ✅ haan — A/B karke |
| Unka **model / weights** | ❌ **nahi** — band dabba hai, koi API nahi deta |
| Kisiki asli awaaz ki **nakal** | ❌ nahi (aur galat bhi hai) — hum style seekhte hain, shakhs nahi |

## System kaise kaam karta hai (4 step, ban chuka)
```bash
python tools/teacher_student.py plan                 # kitne call, kitna kharcha (12 call = 6 bhaav x 2)
python tools/teacher_student.py collect --lines 12    # ELEVENLABS_API_KEY chahiye
python tools/teacher_student.py learn                # naap se mapping -> astra/learned_style.json
python tools/teacher_student.py dry-run              # bina key pipeline test (piper se)
```
1. **collect** — 6 bhaav (neutral, dukh, gussa, khushi, dar, pyaar) ki line API se; audio + settings save.
2. **measure** — asli naap: **sur (F0 Hz)**, **raftaar (akshar/second)**, **zor (RMS)**, **chup**.
3. **learn** — neutral ke muqable har bhaav ka ratio → `astra/learned_style.json`.
4. **apply** — `voice_provider._bhaav_style()` ab **pehle seekha hua** dekhta hai, phir default. Matlab **piper/espeak/edge** bhi ElevenLabs jaisa bhaav dene lagte hain — bina unki key ke.

## Abhi ka naap (dry-run, piper se pipeline test)
| Bhaav | pitch | pace | energy |
|---|---|---|---|
| neutral | 1.00 | 1.00 | 1.00 |
| gussa | 0.93 | **1.30** | **1.18** |
| dukh | 0.88 | 1.04 | 0.98 |
| dar | 0.91 | **1.43** | 1.02 |

Pipeline sach me chalta hai. Asli numbers ElevenLabs ki lines se aayenge.

## Kharcha (tumhara balance bachega)
- 12 call = 12 chhoti line (~420 akshar). Bas itna kaafi hai seekhne ke liye.
- `plan` pehle batata hai, phir `collect` chalta hai — andaza nahi.

## Baad me ElevenLabs hata dena
`learned_style.json` ban jaye, to `ELEVENLABS_API_KEY` hata do — engine **piper/espeak/edge** par chalta rahega, style wahi rahega.
