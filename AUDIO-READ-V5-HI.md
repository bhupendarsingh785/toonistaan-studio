# Audio Read v5 — recheck + 6 bug fix + gehra kiya (21 Nov 2026)

## Recheck me mile 6 bug (sab theek ho gaye)
| # | Bug | Kya hota tha | Fix |
|---|---|---|---|
| 1 | **VAD over-segmentation** | 150 "turns" bana raha tha (pause ko turn samajh raha tha) | min turn **0.6 s** + **0.5 s** se chhote gap jod diye |
| 2 | **Steady awaaz par threshold** | pure tone/music par threshold signal se **upar** chala jata → 0 turns | `thr = min(p15×2, mean×0.55)` |
| 3 | **Separation sab background me** | tone/music wali file me speech stem khaali, analysis fail | speech stem < 25% ho to **original** par padho |
| 4 | **Events background me chhup jaate** | click/thud background me chala jata → event miss | events **original** par + `in_background` flag |
| 5 | **Pace galat** | 48.61 "syl/s" (formula hi galat tha) | energy-peak syllable count, min 0.12 s gap |
| 6 | **Mahaul ka naap galat** | background -52 dB dikha kar "bahut dheema" bol deta | ambience = original ke **chup frames** ka level (15th percentile) |

## Naya (v4 se aage)
- **Wiener-style soft mask** stems (musical noise kam) + over-subtraction 1.6 + smoothing
- **Harmonicity** (spectrum autocorrelation) se music ka faisla — ab flatness akela nahi
- **Krumhansl templates** se **key + scale** (major/minor) + confidence
- Per-turn: **F0, F1/F2 (LPC), pace, zor (dB), bhaav**
- **Self-test** (`--selftest`): 5 synthetic case — tone, silence, 2-turn, clicks, harmonic. **5/5 pass**

## Asli naap (v5)
### Swag ka `arju111.mp3`
- Awaaz **-26.8 dB**, ambience **-48.6 dB** → farq **25.7 dB** = **background lagbhag nahi** (saaf recording)
- **8 turns**, **14.8 s bol**, 7 pause, gap औसत 0.51 s
- Music: harmonicity 0.716, **B major** (confidence 0.83), tempo 166 — par **music_likely = False** (speech 74%)
- **19 events** (thud/impact type)

### Hamara `jungle-nadi-safar-v8.mp3`
- Awaaz **-18.7 dB**, ambience **-40.8 dB** → farq **25.2 dB** — **background bahut dheema** (10–12 dB hona chahiye)
- **70 turns** (150 se aaya, par abhi bhi zyada), 68 s bol, gap max **5.56 s**
- Music: harmonicity 0.786, **B major** (0.64), flatness 0.307
- **Sudhaar chahiye:** bed ka level **+10 dB** badhao, aur gaps chhote karo

## Kami jo abhi bhi hai (sach)
1. 70 turns — hamare render me foley events speech ko tod rahe hain (VAD abhi bhi confuse hota hai)
2. Stem separation **spectral** hai (AI model jaisa clean nahi)
3. Do logon ka sur same → diarization fail
4. Key guess music ke chhote hisse par bhi badal sakta hai
