# v5 — dono ka nichod (tumhara v3.5 + mera v4)

20 Nov 2026 · **50 tests pass, 1 skip** (torch wala, kyunki is machine par torch nahi)

## Tumhare v3.5 se liya (yeh majboot tha, mera kamzor)
| Cheez | Kyun rakha |
|---|---|
| `tools/consent.py` + `record_consent` | ijazat ka alag record — mere me sirf flag tha |
| `tools/speaker_verification.py` (SpeechBrain ECAPA) | asli identity naap, mere MFCC se behtar |
| `add-emotion-reference` + same-speaker attestation | bhaav ka sample, par sirf usi insaan ka |
| `voice_fingerprint` (resume invalidate) | prompt badla to purana chunk reuse nahi hota |
| `script_pipeline.py` | script → lines (multi-speaker, tags) |
| atomic json + path traversal check | crash par file kharab nahi hoti, `..` se bachav |
| retries + stitch + manifest | lambi script ke liye zaroori |
| `preflight`, `audio_qa`, `evaluate_generation` | pehle jaanch, baad me render |
| docs (CHANGELOG, scorecard, research) | hisaab likha rehta hai |

## Mere v4 se liya (yeh tumhare me nahi tha)
| Cheez | Kyun |
|---|---|
| `reference_quality()` gate | chhoti/kam-bolne wali recording par **warn**, `ASTRA_STRICT_REF=1` par **block** |
| `best_windows()` multi-window extract | ek clip se kai saaf hisse (multi-reference ke liye) |
| transcript optional → xtts | **koi bhi recording** chalegi, script ki zaroorat nahi (par tabhi jab xtts ready ho) |
| `audit` command | sab voices ka consent + backend ek jagah |
| gate tests + multi-window test | naye niyam test se bandhe hue |

## Jo hataya / kamzor nikla
- **Mera MFCC-based `voice_match`** — tumhare ECAPA ke saamne kamzor; sirf fallback ke roop me rakha (jab speechbrain na ho).
- **Mera `asetrate` pitch-shift wala demo tarika** — formant kharab karta hai; `rubberband formant=preserved` hi sahi hai (audio demo me use hua).
- **Duplicate `_render_line`** — tumhara wala hi rakha (emotion reference support ke saath).
- **`.pyc` files** zip me nahi rakhni chahiye — hata diya.

## Niyam (dono me se sakht wala)
1. Consent ke bina enroll nahi.
2. 100% copy ka dawa nahi — ECAPA cosine + honest warning.
3. Transcript ke bina sirf xtts; indicf5 ko exact transcript lazmi.
4. Reference kamzor ho to warn (strict mode me block).
