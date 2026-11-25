# Awaaz naturalness — naap kar chuni gayi setting (21 Nov 2026)

## A/B test (6 variant, asli Sarvam calls, runner par)
| Variant | F0 std (sur ka utar-chadhav) | Raftaar | Chupai |
|---|---|---|---|
| **v3 ishita t0.75** | **67.0** ← sabse expressive | 13.56 akshar/s | 24.7% |
| v3 suhani t0.75 p1.05 | 62.9 | 13.73 | 19.3% |
| v3 priya t0.85 | 55.9 | 13.05 | 22.8% |
| v3 priya t0.6 | 52.6 | 12.13 | 20.6% |
| v4-flash (default) | 56.0 | 11.71 | 25.9% |

**Chuni gayi:** dadi = **ishita**, baccha = **tanya**, temperature bhaav ke hisaab se (0.70–0.85).

## v3 vs v4 (asli file ka naap)
| | v3 (purana) | v4 (naya) |
|---|---|---|
| F0 std | ±52.2 Hz | **±69.4 Hz** (+33% zyada expressive) |
| Duration | 31.6 s | 26.8 s (kam khincha hua) |
| Chupai | 5.4% | 5.2% |
| Awaazein | 1 | **2 (dadi + baccha)** |

## Kyun pehle robotic lag raha tha
1. **Temperature 0.6 (default)** = flat, kam expressive → ab 0.75–0.85
2. **8 alag line** = 8 baar prosody restart → ab **6 segment** (ek kirdaar ki lines jodi)
3. **Zyada silenceremove** = "hichki" jaisa → ab halka trim (-50 dB, 0.08 s)

## Sach
- 100% insaan jaisa koi TTS nahi; Sarvam ka expressive mode ab tak ka sabse behtar.
- Aur natural chahiye to **bulbul:v4-flash persona voices** (200+) ya XTTS clone — dono par kaam kar sakti hoon.
