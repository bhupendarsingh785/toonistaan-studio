# Action → Sound (v0.16 action foley)

`astra_audio/action_foley.py` kahani se **physical action** nikalta hai (40+ naam).
`astra/action_brain.py` unko hamare library ke asli sound se jodta hai.

## Kram (render me)
1. `sfx_extra.detect_smart` — shabd/mahaul se (pehle)
2. `action_brain` — rassi, taala, khidki, koodna (agar upar kuch na mile)
3. `story_brain` — v0.11 story intelligence (uske baad)
4. `scene bed` — khaali scene na lage

## Mapping (mukhya)
| Action | Hamara sound |
|---|---|
| rope_uncoil / rope_friction / knot_tighten | `paper_flutter` (asli rassi nahi hai) |
| window_open / window_exit | `door_open_a` / `gate_open` |
| window_open_creak | `door_iron_creak_old` |
| key_lock / door_handle | `door_lock_open` |
| ladder_climb | `steps_stairs_up` |
| jump_down / landing | `fall_impact` |
| water_entry | `water` |
| footsteps_leaves | `footsteps` + `leaves` |

## Kya missing hai (asli recording chahiye)
- **rope / rassi** — khinchne, khulne, gaandh kasne ki awaaz
- **cloth rustle** — kapde ki sar-sarahat
- **dry leaves crunch** — sookhe patton par kadam
- **wooden ladder creak** — lakdi ki seedhi

Jab tak ye nahi, system **nazdeeki** sound use karta hai (jhoot nahi bolta — report me likhta hai).
