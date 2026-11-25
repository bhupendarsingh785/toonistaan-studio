# Awaaz Bank — apni asli awaazein (25–35 kirdaar), poori tarah private

Kisi company par nirbhar nahi: recording aapki, model (IndicF5, MIT) aapke computer par, sab `voices/bank/` me.

## 1. Form kholo
```
pip install gradio
python tools/awaaz_bank.py ui          # browser me: http://127.0.0.1:7861  (sirf aapke computer par)
```
Har kirdaar ke liye: naam, ling (stri / purush / bachcha / budha / budhi), umar, **ijazat ka box**.
Phir har bhaav ka apna khaana — wahin **record karo ya file daalo**:

| Khaana | Padhne ka vaakya | |
|---|---|---|
| ⭐ Saadharan | आज सुबह मैं बाज़ार गया और ताज़ी सब्ज़ियाँ, फल और थोड़ी मिठाई ले आया। क्या तुम्हें पता है, नदी के उस पार एक पुराना मंदिर है? | **zaroori** |
| Khushi / hansna | अरे वाह! हा हा हा... सच में? ये तो कमाल हो गया! | marzi |
| Gussa | बस! बहुत हो गया। मैंने कितनी बार कहा है, ये काम मत करो! | marzi |
| Udaas | अब वो दिन कभी वापस नहीं आएँगे... मुझे उसकी बहुत याद आती है। | marzi |
| Dar | कौन है वहाँ? मुझे... मुझे बहुत डर लग रहा है। | marzi |
| Dheere | श्श्श... धीरे बोलो, कोई सुन लेगा। | marzi |
| Pukaar | अरे ओ मोहन! जल्दी इधर आओ! | marzi |
| Pyaar | आ जा बेटा, मेरे पास बैठ। सब ठीक हो जाएगा। | marzi |

Vaakya badal kar bole to neeche wale box me **wahi likho jo bola** (shabd-ba-shabd).

**1. Jaanch karo** -> har recording par turant: lambai, shor, phatna, bhinbhin (pankha/bijli), goonj, sur.
Kami ho to saaf bataata hai kya theek karna hai. **2. Save** -> bank me, aur sur se khud: bhaari / beech / halki.

## 2. Achhi recording
Shaant chhota kamra (parde/bistar), pankha-AC-TV band · phone 15–20 cm · 6–12 second · apne andaaz me ·
original file (WhatsApp wali nahi) · bachche ke liye maa-baap ki ijazat.

## 3. Kahani me apne aap
- Jis kirdaar ka naam bank me hai (जैसे गौरी) -> uski **asli awaaz**.
- Line ka bhaav (likha ho ya ASTRA ne samjha) -> **usi bhaav ki recording** reference banti hai
  (gussa -> gussa wali; hairani -> khushi wali; na ho -> saadharan).
- Kahani me naya kirdaar (जैसे रामू) -> bank ki koi **khaali** awaaz usi ling ki (`aadmi-1`, `aurat-2` jaise naam
  se recording kar ke rakho = pool). Yaad rehta hai: `knowledge/cast_auto.json`.
- IndicF5 na chale -> us line ke liye Piper (kahani adhoori nahi rehti) aur saaf sandesh.

```
python tools/awaaz_bank.py dikhao
python tools/awaaz_bank.py bolo गौरी "नमस्ते दादी" test.wav --bhaav khushi
python tools/kahani_dimaag.py jaanch stories/meri_kahani.txt      # kaun kis awaaz/bhaav me
python tools/kahani_dimaag.py stories/meri_kahani.txt out/kahani.mp3
```

## 4. IndicF5 (ek baar setup)
`indicf5_fix_v1/INSTALL_HI.md` ke hisaab se. Model gated hai: Hugging Face par ek baar shartein maan kar
`HF_TOKEN` se download; uske baad aapke computer par. GPU ho to `ASTRA_F5_DEVICE=cuda`.
Model ek hi baar load hota hai (pehle har line par dobara hota tha).

## Imaandaari
- Asli IndicF5 se yahan awaaz nahi banayi ja saki (internet/RAM nahi). Form, jaanch, bank, bhaav-chunaav aur
  kahani me jodna nakli awaaz se test hua — sab sahi chala.
- IndicF5 kabhi shabd chhod deta hai -> agla kadam: `realtime/kaan.py` (whisper) se har line sun kar dobara banana.
- Zero baseline Piper ka hai; asli awaazon ka apna zero pehli achhi kahani ke baad banana chahiye.

---

# Web aur dataset se — khud dhoondho, parkho, chuno, seekho

## A. Safai jaanch (har aane wali file par) — `tools/saaf_jaanch.py`
| Kharab (hata di jaati hai) | Dhyaan (chalti hai, theek kar di jaati hai) |
|---|---|
| phati awaaz (clipping) · lagbhag khaali | shuru/ant kata hua -> fade |
| **beep / watermark tone** (website ka nishaan) | shuru/ant ke 3s alag (intro/jingle) -> kaat do |
| sfx me **koi bol raha hai** (website ka naam, announcement) | DC jhukaav |
| bijli/pankhe ki bhinbhin 50/60 Hz | sfx me thoda shor |
| beech me awaaz gayab (dropout) | dabbi awaaz (sfx me) |
| goonj (insaan ki awaaz me) · insaan ki awaaz me dabbi/phone jaisi | bahut lambi -> kaat do |
| bola hua likhe text se mel nahi (whisper ho to) — extra shabd/ad | |
| **duplicate** — library me pehle se wahi awaaz | |

Jhingur/chidiya jaisi asli patli awaaz ko beep nahi maanta (beep bilkul sine jaisi patli hoti hai).
```
python tools/saaf_jaanch.py file.mp3 --kism sfx|bed|awaaz [--text "..."] [--insaan]
```

## B. Ped-paudhe, jeev-jantu, harkat — `tools/awaaz_khoj.py`
```
python tools/awaaz_khoj.py khoj मोर            # Hindi shabd -> khud samjha -> web -> 15 laaye -> jaanch -> 4 rakhe
python tools/awaaz_khoj.py bharo                # saare khaali khaane
python tools/awaaz_khoj.py raay library_awaaz/peacock/123_x.mp3 galat     # sunkar batao
python tools/awaaz_khoj.py sikhao मधुमक्खी "bee buzz"
python tools/awaaz_khoj.py dikhao
```
- Sirf **CC0 aur CC-BY** (NonCommercial kabhi nahi — channel commercial hai). Har file ka naam/uploader/link: `library_awaaz/CREDITS.txt` (CC-BY me video description me credit dena hota hai).
- Har khoj ki report: `library_awaaz/<khaana>/KHOJ.md` — kaun rakha, kaun hataya, kyun.
- **Seekhna**: 'sahi' -> file zyada baar bajegi, uploader par bharosa badhega, wo search shabd pehle aayega.
  'galat' -> file hategi, bharosa ghatega, us khaane ke liye nayi khoj. Naye Hindi shabd khud `kahani_rules.json` me jud jaate hain.
- Kahani banate waqt: jo awaaz library me nahi, **khud dhoondhi jaati hai** (key ho to; band karna ho: `ASTRA_AUTO_KHOJ=0`).
- Insaan ki gair-bolne wali awaazein (hansi, rona, taali, bachche khelte, bheed, khaansi) bhi — inme insaan ki awaaz chalti hai.

## C. Insaanon ki awaaz (ijazat wale dataset) — `tools/awaaz_dataset.py`
```
python tools/awaaz_dataset.py chuno D:/cv-corpus/hi --kitne 30                        # Common Voice Hindi (CC0)
python tools/awaaz_dataset.py chuno D:/IndicVoices-R/hindi --kitne 30 --license "IndicVoices-R (shartein)"
```
- Har bolne wale ki 5–14s clip, poori safai jaanch + (whisper ho to) bola hua = likha hua.
- Ling x umar me baant (aurat/aadmi jawan/madhyam, kishor, budha/budhi), har khaane me **bhaari se halki** tak phailaav.
- Bank me `ds-stri-jawan-02`, `ds-budha-01` jaise naam, license + srot ke saath. Kahani ke naye kirdaar ko khud sahi kism ki
  khaali awaaz (दादा -> budha, सरला -> jawan stri, बच्चा -> kishor agar bachcha na ho).
- Report: `knowledge/dataset_report.md` — chuni gayi aur kyun hatayi.

**Sach:** datasets me zyaadatar saadharan bolna — hansna/rona/gussa wali clip nahi, aur 12 se chhote bachche lagbhag nahi.
Mukhya kirdaaron ke bhaav aur bachchon ke liye apni recording (form) sabse achhi. YouTube/random site se kisi ki awaaz nahi.
