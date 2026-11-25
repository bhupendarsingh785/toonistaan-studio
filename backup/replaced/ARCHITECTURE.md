# Toonistaan: Virtual Actor System (12 engines) — asli haal (16 Nov 2026)

Lakshya: kirdaar insaan ki tarah chale, bole, haath hilaye, cheez uthaye, bhaav dikhaye, aur har scene mein ek jaisa rahe.

| # | Engine | Abhi kya hai (free, CPU) | Status | Asli (full) version ke liye kya chahiye |
|---|---|---|---|---|
| 1 | Facial animation | `motion.py` Talker: munh, daant, bhaunh, aankh jhapakna | ✅ basic | 3D face rig (blendshapes) ya GPU talking-head (SadTalker/LatentSync, Apache-2.0) |
| 2 | Full body rig | `puppet.py`: kirdaar sheet -> GrabCut cutout, 33 joint (MediaPipe) + baanh snap, ~1400 point mesh, haddi-motai weights | ✅ 2D v1 | 3D: MPFB/MakeHuman |
| 3 | Human motion | `pose_at`: idle, talk, walk, run, jump, wave, point, clap, cheer, nod (saamne se) | ✅ 2D v1 (baithna/side-walk abhi nahi) | mocap + 3D |
| 4 | Lip-sync | awaaz ki taakat se munh (energy) | ✅ basic | Phoneme/viseme (Rhubarb, MIT) — 87 MB, disk chahiye |
| 5 | Haath & ishaare | bolte waqt haath ka ishaara, hilana, point, taali (ungliyan alag nahi) | 🟡 | 3D hand rig |
| 6 | Emotion & acting | 6 bhaav: neutral, happy, sad, angry, surprised, scared -> chehra (kone, bhaunh, aankh) + body (sir jhukna, kaanpna, uchhalna) | ✅ v1 | blendshapes |
| 7 | Object interaction | — | ❌ | 3D scene + IK, ya AI video |
| 8 | IK & physics | pair zameen ki line par tike, parchhai, kood mein parchhai chhoti | 🟡 basic | Blender IK |
| 9 | Cloth/hair secondary motion | parallax + saans sway | 🟡 | Blender cloth/hair sim |
| 10 | Environment interaction | VFX: rain, lightning, leaves, dust, rays, birds, fireflies | ✅ | — |
| 11 | Character consistency | ek sheet = har scene wahi kirdaar (puppet) + cast bible + checker | ✅ (puppet scenes) | |
| 12 | Motion intelligence & quality | `check_images.py` + body/face tracking + aankh se 12 sawaal + log | ✅ | Video ke har frame ki jaanch (jerk/float) |

## Speed system (kaam baant kar)
- Server: awaaz turant (edge-tts), tasveer library cache (dobara 1 s).
- Local: `story_video.py` har scene alag process mein (`--jobs N`, default = CPU cores), lambe scene pehle.
- Clip cache: same tasveer + setting + awaaz = purana clip turant; sirf badla scene dobara banta (ep03: 232 s -> 65 s).
- Rukawat: free tasveer service 1 image / 45 s (ek IP). Isse tez: Pollinations key ya Canva credit (parallel).

## Seedhi baat
Asli insaan jaisi poori-body chalti video (engine 3, 5, 7, 8) ke do hi raaste hain:
1. **AI video model** (Veo/Seedance/Kling): GPU wale, free mein seemit (Google Flow ~roz kuch clip; Canva paid).
2. **Apna 3D studio** (Blender + MakeHuman + mocap): free software, par GPU ya bada server + render ka time chahiye.
Free CPU par hum 2D puppet engine (2, 3, 6, 8, 11) se poori-body chaal de rahe hain; asli 3D jaisi gehraai (ghoomna, baithna, cheez uthana, kapde ki physics) ke liye upar ke do raaste.

## Human Motion Core (`motion_core.py`, sudhar 41–55)
`Stage` ek scene ke sab kirdaaron ko ek saath chalata hai (ek baar banta, har frame `stage.draw(frame, i)`).

| # | Sudhar | Kya bana | Status |
|---|---|---|---|
| 41 | Chaal (gait) | bachcha/bada/buzurg ki alag chaal, bhaav se chaal badle, pair ke kadam se raftaar (fisalna kam) | ✅ |
| 42 | Haath ki samajh | kalai + pakad, bolte waqt ishaara | 🟡 ungliyan alag nahi (2D sheet) |
| 43 | Aankh ki nazar | sunne wala bolne wale ko dekhe, chhoti aankh-harkat (saccade) | ✅ |
| 44 | Saans | seena/kandhe halki saans, umr ke hisaab se | ✅ |
| 45 | Cheez pakadna | reach → hold → give, 2-haddi IK, cheez ek haath se doosre mein | ✅ 2D |
| 46 | Baatcheet acting | jiski awaaz, uska munh; sunne wala sir hilaye aur dekhe | ✅ |
| 47 | Bina jhatke badlaav | har action ke beech 0.45 s blend, pahunchne par apne aap idle | ✅ (baithna abhi nahi) |
| 48 | Wazan aur santulan | buzurg jhuke, chaal mein sharir ka jhool | 🟡 |
| 49 | Kirdaaron ka aapsi kaam | dena-lena, ek doosre ko dekhna, sir hilana | 🟡 (gale lagna/chhoona nahi) |
| 50 | Peeche ki halchal | sir, haath, baanh par spring (dheela jhool) | 🟡 (kapde ki physics nahi) |
| 51 | Chhote bhaav | pal bhar ki bhaunh/honth harkat | ✅ |
| 52 | Pair zameen par | zameen ki line, parchhai, dhalaan (`slope`) | 🟡 (seedhiyan nahi) |
| 53 | Bhaav se action | dar mein kaanpna, khushi mein uchhalna, dukh mein jhukna | ✅ |
| 54 | Motion retargeting | ek hi timeline kisi bhi kirdaar sheet par (haddi naap se) | 🟡 (mocap BVH nahi) |
| 55 | Motion jaanch | ghutna ulta-rok, jhatka-rok (14°/frame), haath dhad ke aar-paar ginti, report | ✅ |

Actor JSON:
```json
{"sheet": "chhotu_5.jpg", "age": "child", "voice": "swara_bachcha", "emotion": "scared",
 "x": 0.2, "y": 0.95, "height": 0.5, "slope": 0.0,
 "timeline": [{"t": 0, "action": "walk", "to": 0.45},
              {"t": 4, "action": "talk", "emotion": "happy", "target": {"actor": 1}},
              {"t": 9, "action": "reach", "target": {"prop": true}},
              {"t": 11, "action": "give", "target": {"actor": 1}}],
 "prop": {"sheet": "nest_prop.jpg", "size": 0.12, "in_hand": false, "at": [0.5, 0.93]}}
```
Actions: idle, talk, wave, point, clap, nod, cheer, walk, run, jump, reach, hold, give.
Speed: ~0.4 s/frame (2 kirdaar, 2 core); scene alag process mein chalte hain (`--jobs`).

## Puppet use (scene JSON)
"people": 0, "emotion": "happy", "actors": [{"sheet": "chhotu_5.jpg", "action": "walk", "x0": 0.25, "x1": 0.6, "y": 0.93, "height": 0.62, "voice": "swara_bachcha", "emotion": "surprised"}]
- sheet: `studio/sheets/` (saada background, poori body, A-pose: haath body se door). Naya kirdaar = ek nayi sheet.
- voice: is awaaz ki line par isi kirdaar ka munh hilega (kai kirdaar ek scene mein).
- Speed: ~0.2 s/frame per kirdaar (2 core par 15 s scene ~2 min).
- Abhi ki kamiyan: kandhe ke paas aasteen ka tukda reh jaata (haath upar karne par), chalte waqt pair thode fisalte, sirf saamne ka view.
