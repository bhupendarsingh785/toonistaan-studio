# ASTRA Sound Library

**347 sounds** · 16 folders · 68 MB · sab asli recordings (Pixabay / Freesound / Mixkit)

## Folders

| Folder | Sounds | Kya hai |
|---|---|---|
| `voices` | 64 | insaan ki awaaz — cheekh, hansi, rona, vampire (64) |
| `animals` | 51 | jaanwar — kutta, billi, ghoda, sher, dragon, alien |
| `ambience` | 44 | mahaul — baarish, mandir, church, magic, jungle |
| `vehicles` | 38 | gaadi/train — horn, station, steam (38) |
| `footsteps` | 22 | kadam — mitti, gravel, seedhi, barf (22) |
| `door` | 20 | darwaza — khulna/band, khatkhatana (20) |
| `machines` | 20 | machine — grinder, mixer, blender, coffee |
| `bells` | 17 | ghadi/ghanti — 12 baje, tower, cuckoo |
| `music` | 16 | music — dhol, shehnai, romantic, sad, intro |
| `horror` | 13 | darr — drone, sting, ghost, monster, scream |
| `foley` | 12 | chhoti cheezein — kagaz |
| `water` | 10 | paani — kettle, glass, bubbles, underwater |
| `kitchen` | 10 | rasoi — cooker, ubalna |
| `fire` | 7 | aag — crackle, fireplace, vinyl |
| `crowd` | 2 | bheed — taaliyan, bhagdad |
| `nature` | 1 | jungle ambience |

## Naya sound jodna

1. mp3 ko `astra/library/<folder>/<naam>.mp3` me rakho
2. `astra/library.py` ke `DEFAULT_INDEX` me entry likho:
   `"naam": {"file": "<folder>/<naam>.mp3", "tags": ["hindi","english"], "license": "Pixabay"},`
3. Bas — `library.fetch("naam")` turant kaam karega.

## Awaaz ka kram (har SFX ke liye)

1. **Local library** (ye repo) — sabse achi quality
2. **Freesound** (key: `FREESOUND_API_KEY`) — asli recording
3. **Mixkit** — free, key nahi chahiye
4. **Procedural** — apne banaye 19 synth (cooker, chai, chaabi…)

## Verification

`index: 347 | mp3: 347 | missing: 0 | unindexed: 0 | duplicates: 0`