# PIPER — kya karna hai (saaf Hindi)

**Kya hai:** Piper — offline neural, dheema par apna

## 1. Awaaz ki setting (per kirdaar)

| Kirdaar | Setting |
|---|---|
| narrator | `{"length_scale": 1.29, "sentence_silence": 1.2}` |
| dada | `{"length_scale": 1.29, "sentence_silence": 1.04}` |
| purush | `{"length_scale": 1.16, "sentence_silence": 0.64}` |
| maa | `{"length_scale": 0.93, "sentence_silence": 0.56}` |
| gudiya | `{"length_scale": 0.93, "sentence_silence": 0.48}` |
| sonu | `{"length_scale": 1.1, "sentence_silence": 0.4}` |

## 2. Bhaav ka naksha (sur ×, raftaar ×, thahraav ×)

- **neutral**: sur 1.0 · raftaar 1.0 · thahraav 1.0
- **pyaar**: sur 0.97 · raftaar 0.94 · thahraav 1.3
- **khushi**: sur 1.06 · raftaar 1.08 · thahraav 0.8
- **dukh**: sur 0.93 · raftaar 0.88 · thahraav 1.6
- **dar**: sur 1.04 · raftaar 1.12 · thahraav 0.7
- **gussa**: sur 1.02 · raftaar 1.15 · thahraav 0.6
- **hairan**: sur 1.08 · raftaar 1.05 · thahraav 0.9

## 3. Beats (16 step — `X` = bajta hai)

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
**boom_bap** (90 BPM)
```
kick  X.....X..X......
snare ....X.......X...
hat   X.X.X.X.X.X.X.X.
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
**one_drop** (78 BPM)
```
kick  ........X.......
snare ....X.......X...
hat   X.X.X.X.X.X.X.X.
```
**afrobeat** (108 BPM)
```
kick  X..X..X...X..X..
snare ..X..X..X..X..X.
hat   X.XX.X.XX.XX.X.X
```

## 4. Bhaav ke asli signal (naap se)

- **cheekh**: `{"zor_dbfs": -10.4, "high_band_3k_pct": 29.1}`
- **hasi**: `{"modulation_3_8hz": 0.315}`
- **darr_kaanpta**: `{"f0_jitter": 0.057}`
- **gussa**: `{"f0_sd_min": 50}`
- **dukh**: `{"f0_max_hz": 165, "zor_dbfs_max": -26}`

## 5. Audio ke blueprint

- **kahani**: {"pause_s": 3.0, "background_below_db": [10, 12], "turns_avg_s": 4.0, "mood_mix": "dukh 30%, neutral 40%, khushi 15%, dar 15%"}
- **vlog**: {"pause_s": 5.0, "background_below_db": [20, 22], "turns_avg_s": 1.3, "f0_hz": [150, 195]}
- **gaana**: {"bpm": [76, 132], "mix_mid_pct": [52, 61], "chords": "minor family for dard, major for bhakti"}
- **horror**: {"scream_pct": 3, "story_pct": 46, "silence_before_scream": true, "build_before_jhatka_s": [5, 10], "cycle_s": [60, 90]}

## 6. Is engine ke niyam

- thread-safe nahi — ek baar me ek render
- 200 akshar par todo

## 7. QA (bina iske deliver nahi)

- sur band me (dada 88–125, dadi 140–185, mahila 165–205, ladki 190–240, bachcha 240–330)
- sur ka kaanpna (std) 12+
- raftaar 3.0–4.5 akshar/s
- background 8–16 dB neeche
- clipping 0%, peak < 0.95
