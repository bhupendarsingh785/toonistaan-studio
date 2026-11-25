# Real-time Hindi checker + turant sudhaar — `tools/realtime/`

Line bante hi (agli line ke render ke saath-saath) jaanch karta hai: **kaun sa akshar galat hua, kya ban gaya,
kis kism ki galti hai**. Phir use turant theek karta hai, aur yaad rakhta hai ki kaunsa engine kis akshar mein kamzor hai. 100% local.

## Spec me kya kamzor tha → kya badla

| Spec (v65) | Kamzori | Ab |
|---|---|---|
| Real-time gates: clipping/echo/brightness/gap/pause | Sirf awaaz dekhte hain. **Hindi sahi boli ya nahi, banate waqt koi nahi dekhta** | Har line ASR → **akshar-akshar milaan** (`akshar.py`) |
| WER (shabd) baad me, 4.5 min | Shabd ke level par; kaun sa akshar, kya kism, nahi batata | **Akshar CER** + 15 kism (mahapraan, ghosh, murdhanya, ushm, nukta, ड़/ढ़, matra, schwa, anunasik, sanyukt…) |
| — | ASR ki likhai (ं/ँ, nukta, गई/गयी) ko galti gina jaata | **Pakki galti** (line dobara) vs **shak** (darj, line nahi rukti); likhai ke fark barabar maane jaate hain |
| Echo: 17–31 ms autocorrelation > 0.78 | 105 Hz awaaz ka 2–3 guna period = 19/28.5 ms → **sur ko echo samajhta** | Cepstrum, F0 ke multiples chhod kar |
| Brightness 1700–2300 Hz sabke liye | Har awaaz/engine ki chamak alag | Awaaz ki range di ho to; warna kirdaar ke apne profile se |
| Auto-fix: EQ/level/pause | Uchcharan ka koi sudhaar nahi | **Likhai badal kar dobara** (ख→क्ह, nukta roop, ि↔ी, ँ↔ं, क्ष→क्श…) + raftaar/sur |
| — | Galti yaad nahi rehti | **Galti-bahi** + **shabdkosh** (agli baar render se pehle) + **voice-profiles** |
| — | Kirdaar ki awaaz bhatke to pata nahi | **Nirantarta**: sur/raftaar/zor (pakka), chamak/rang (halka); seema kirdaar ke apne utaar-chadhav se |

## Files

| File | Kaam |
|---|---|
| `akshar.py` | akshar todna, normalize (ं=ँ, गयी=गई…), akshar alignment, galti ki kism, laghu-guru matra ginti |
| `kaan.py` | faster-whisper (int8, beam 1, bina prompt/pichhle text — ASR khud spelling na bhare), cache, **SimulatedEar (sirf test)** |
| `gates.py` | khaali, clipping, echo (F0-safe), brightness, gap, ant-kata (+ line par hi sudhaar) |
| `nirantarta.py` | kirdaar profile: sur, raftaar (matra/s), zor, chamak, rang; bhaav ki chhoot (gussa/dar +8% sur) |
| `sudhaar.py` | kism → ummeedwar likhai; shabdkosh (kirdaar + poora engine) |
| `bahi.py` | galti ka khaata: kamzor akshar, kism-war, kaunsa sudhaar jeeta, kahani-dar-kahani CER; "kabhi theek nahi hota" seekhna |
| `live.py` | sab jodta hai: render → jaanch → sudhaar (max 3) → yaad; live log + JSON + galti report |

## Chalao

```bash
pip install faster-whisper librosa soundfile
python tools/realtime/live.py --lines story.json --engine piper --piper-models voices.json \
       --whisper-model small --out out/kahani --strict          # CI: pakki galti bachi to exit 1
```

**story_local.py me jodna (asli real-time):**
```python
from tools.realtime.live import LiveChecker, PiperTTS
from tools.realtime.kaan import FasterWhisperEar, CacheEar
chk = LiveChecker(PiperTTS(models), CacheEar(FasterWhisperEar("small"), "knowledge/asr_cache"), engine="piper")
futs = []
for i, line in enumerate(lines):
    wav, sr = render_line(line)                 # aapka render
    futs.append(chk.submit(i, line, wav, sr))    # jaanch alag worker me — agli line ka render nahi rukta
final = [f.result() for f in futs]               # jodne se pehle: har line jaanchi + sudhri
chk.save(); print(chk.report_md(chk.summary("kahani")))
```

## Live log kaisa dikhta hai
```
   ✗ line 4: shabd 'खाना' — akshar 'खा' → 'का'  [महाप्राण (… 'ह' साँस)]
   ↻ line 4: 'खाना' [महाप्राण] aazmaya 'h-spell' → 'क्हाना' → ✓ theek
✓ PASS  line 4 [dadi] render 99 ms · jaanch 48 ms · sudhaar: uchcharan:खा→h-spell
   ★ line 9: pehle-se-sudhaar (seekha hua): खाना
   ⓘ line 6: 'क्षत्रिय' [संयुक्त अक्षर] — seekha hua: is engine par yeh kism kabhi theek nahi hui → seedha 'engine badlo'
   ⚠ line 7: narrator ki awaaz bhatki — raftaar 13.89 (chahiye 11.13)
```

## Test (is folder me)
`test/kahani-1.json`, `kahani-2.json` + `test/sim-kamzori.json` (nakli engine-kamzori) + `test/example-report-kahani-2.md`.
Kahani 1: pakki galti 6 → 2 (CER 0.038 → 0.013). Kahani 2: seekhi likhai pehle se lagi (खाना, ज़मीन — 0 galti),
na sudhrne wali kism (ष, क्ष) par seedha "engine badlo", tez line pakdi aur theek.

## Seemayein (sach)
- **Test SIMULATED kaan se hua** (model download is machine par band tha). Asli sateekta faster-whisper par nirbhar hai —
  apni machine par ek baar asli kahani par chala kar `bahi` dekhein.
- ASR kabhi galat bole shabd ko bhi "sahi" likh deta hai (bhasha-model ka asar) → kuch galtiyan chhup sakti hain.
  Isliye shabd-probability < 0.45 ko "shak" maana jaata hai. Agla kadam: doosra kaan — phoneme recognizer (wav2vec2 phoneme CTC, local).
- 2 core par faster-whisper `small` har line par ~1–3 s le sakta hai; jaanch alag worker me chalti hai, isliye render nahi rukta,
  par bahut chhoti lines par jaanch render se peeche reh sakti hai. GPU/`base` model se tez.
- "Engine badlo" abhi sirf **sujhav** hai; engine_bus se doosre engine par line dobara banwana agla kadam hai.
- ष/श ko kai Hindi bolne wale aur ASR ek jaisa bolte/likhte hain — chahein to `akshar.SEVERITY["ushm"] = "soft"`.

---

## Bhaav (bhavna) — chahiye kitna, mila kitna, kis shabd par — `bhaav.py` + `knowledge/bhaav-rules.json`

Har line par (shabdon wali jaanch ke saath hi):

**1. Lakshya (text se):** kaun sa bhaav (ख़ुशी, ग़ुस्सा, डर, दुख, हैरानी, प्यार, सामान्य), kitna (0–100%), aur **zor wale shabd**:
line ka `emotion` field + bhaav-shabd (रो, डर, वाह…) + vismayadi (अरे, हाय, वाह) + tez-karne-wale (बहुत, बिल्कुल) + ! ? …
Har zor wale shabd ka lakshya: **kitna lamba** (apni ummeed se ×), **kitna ooncha sur** (st), **kitna zor** (dB), **pehle/baad ruka** (ms).

**2. Maap (audio se), kirdaar ki apni saamanya awaaz ke mukable:** sur, sur ka phailav, raftaar (laghu-guru matra/s),
zor, chamak, aakhri sur (utaar/chadhav), ruke. Har bhaav ki "signature" se milaan →
`chahiye दुख 86% · mila दुख 36% → lakshya ka 42% (kam)`. **Zyada** bhaav bhi pakda jaata hai (lakshya ka 150%+).
Sur ki octave-galti saaf ki jaati hai; saamanya awaaz ka apna utaar-chadhav seekh kar usse chhote fark ko bhaav nahi maana jaata.

**3. Shabd-war:** har shabd ki shuru/ant (ASR timestamps, warna matra se baant kar awaaz ke gaddhon par), lambai, sur-shikhar,
zor (saadharan shabdon ke mukable), pehle ka ruka → `'आँसू': chahiye ×1.3/−1st/−1dB · mila ×1.12/−1st/+1dB`.

**4. Sudhaar (max 3, har baar chhota kadam, sabse achhi koshish rakhi jaati hai):** line par sur/raftaar/zor/chamak →
dobara render → **shabd tarashna** (zor wale shabd lambe/oonche/tez, unse pehle ruka) → aakhri shabd ka sur.
Bhaav wali line par nirantarta sur/raftaar/zor ko wapas nahi kheenchti (woh jaanbujh kar alag hain).

**5. Seekhna (`knowledge/bhaav-yaad.json`):**
- har engine/awaaz/bhaav ke jeete hue param → agli baar **render se pehle** (`★ pehle-se-bhaav`)
- kaun sa bhaav kitni baar kam pada, lakshya ka ausat
- saamanya awaaz ka profile + utaar-chadhav
- **aapki raay:** `python tools/realtime/bhaav.py --report out.json --line 3 --kam` (ya `--zyada`, `--sahi`) →
  naap ka calibration aur shuruaati param badalte hain

**Test (espeak, nakli kaan):** kahani 1 — dukh 13% → 74%, dar 42% → 85%, khushi 59% (kam, darj hua);
kahani 2 (seekhne ke baad) — dar seekhe param se pehli render me 101%, khushi ek sudhaar me 101%, 5/5 PASS.

**Seemayein:** signature shuruaati andaaze hain (prosody research ke aam rujhaan) — har awaaz ke liye sahi lines aur aapki raay
se behtar honge. Khushi/hairani/dar milte-julte hain (oonchi urja) — kabhi "mila हैरानी" dikhega jabki ख़ुशी % bhi saath dikhaya jaata hai.
Kuch hisse (sur ka phailav, ruke) sirf param se poore control nahi hote — piper me `noise_scale`/`noise_w` (bhaav ke liye) jodna agla kadam.
Word tarashna (time-stretch/pitch-shift) halki kalakriti (artifact) la sakta hai — sun kar jaanchein.
