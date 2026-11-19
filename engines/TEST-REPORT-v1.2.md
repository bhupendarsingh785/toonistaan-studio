# Char Engine Test Report — Four Independent Hindi Voice Intelligence v1.2

Test date: 2026-11-19 · Tester: Seetal (ASTRA) · Package: `Four_Independent_Hindi_Voice_Intelligence_v1.2.zip`

## 1. Kya test kiya

| Test | EDGE | ELEVENLABS | ESPEAK | PIPER |
|---|---|---|---|---|
| `app.py preflight` | ready | key nahi | espeak binary nahi | model nahi → model diya, ready |
| 68 unit tests | 68 OK | 68 OK | 68 OK | 68 OK |
| `scan` / `profiles` / `phonology` / `prosody-analyze` / `story-audio-plan` | chalta hai | chalta hai | chalta hai | chalta hai |
| `render` (asli awaaz) | network block (sandbox) | key ke bina band | binary ke bina band | **ban gaya** |
| `render-story` (poori kahani + jod) | — | — | — | **ban gaya** |

Sandbox me internet band hai, isliye EDGE ki asli awaaz yahan test nahi ho payi — uske liye GitHub runner chahiye (wahan chalti hai).

## 2. Jo kami mili (aur theek ki)

### Kami 1 — error ledger hi crash kar deta tha (chaaron engine)
`error_memory.py` me `x["fingerprint"]` seedha padha ja raha tha, par purane ledger rows me ye field hi nahi hai → `KeyError: 'fingerprint'`. Isse asli error chhup jata tha.
**Fix:** `.get("fingerprint")` + `repeat_observations` ka safe default. Ab saaf message aata hai:
`AUDIO_FAILED 1 Install eSpeak NG; binary not found. error_id …`

### Kami 2 — kirdaar ki pehchan galat thi (chaaron engine)
`hindi_core.py` poore vakya me keyword dhoondhta tha, isliye:
- `आरव: माँ, क्या आज…` → आरव ko **female** mil gaya (kyunki line me "माँ" tha)
- `दादी: … दादाजी सो रहे हैं` → दादी ko **male** mil gaya ("दादा" match)
**Fix:** pehle speaker ke **apne naam** se pehchano (lamba hint pehle), vakya se sirf **umar** ka andaza, ling kabhi nahi.
Ab: दादी → elderly/female, माँ → adult/female, आरव → adult/unspecified.

### Kami 3 — sab kirdaar ek hi awaaz me (sabse badi kami)
Ek hi model (pratham, mard) — narrator, ladka, maa, dadi sab 97–110 Hz par. `voice_shape()` bilkul nahi tha.
**Fix (teen hisse):**
1. `character_voice.voice_shape()` — umar + ling se pitch/raftaar (bachcha 1.45, dadi 0.82, aurat 1.05…)
2. `dialogue_renderer._reshape()` — har chunk par ffmpeg se sur/raftaar
3. **ling ke hisaab se model**: female → `hi_IN-priyamvada`, male → `hi_IN-pratham`

Ab naap (PIPER, asli render):
| Kirdaar | Pehle | Ab |
|---|---|---|
| वाचक (narrator) | 103 Hz | 107 Hz |
| आरव | 110 Hz | 111 Hz |
| माँ | 103 Hz | **246 Hz** |
| दादी | 97 Hz | **176 Hz** |

### Kami 4 — FFmpeg na hone par jod band
`audio_assembly.py` sirf PATH par `ffmpeg` dhoondhta tha → `"FFmpeg not installed"`, poori kahani jud hi nahi paati.
**Fix:** `imageio_ffmpeg` fallback. Ab `story_final.wav` ban raha hai (13.1 s).

### Kami 5 — purani profile file chup-chaap galat awaaz deti thi
`profiles/characters.json` purana ho to wahi use hota tha (galat ling ke saath).
**Fix:** profile file na ho to scan se khud bana lo.

## 3. Jo abhi bhi baaki hai (imaandari se)

- **आरव jaisa naam**: script me umar ka ishara nahi to adult hi rahega. Naam se umar ka andaza lagana galat hoga — manual profile dena behtar.
- **Emotion**: `prosody-analyze` sirf plan deta hai; asli bhaav model par nirbhar hai. PIPER/ESPEAK me emotion nahi aata.
- **ESPEAK**: `espeak-ng` system package chahiye (sandbox me apt nahi). Robot awaaz — sirf fallback.
- **ELEVENLABS**: key + per-character voice ID ke bina kuch nahi. Paisa lagta hai.
- **EDGE**: internet chahiye; offline machine par nahi chalega.
- **Naturalness**: PIPER abhi bhi robot-jaisa hai (f0 ghumav 7 vs insaan 10). Asli natural ke liye neural model chahiye — Sarvam ya bada open model.

## 4. Aage kya (poochh kar)

Charon engine alag-alag theek se chal rahe hain. Inko jodne ka tareeka main tab bataungi jab tum kaho — kyunki jodne se pehle tay karna hoga:
1. Kaun **default** hoga, aur kaun **fallback**?
2. Ek hi kirdaar ki awaaz sab engine me **same** rahegi ya nahi?
3. Jo engine fail ho, uska error doosre ko dikhega ya chhup jayega?
