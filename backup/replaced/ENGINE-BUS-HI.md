# Chaar engine ka taalmel — Engine Bus + Bhaav ki samajh

**134 tests pass, 1 skip** · `tools/engine_bus.py` + `tools/bhavna.py`

> **Sudhaar (20 Nov, recheck ke baad):**
> - **Chaar engine (core):** EDGE, ELEVENLABS, ESPEAK, PIPER — router ki default chain yahi hai.
> - **Paanchva engine (Sarvam):** bus me poora member hai — baat karta hai, kaam leta hai, galti sudharta hai.
>   Par chaar me gina nahi jata; router me sirf `--engine sarvam` / `ASTRA_INCLUDE_SARVAM=1` par aata hai.

## 1. Chaar engine aapas me baat karte hain

| Command | Kaam |
|---|---|
| `status` | kaun kaun hai, zinda hai ya nahi, kya kar sakta hai |
| `say --from sarvam --to piper --kind task --text "..."` | ek engine doosre ko kaam/message bheje |
| `inbox --engine piper` | us engine ke paas kya aaya |
| `broadcast` (code me) | sabko ek saath bhejo |
| `heartbeat --engine piper --down` | engine band hai — registry me likh jata hai, kaam us par nahi jayega |

Messages file me rehte hain (`bus/messages/<engine>/`), isliye ek engine band ho jaye to bhi baaki ka record bacha rehta hai.

## 2. Kaam todkar jaldi banana
`plan` / `run` script ko parts me todta hai, aur har part sahi engine ko deta hai:
- pehle **bhaav** dekha jata hai (dukh wali line sirf wahi engine jo dukh kar sakta hai)
- phir **speed/cost** (free aur tez pehle)
- **ek kirdaar = ek engine** (awaaz nahi badalti)
- engine fail → wahi part doosre engine par, bhaav wahi
- `manifest.json` se aadha kaam bachta hai (resume)

## 3. Bhaav ki samajh (`tools/bhavna.py`) — 11 bhaav
neutral, khushi, dukh, gussa, dar, pyaar, hasai, rona, hairan, sharam, thakan.

Har bhaav ke saath: **Hindi naam**, **arth**, **sur** (pitch), **raftaar**, **zor**, **kahan rukna**, **Hindi cues** (jinse pehchanta hai), aur **misaal**.

```bash
python tools/bhavna.py detect --text "चुप रहो!! कुछ मत बोलो!"     # → gussa, 0.80
python tools/bhavna.py show --name dukh                          # poora knowledge
python tools/bhavna.py list
```

Pehchan kaise hoti hai: cues (शब्द) + vakya ke nishaan (`!!`, `?`, `...`) + khaali line → neutral. Jab script me `[bhaav]` tag na ho, bus **khud bhaav pehchan kar** engine chunta hai.

## 4. Engine "samajhdar" kaise bane
- **Hindi samajh**: `hindi_natural.py` (₹, %, samay, numbers, Hinglish) + `bhavna.py` cues
- **Bhaav pehchan**: 11 bhaav, confidence ke saath
- **Bhaav ka asar**: sur/raftaar/zor — engine ko bataya jata hai, andaza nahi
- **Awaaz ki pehchaan**: `voice_match.py` (F0 + timbre), `speaker_verification.py` (ECAPA)

## 5. Agla kadam (jo abhi baaki hai)
- Bus me **parallel workers** (4 engine ek saath) — structure taiyar hai
- 11 bhaav ke **asli voice samples** (abhi knowledge hai, per-bhaav reference nahi)

## 6. Galtiyan alag karna + sudhaar (naya)

Har galti `bus/errors.json` me likhi jati hai: **kaun engine, kaun part, kya galti, aur kis engine ne sudhara**.

- Jo engine fail hua, usko **khabar** jati hai (`thanks` message) aur jo bacha usko `sudhaar` message
- `heartbeat` me us engine ka note bhi update hota hai
- Report dekho: `python tools/engine_bus.py sudhaar`

## 7. Parallel — project jaldi
```bash
python tools/engine_bus.py run --script story.txt --out output/bus --workers 4
```
4 part ek saath. Har part ka engine pehle se tay (bhaav ke hisaab se), kirdaar ka engine lock, aur galti par doosra engine.

## 8. Naap (is machine par)
- 8 line, 4 workers, fake renderer → 8/8 done, 0 fail
- galti wali line → error ledger me entry + `fixed_by` likha gaya
