# Asli awaazein (real recordings) — kaise on karein

## 1. Freesound (asli recording, free)
1. Account banao: https://freesound.org/home/login/
2. API key lo: https://freesound.org/apiv2/apply → **Apply for a new API credential** → *Client secret / Api key* copy karo
3. GitHub par secret add karo: repo → Settings → Secrets and variables → Actions → **New repository secret**
   Name: `FREESOUND_API_KEY`
4. Bas — ab har SFX pehle Freesound se aayega, na mile to procedural.

**Licence ka dhyan:** har sound ka licence metadata `astra/cache/real/<naam>.json` me save hota hai.
CC0 = credit ki zaroorat nahi. CC-BY = credit dena zaroori (author ka naam).

## 2. Pixabay ka sach
Pixabay ka **official API sirf images + videos** deta hai — sound effects aur music official API me **nahi** hain.
(Isliye Pixabay se real SFX programmatically nahi aate; unki site se manually download kar sakte ho.)

## 3. Awaaz ka volume (LUFS) — industry standard
| Kahan | Target |
|---|---|
| Podcast / Pocket FM jaisa | **−16 LUFS** |
| YouTube | −14 LUFS |
| TV / broadcast (EBU R128) | −23 LUFS |
| Hamara master | **−16 LUFS, TP −1.5 dB** |

Isi liye hamara mix podcast ke liye theek hai; YouTube par daalna ho to `loudnorm=I=-14` kar dena.

## 4. Module
```python
import real_audio
real_audio.fetch("footsteps")     # -> wav path ya None
real_audio.search("thunder")      # -> list (key ho to)
real_audio.normalize_lufs("a.wav", -16)
```
