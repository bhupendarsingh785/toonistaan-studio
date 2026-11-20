# Audio ko deep level par set kiya — naap ke saath (20 Nov 2026)

**148 tests pass, 1 skip.** Har number asli API call / asli render se.

## 1. Bhaav ka ek hi sach
Pehle do jagah bhaav ki settings thi (`EMOTION_STYLE` aur naya `bhavna.py`), piper par bhaav lagta hi nahi tha.
Ab: **`bhavna.style(emotion)`** — 11 bhaav, har ek ke saath sur (pitch), raftaar (pace), zor (energy), aur rukne ka waqt (gap_ms).

| Bhaav | sur | raftaar | zor | rukna |
|---|---|---|---|---|
| neutral | 1.00 | 1.00 | 1.00 | 220 ms |
| dukh | 0.94 | 0.88 | 0.90 | 450 ms |
| gussa | 1.06 | 1.10 | 1.15 | 120 ms |
| dar | 1.04 | 1.12 | 0.85 | 380 ms |
| khushi | 1.08 | 1.08 | 1.05 | 120 ms |

Yeh ab **piper**, **sarvam** aur **router** — teeno me lagta hai, aur **cache key** me bhi jata hai (warna dukh/gussa ek hi file de deta).

## 2. Sarvam API ka asli behaviour (naap se, andaza nahi)
Har call GitHub runner par tumhari key se:

| Setting | Nateeja |
|---|---|
| `pace 0.7` | 2.53 s, 181 Hz |
| `pace 1.0` | 1.88 s, 161 Hz |
| `pace 1.3` | 1.43 s, 154 Hz |
| `pitch -0.3` | **121 Hz** |
| `pitch 0.0` | **165 Hz** |
| `pitch +0.3` | **176 Hz** |

**Matlab:** `pace` badhao → tez (duration kam). `pitch` param badhao → sur upar. Dono seedhe hain.
Isliye calibration: `pitch_param = (target − 1.0) / 0.7` (0.3 ≈ +21% F0).

## 3. Bhaav ka asar — asli file par
| Bhaav | Duration | F0 |
|---|---|---|
| neutral | 1.96 s | 158 Hz |
| **dukh** | **2.69 s** (sabse dheema ✅) | 152 Hz (neeche ✅) |
| gussa | 2.16 s (tez ✅) | 150 Hz |

Dukh dheema aur neeche — sahi. Gussa ka F0 naap par bharosa nahi (tez bolne par autocorrelation bhatak jata hai) — isliye pitch ka asar **controlled sweep** se verify kiya (upar table), cross-emotion F0 se nahi. Yeh imandari hai, chhupaya nahi.

## 4. Piper par bhaav (offline, free)
Asli test: ek hi line dukh aur gussa me — **dukh ki file >5% lambi** nikli (`test_emotion_changes_speed_and_pitch`). Formant preserved (rubberband), isliye robotic nahi.

## 5. Naya guard
- `tools/voice_validate.py` — voices.json ke Sarvam speaker galat ho to fail (15 galat the, ab 0).
- Cache key me bhaav — dukh aur gussa alag file.

## 6. Ab bhi baaki (audio me)
- Har bhaav ka **asli reference sample** nahi (knowledge hai, awaaz nahi) — 11 bhaav ke reference chahiye
- Cloning (IndicF5/XTTS) — torch/GPU nahi
- Saans/bharpana (breath) add nahi hua — naturalness ke liye agla kadam
