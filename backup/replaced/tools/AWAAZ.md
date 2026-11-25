# Toonistaan Awaaz Tool

## Setup (ek baar)
1. Python 3 aur ffmpeg install karo.
2. `pip install edge-tts`

## 1. Likha hua → awaaz
```
python3 tools/awaaz.py bolo "दादाजी! बचाओ!" --kirdaar swara_bachcha -o chhotu.mp3
python3 tools/awaaz.py bolo "डरो मत बेटा।" --kirdaar madhur_dada --bhaav calm -o dada.mp3
python3 tools/awaaz.py kirdaar          # saare kirdaar aur bhaav
```
- **Kirdaar:** madhur (narrator), swara (maa), swara_bachcha, madhur_bachcha, swara_dadi, madhur_dada
- **Bhaav:** happy, sad, angry, scared, surprised, calm, excited, whisper. Na do to Hindi shabdon se apne aap.

## 2. Apni recording saaf karo
```
python3 tools/awaaz.py saaf meri_recording.m4a -o saaf.mp3
python3 tools/awaaz.py saaf shor_wali.m4a --shor 32     # zyada shor ho tab
```
Kya hota hai, kram se:
1. Shor hatao (pankha, AC, hiss).
2. 80 Hz se neeche ki hum kaato.
3. Pehle awaaz ka star barabar karo.
4. Chup ke waqt gate lagao, taaki bacha shor dab jaaye.
5. Bhari awaaz kam karo.
6. 3.2 kHz par saafi badhao.
7. "S" ki seeti kam karo.
8. Compressor se dheemi aur tez awaaz barabar karo.
9. Limiter lagao, taaki awaaz kabhi na phate.
10. -16 LUFS par lao (YouTube/Pocket FM star).

**Jaanch:** shor wali recording mein awaaz/shor ka farak 11.7 dB se ~32 dB ho gaya.

**Achhi recording ke tips:**
- Phone munh se ek haath door rakho.
- Kamre mein parde ya kapde ho to goonj kam hoti hai.
- Pankha aur AC band karo.
- Pehle 2 second chup raho, taaki tool shor pehchaan sake.

## Video mein kaise judta hai
- `studio/gen_assets.py`: har line ki awaaz, kirdaar aur bhaav ke saath.
- `studio/story_video.py`: saafi wali chain, peeche ka mahaul (baarish, hawa, jhingur), music dabana (ducking) aur -16 LUFS.
