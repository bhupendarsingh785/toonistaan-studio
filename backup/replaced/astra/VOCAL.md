# Vocal Intelligence (v0.17) — kahan chalega, kahan nahi

## Kya hai
`astra_audio/vocal_intelligence.py` — neural (deep learning) vocal analysis:
- **ASR** (faster-whisper) — awaaz se **text + timestamps**
- **Diarization** (pyannote) — "kitne log bol rahe hain, kab kaun"
- **Embeddings** (SpeechBrain ECAPA) — awaaz ka vector (consistency check)
- **Emotion** (HF model) — bhaav ka andaza (sirf suggestion)
- **Dataset manifest** (`vocal_dataset.py`) — consent ke saath voice data index

## Kahan chalta hai
| Jagah | Chalega? | Kyun |
|---|---|---|
| **Main render** (`cinema.py`) | ❌ | torch/whisper bhaari — Render free par nahi |
| **GitHub Actions — `vocal-check.yml`** | ✅ | manual, alag job, 45 min limit |
| **Local/Colab (GPU)** | ✅ | best |

## Zaroori cheezein
- `HF_TOKEN` (GitHub secret) — pyannote model ke liye (terms accept karna padta hai)
- Pehli baar model download (network + disk)
- CPU par whisper `int8` = dheema par chalta hai

## Niyam (unke aur hamare)
- Original audio **read-only**, report alag file
- Transcript/speaker/emotion — **human review** ke baad hi publish
- Speaker labels **anonymous** (`SPEAKER_00`)
- Ek hi narrator ke do speakers ban sakte hain; do milti awaazein jud sakti hain
- **Voice clone nahi** karta, model train nahi karta

## Base system safe
`astra_audio` ke imports **lazy** hain — torch na ho to `backend_status()` me `False` dikhta hai,
baaki sab chalta rehta hai (25 tests pass bina ML ke).
