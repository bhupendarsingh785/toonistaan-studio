# Sarvam — 6 ID tak rotation (21 Nov 2026)

## Secret ke naam (GitHub → Settings → Secrets → Actions)
| # | Naam |
|---|---|
| 1 | `SARVAM_API_KEY` |
| 2 | `SARVAM_API_KEY_2` |
| 3 | `SARVAM_API_KEY_3` |
| 4 | `SARVAM_API_KEY_4` |
| 5 | `SARVAM_API_KEY_5` |
| 6 | `SARVAM_API_KEY_6` |

Naya secret: https://github.com/bhupendarsingh785/toonistaan-studio/settings/secrets/actions/new

## Kaise kaam karta hai (`tools/sarvam_keys.py`)
1. **Zinda keys pehle** — jo chal rahi hain woh upar.
2. **Coin khatam (401/402/403/429)** → us key ko **cooldown** (default 1 ghanta) me daal kar **agli** try.
3. **Server error (5xx)** → usi key se **dobara** (coin barbaad na ho).
4. **Dead key yaad rehti hai** — `.sarvam_keys_state.json` me (key nahi, sirf **hash**).
5. Chhoti test: `python tools/sarvam_keys.py status` / `reset`.

## Sach
- Har key ka apna coin — 6 ID = 6 alag balance.
- Rotation **apne aap** hoti hai; tumhe kuch karna nahi.
- Key **kabhi** chat, file ya log me nahi likhi jaati (state me sirf 10-akshar hash).
