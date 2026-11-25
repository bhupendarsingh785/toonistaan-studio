# Kathin kaam par engine — 7 aur bug theek (21 Nov 2026)

**tests 184 pass · load score: free 100% · piper 100% · espeak 100% · edge 100%**

## Naya tool: `tools/engine_load.py`
4 kathin test har engine par:
1. **ek hi line 5 baar** → cache se tez hona chahiye
2. **8 lines parallel** → sab banein (threads me takkar na ho)
3. **lamba text** → poori file, khamosh na ho
4. **do engine ek saath** → shared cache me race na ho

## Mile 7 bug
| # | Bug | Hal |
|---|---|---|
| 1 | **`/tmp` sirf 64 MB** tha aur bhar gaya → `OSError: No space left on device` | naya `tools/worktmp.py` — sab temp `/scratch` (262 GB) par |
| 2 | **piper parallel me 2 lines fail** — `PiperVoice` thread-safe nahi | shared voice + **lock**, lamba text ke liye per-thread voice |
| 3 | **piper lamba text 210 s** (har chunk par model load) | per-thread voice **ek baar** load, phir reuse → 54 s audio, 72 s |
| 4 | **espeak crash: "double free or corruption"** | voice + params + synth — **sab ek lock me** |
| 5 | **espeak voice list (350) bhar jati** → render band | har 150 render par library reset |
| 6 | **cache index.json race** — do render ek saath likhein to JSON toot jata | `_save()` par lock + `os.getpid()` temp file |
| 7 | **`Path` NameError** (dobara) — module me Path import nahi tha | top-level `from pathlib import Path` |

## Speed (asli naap, 2-core sandbox)
| Engine | ek line | cache hit | 8 lines parallel | lamba text |
|---|---|---|---|---|
| free | 0.96 s | **0.31 s** | 2.0 s | 5.3 s (124 s audio) |
| espeak | 0.70 s | **0.10 s** | 1.0 s | 1.5 s (109 s audio) |
| edge | 3.1 s | **1.1 s** | 4.4 s | 4.8 s (129 s audio) |
| piper | 8.2 s | **1.4 s** | 17 s | 72 s (54 s audio) |

## Sach
- **piper sabse dheema** (2 core, 61 MB model) — GPU ya chhota model chahiye tez karne ke liye.
- espeak ki awaaz robotic hai par **sabse tez** (109 s audio, 1.5 s me).
- Cache hit par sab **3–7x tez**.
