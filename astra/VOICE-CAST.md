# ASTRA — Awaaz ki poori list (VOICE CAST)

Sab kirdaar, unki awaaz, pitch aur Hz — ek hi jagah: **`astra/voices.json`**.
Badalna ho to **sirf wahi file** chhedo. `tools/voice_provider.py` use khud padh leta hai.
Purane naam (arjun, meera, swara…) waise hi chalte rahenge — kuch toota nahi.

| Kirdaar | Kaisa | Sarvam speaker | Pitch | Hz | Kab |
|---|---|---|---|---|---|
| sutradhar | kahani sunane wala | shubh | 1.00 | 112 | shuruaat/ant |
| madhur | jawan, shaant | shubh | 1.00 | 112 | hero |
| arjun | jawan, himmat wala | rahul | 1.00 | 110 | action |
| ramesh | gaon ka aadmi | aditya | 0.86 | 118 | aam aadmi |
| salim | tez bolne wala | rohan | 1.03 | 138 | dosti/mazak |
| chaiwala | halka, mazakiya | sunny | 1.15 | 150 | comedy |
| driver | gaadi wala | manan | 1.02 | 122 | safar |
| constable | police | ratan | 0.97 | 126 | dhamki |
| doctor | shaant | varun | 1.00 | 112 | bharosa |
| pandit | budha | ashutosh | 0.92 | 100 | pooja |
| chacha | budha, garv | dev | 0.94 | 98 | ghar |
| kaka | bahut budha | kabir | 0.95 | 92 | dheemi baat |
| mukhiya | sarpanch | sumit | 0.90 | 96 | gaon |
| bhoot | daravani | aayan | 0.80 | 86 | horror |
| chudail | daravani aurat | ishita | 0.88 | 172 | horror |
| meera | jawan aurat | ritu | 1.04 | 210 | heroine |
| sunita | ghar ki aurat | shreya | 1.03 | 205 | rasoi |
| aurat | aam awaaz | neha | 1.03 | 200 | bheed |
| maa | pyaar, thaki | kavitha | 0.94 | 228 | bhaavna |
| behen | chhoti, chulbuli | tanya | 1.16 | 252 | mazak |
| chachi | bolti tez | kavya | 1.02 | 220 | jhagda |
| bhabhi | ghar ki bahu | pooja | 1.05 | 215 | ghar |
| dadi | budhi, dhimi | roopa | 0.86 | 186 | kahani |
| bachcha | 6-8 saal | priya | 1.30 | 285 | masoom |
| announce | station/airport | mani | 1.35 | 168 | announcement |

## Niyam
- **Ek kirdaar = ek awaaz**, kahani ke shuru se ant tak.
- Do kirdaar ke Hz me **8 Hz se zyada** antar rakhna (warna awaaz mil jati hai).
- Bacche ki awaaz **280+ Hz**, budhe **100 se neeche**, bhoot **90 se neeche**.
- Naya kirdaar chahiye? `voices.json` me ek line jodo — bas.

## Dekho
```python
import sys; sys.path.insert(0, "tools")
import voice_provider as vp
print(vp.voice_cast())
```

## Umar ka rang (AGE_STYLE)
Awaaz sirf pitch se nahi badalti — kism ke hisaab se filter bhi lagta hai (`AGE_STYLE`):

| Kism | Pitch guna | Raftaar | Kampan (tremolo) | Lowpass | Highpass |
|---|---|---|---|---|---|
| female_old (dadi) | 0.94 | 0.93 | 3.2 Hz / 0.16 | 7200 | — |
| male_old (chacha, kaka, pandit) | 0.95 | 0.94 | 3.0 Hz / 0.14 | 7600 | — |
| child (bachcha) | 1.00 | 1.02 | — | — | 180 |
| creature (bhoot, chudail) | 0.96 | 0.92 | 5.0 Hz / 0.35 | 6000 | — |
| announce | 1.00 | 1.00 | — | — | 260 |

Isliye **dadi ki awaaz ladki jaisi nahi lagti** — dheemi, bhaari, thodi kampan wali.
Test (200 Hz tone): dadi chain ke baad **188 Hz**, behen chain ke baad **200 Hz** — farq saaf.
