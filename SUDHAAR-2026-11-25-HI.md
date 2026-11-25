# ASTRA — poori jaanch aur sudhaar (25 Nov 2026)

## Chalane ka sahi kram (aapke computer par)

```
pip install -r requirements.txt
python tools/cast_build.py baseline/zero/script.txt out.mp3      # pehli baar Piper awaaz khud download (~60 MB x2)
python tools/zero_baseline.py --check out.mp3
python checker/voice_checker.py --file out.mp3
python tools/kram.py jaanch
python tools/system_doctor.py

# NAYA — poori audio-drama (har kirdaar alag + bhaav + doori + mahaul + harkat)
python tools/kahani_dimaag.py library-badao 6                     # asli recordings (freesound_key.txt me free key)
python tools/kahani_dimaag.py jaanch stories/kahani_dimaag_namuna.txt
python tools/kahani_dimaag.py stories/kahani_dimaag_namuna.txt out/drama.mp3
```

## Kya toota tha (sach me, jaanch se mila)

| # | Kharabi | Asar | Sudhaar |
|---|---|---|---|
| 1 | `cast_build` me Piper ki 22050 Hz awaaz ko bina badle 24000 Hz file me likha jaata tha | har awaaz ~9% tez aur patli (zero me गौरी 216–265 Hz, jabki asli 207 Hz) | sahi resample; `length_scale` 1.32 -> 1.21 taaki raftaar wahi rahe. Test: गौरी ab 208.7 Hz |
| 2 | Raaste `/scratch/work/...` pakke likhe the | aapke computer par `cast_build` chalta hi nahi | `.work/` (ya `ASTRA_WORK`), awaaz `voices/` (ya `ASTRA_VOICES`) |
| 3 | Piper model (onnx) zip me nahi | pehla command hi gir jaata | na mile to khud download, warna saaf sandesh |
| 4 | Cache ki chaabi me kirdaar ki settings nahi thi | CAST badlo, phir bhi purani awaaz aati | settings bhi chaabi me |
| 5 | Windows par `ffbin` ka shim (sh script) nahi chalta -> ffmpeg nahi milta | rubberband chup-chaap band = **sab kirdaar ek jaise** | seedha bundled ffmpeg; rubberband na ho to Praat se sur badalna (formant bacha) |
| 6 | `zero_baseline` / `voice_checker` file na milne par lamba traceback / galat "XX" | samajh nahi aata asli galti kahan | saaf sandesh: "pehle cast_build chalao" |
| 7 | `pronounce_test.py` `faster_whisper` ke bina import hi nahi | `kram jaanch` = "1 module me dikkat" | optional import |
| 8 | Document me likha tha "purana/ me archive" — par `tools/purana/` tha hi nahi | collision 2, orphan 4, BROKEN 1, P0 bug 1 | ASTRA ke apne `kram.py purana --karo` se 11 purani file + 4 akeli file `tools/purana/` me (delete nahi) |
| 9 | Doctor `__init__.py` ko takraav ginta tha; activate audit archive bhi jaanchta tha | jhoothe FAIL | dono sahi |
| 10 | Saans har baar ek hi seed se | har chupp me bilkul ek jaisi saans | har saans alag |
| 11 | Script me `#`, `[dṛśya]`, `(awaaz)` line bhi bolne lagti | — | ab chhodi jaati hain |

## Pehle -> ab

| Jaanch | Pehle | Ab |
|---|---|---|
| kram jaanch | 1 module me dikkat | **SAB THEEK** |
| system_audit | orphan 4 | orphan 0, collision 0, **SAB JUDA AUR CHALU** |
| bug_hunt | P0 1, P1 105 | **P0 0**, P1 95 |
| system_doctor | PASS 20 / FAIL 5 | **PASS 23 / FAIL 2** |
| activate | BROKEN 1 | BROKEN 0 |

Bache 2 FAIL machine ke hain, code ke nahi: `agents: mesh` (internet chahiye), `piper voices` (pehli baar cast_build chalate hi download).

## Naya: `tools/kahani_dimaag.py` (level 7_dimaag)

cast_build ki awaaz (zero chain) ke upar faisle:
- **Kirdaar**: CAST wale waise hi; naya kirdaar = naam se andaza (दादी -> budhi, भेड़िया -> janwar, बच्चा ...) aur `knowledge/cast_auto.json` me yaad.
- **Bhaav**: `(गुस्से से)` jaisa likha ho to wahi; na likha ho to ASTRA ka apna `realtime/bhaav.py` (halka, 60%). Sur badlav 0.9–1.12x — zero ki "mana" seema ke andar.
- **Doori / disha**: paas, door, bahut door, jhadi ke peeche, deewar ke peeche, phone, mann me, baayein/daayein. Pichli line "दूर से कमला ने पुकारा" bhi samajhta hai.
- **Mahaul**: raat/din/jungle/gaon/shahar/ghar/barish/nadi; ghar ke andar bahar ki awaaz dabi hui; bolte waqt mahaul neeche (ducking); beech-beech me door ki awaazein.
- **Harkat**: seedhi, kadam, darwaza, gaadi, jeev... sirf varnan se (kirdaar "कुत्ता" bole to bhaunk nahi). Ek ke baad ek (pehle seedhi, phir darwaza).
- **Zero guard**: kirdaaron ki saaf awaaz (`*_voice_dry.wav`) har baar zero se naapi jaati hai. Zero script is raaste se bhi ✓.
- Sikhana: `knowledge/kahani_rules.json`. Doctor me naya check: `kahani dimaag`.

## Imaandaari — kya abhi pakka nahi

- Yahan internet band tha, isliye asli Piper awaaz se sunkar test nahi hua (nakli 207/97 Hz awaaz se poori pipeline aur zero check chala). Aapke computer par pehli baar chalakar suniye.
- Sudhaar #1 ke baad sur thoda neeche (asli) hoga. Agar zero ki purani (tez) awaaz hi pasand thi to `LENGTH_SCALE` aur pitch badal sakte hain — par wo galti thi.
- Zero baseline me sirf female engine ke 3 kirdaar hain; vaachak/हरिदास/सरपंच (male) ka koi naap nahi. Male ke liye alag zero banana chahiye.
- Freesound `library-badao` ka asli download yahan test nahi ho saka (site block). Pehli baar chalakar dekhiye.
- `/scratch/input/...` wali 21 demo/test file ab bhi purane raaste maangti hain (catalog ki 1142 awaazein zip me nahi thi). Ye mukhya raaste me nahi hain.

## Naya (2): Awaaz Bank — apni asli awaazein
`tools/awaaz_bank.py` + guide `AWAAZ-BANK-HI.md`. Browser form (har bhaav ka khaana: saadharan zaroori, hansna/gussa/udaas/dar/dheere/pukaar/pyaar marzi), turant jaanch, `voices/bank/` me save, IndicF5 se clone (model ek baar load), cast_build me engine `indicf5`, kahani_dimaag line ke bhaav se sahi recording chunta hai, naye kirdaar ko bank ki khaali awaaz. Doctor me check: `awaaz bank`.

## Naya (3): Web/dataset se khud chunna aur seekhna
`saaf_jaanch.py` (beep/watermark, bolta hua naam, jingle, bhinbhin, dropout, dabbi, duplicate...), `awaaz_khoj.py` (Freesound CC0/CC-BY, Hindi shabd khud samjhe, sahi/galat se seekhe, kahani me khud), `awaaz_dataset.py` (Common Voice / IndicVoices-R se ling x umar x sur). Doctor: `safai jaanch` self-test. Guide: `AWAAZ-BANK-HI.md`.

## Aakhri poori jaanch (shuru se ant tak)
Naye sire se khol kar ek saath chalaya: aapke 4 command -> zero ✓ · kram SAB THEEK · awaaz bank + dataset (8 alag awaaz) ·
web khoj (nakli web) · poori kahani IndicF5 ke saath aur **bina IndicF5** (har kirdaar ke liye ek baar saaf sandesh, kahani poori).

Is jaanch me mile aur theek kiye:
| Kya | Asar | Sudhaar |
|---|---|---|
| `sound_resolver.py`: `word` naam ki cheez bani hi nahi thi | Hindi shabd-kosh kabhi use nahi hota tha (galti chup-chaap nigli jaati) | sahi shabd |
| 49 file me `/scratch/...` pakka | aapke computer par galat jagah / girna; ek jagah likhna, doosri jagah padhna | `tools/astra_paths.py` — ek jagah se saare raaste (purana `/scratch` ho to wahi) |
| IndicF5 na ho to har line par model load ki koshish | bahut dheema + har line par wahi galti | ek baar yaad, ek sandesh |
| backup (Piper) awaaz asli awaaz ke naam se cache | IndicF5 lagne ke baad bhi purani Piper awaaz | alag naam |
| haath se JSON me comma chhoota | poora system lamba error de kar girta | "line 5, column 4 par galti" — system ki apni file kharab ho to alag rakh kar naye sire se |
| khaali kahani | sirf mahaul wali bekaar file | saaf mana |
| bina danda ki bahut lambi line | TTS bigadta | 200 akshar ke tukde |

Nateeja: compile galti 0 · import 126/126 · kram SAB THEEK · orphan 0 · collision 0 · P0 0 · BROKEN 0 · doctor PASS 24 / FAIL 2
(bache 2: internet wala agents mesh, aur Piper model jo pehli baar cast_build chalate hi download hota hai).
Faaltu file: kuch nahi hataya. `tmp/` (64 KB), `backup/` (140 KB) aur top ki 40 purani `.md` report — nuksaan nahi; chaho to purani reports `docs/` me rakh denge.
