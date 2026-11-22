# Duniya engine — asli duniya jaisi awaaz (100% local)

Yeh folder aapke Seetal pipeline ke **Step 5, 7, 8 aur 9** ko badalta/badhata hai.
Koi cloud nahi, koi API key nahi: sirf `numpy`, `scipy`, `ffmpeg`.

## Files

| File | Kaam |
|---|---|
| `tools/world/duniya.py` | world engine: scene padhna → stereo duniya → ruke → mix → master |
| `tools/world/world_qa.py` | naye QA gate (holes, stereo, pauses, breathing, mud, LUFS) |
| `knowledge/world-map.json` | gyaan: 150+ shabd → awaaz, level, surface, din/raat, ruke ke niyam |

## Kya badla aur kyun (v8 ka naap → v9)

| Check | v8 (purana) | v9 demo | Kyun zaroori |
|---|---|---|---|
| Background ke chhed | 10.2% FAIL (106 baar sannata) | 0% PASS | asli duniya kabhi chup nahi hoti |
| Stereo | 0.00 (mono) FAIL | 0.165 PASS | nadi baayein se daayein guzarti hai |
| Vakya ke ruke / minute | 1.4 FAIL | 13.8 PASS | saans, bhaav, samajh |
| Lambe saans-ruke / minute | 0 FAIL | 1.25 PASS | scene ko jagah, nadi sunai deti hai |
| Bhaaripan (mud) | -1.3 dB WARN | -4.1 dB PASS | gol-mol awaaz saaf |
| Loudness | -18.1 LUFS | -16.2 LUFS | YouTube/phone standard |

## Sabse badi galti pipeline me (zaroor badlein)

**Step 5 `voice_fx.compress_silences` (50ms+ gap → 28ms, speech ≥89%)** awaaz ko robotic bana raha hai.
Insaan kahani sunate waqt rukta hai. Naya niyam (`world-map.json → pauses_s`):

- line ke **andar** ka gap: 0.10 s se kam mat karo, 0.35 s se zyada mat hone do
- comma ke baad 0.16–0.26 s · vakya (।) ke baad 0.45–0.70 s · sawaal/! ke baad 0.55–0.85 s
- kirdaar badle to 0.35–0.60 s · scene badle to 1.4–2.6 s (yahan duniya ubharti hai)
- QA gate `speech %` ko **65–80** karo (89% = bina saans ka bolna)

```python
# voice_fx.py me
def compress_silences(x, sr, min_gap=0.10, max_gap=0.35, thr_db=-45):
    # gap ko max_gap tak chhota karo, par min_gap se neeche KABHI nahi
```

Line ke beech ke ruke ab `duniya.py` khud daalta hai (`repace_lines`). Isliye Step 5 ko sirf line ke andar wale gap tak seemit rakhein.

## Pipeline me kaise jodein

```bash
# Step 3–4 ke baad: har line ki wav jod ke voice.wav + story_local.json (start/end/text/who) banao
python tools/world/duniya.py --voice voice.wav --marks story_local.json --out out.mp3
python tools/world/world_qa.py --audio out.mp3 --json qa_world.json   # audio_judge ke saath
```

- `--marks` do to engine har line ke shabd padh ke scene banata hai: नदी → river, चल/कदम → footsteps (surface: पत्ते/मिट्टी/पत्थर/पानी), रात → crickets, बारिश → rain, गरज → thunder...
- Zikr hote hi awaaz 1.2 s me ubharti hai, aur scene me bani rehti hai (yaad).
- Line me `"pan": -0.3` do to kirdaar aur uske kadam baayein taraf sunai denge.
- `scene.json` se haath se bhi objects/walks de sakte ho (dekho `demo/scene-jungle-nadi.json`).
- `--auto-pauses`: script na ho tab (jaise v8 demo) chup jagah dhundh ke insaan jaise lamba karta hai.

## Library (asli recordings) — realism ka agla kadam

Engine pehle `astra/library` (ya `ASTRA_LIBRARY` env) me naam se file dhundhta hai:
`*river*`, `*stream*`, `*nadi*`, `*bird*`, `*koel*`, `*footstep*`, `*dog*`, `*cow*`, `*crowd*`...
Mile to **asli recording** (random jagah se, 2 s crossfade loop), na mile to procedural synth.

- Procedural synth (khud bana): river, wind, leaves, rain, crickets, birds, koel, thunder, kadam (4 surface).
- **Jaanwar aur insaan (kutta, gaay, bandar, log, bheed, aag) ka synth nahi hai.** In ke liye
  library me recording chahiye (`world-map.json` me `"synth": false`). Nakli kutte ki awaaz scene bigaadti hai,
  isliye engine inhe chupchap chhod deta hai aur report me `MISSING` likhta hai.
- Asli recording synth se hamesha zyada real lagegi. Apni khud ki recording (phone se nadi/jungle) sabse achhi.
  Bahar se lo to CC0 wali lo, taaki 100% aapki rahe.

## Awaaz (TTS) — naturalness ki asli had

World layer kitni bhi achhi ho, Piper medium voice ki had wahi rahegi. Local, offline chalne wale behtar vikalp:

| Engine | Size | Khaasiyat | License (khud jaanch lein) |
|---|---|---|---|
| Indic Parler-TTS (AI4Bharat) | ~0.9B | text se style control (dheema, garam, bhaav), 21 bhasha | Apache-2.0, gated download |
| Kokoro-82M | 82M | bahut halka, CPU par tez; Hindi: hf_alpha, hf_beta, hm_omega, hm_psi | Apache-2.0 |
| IndicF5 (AI4Bharat) | ~0.4B | voice cloning: 3–10 s ki reference se wahi awaaz | model MIT, par training data non-commercial |

Sujhav: pehle **Kokoro** (2 core par bhi chalega) ko 5th engine ki tarah `voice/engines/kokoro/` me jodo,
aur Indic Parler ko A/B test me rakho. Clone sirf usi awaaz ka karo jiski ijaazat ho.

## Seemayein (sach)

- v9 demo me awaaz v8 ki hi hai (uska purana mono bed bhi andar mila hua hai). Sabse saaf nateeja tab aayega
  jab engine ko **sirf dialogue** wali voice.wav milegi, bina pehle ke background ke.
- Demo me script nahi tha, isliye scene haath se diya (`demo/scene-jungle-nadi.json`); `--marks` ke saath ye apne aap hoga.
- Synth nadi/chidiya achhi hain par asli recording jitni nahi. Library bharte hi engine unhe use karega.

## v10: Harkat + Bhaav (kirdaar ki har harkat, duniya ki pratikriya) — `tools/world/harkat.py`

**Pehle kya galat tha:** kadam background (patton ki sarsarahat) ke saath ek hi bus me normalize hote the,
same frequency par the, isliye dab jaate the (awaaz se ~23 dB neeche). Ab **FX bus alag hai**: har harkat
awaaz ke mukable apne fixed level par hai aur sirf 2 dB duck hoti hai.

| Script me shabd | Kya sunai deta hai |
|---|---|
| चल / कदम / गुज़र | kadam: edi + panja, sookhe patton ki charmar (surface: patte/mitti/patthar/ghaas/paani) |
| दौड़ / भाग | tez, bhaari kadam + haanfna; "रुका" aaye to wahin khatm |
| रुक / ठहर | aakhri kadam ki ghisat |
| गिर / फिसल · कूद | dhamm + patton ka bikharna · uchhal + girna |
| टहनी / चटक | sookhi lakdi tootna (shabd ke pal par) |
| छपाक / पानी में | chhapaak + bulbule |
| भेड़िया | pehli baar door se hu-aa, phir 4 panjon ki chaal: door se paas, ek taraf se doosri |
| गुर्रा · हुआँ | gurrahat · lambi hu-aa |
| गरज / बिजली | paas ki kadak + lambi gadgadahat (shabd ke pal par) |
| बारिश | barish ka bed (patton par boondein) |

**Bhaav → duniya:** `dar` = chidiyan chup, hawa tez, halki dhak-dhak · `khushi` = chidiyan zyada · `dukh` = hawa dheemi.
`bhaav` field na ho to shabd se pehchaan (डर, काँप, खुश, रो...).

**Shabd par timing:** ASR word timestamps (`"words": [{"w","start"}]`) line me ho to awaaz theek shabd par;
na ho to akshar ke hisaab se andaaza.

**Scene file se haath se:** `events`, `objects`, `emotions_at` me `"breath": n` likho to wo n-ve saans-ruke par lagega
(dekho `demo/scene-jungle-nadi-v10.json`).

**QA:** ruke ab voice-stem (`out.pauses.json`) se gine jaate hain, kyunki FX ruke ko bhar dete hain.
`mud` WARN garaj/barish wale scene me aana normal hai (garaj ka bass asli hai).

## v11: Pakka system — rozmarra ki duniya, halat, ghar/bahar, phone, khud seekhna

**Kamzori kya thi:** engine sirf jungle ke kuch shabd jaanta tha, aur "aadha shabd" milata tha
(`आगे` me `आग` → aag; `हवा चलने लगी` → kisi ka chalna). Rozmarra ki awaazein (phone, darwaza, ghar) thi hi nahi,
aur koi cheez "kab tak chale" (halat) ya "andar/bahar" nahi samajhta tha.

| Naya hissa | File | Kaam |
|---|---|---|
| Rozmarra ki awaazein (34) | `tools/world/awaazein.py` | phone (ghanti, ringtone, vibrate, uthana, rakhna, message), darwaza (khatkhat, charr, khulna, band), ghadi, bartan, cooker, nal, tapakna, kaagaz, kapda, typing, kaanch, aag, kulhaadi, kursi, taali, mandir/school/cycle ghanti, horn, gaadi/bike guzarna, kutta, murga, mendhak |
| Gyaan-kosh | `knowledge/sound-events.json` | 40+ events: shabd, awaaz, level, disha/doori, **halat** (phone tab tak baje jab tak "उठाया/हेलो" na aaye), aawa-jaahi, ghar/bahar, mausam, bhaav→duniya |
| Spotting | `tools/world/spotting.py` | kahani → cue sheet (kaun si awaaz, kis pal, kahan, kab tak). Niyam hamesha; **local LLM (Ollama) optional** chhupi awaazon ke liye |
| Khud seekhna | `knowledge/missing-sounds.json` | jis line me awaaz wala shabd ho par system ke paas awaaz na ho, woh yahan jama hoti hai (ginti ke saath). Agent isse naye events jodta hai |

**Ab apne aap hota hai:**
- **Halat (state):** phone ki ghanti "उठाया/हेलो" tak bajti hai, phir uthane ki click; aag "बुझ" tak; barish "बारिश रुकी" tak,
  phir 12 s tapakti boondein + chidiyan wapas; toofan me har 6–14 s garaj; "दोपहर" par subah khatm.
- **Ghar/bahar:** andar = kamre ki chhoti goonj (0.45 s) + room tone; bahar ka mausam deewar ke peeche (dabba, -8 dB).
  Bahar = khuli goonj + hawa.
- **Aawa-jaahi:** "आया" = kadam door (left) se paas; "चला गया" = paas se door (right); "अंदर आए" = darwaza + kadam;
  "बाहर निकला" = darwaza band; "बैठ गया" = kapde + (andar ho to) kursi.
- **Phone par baat:** line me `"phone": true` (ya who me "(phone)") to awaaz 300–3400 Hz, patli, bina goonj — us paar wali.
- **Scene ki saans:** agli line "शाम को / थोड़ी देर बाद / अगले दिन…" se shuru ho to pehle 1.4–2.6 s ka ruka.
- **Shabd ki pehchaan:** poora shabd milta hai; jad (stem) ke liye shabd ke ant me `*` (jaise `"बैठ*"`).
  Context ki galti se bachav: `हवा चल`, `बारिश रुक`, `पता चल`… harkat nahi maani jaati.

**Local LLM jodna (optional, 100% offline):**
```bash
ollama pull qwen2.5:7b          # ek baar
python tools/world/duniya.py --voice voice.wav --marks story.json --llm qwen2.5:7b --out out.mp3
```
LLM band ho to system chupchap sirf niyamon se chalta hai. LLM ke naye sujhaav (`new:tractor_engine`) missing-sounds me jaate hain.

**Naya sound jodna (3 kadam):** (1) `awaazein.py` me function + `REGISTRY` (ya library me recording rakho),
(2) `sound-events.json` me entry (shabd, level, pan, dist, state), (3) test kahani chalao, `world_qa.py` me `missing_sounds: 0`.

**Test:** `demo/test-ghar-phone-barish/` — 14 line ki kahani (subah ghar, phone, mama ka call, toofan, barish, darwaza, bahar, kutta, dar).
Is test me awaaz **espeak-ng** ki hai (sirf jaanch ke liye robotic) — asli kahani me aapka engine awaaz dega.

## v12: Seekhna + Rachna — ek baar suno, hazaar tareeke se banao

| File | Kaam |
|---|---|
| `tools/world/seekho.py` | ek recording → **DNA** (gehra vishleshan): roop (events/texture), tukde + unki poonchh (decay), laya (IOI), sur (f0, voiced), rang (MFCC, centroid), aakaar (attack/decay/AM), pehchaan-vector. `sound-events.json` me apne aap darj |
| `tools/world/rachna.py` | DNA se **naye roop**: events = asli tukde nayi laya me (har tukde ka apna sur/zor/chamak, kabhi do tukdon ka mel); texture = granular (kabhi na dohrane wali) |
| `knowledge/situation-rules.json` | halat → badlaav: bhaav (dar/gussa/khushi/dukh/shanti), aakaar (chhota/bada/bachcha), zor (halka/tez), aur QA ki seema |
| `knowledge/learned/<naam>/` | `dna.json`, `source.wav`, `memory.json` (pichhle 24 roop), `limits.json` (seekhi surakshit seema) |

**Khud-jaanch (har roop par, 6–9 ummeedwar):**
1. **Pehchaan:** naya roop apni asli awaaz se ≥ 0.45 mile **aur** system ki har doosri seekhi awaaz se 0.10 zyada.
   (Yaani sunne wala ise ab bhi "gaay" hi pehchaane, ghoda nahi.)
2. **Naya-pan:** pichhle 24 roopon se alag. Ek jaisa roop dobara nahi.
3. **Fail hua?** Halat ka asar aadha karke phir koshish. **Har koshish se seekhta hai:** kitna sur badalne par awaaz
   pehchaan me rehti hai (ghoda: -3 semitone tak). Agli baar shuru se is seema me.

**Kahani me apne aap:** "बड़ा घोड़ा ज़ोर से हिनहिनाया। सब डर गए!" → horse + size=bada + intensity=tez + emotion=dar.
Kram: seekhi awaaz (rachna) → library recording → synth. Ek shabd par seekhi awaaz ho to synth wali hat jaati hai (`prefer`).

**Seekhao:**
```bash
python tools/world/seekho.py --file gaay.wav --name cow --kw "गाय,बछड़ा,रंभा*" --pan 0.5 --dist 5
python tools/world/seekho.py --library astra/library        # library ki har file (naam se event)
python tools/world/rachna.py --name cow --n 10 --emotion dar --out-dir roop/   # 10 naye roop sunne ke liye
```

**Test (asli recordings, LibreOffice gallery se, 11 kHz purani quality):** gaay, ghoda, gilaas, taaliyan, gong, train.
32 roop me 30 pehle round me PASS; 2 fail (bada ghoda) → retry se PASS, seema seekhi gayi.

**Agents ke liye (self-evolving loop):**
`missing-sounds.json` padho → achhi CC0 recording dhundho (research agent) → `seekho.py` → test kahani → `world_qa.py`
(`missing_sounds: 0`) → commit. Jitni zyada aur behtar recordings, utni asli duniya.

**Seemayein:** rachna ki asliyat source recording jitni hi hai (11 kHz se 11 kHz). Ek recording = ek "kism";
bahut alag kism (jaise bhaunkna vs gurrana) ke liye alag recording sikhao. Pehchaan-vector ek naap hai, kaan nahi —
aakhri faisla sun ke karein.
