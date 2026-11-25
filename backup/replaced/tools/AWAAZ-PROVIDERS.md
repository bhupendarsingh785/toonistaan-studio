# Awaaz ke raste (voice providers)

## Kram
1. **ElevenLabs** — sabse insan jaisi awaaz (free 10k akshar/mahina). Key: `ELEVENLABS_API_KEY`
2. **edge-tts** — Microsoft neural Hindi (free, hamesha chalta hai, key nahi chahiye)

Key na ho to sab kuch pehle jaisa chalta rahega — koi crash nahi.

## ElevenLabs key (free)
1. https://elevenlabs.io/app/settings/api-keys → login → **Create API key** → copy
2. GitHub → Settings → Secrets and variables → Actions → **New repository secret**
   Name: `ELEVENLABS_API_KEY`
3. Bas — ab har line pehle ElevenLabs se banegi, fail hone par edge-tts.

## Kirdaar -> voice
| kirdaar | voice | speed |
|---|---|---|
| madhur | male_adult (Adam) | 0.92 |
| swara | female_adult (Sarah) | 0.95 |
| swara_bachcha | female_young (Charlotte) | 1.06 |
| madhur_bachcha | male_young (Liam) | 1.06 |
| swara_dadi | female_old (Lily) | 0.88 |
| madhur_dada | male_old (Daniel) | 0.88 |

Apni voice id dena ho to env: `ELEVEN_VOICE_MADHUR`, `ELEVEN_VOICE_SWARA` (aur aage).

## Free quota ka hisaab
10,000 akshar/mahina = lagbhag **15-20 minute** ki kahani. Bada kaam ho to:
- chhoti lines pe edge-tts, hero lines pe ElevenLabs
- ya plan upgrade

## Module
```python
import voice_provider
voice_provider.have_eleven()          # key hai?
voice_provider.eleven_tts("नमस्ते", "swara_bachcha", "out.mp3")
```
