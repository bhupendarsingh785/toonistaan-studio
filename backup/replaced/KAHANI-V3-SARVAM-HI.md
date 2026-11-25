# Kahani v3 — Sarvam ki asli awaaz (21 Nov 2026)

## Kya badla (robotic/ruka-ruka ka hal)
| Pehle | Ab |
|---|---|
| edge TTS (robotic) | **Sarvam bulbul:v3** (insaan jaisa Hindi) |
| 8 alag line = 8 baar prosody restart | **ek hi continuous render** (koi beech ka break nahi) |
| bhaav se rate -12% (dheema = ruka-ruka) | **SARVAM_NATURAL=1**: pace sirf **0.94–1.12**, pitch **±0.1** |
| line ke aage-peeche chupai | `silenceremove` trim |

## Naap
- **31.6 s**, RMS **-18.6 dBFS**, silence **5.4%**, ek hi line (0 break)
- Background: jungle + barish bed (duck ke saath), foley: kadam, garaj, chidaiyan

## Kaise chalaya (runner par, key sandbox me nahi hoti)
`.github/workflows/story-sarvam.yml` → `STORY_ENGINE=sarvam` → artifact → download.

## Sach
- Sarvam **coin kharch** karta hai (ek render ~500 akshar). 3 key rotation chalu hai.
- 100% insaan jaisa koi TTS nahi deta; Sarvam ab tak ka **sabse natural** hai jo hamare paas chalta hai.
