# Duniya ki awaaz — aankh band karke mehsoos hone wala audio (20 Nov 2026)

**154 tests pass, 1 skip.** Naya module: `tools/world_scape.py`. Demo: `duniya-ki-awaaz-demo.mp3` (27.9 s).

## Kaise kaam karta hai

1. **Text padhta hai** aur jagah/mausam/zameen/cheezein pehchanta hai:
   - jagah: gaon, jungle, nadi, sadak, station, ghar, mandir
   - mausam: barish, toofan, bijli (garaj)
   - zameen: ghaas, keechad, patthar, sookhe patte, lakdi, sadak
   - cheezein: tractor, gaadi, ghanti, train
2. **Teen parat banata hai:**
   - **BED** — laga rahe (jungle, nadi, gaon) — loop
   - **MID** — barish, garaj, hawa
   - **CLOSE** — kadam (zameen ke hisaab se), patte, darwaza
3. **Ducking** — jab kirdaar bolta hai, bed apne aap 9 dB neeche (bolne wala saaf)
4. **Space** — halka reverb + limiter + loudness -18 LUFS (kharab na ho, phone par bhi saaf)

## Demo me kya hai (asli library se)
`duniya-ki-awaaz-demo.mp3` — jungle bed + nadi + barish + garaj + sookhe patton me kadam.
Naap: **27.9 s, peak 0.78, RMS -19.8 dBFS** (normal, distort nahi).

## Command
```bash
python tools/world_scape.py plan --text "वह जंगल से गुजरा, नदी बह रही थी।"
python tools/world_scape.py build --script scene.txt --out output/world --seconds 28
```
Har build ke saath `world.cues.json` — kaun parat, kitna zor, kahan se.

## Jo abhi library me NAHI hai (isliye demo me nahi aaya)
| Chahiye | Status |
|---|---|
| **Tractor** ki awaaz | nahi hai — demo me "missing" likha gaya, jhooth nahi bola |
| Jhaadiyan (bushes) ki apni awaaz | nahi — filhaal sookhe patte + ghaas se kaam chala |
| Nadi ki alag recording | 1 hi file hai (`forest_river_bed`) |
| Garaj (thunder) | 1 hi file (`thunderstorm`) — alag-alag doori ke 3-4 chahiye |

## Agla kadam (audio perfect karne ke liye)
1. **Tractor, bushes, nadi (paas/door), garaj (3 doori)** — ye 6-8 awaazein bhejo, main index me daal dunga
2. **Panning + doori** — kadam left→right, tractor door se paas (abhi sirf volume se doori)
3. **Scene badalna** — gaon → jungle ke beech crossfade (abhi ek hi scene)
