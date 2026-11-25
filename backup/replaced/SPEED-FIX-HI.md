# Engines ko tez kiya — asli naap ke saath

20 Nov 2026 · **114 tests pass, 1 skip**

## Dikkat kya thi (naap kar pakdi)
| Kami | Nateeja |
|---|---|
| Piper har line par **naya process** (`python -m piper`) | har line 2-3 s sirf startup me |
| Model **har line par dobara load** (61 MB ONNX) | pehli line 18-31 s |
| Pitch ke liye `asetrate` | gala (formant) bigadta tha → robotic |
| Post-processing **5 alag ffmpeg calls** | 5-9 s extra |
| `fit_to_target` 3 round | 2-3 extra ffmpeg pass |
| `os.replace` alag device par | FIT_FAIL error, pitch fit fail |
| Ek-ek line **sequential** | 10 line = 10x waqt |

## Kya badla
| Badlav | Fayda |
|---|---|
| **In-process Piper** (`PiperVoice` ek baar load) | model sirf ek baar, phir seedha python se |
| **Ek hi ffmpeg pass** (pitch + highpass + umar + volume) | 5 call → 1 call |
| **rubberband formant=preserved** | sur badla, gala wahi → insaani |
| `fit_to_target` default 1 round | extra pass khatam |
| `os.replace` fail par `shutil.move` | cross-device bug khatam |
| **Parallel render** (`render_story_parallel`, 4 workers) | 4 line ek saath |
| **Cache** (`render_cache`) | dobara bani line 0 s, Sarvam ka paisa 0 |
| **`engine_bench.py`** | kaun tez hai, asli number |

## Naap (is machine par, CPU)
| | Pehle | Ab |
|---|---|---|
| Pehli line (model load ke saath) | 18.75 s | 6.9 s |
| Uske baad har line | 7.0 – 31.7 s | **1.4 – 1.8 s** |

Yani **~5x se ~18x tez**, aur awaaz robotic nahi (formant preserved).

## Chalane ka tareeka
```bash
python tools/engine_bench.py --engines piper,edge,sarvam
python tools/render_cache.py stats
```
