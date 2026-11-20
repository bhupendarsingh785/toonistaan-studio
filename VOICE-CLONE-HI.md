# Voice Clone — kisi ki awaaz copy karke poori script usi awaaz me

Yeh module **`tools/voice_clone.py`** hai. Isse koi bhi awaaz (mahila, ladki, ladka, budhi, bachcha) enroll hoti hai aur phir poori script usi awaaz me bolti hai.

## 1. Kaam kaise hota hai

```
enroll  →  5-15 second recording + exact transcript + ijazat (--consent)
speak   →  script ki har line us awaaz me banti hai (001.wav, 002.wav, ...)
mix     →  (baad me) background ke saath jodna
```

## 2. Backend — cloning kaun karega

| Backend | Kaam | Chahiye |
|---|---|---|
| **indicf5** | reference audio + transcript se cloning | `torch` + 8 GB+ RAM/GPU + HF token |
| **xtts** | Coqui XTTS-v2, 17 language | `pip install TTS` (GPU ho to tez) |
| piper | **cloning nahi karta** — sirf fallback | piper binary |

Jaanch: `python tools/voice_clone.py backends`

## 3. Ijazat lazmi (guard)

- Bina `--consent` enroll hi nahi hota.
- Awaaz uski hi honi chahiye, ya likhit permission ho.
- Kisi ki nakal karke thagi/धोखा karna — mana hai. Guard code me hai, isliye galti se bhi nahi hoga.

## 4. Commands

```bash
# 1) enroll (recording + transcript + consent)
python tools/voice_clone.py enroll --name dadi \
  --audio dadi.wav \
  --transcript "नमस्ते, मैं दादी हूँ। तुम आ जाओ, खाना ठंडा हो रहा है।" \
  --consent

# 2) list
python tools/voice_clone.py voices

# 3) poori script usi awaaz me
python tools/voice_clone.py speak --name dadi --script story.txt --out output/dadi/
```

## 5. Recording kaise honi chahiye

- 5-15 second, ek hi aadmi, bina shor, bina music.
- Saaf bolna, normal raftaar (na bahut dheema, na tez).
- **Transcript bilkul wahi** jo bola gaya — ek shabd ka farq bhi quality gira deta hai.
- Bhaav chahiye to har bhaav ka alag sample (neutral / dukh / khushi / gussa).

## 6. Abhi kya rukā hua hai

Is machine par `torch` aur `TTS` nahi hain, isliye cloning backend "ready" nahi dikhata — code taiyar hai, engine nahi.
Chalane ke liye: `pip install torch` (ya `pip install TTS`), phir `backends` command se check karo.

## 7. Tests

`python -m pytest tests/test_voice_clone.py -q` → 5/5 pass
(consent guard, enroll, list, speak, aur "backend na ho to jhoothi safalta na dikhe" — sab test hua.)
