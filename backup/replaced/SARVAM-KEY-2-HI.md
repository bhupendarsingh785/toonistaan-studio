# Dusri Sarvam ID — key kaise daalein (21 Nov 2026)

## 1. Key kahan se lein
- Sarvam dashboard: **https://dashboard.sarvam.ai/**
- Login (dusri ID se) → **API Keys** → *Create new key* → copy.

## 2. Key kahan paste karein (chat me NAHI)
- GitHub repo secrets: **https://github.com/bhupendarsingh785/toonistaan-studio/settings/secrets/actions/new**
- **Name:** `SARVAM_API_KEY_2`  ← bilkul yahi naam (main isi se padhti hoon)
- **Secret:** key paste → *Add secret*

## 3. Ab system kya karega
- `SARVAM_API_KEY` (pehli ID) + `SARVAM_API_KEY_2` (dusri ID) — dono padhta hai.
- Pehli key par **401/402/403/429** (coin khatam/quota) aaye to **apne aap dusri** try hoti hai.
- Dono ki coin alag-alag bachti hai — ek khatam ho to doosri se kaam chalta rahega.
- Teesri/chauthi bhi jod sakte ho: `SARVAM_API_KEY_3`, `SARVAM_API_KEY_4`.

## 4. Test
`tests/test_sarvam_keys.py` — 3 test: rotation, duplicate na ho, khaali ho to saaf.
