# Awaaz ke engine — Sarvam se aage

## Kram (auto mode)
1. **sarvam** — sabse acchi Hindi (tumhari API key, kharch hota hai)
2. **eleven** — free 10k akshar/mahina (key chahiye)
3. **piper** — **poora OFFLINE**, 0 kharch, internet band ho to bhi chalta hai
4. **edge** — Microsoft neural, free, key nahi (internet chahiye)

## Kharch 0 karna ho
```bash
ASTRA_VOICE_ENGINE=piper   # ya edge
```

## Piper (offline)
- Model: `hi_IN-pratham-medium` (male) + `hi_IN-priyamvada-medium` (female)
- Pehli baar ~63 MB download, phir **hamesha local**
- Folder: `~/.cache/astra_piper` (ya `ASTRA_PIPER_DIR`)
- Kirdaar ka farak: **pitch** (SARVAM_PITCH) + **raftaar** (length_scale)
- Sach: piper ki awaaz **edge se thodi kam natural**, par **bilkul free + offline**

## Cache
Ek line ek baar banti hai; dobara usi text/awaaz par **API call zero** (TTS cache).
