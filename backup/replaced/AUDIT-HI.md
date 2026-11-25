# Poora system audit — part by part (20 Nov 2026)

**Method:** 980 Python files, dono repo (toonistaan 454 + astra-master 526) — syntax, undefined names, duplicate dict keys, missing imports. Har cheez script se, andaza nahi.

## Pehle (audit se pehle)
| Cheez | Kitni mili |
|---|---|
| Syntax errors | 0 |
| Undefined names | 0 |
| **Duplicate dict keys** | **26** |
| Missing local imports | 1 |

## Kya theek hua (26 duplicate keys — data chup-chaap gir raha tha)
| File | Dikkat | Hal |
|---|---|---|
| `astra/library.py` VARIANTS | 10 keys duplicate (`vinyl`, `jungle`, `magic`, `transition`, `dragon`…) → **baad wali list pehli ko kha jaati thi** | lists **merge** (union) — 240 variants bache |
| `astra/real_audio.py` | 4 keys (`footsteps`, `rain`, `wind`, `fire`) | naye naam: `footsteps_indoor`, `rain_heavy`, `wind_blowing`, `fire_crackling` — 54 terms |
| `astra/hindi_natural.py` | `raat`, `chalo` do baar | duplicate hataya |
| `tools/hindi_speech_normalizer.py` | 8 keys (`chahiye`, `jaldi`, `phir`…) | duplicate hataye |
| `engines/*/performance.py` (chaar) | `";"` do baar — **full-width `；` kho raha tha** | `"；"` alag key |
| `tools/predict_sound.py` | `features` module hi nahi tha | `audio_features_v22` se import |

## Ab (audit ke baad)
**0 syntax · 0 undefined · 0 duplicate dict key · 0 missing import** — dono repo.

## Tests
- toonistaan: **168 pass, 1 skip**
- astra-master mesh: 3 pass

## Ek false positive bhi pakda
`key_guard` apne hi test ki nakli key ko leak bata raha tha → ab `tests/` skip + `abc/xyz/fake/test…` se shuru hone wali value ignore. Scan: **2775 files, 0 leak**.

## Sach: ab bhi kamzori
1. **Cognition** (skeptic + decision gate) mesh me nahi — data aata hai, par "sach hai ya nahi" ka faisla nahi hota.
2. **Domain diversity** kam (2–4) — 5 source hain, par khabar ke link Google News ke hote hain.
3. **Semantic duplicate** (same baat alag shabdon me) nahi pakadta — sirf URL+sha.
4. **Piper ke liye bachcha/old voice** ka model nahi (dadi ke liye pitch-shift).
5. **elevenlabs key** ke bina woh engine band.
