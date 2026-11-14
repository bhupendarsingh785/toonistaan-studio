# Toonistaan Studio (Arjun ka poora system)

Hindi 3D cartoon kahaniyan banana, jaanchna aur YouTube (@Toonistaan3D) par daalna. Sab free tools se.
Ise Claude (arjun-studio agent) chalata hai; aapko sirf bolna hai kya banana hai.

## Andar kya hai

| Folder / file | Kaam |
|---|---|
| `studio/story_video.py` | Kahani video banata hai (1 se 10+ minute): camera chaal, fade, Hindi subtitle, title, music, SFX, .srt |
| `studio/gen_assets.py` | Server par: har scene ki free tasveer (Pollinations) + Hindi awaaz (Madhur/Swara neural, ya Piper) |
| `studio/check_images.py` | Image checker: dhundhlapan, roshni, khaali background, chehra, logon ki ginti |
| `studio/body_check.py` | Poori body (33 point) + haath (21 point) tracking, anupaat jaanch |
| `studio/contact_sheet.py` | Saari tasveerein ek sheet par |
| `studio/unpack_exec.py` | Server se aayi files kholna |
| `studio/sfx.py` | 13 sound effect + 5 mood music (bina internet) |
| `studio/models/` | Free AI models: chehra (YuNet), body/haath (MediaPipe), opencv_zoo se (Apache-2.0) |
| `studio/fonts/Hind-Bold.ttf` | Hindi subtitle font (OFL licence) |
| `studio/series/rampur/` | Episode 1 "रामपुर का बाँध": JSON, scenes, awaaz, notes |
| `studio/series/toonistaan_cast.md` | Kirdaaron ki list + Canva reference id |
| `studio/scenes/`, `render.js`, `make_episode.py`, `assemble.py`, `tts.py` | Purana 3D/2D engine (chhote demo) |
| `blender/make_hero.py` | Blender mein asli 3D kirdaar (mesh, rig, baal, kapde) |
| `youtube_studio/studio.py` | YouTube upload, schedule, thumbnail, subtitle, playlist, branding |
| `setup_server.sh` | Naya server zero se taiyaar karna |
| `.gitignore` | Secret files ko GitHub se bahar rakhta hai |

## Pakka niyam (sabse zaroori)
- `youtube_studio/secrets/` (client_secret.json, token) **kabhi GitHub par ya kisi ko nahi**. Ye aapke channel ki chaabi hai.
  Ye GitHub wali zip mein nahi hai; aapke paas purani `Toonistaan_YouTube_Studio.zip` mein hai, use sambhal ke rakhiye.
- GitHub repo **Private** banana.

## Zero se setup (step by step)

### A. GitHub par rakhna (sabse aasaan: Claude khud kare)
1. claude.ai/settings/connectors kholo -> GitHub -> Reconnect -> GitHub login -> Authorize (All repositories).
2. Claude ko likho: "Kit ko GitHub par private repo toonistaan-studio mein daal do".
3. Claude repo banayega aur saari files daal dega. Bas.

### B. GitHub par khud rakhna (computer chahiye; phone se folder upload nahi hota)
1. github.com par login -> upar `+` -> **New repository**.
2. Name: `toonistaan-studio`, **Private** chuno, "Add a README" mat chuno -> **Create repository**.
3. Computer par zip unzip karo. Andar `toonistaan-studio` folder milega.
4. Repo page par **uploading an existing file** link dabao.
5. `toonistaan-studio` folder ke **andar ki saari cheezein** (studio, blender, youtube_studio, README.md, setup_server.sh, .gitignore) browser mein kheench ke daalo. (Chrome/Edge folder ke saath upload karta hai.)
   - Ek baar mein 100 file ki seema hai: pehle `studio` folder, phir baaki.
   - `.gitignore` chhupi file hai: Windows mein "Hidden items" on karo, Mac mein Cmd+Shift+. dabao.
6. Neeche **Commit changes** dabao. Ho gaya.

### C. Server (Ample Computer) zero se (sirf naya server banana pade tab)
1. Claude ko likho: "Naya Toonistaan server banao aur setup_server.sh chalao".
2. Claude Ample par Ubuntu 24.04 server banayega (free plan: 2 GB), script chalayega, aur aakhir mein `SETUP_DONE` dikhega.
3. Phir Claude `studio/gen_assets.py` aur `blender/make_hero.py` ko `/root/studio/` mein daalega.
   Dhyaan: 2 GB disk lagbhag bhar jaati hai. Bade kaam (lip-sync, MakeHuman, server par poora video) ke liye Ample Pro chahiye.

### D. YouTube login (ek baar)
0. Pehle channel ki chaabi wapas rakho: purani `Toonistaan_YouTube_Studio.zip` se `secrets/client_secret.json` ko `youtube_studio/secrets/client_secret.json` par (sirf apne computer/server par, GitHub par kabhi nahi).
1. Claude ko likho: "YouTube login karo".
2. Claude ek link dega -> kholo -> **collegestudents701** account -> **Toonistaan** channel chuno -> **Allow**.
3. "This site can't be reached" aaye to ghabraana nahi: address bar ka **poora link copy** karke Claude ko bhej do.
4. Claude `check` chalayega; "login ✅" aana chahiye.
5. Google Cloud mein OAuth app **In production** rakhna, warna login 7 din mein khatam ho jaata.

## Roz ka kaam (bas itna bolna hai)
- "Naya episode banao: <kahani ka idea>, 2 minute" -> Claude script, awaaz, tasveerein, jaanch, video sab karega.
- "Is video ko kal 6 baje upload karo" -> schedule.
- Har tasveer pehle image checker se pass hoti hai; galat ho to dobara banti hai.

## Episode kaise banta hai (andar ka tareeka)
1. Episode JSON (namuna: `studio/series/rampur/ep01_bandh.json`): scene, English image prompt, Hindi lines (`madhur`/`swara`), music, camera, SFX, `people`.
2. Server: `python3.11 gen_assets.py ep.json epdir` (har tasveer ~1.5 min, free).
3. Laana: `unpack_exec.py`.
4. Jaanch: `python studio/check_images.py epdir ep.json` + aankh se 12 sawaal (image-checker skill). FIX wale scene dobara.
5. Video: `python studio/story_video.py ep.json epdir out.mp4` (font `studio/fonts/Hind-Bold.ttf` ko `~/.fonts` mein copy karke).
6. Upload: `youtube_studio/studio.py enqueue ...` phir `plan`.

## Licence / credit
- Tasveerein: Pollinations (free), Canva (aapke account se).
- Awaaz: Microsoft Edge neural voices (edge-tts), Piper voices (rhasspy, open licence).
- Models: OpenCV Zoo (YuNet, MediaPipe) Apache-2.0. Font: Hind (SIL OFL).
- Saare kirdaar original; kisi mashhoor cartoon ya asli insaan ki nakal nahi.

## Backup (agar kabhi kuch kho jaaye)
- `skills/`: saare 6 agent (SKILL.md). Claude mein dobara jodna ho to likho: "skills folder se mere agent wapas bana do".
- `scheduled_tasks/research_agent.md`: roz chalne wale research agent ka poora prompt.
- `gallery/`: logo, banner, poster, duniya, body-check, Blender kirdaar.
- Canva ki kirdaar tasveerein aapke Canva account mein hain (id `studio/series/toonistaan_cast.md` mein).
- Bade video (Rampur ka Bandh 22 MB) GitHub mein nahi; chat se download karke Google Drive/phone mein rakho.
