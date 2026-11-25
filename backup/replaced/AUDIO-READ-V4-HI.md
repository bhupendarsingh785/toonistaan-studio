# Audio Read v4 — awaaz, music, background, mahaul alag alag (21 Nov 2026)

## Kya kar sakta hai ab
| Cheez | Kaise | Sach |
|---|---|---|
| **Awaaz alag, background alag** | spectral subtraction (median spectrum = jo har waqt hai) | 2 stems ban jaate hain: `speech.wav`, `background.wav` |
| **Music alag pehchanna** | tonal ratio + tempo + confidence | "music hai / nahi" — 100% nahi |
| **Sur/dhun (swar)** | chroma (12 pitch class) → key guess | jaise "B", D#/F#/A strong |
| **Tempo/beat** | onset autocorrelation | BPM + confidence |
| **Chhoti-badi awaazein** | background stem par onset + type (thud/hiss/tonal) | kab, kaisi |
| **Mahaul (mahaul kitna bhar raha)** | speech vs background ka dB farq | "background zyada loud / dheema / theek" |
| **Kirdaar ka bhaav** | har turn ka pace + sur + zor | khushi / dukh / gussa / neutral |
| **Kirdaaron ka aapas ka rishta** | turns ke beech gap: back-and-forth, long gaps | kaun tez jawab deta hai |
| **Kirdaar ke bolne ka andaaz** | turn ki lambai, sur ka utar-chadhav, raftaar | "dheere thehra" ya "tez josh" |

## Swag ke audio par (arju111.mp3)
- Awaaz **-29.1 dB**, background **-35.4 dB** → farq **6.3 dB** = **background thoda zyada** (10-12 dB hona chahiye)
- Speech **11.5 s**, **23 turns**, gap औसत **0.31 s** — 18 baar turant jawab (ruk-ruk kar bolta hai)
- Music: tonal 0.775, key guess **B** (F# 0.21, D# 0.11, A strong), tempo 100 BPM
- **Sach:** ye tonal-ness recording ke hiss/noise se bhi aa sakti hai — music ka pukka pata nahi

## Hamare khud ke render par (jungle-nadi-safar-v8)
- 150 turns (zyada tukde — VAD chhota kar raha hai: **sudhaarna hai**)
- background **bahut dheema** mila → mahaul mehsoos nahi hoga; bed ka level badhana chahiye
- key guess **B**, tempo 100 BPM, tonal 0.52

## Kami jo abhi bhi hai (imaandari se)
1. **VAD over-segment** karta hai (150 turns) — pause ko turn samajh leta hai
2. Music aur "stable noise" me farq **pakka nahi** (dono tonal dikhte hain)
3. Do logon ke sur same ho to diarization **fail** hoti hai
4. Stem separation **spectral subtraction** hai — thodi awaaz speech me bhi reh jaati hai (AI model jaisa clean nahi)
