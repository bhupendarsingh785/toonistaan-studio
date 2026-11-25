# ElevenLabs — private setup (20 Nov 2026)

**Matlab:** key kahin dikhe nahi, kahin likhi nahi jaaye, aur engine sirf apne private channel se chale.

## 1. Key kahan rehti hai
- **Sirf GitHub secret** me: `ELEVENLABS_API_KEY` (Settings → Secrets → Actions).
- Code me kabhi nahi — `tools/key_guard.py` har commit par check karta hai (2770 files scan, **0 leak**).
- `.gitignore` me `**/secrets/`, `client_secret*.json` pehle se hai.

## 2. Engine kaise chalta hai
- Key sirf **environment variable** se padhi jaati hai (`os.environ`), file se nahi.
- Sandbox me key **nahi** hoti → wahan engine "optional" dikhta hai, fail nahi.
- Render **GitHub runner** par hota hai (private), wahan secret available hoti hai — `.github/workflows/engine-live-test.yml`.

## 3. Guard (galti se leak na ho)
```bash
python tools/key_guard.py          # scan — leak mile to fail
python tools/key_guard.py --list   # sirf report
```
Pakadta hai: `xi-api-key: …`, `sk-…`, `SARVAM_API_KEY = "…"`, `api_key: "…"`, aur git me aayi `.env`/`secrets.json`.

## 4. Test
`tests/test_key_guard.py` — 4 test: pattern pakadta hai, placeholder nahi pakadta, repo saaf hai.

## Sach
- Key **tumhare paas** hai; main use kabhi chat me nahi maangungi aur na likhungi.
- Bina key: ElevenLabs band, baaki **teen engine (edge, piper, espeak) chalte hain**.
