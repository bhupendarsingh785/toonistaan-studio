# ASTRA — CORE RULES (dimaag)

Ye file meri soch hai. Har kahani banane se pehle **yahi** padhna hai. Koi bataye bina bhi
in niyamon par khara utarna hai.

## 1. Awaaz (voice) — sabse zaroori
- **Ek kirdaar = ek awaaz, shuru se aakhir tak.** Naam se mapping fix hai, kabhi na badle.
- **Umar aur ling ke hisaab se farak** (speaker + pitch + pace):
  - Dadi / budha: pitch 0.85-0.90, pace 0.85-0.90
  - Jawan mard: pitch 1.00, pace 0.98-1.03
  - Jawan aurat: pitch 1.02-1.05, pace 1.00
  - Ladki (teen): pitch 1.15-1.20, pace 1.10
  - Baccha / bacchi: pitch 1.30-1.35, pace 1.10-1.12
  - Bhoot / chudail: pitch 0.78-0.88, pace 0.78-0.82
- Do kirdaar ki awaaz **kabhi same nahi** — `astra/story_check.py` isko pakadta hai.

## 2. Background (SFX) — duniya ki tarah
- Sound **vaakya ke kaam** se chuno: खुला→gate_open, बंद→gate_close, बैठा→chair,
  थाली→plate, लेटा→bed, चढ़ा→stairs, दौड़ा→run, पैदल/चलते→footsteps.
- **Mahaul ka gate**: har env me sirf wahi sounds jo wahan ho sakte hain (room me train nahi).
- **Lambai cap**: footsteps 3.5s, door 4s, knock 3s, train 7s — scene ke andar hi, fade-out ke saath.
- Har scene me **kam se kam ek mahaul-awaaz** (village→chidiyan, room→ghadi, night→jhingur, street→bheed).
- Bhaav (emotion) se sound sirf **horror/suspense** me; realistic kahani me nahi.

## 3. Mix
- Awaaz hamesha sabse upar. Ambience 0.16, SFX 0.62-0.88 (door/knock zyada).
- SFX line ke **baad** shuru (0.02s), pehle nahi.
- Master −16 LUFS, limiter; shuru me 0.9s lead-in.

## 4. Safai
- Har library file pehle se saaf (denoise + gate + loudnorm). Naya sound aaye to
  `clean-library.yml` khud chalega. Kabhi bina saaf sound use nahi.

## 5. Kahani ki soch (logic)
- Jo kahani me ho raha hai, wahi sunai de. Ghar pahunch gaya to train ka horn nahi.
- Darwaza khula to awaaz, kadam chale to kadam, baith gaya to kursi.
- Bina wajah koi awaaz nahi; koi zaroori awaaz chhoote nahi.
- Har kahani pehle `astra/story_check.py` se guzre — phir render.

## 6. Provider kram
1. Local library (347+) → 2. Freesound → 3. Mixkit → 4. Procedural
Awaaz: Sarvam → ElevenLabs → edge-tts.

## DELETE RULE (kabhi na todna)

Swag kabhi kabhi bol kar likhta hai — usme shabd badal jaate hain ("delete" ki jagah
kuch aur, ya kuch aur ki jagah "delete"). Isliye:

1. Delete ki baat aaye to **turant mat karo**. Pehle **naam le kar** poochho:
   "kya ye file(s) delete karun?" — list ke saath.
2. Sirf **haan** milne par delete. "Haan" na mile to **kuch mat chhedo**.
3. Ek se zyada file ho to **ek-ek karke** batao, poora folder kabhi na udaao.
4. Duplicate hataana (ek recording do baar) **chhoot** hai — wo guard/dedupe khud karta hai,
   par naya batch aane par bhi pehle **check** karo, phir hataao.
5. Guard (`astra/guard.py`) hi aakhri deewar hai — galti se kuch gaya to wapas laata hai.
