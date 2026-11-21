# Sarvam — 12 ID tak + alag ledger system (21 Nov 2026)

## 1. Ab 12 ID tak chalega
Secret ke naam (jitni ID ho, utne hi daalo):
```
SARVAM_API_KEY        (ID 1)
SARVAM_API_KEY_2 … SARVAM_API_KEY_12
```
Naya secret: https://github.com/bhupendarsingh785/toonistaan-studio/settings/secrets/actions/new

## 2. Rotation (pehle jaisa, ab 12 tak)
1. **Zinda keys pehle**
2. **Coin khatam (401/402/403/429)** → us key ka **cooldown** + agli
3. **Server error (5xx)** → usi key se dobara
4. State file me **sirf hash** (key kabhi nahi)

## 3. Naya alag system: `sarvam-keys-ledger.html`
Ek **offline ledger** (phone par khulta hai) — key **daalne ki jagah hi nahi**:
- Har ID ka **label** (ID-1 / ghar / office), **coin bache**, **status** (ok / low / dead), **note**
- Data **sirf tumhare browser** me (localStorage) — kahin upload nahi
- **Backup (JSON)** / **Restore**
- Upar likha rehta hai kaunsa secret naam kis ID ka hai

Isse tumhe yaad rakhne ki zaroorat nahi — kaunsi ID me kitna coin bacha hai, ek nazar me.

## 4. Command (terminal me)
```bash
python tools/sarvam_keys.py status     # kaunsi key zinda/dead
python tools/sarvam_keys.py reset      # cooldown saaf
```

## Sach
- Ledger **hisaab** rakhta hai, key nahi — key sirf GitHub secret me.
- Cooldown default 1 ghanta; `SARVAM_KEY_COOLDOWN` se badal sakte ho.
