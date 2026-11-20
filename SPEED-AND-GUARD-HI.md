# System ko fast + majboot banaya (Sarvam ka paisa bachta hai)

20 Nov 2026 · **112 tests pass, 1 skip**

## 1. Render Cache — `tools/render_cache.py`
Ek hi line dobara banane par **paisa aur time dono bachte hain**.

- Key = text + voice + engine + params ka hash
- Cache hit → seedha wahi file, engine call hi nahi
- `cache.json` me hisaab: kitni entries, kitne hits, kitna MB
- Purani entries saaf karne ka option

```bash
python tools/render_cache.py stats
python tools/render_cache.py clear --older-than 30
```

## 2. TTS Guard — `tools/tts_guard.py`
Har engine call isi se guzarta hai:

| Kaam | Fayda |
|---|---|
| cache pehle dekho | Sarvam ka credit nahi katta, piper ka time nahi lagta |
| **3 retry + backoff** | Sarvam 429/5xx par apne aap dobara koshish |
| **quality check** | khaali/NaN/bahut chhoti/bahut khamosh file par saaf error — chup-chaap kharab audio nahi |

```bash
python tools/tts_guard.py check --file out.wav
python tools/tts_guard.py cache-stats
```

## 3. Router me juda
`tools/engine_router.py` ab har engine call `tts_guard` se karta hai —
report me likha aata hai `cache se` ya `banaya`, aur fail hone par agla engine.

## 4. Kyun "Sarvam ki help" is tarah
Sarvam sabse natural Hindi deta hai, par **har call paisa** hai. Isliye:
- Sarvam pehla engine (chain me sabse aage)
- par cache + retry + quality gate ke saath — dobara paisa nahi, aur fail par dikh jata hai
- baaki engine (edge/piper/espeak/eleven) fallback

Yani Sarvam ki **quality** milti hai, par **kharch** niyantran me rehta hai.

## 5. Tests
`python -m pytest tests -q` → **112 pass, 1 skip** (skip = torch wala, machine par torch nahi)
