# Local Story — sirf apne system se (Sarvam nahi)

**Kaise chalta hai:** Piper (offline neural TTS, Hindi) + **apni ambience** (numpy se bani barish/hawa/jhingur/nadi/pad) + apna mix (ducking, limiter, -16 dBFS).

## Setup (ek baar)
```bash
pip install piper-tts imageio-ffmpeg numpy
mkdir -p voices && cd voices
# Hindi voices (61 MB each)
curl -L -o hi_IN-pratham-medium.onnx      https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx
curl -L -o hi_IN-pratham-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json
curl -L -o hi_IN-priyamvada-medium.onnx      https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx
curl -L -o hi_IN-priyamvada-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx.json
```

## Chalana
```bash
python tools/local_story/story_local.py out.mp3
```

## Kirdaar ki tuning (asli naap se, `story_local.py` me)
| Kirdaar | Voice | length_scale | pitch (semi) | Naapa F0 |
|---|---|---|---|---|
| narrator | pratham | 1.12 | -1.0 | **101 Hz** |
| dadi | priyamvada | 1.24 | **-5.5** | **175 Hz** |
| maa | priyamvada | 1.02 | -2.0 | **200 Hz** |
| sonu (bachcha) | priyamvada | 0.92 | **+4.0** | **287 Hz** |

## Ambience (apni, sample ke bina)
`ambience.py`: `rain()`, `wind()`, `crickets()`, `river()`, `pad_chords()` — sab numpy noise + filter + LFO se.

## Sach
- Piper **Sarvam se kam natural** hai (robotic touch), par **free, offline, unlimited**.
- Yahan **koi sample library nahi** — ambience bhi code se banti hai.
- Har line ka F0 naap kar target band me laaya gaya (4/4 pass).
