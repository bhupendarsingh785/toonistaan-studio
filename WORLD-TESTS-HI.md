# Duniya ke tarike se testing — hazaaron combination (21 Nov 2026)

**198 tests pass · 2 skip · system_check 19/19 · matrix + world battery: 0 problem (chaaron engine)**

## Do naye tools

### 1. `tools/test_matrix.py` — combination explosion
- **Equivalence partitioning**: text 8 hisson me (tiny, short, medium, long, numbers, mixed, emoji, punctuation)
- **Boundary value**: 1, 199, 200, 201, 900 akshar (API limits ke kinare)
- **Combinatorial**: engine × text × bhaav × format — random sample (jitne chaho: `--combos 2000`)
- **Metamorphic**: dukh > gussa (dheema/tez), punctuation se shabd na badle
- **Golden master**: ek line ka naap yaad, badla to pakdo
- **Property-based**: ok ⇒ file hai, dur > 0.15 s, RMS > 0.005, header sahi
- **Chaos**: khaali text, "।।।", galat engine, galat bhaav

### 2. `tools/world_tests.py` — industry/AI style
| Tarika | Kya pakadta hai |
|---|---|
| **Differential** | chaar engine ek hi line — koi 3x se ajeeb ho to flag |
| **Soak** | 15–25 lines lagataar — dheemapan/leak |
| **Pairwise** | engine × format × bhaav ka coverage % |
| **Mutation-lite** | kharab cache file system reject karta hai ya nahi |
| **Regression** | purane golden naap se tulna |
| **Risk-based** | sabse khatarnak 5 case pehle (lamba, khaali, bad engine, mp3, parallel 6) |

## Mile 4 bug (is round me)
| # | Bug | Hal |
|---|---|---|
| 1 | **`.mp3` maangne par WAV bytes** (espeak/piper) | `_fix_format()` — **asli header** dekhta hai (extension par bharosa nahi), ffmpeg se convert |
| 2 | **chhota text (1 akshar / "हाँ।") fail** — quality gate 0.35 s maangta tha | min 0.08 s (text ke hisaab se) |
| 3 | **piper long text par traceback ka dher** | chup-chaap fail + CLI fallback |
| 4 | **piper parallel fail par kuch nahi hota tha** | fail hone par seedha CLI (bharosa) |

## Nateeja
| Engine | matrix | differential | soak | pairwise | mutation | regression | risk |
|---|---|---|---|---|---|---|---|
| free | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| espeak | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| piper | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| edge | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Sach
- Matrix ka sample random hai — `--combos 2000 --seed 7` se hazaaron combination chal sakte hain (waqt zyada lagega).
- Ye **functional** testing hai; "kitni natural lagti hai" woh sun kar hi pata chalega (MOS test insaan se hota hai).
