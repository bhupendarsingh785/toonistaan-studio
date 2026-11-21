# Audio Read v3 — deep research wala system (21 Nov 2026)

v2 se aage: ab **MFCC clustering, formants (LPC), tempo, LUFS, dynamic range** bhi.

## Research se liye gaye tarike
| Tarika | Kis kaam ke liye |
|---|---|
| **MFCC (26 mel filter + DCT)** | awaaz ki "banawat" — kaun bol raha hai |
| **k-means clustering** | speaker diarization (S1, S2…) — par **F0 me 18 Hz farq** ho tabhi alag maanta hai |
| **LPC (Levinson–Durbin) → F1/F2** | umar/kism ka pata (F1 ~450 Hz = bhaari/bade vocal tract) |
| **Spectral flux + peak picking** | background events: kab, kaisi (thud/hiss/tonal), decay (reverb) |
| **Onset autocorrelation → tempo** | music hai ya nahi (confidence ke saath) |
| **Per-second dBFS + LUFS approx + dynamic range** | level ki sacchai |
| **Speech-band syllable peaks (min 0.12 s gap)** | asli bolne ki raftaar |

## Swag ke `arju111.mp3` par v3 ka natija (asli naap)
| Cheez | Value |
|---|---|
| Lambai / level | 20 s · **-26.4 dBFS** · LUFS ~**-27.1** · peak 0.26 · clipping **0%** |
| Noise floor / dynamic range | **-48.6 dB** · **14.8 dB** |
| Bolna / chupai | **15.3 s bol** · 4.6 s chup · **9 segment** · **8 pause** |
| Raftaar | **3.47 syllable/s** (dheemi, thehr-thehr kar) |
| Sur | **120 Hz** (112–124), variability **3.6** → bahut flat |
| Speaker | **S1 (ek hi aadmi)** · F1 **444 Hz**, F2 1500 Hz → bhaari/bade vocal tract |
| Background | **28 onsets**, tempo 150 BPM par **confidence 4.59** — par speech 76% hai, isliye **music = nahi** (thud/table ki awaazein) |

## Kya sudhra (v2 → v3)
1. v2 me ek hi aadmi ko **3 speakers** bana raha tha → ab **1 speaker** (F0 separation ka niyam)
2. v2 me music ka **false positive** tha → ab confidence + speech ratio dekhta hai
3. Raftaar 9.5 syl/s (galat) → **3.47 syl/s** (min-gap peak picking)
4. Ab **F1/F2 formants** se umar/kism ka andaaza, aur **decay** se reverb

## Sach (kya nahi kar sakta)
- Do logon ke sur bilkul same ho to clustering unhe alag **nahi** kar sakti.
- Music/speech ka faisla **confidence + ratio** par hai — 100% nahi.
- F1/F2 se "umar" sirf **andaaza** hai (asli umar nahi bata sakte).
