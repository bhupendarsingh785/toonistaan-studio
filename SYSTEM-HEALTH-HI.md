# System health — bug hunt + engine connection (20 Nov 2026)

**142 tests pass, 1 skip.** Sab kuch code padh kar aur chala kar — andaza nahi.

## 1. Do asli bug mile aur theek hue

| Bug | Kahan | Kya hota tha | Fix |
|---|---|---|---|
| `actions` / `brain` **undefined** | `astra/cinema.py` line 217–222 | jis line me SFX na milta, wahan **NameError** se cinema ruk jata | `ACTION_MAP`/`EVENT_MAP` safely import (na mile to `{}`) |
| **9 duplicate keys** | `astra/library.py` `VARIANTS` | baad wali entry pehle wali ko chup-chaap mita deti thi (vinyl, transition, magic, bell…) | dono list **merge** (vinyl 13, transition 25 — kuch nahi khoya) |

Aur ek chhupa bug: `system_check` ka library test full-suite me fail ho raha tha (kisi test ne `sys.path` badal diya) — ab file se seedha load hota hai.

## 2. Chaar engine + Sarvam ka connection majboot

- **Bus ↔ Router juda**: `engine_bus.py run --live` ab asli `engine_router.render_line` se bolta hai — ek hi darwaza, ek hi fallback chain (EDGE → ELEVENLABS → PIPER → ESPEAK).
- **Galti ledger**: jo engine fail hota hai, `bus/errors.json` me entry + `fixed_by` (kisne sudhara) + dono engine ko message.
- **Voice lock**: ek kirdaar ka engine badalta nahi, warna beech me awaaz badal jati.
- **Parallel**: `--workers 4` se chaar part ek saath.

## 3. Naya: `tools/system_check.py`
Ek command me poore system ki report:
```bash
python tools/system_check.py
```
Batata hai: kaun engine tayyar hai (binary/key), bus ke chaar engine, galti ledger, cache, library (1826 sounds / 239 variant tags), naye modules import hote hain ya nahi, tests.

Aaj ka natija: **14/17 pass** — jo teen fail hain woh sach hain: `edge`, `elevenlabs`, `espeak` tayyar nahi (binary/key nahi).

## 4. Ab bhi khuli dikkat (imandari se)
- EDGE / ELEVENLABS / ESPEAK — binary ya key nahi (sandbox me)
- Playwright nahi — browser HTTP fallback par
- Cloning (IndicF5/XTTS) — torch/GPU nahi
- Training data 0 examples
