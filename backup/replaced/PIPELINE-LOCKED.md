# 🔒 PIPELINE LOCKED — kahani ka audio (21 Nov 2026)

Yeh **standard pipeline** hai. Isi se aage sab kahaniyan banengi (jab tak Swag na bole).

## 1. Awaaz (Sarvam bulbul:v4-flash, key rotation 12 tak)
| Kirdaar | Persona | Pitch | Pace | Naapa F0 |
|---|---|---|---|---|
| narrator | `shubh_hi_stories_dramatic` | -0.10 | 0.96 | 111 Hz |
| dada (बुज़ुर्ग) | `ratan_hi_latenight_warm` | -0.34 | 0.93 | 114 Hz |
| dadi (बुज़ुर्ग) | `simran_hi_narration` | -0.15 | 0.95 | 142 Hz |
| maa (महिला) | `aparna_hi_customer` | -0.05 | 0.98 | 198 Hz |
| gudiya (18 साल) | `ritu_hi_kids` | -0.08 | 1.03 | 258 Hz |
| sonu (बच्चा) | `chhavi_hi_kids` | +0.10 | 1.06 | 293 Hz |

**Niyam:** dadi/dada = 110–185 Hz, mahila = 165–205, ladki = 190–240, bachcha = 240–330.
(Swag ne kaha: "thoda-thoda patla karenge" — isliye pitch values yahan se hi badalni hain.)

## 2. Sound design (deep — har cheez ki awaaz)
`tools/story_soundmap.py`: script padh kar cheezein pehchanta hai (bhediya, nadi, patte,
darwaza, khidki, baarish, garaj, train, chai, pakshi, jhिंगुर, hawa, bheed) aur library se
asli file utha kar **usi line ke shuru me** lagata hai. Na mile to "MISSING" report karta hai.

Chalane ka tareeka: `python tools/story_audio.py --script stories/x.json --soundmap --out out.mp3`

## 3. Mix
- Dialogue: highpass 75 → compressor 2.5:1 → treble +1.5 dB → -2 dB
- Bed (jungle/barish/nadi): loop, sidechain **6:1 ducking** dialogue ke waqt
- Aakhir: `loudnorm I=-18 LUFS`, limiter 0.95, MP3 160 kbps

## 4. Jaanch (bina iske deliver nahi)
1. Har line ka F0 naapo → target band se milao
2. Missing sounds = 0 hona chahiye (soundmap report)
3. RMS -18 dBFS ke aas-paas, peak < 0.95
4. cues.json bane (video/subtitle ke liye)

## 5. Workflow
`.github/workflows/story-safar.yml` (Sarvam keys secrets se) → artifact → download → deliver.
