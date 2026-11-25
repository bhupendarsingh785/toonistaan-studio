# Kisi bhi audio ko padhna — aur usse seekhna (21 Nov 2026)

Swag koi audio bhejta hai → hum use **padh** lete hain (sirf sunte nahi).

## Naya tool: `tools/audio_profile.py`
Ek audio ka poora naksha:
- **Sur:** F0 median/std/range, jitter (kaanpna)
- **Bolne ka andaaz:** raftaar (energy variation), rukne ka pattern (kitni baar, kitna lamba)
- **Zor:** RMS dBFS, peak, chupai %
- **Background:** noise floor, **spectral flatness** (bed hai ya saaf), onsets (kitni alag awaazein), **stereo width**
- **Andaaz ka nichod:** gender/age guess (sur se), expressiveness
- **Tulna:** hamare cast se — kaunsa persona sabse kareeb + kya badalna hai

## Naya tool: `tools/audio_learn.py`
Padhne ke baad **sudhaar**:
- pitch kitna Hz upar/neeche karna hai (aur Sarvam ka pitch param kitna)
- flat hai to temperature +0.1
- rukta hai to pace +
- background/level ka note
- sab kuch `knowledge/audio-lessons.jsonl` me jama hota hai (agle render me kaam aata hai)
- `--apply` se seedha `voice-core/cast-presets.json` me pitch badal deta hai

## Asli test — Swag ke bheje `arju111.mp3` par
| Cheez | Naap | Matlab |
|---|---|---|
| Lambai | 19.99 s | — |
| Sur | **119 Hz** (std 11.3, range 24) | purush, bhaari/budha jaisa |
| Rukna | 8 baar, औसत 0.57 s | thoda ruk-ruk kar bolta hai |
| Zor | -26.4 dBFS (dheemi recording) | boost chahiye |
| Background | flatness 0.156, noise -50.8 dB | saaf, bed nahi |
| Tulna | narrator (90–125 Hz) | band me hai ✅ |

**Seekh:** uski awaaz **narrator** ke barabar hai — par **flat** hai (std 11.3) aur **ruki-ruki** (8 pause / 20 s).
Hamare render me isliye **temperature zyada** aur **pause kam** rakhenge.

## Sach
- Ye naap **asli audio** se aaye hain (andaza nahi).
- 119 Hz se "budha" guess aata hai — gender/age **guess** hai, pukka nahi.
- Background ki jaanch **flatness** par hai — music vs noise ka farq 100% nahi batata.
