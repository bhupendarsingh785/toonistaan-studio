# Chaar engine par ek hi kathin test — 6 aur bug theek (21 Nov 2026)

**system_check 19/19 · tests 180 pass, 2 skip · stress score: free 100%, piper 100%, espeak 100%, edge 100%**

## Naya tool: `tools/engine_stress.py`
Har engine par 7 test (ek hi tarah, andaza nahi):
1. normal line → file bane, 0.5 s se lambi, khamosh na ho
2. **khaali text** → saaf False
3. **sirf "।।।"** → saaf False
4. **lamba text (600+ akshar)** → poori file bane
5. **.wav maanga** → asli `RIFF` header
6. **bhaav ka asar** → dukh ki duration > gussa
7. **khamosh nahi** → RMS > 0.01

## Mile 6 bug (stress test se)
| # | Bug | Hal |
|---|---|---|
| 1 | **`.wav` me MP3 bytes** (free + edge) | free: PCM WAV; edge: `_edge_transcode` |
| 2 | free me **wav + bhaav** me src==dest → style lagta hi nahi tha | temp file me convert, phir style |
| 3 | **`NameError: Path`** — `_edge_transcode` ke annotation me (module me Path import nahi) | annotation hata, andar import |
| 4 | piper/espeak **"।।।" par garbage audio** (0.4–0.8 s) | `has_words()` guard teeno engine me |
| 5 | **kharab audio cache me phans jata tha** — ek baar garbage bana to hamesha wahi milta | `render_cache._usable()` — 0.25 s se chhoti ya khamosh file reject |
| 6 | guard **cache ke baad** chal raha tha (isliye purana kachra wapas aata) | guard ab **router me, cache se pehle** — ek hi darwaza |

## Sabak
- **Cache = zahar bhi** — bina quality check ke cached garbage hamesha wapas aata hai.
- **Guard sabse pehle** (router), phir cache, phir engine — isi order me.
- **Test file me bhi asli audio** chahiye — khamosh dummy file ab reject hoti hai (sahi baat).

## Sach
- espeak lamba text 54 s leta hai (150 wpm) — tez chahiye to `espeak_SetParameter` se rate badhao.
- Google TTS unofficial hai — retry + chhote chunk ke bharose.
