# Voice Clone — video/audio se awaaz nikaalo, phir usi awaaz me poori kahani

Teen module milkar kaam karte hain:

| File | Kaam |
|---|---|
| `tools/voice_extract.py` | video/audio se awaaz nikaalta hai, shor kam karta hai, sabse saaf 5-15 s chunta hai |
| `tools/voice_clone.py` | us awaaz ko enroll karta hai aur script ki har line usi awaaz me bolta hai (bhaav ke saath) |
| `tools/voice_match.py` | "kitna match hua" ka imandar naap (F0 + timbre) |

## 1. Video se awaaz nikaalo

```bash
python tools/voice_extract.py run --in dadi.mp4 --out voices/dadi --seconds 12
```
- audio nikalta hai (ffmpeg)
- shor kam: `highpass=90, afftdn, loudnorm`
- sabse saaf window chunta hai (bolne ka hissa zyada, shor kam)
- `reference.wav` + `extract.json` (transcript ke saath, agar faster-whisper mile)

## 2. Enroll (ijazat ke saath)

```bash
# seedha video se
python tools/voice_clone.py enroll --name dadi --from-media dadi.mp4 \
  --transcript "नमस्ते, मैं दादी हूँ। तुम आ जाओ, खाना ठंडा हो रहा है।" --consent

# ya pehle se bani reference se
python tools/voice_clone.py enroll --name dadi --audio reference.wav --transcript "..." --consent
```
**Bina `--consent` enroll nahi hota** — awaaz uski hi ho ya likhit permission ho.

## 3. Poori script usi awaaz me (bhaav ke saath)

Script me bhaav square bracket me likho:

```
[neutral] शाम ढल रही थी।
[dukh] बेटा, आ जा पास। दादी तेरे को ही ढूँढ रही थी।
[gussa] चुप रहो! कुछ मत बोलो।
[dar] कौन है वहाँ?
[hasai] देखो ना, कितनी बड़ी तितली!
```

```bash
python tools/voice_clone.py speak --name dadi --script story.txt --out output/dadi/
```
Har line ka file banta hai: `001_neutral.wav`, `002_dukh.wav`, …

## 4. Match check (imandar)

```bash
python tools/voice_match.py check --ref reference.wav --new output/dadi/002_dukh.wav
```
Batata hai: sur ka farq (Hz aur %), timbre cosine, aur verdict — saath me saaf warning ki yeh pehchaan ka saboot nahi.

## 5. Sach (jhooth nahi)

- **100% copy koi system nahi deta.** Achhe cloning models ~90-95% "suni jaane wali" similarity dete hain, aur woh reference ki quality par nirbhar hai.
- Cloning backend chahiye: **IndicF5** (free, GPU) ya **XTTS-v2** (`pip install TTS`). Abhi is machine par dono nahi — code taiyar hai, engine nahi.
- Background shor wali recording se copy kamzor aati hai — `voice_extract` usi ko sudharta hai.

## 6. Tests
`python -m pytest tests -q` → **68 pass** (clone, extract, match — sab ke apne test).
