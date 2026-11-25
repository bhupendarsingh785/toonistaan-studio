# Free API ko majboot kiya — 5 asli bug theek (21 Nov 2026)

**system_check 19/19 · tests 176 pass, 2 skip** — har bug stress-test se mila, andaza nahi.

## Mile 5 bug aur unka hal
| # | Bug (asli test se) | Hal |
|---|---|---|
| 1 | `.wav` maangne par file me **MP3 bytes** aa rahe the (header `\xff\xf3`) | extension dekho: wav maanga to **asli PCM WAV** (`RIFF`) banata hai |
| 2 | **khaali text** aur **sirf "।।।"** par `True` laut raha tha (0.29 s khamosh file) | `_has_words()` — bina akshar kuch nahi banega, saaf `False` |
| 3 | network/429 par chunk **chup-chaap gir jaata** tha | **3 retry + backoff** (0.8 s, 1.6 s) har chunk par |
| 4 | bhaav ka pace galat jagah se aa raha tha (dry-run ko "elevenlabs measured" likh diya tha) | `source` sach likhta hai: `piper dry-run` / `elevenlabs (measured)` |
| 5 | dry-run ka naap **seekha hua** maan liya jaata tha → dukh **tez** ho gaya tha | provider ab sirf **asli naap** (elevenlabs/sarvam) maanta hai |

## Ab naap (free engine, asli file se)
| Bhaav | pace | duration |
|---|---|---|
| neutral | 1.00 | 3.46 s |
| **dukh** | 0.88 | **3.92 s** (dheema ✅) |
| **gussa** | 1.10 | **3.14 s** (tez ✅) |

## Aur majbooti
- Lambe text: 6 vakya → 2 chunk (max 187 akshar), jodne par text **bina khoi**.
- 24 s ki lambi file bhi sahi bani (24.22 s, RMS 0.104).
- Retry ke baad bhi fail ho to **jhooth nahi** — `False` + reason.

## Sach
- Google TTS **unofficial** hai — bahut zyada load par block kar sakta hai (isliye retry + chunk chhote).
- Awaaz robotic-ish hai; bhaav se sudharti hai par piper/edge se kam natural.
