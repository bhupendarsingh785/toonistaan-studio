# EDGE — kya karna hai (Hindi)

**Kya hai:** Microsoft Edge TTS — free, online, tez

## 1. Sur ka target (naap kar)

| Kirdaar | F0 (Hz) |
|---|---|
| narrator | 90–125 |
| dada | 95–130 |
| dadi | 140–185 |
| mahila | 165–205 |
| ladki | 200–245 |
| bachcha | 240–330 |

## 2. Robot lagne ke 5 karan (inse bacho)

- pitch shift se formants khisakte hain (chipmunk/monster) → resample + formant soch
- comb-filter reverb (17/23/31 ms) = goonj → reverb band ya smooth tail
- line ke andar lambi khamoshi = 'ruk-ruk kar bolna' → 110 ms se lambi gap 65 ms karo
- line ke shuru/aakhir ki silence trim nahi = har line ke baad hole
- mid patla + high chubhta = hollow/machine awaaz (mid 55–65%, high ≤20%)

## 3. Smoothness ke niyam (ruk-ruk kar bolna band)

- piper: length_scale 0.92–1.05 (1.2+ = ruk-ruk kar bolna)
- piper: noise_scale 0.62, noise_w_scale 0.75 (natural prosody)
- har line: trim 25–40 ms → andar ki 80 ms+ gap ko 35 ms karo → 20 ms fade-in
- lines ke beech pause 0.22–0.35 s (1.5 s nahi)
- humanize me amplitude micro-dips band (woh shabd kaat dete hain)
- target: andar ke 80 ms+ gaps ≤5, pace 12–14 akshar/s, speech 65–70%
- smooth reference ka target: low 15–17, mid 55–57, high 27–30%, brightness 2086–2187 Hz, RMS -18.5 dBFS

## 4. Bhaav ke signal

- **cheekh**: `{"rms_dbfs": -10.4, "high_3k_pct": 29.1}`
- **hasi**: `{"modulation_3_8hz": 0.315}`
- **darr**: `{"f0_jitter": 0.057}`
- **gussa**: `{"f0_sd_min": 50, "jitter_max": 0.05}`
- **dukh**: `{"f0_max": 165, "rms_dbfs_max": -26}`

## 5. Shabd galat (piper G2P)

piper ka Hindi G2P: व girta hai, ि→े, ठ→ख/त, श→ष, ौ→ो

| Script | Bola jaata |
|---|---|
| बारिश | बारेश |
| गाँव | गाँ |
| ठंडक | खन्न |
| देखो | बेखो |
| भीगने | भीट में |
| कितनी | किच्मी |
| छाता | च्हाता |
| खुशबू | फुष्बो |

**Hal:** respell dictionary + carrier-phrase test (अब सुनो, <शब्द>) — akela shabd ASR se test nahi hota

## 6. Beats (16 step)

**keherwa** (92 BPM)
```
kick  X.......X.......
snare ....X.......X...
hat   X.X.X.X.X.X.X.X.
```
**dadra** (84 BPM)
```
kick  X.....X.........
snare ......X.....X...
hat   X...X...X...X...
```
**teen** (100 BPM)
```
kick  X.....X.....X...
snare ....X.......X..X
hat   X.X.X.X.X.X.X.X.
```
**unwind** (76 BPM)
```
kick  X.......XX..X..X
snare X......X....X.XX
hat   X.X..X......XX..
```
**bhakti** (132 BPM)
```
kick  ......XXXX.XX...
snare ............XXXX
hat   .........XXX....
```
**four_floor** (124 BPM)
```
kick  X...X...X...X...
snare ....X.......X...
hat   ..X...X...X...X.
```
**trap** (140 BPM)
```
kick  X.......X...X...
snare ....X.......X...
hat   X.XXX.XXX.XXX.XX
```
**breakbeat** (165 BPM)
```
kick  X..X....X.X.....
snare ....X.......X...
hat   X.X.X.X.X.X.X.X.
```

## 7. QA (bina iske deliver nahi)

- clipping_pct: <0.01
- peak: 0.5–0.97
- dc_offset: <0.01
- mid_pct: 55–68
- high_pct: <=20
- snr_db: 12–22
- echo: <0.78 (insaan 0.43–0.72)
- f0_spread_pct: <=15
- wer: <0.25
- internal_gap_ms: <=70
- footstep_material_centroid: target band ke andar (dirt 200-900, concrete 1800-5000, leaves 3500-9000)

## 8. Is engine ke niyam

- pitch +30Hz se upar nahi
- har vakya alag render
