# बीट्स और सात सुर — अपना संगीत बनाने का सिस्टम

कोई sample नहीं, कोई बाहरी library नहीं — **सब कुछ अपने कोड से बनता है**।

## 1. सात सुर (सरगम)
| सुर | पाश्चात्य | सा से दूरी |
|---|---|---|
| सा (Sa) | C | 0 |
| रे (Re) | D | 2 |
| ग (Ga) | E | 4 |
| म (Ma) | F | 5 |
| प (Pa) | G | 7 |
| ध (Dha) | A | 9 |
| नि (Ni) | B | 11 |

**7 थाट (scales)** जो सिस्टम में हैं:
- **बिलावल** (major) · **खमाज** · **काफ़ी** · **भैरवी** · **भैरव** · **यमन** (तीव्र म) · **आसावरी**

हर थाट में सुरों के नंबर बदलते हैं — इसलिए एक ही धुन अलग थाट में अलग मिज़ाज देती है।
उदाहरण: **भैरवी** = डर और गम · **बिलावल** = खुशी और वीरता · **आसावरी** = दुख · **खमाज** = रोमांस।

## 2. बीट्स (ताल)
16 step = 1 bar। हर step पर बजता है: **किक, स्नेयर, हाय-हैट, तबला**।

**भारतीय ताल:** केहरवा (92) · दादरा (84) · तीन ताल (100)
**दुनिया की बीट्स:** four-on-floor (124) · boom-bap (90) · trap (140) · breakbeat (165) · one-drop (78) · afrobeat (108)

## 3. मिज़ाज (mood) → अपने आप सेटिंग
| मिज़ाज | ताल | थाट | बास | पैड |
|---|---|---|---|---|
| epic | तीन ताल | बिलावल | root+fifth | wide |
| horror | one-drop | भैरवी | drone | dark |
| sad | दादरा | आसावरी | root | soft |
| romantic | केहरवा | खमाज | root+fifth | warm |
| action | breakbeat | भैरव | root+fifth | wide |
| happy | afrobeat | बिलावल | root+fifth | warm |
| lofi | boom-bap | काफ़ी | root | soft |
| trap | trap | काफ़ी | drone | dark |

## 4. चलाने का तरीका
```bash
python tools/music_make.py --mood horror --bars 16 --root D --out horror.mp3
python tools/music_make.py --mood epic --pattern teen --scale bilawal --bpm 100 --bars 32
python tools/music_make.py --list          # सारे pattern/scale देखो
```

## 5. अंदर क्या है (तकनीक)
- **किक:** sine sweep 110→45 Hz + click
- **स्नेयर:** noise + 185 Hz tone
- **हाय-हैट:** differenced noise (high-pass) + fast decay
- **तबला:** pitch-drop sine + ring
- **तार (pluck):** Karplus-Strong (asli taar jaisa, sample ke bina)
- **पैड:** additive sine stack + LFO + envelope
- **sidechain:** ढोल के वक़्त पैड/बास 45% तक दबता है
- **reverb:** 4 comb delays
- **level:** RMS −14 dBFS, peak ≤ 0.90

## 6. जाँच (जो नापा गया)
8 tracks बनाए: epic 28.8s · horror 36.9s · sad 34.3s · romantic 31.3s · happy 26.7s · lofi 32.0s · trap 20.6s · action 17.5s
सबका **RMS −14.3 dBFS**, peak **0.34–0.42** — clipping 0%।

## 7. सच
- यह **synth-based** है — Bollywood जैसा rich नहीं, पर **अपना, free, unlimited**।
- BPM detector कभी-कभी 2× या ½× पकड़ता है (हैट की वजह से) — यह पढ़ने की गलती है, बीट की नहीं।
- असली ढोल/तबला की गहराई के लिए आगे sample-based layer जोड़ना पड़ेगा।
