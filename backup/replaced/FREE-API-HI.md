# Free API — bina key wali TTS jud gayi (21 Nov 2026)

**system_check: 19/19 ✅ · tests: 174 pass, 2 skip**

## Jo abhi chalta hai (asli test, bina key)
| Engine | Kaise | Naap |
|---|---|---|
| **free (Google Translate TTS)** | `translate.google.com/translate_tts` | **0.9 s, 16–44 KB** ✅ |
| piper | offline neural | 5.4 s ✅ |
| espeak | espeakng-loader | ✅ |
| edge | Microsoft | 0.9 s ✅ |
| elevenlabs | key chahiye | optional |

## Naya `tools/free_api.py`
- **Ek hi darwaza** — nayi free API jodni ho to `PROVIDERS` me ek function, bas.
- Lambe text ko **200 akshar ke tukdon** me todta hai, phir jodta hai (Google ki limit).
- **Bhaav lagta hai**: raftaar `atempo`, sur `rubberband (formant preserved)`, zor `volume` — dukh dheema, gussa tez.
- `python tools/free_api.py "नमस्ते" --bhaav dukh --out x.mp3`

## Router me
`engine="free"` — ab chaar bina-key engine: **free, piper, espeak, edge**.

## Agar tum koi aur free API jodna chaho
1. Key ho to **GitHub secret** me daalo (chat me nahi).
2. Mujhe naam bata do — main `PROVIDERS` me adapter likh dungi + asli test + tests.
   Jaise: `SARVAM_API_KEY` (free tier), Hugging Face free, Cloudflare Workers AI, Gemini TTS.

## Sach
- Google Translate TTS **free hai par unofficial** — bahut zyada lambi line ek saath mat bhejo (tukdon me jaata hai).
- Awaaz robotic-ish hai (bhaav se sudharta hai, par piper/edge se kam natural).
