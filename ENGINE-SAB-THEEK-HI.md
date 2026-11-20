# Sab engine theek — 18/18 pass (20 Nov 2026)

**system_check: 18/18 ✅ · tests: 164 pass, 1 skip · teen engine sandbox me asli render kar rahe hain**

## Kya theek kiya (asli naap)

| Engine | Hal | Sandbox me naap |
|---|---|---|
| **edge** | ❌ pehle "binary nahi" → ✅ **chalta hai** | **0.8–2.8 s**, 19–33 KB |
| **piper** | ❌ → ✅ **chalta hai** | **5.7–7.1 s**, 60–91 KB |
| **espeak** | ❌ → ✅ **chalta hai** | **0.3 s**, 173 KB |
| **elevenlabs** | key chahiye | runner par secret se test hota hai |

## Edge ka asli upay (yeh sabse badi dikkat thi)
Edge-tts sandbox me 2 wajah se fail hota tha:
1. **proxy** — edge-tts aiohttp use karta hai, env proxy nahi leta → `--proxy` / library me `proxy=` diya.
2. **CA** — edge_tts andar `certifi` **hardcode** karta hai, isliye proxy ka certificate nahi pahchanta.
   **Upay:** render se pehle apna SSL context banate hain (`certifi` + sandbox ka `SSL_CERT_FILE`) aur `edge_tts.communicate._SSL_CTX` ko replace kar dete hain. Isi se **edge chalta hai** — system package, sudo, kuch nahi chahiye.

## Ek command se sab
```bash
python tools/engine_setup.py           # install + asli render test (teen engine)
python tools/engine_setup.py --check   # sirf check
python tools/system_check.py           # poora system: 18/18
```
`CORE = (piper, espeak, edge)` — ye teen **bina key** chalte hain. ElevenLabs **optional** hai (key ho to aur behtar).

## Runner par ElevenLabs ka test
`.github/workflows/engine-live-test.yml` — GitHub secret `ELEVENLABS_API_KEY` wahan available hota hai, isliye chaar engine wahan test hote hain + router ki chain bhi.
