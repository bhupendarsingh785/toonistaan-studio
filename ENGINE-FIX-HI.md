# Chaaron engine ki kami theek ki — asli naap ke saath (20 Nov 2026)

**162 tests pass, 1 skip. system_check: 17/18 pass** (sirf ElevenLabs key baaki, woh tumhare paas hai).

## Kya theek hua

| Engine | Pehle | Ab | Kaise |
|---|---|---|---|
| **piper** | ❌ "binary nahi" | ✅ **chalta hai** (5.7 s, 60 KB) | `pip install piper-tts` + Hindi model `models/hi_IN-priyamvada-medium.onnx` (61 MB) |
| **espeak** | ❌ "binary nahi" | ✅ **chalta hai** (81 KB WAV) | `pip install espeakng-loader` — espeak-ng ka library andar hi aa jata hai, system package ki zaroorat nahi |
| **edge** | ❌ "binary nahi" | ⚠️ installed, **internet chahiye** | `pip install edge-tts` — sandbox ka proxy `speech.platform.bing.com` band karta hai; **GitHub runner par chalta hai** |
| **elevenlabs** | ❌ "key nahi" | ⚠️ key chahiye | `ELEVENLABS_API_KEY` GitHub secret me daalo, phir chalta hai |

## Naya tool: `tools/engine_setup.py`
```bash
python tools/engine_setup.py           # install + asli render test
python tools/engine_setup.py --check   # sirf check
```
Har engine ka **asli render** karke file ka size batata hai — bina chalaye "ok" nahi bolta.

## Router me badlav
- `espeak` ab `vp.espeak_tts()` se chalta hai — **binary ki zaroorat nahi** (ctypes + espeakng-loader), aur **bhaav** (sur/raftaar) bhi lagta hai.
- `system_check` ab sach dekhta hai: piper = module + model, espeak = loader, edge = binary (+ internet note), elevenlabs = key.

## Ab bhi sach
- **edge-tts sandbox me nahi chalega** (network band) — runner par chalta hai.
- **ElevenLabs bina key nahi chalega** — key tumhare GitHub secrets me hai, sandbox me nahi.
- `models/` git me nahi jata (61 MB) — `engine_setup.py` khud download karta hai.
