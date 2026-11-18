# Hindi ko natural bolna — Sarvam se kya seekha

Sarvam ka Bulbul sunne me insaani lagta hai. Unke apne blog (sarvam.ai/blogs) ke
mutabik raaz sirf "bada model" nahi — teen cheezein hain. Hum wahi teen cheezein
apne system me daal rahe hain, **bina kisi paid API ke**.

## 1. Text normalisation (sabse bada farq)
Bolne se pehle text ko bolne wale roop me badalna:
`"Dr. Sharma ka appointment 18 Jan ko 7:30 AM pe hai"`
→ `"डॉक्टर शर्मा का अपॉइंटमेंट अठारह जनवरी को साढ़े सात बजे सुबह है"`
- numbers → Hindi shabd (lakh/crore tak, 21-99 ke asli roop: पच्चीस, निन्यानवे)
- ₹ / Rs → "रुपये", % → "प्रतिशत", km → "किलोमीटर"
- 7:30 AM → "साढ़े सात बजे सुबह", 19:45 → "पौने आठ बजे"
- 18 Jan → "अठारह जनवरी"
- Dr./Mr./Prof./etc. → डॉक्टर/मिस्टर/प्रोफ़ेसर/वगैरह

Yahi "robotic" aur "insaan" ka asli farq hai — Sarvam bhi yahi likhta hai.

## 2. Uchchaaran (G2P)
English niyam Hindi par lagane se awaaz "parayi" lagti hai. Isliye aam Hinglish
shabd Devanagari me de dete hain: ka→का, hai→है, ticket→टिकट, train→ट्रेन.
(120+ shabd `astra/hindi_natural.py` ke `HINGLISH` me.)

## 3. Prosody (kahan rukna, kitni der)
Sarvam ye LLM se seekhta hai. Hamare paas niyam hain:
- vakya comma/danda par toota jata hai
- 10 shabd se lamba hissa phir toota jata hai
- "लेकिन / और / फिर" par chhota pause (0.18s), comma par 0.35s, vakya ke ant par 0.6s
- sawal ke ant me pause alag

## Kaise chalana hai
```python
from astra.hindi_natural import normalize_text, naturalize
normalize_text("Ticket ₹1,25,000 ka hai, 15% tax alag.")
# 'टिकट एक लाख पच्चीस हज़ार रुपये का है, पंद्रह प्रतिशत टैक्स अलग.'
naturalize("...")   # [{'text': ..., 'pause_after': 0.18}, ...]
```

## Abhi kya baaki hai
- Devanagari me na likhe angrezi shabd (jaise "aayegi", naam) — inke liye
  transliteration chahiye. Sarvam ye model se karta hai.
- Emotion/prosody ka model — Sarvam ka LLM; hamare paas niyam hi hain.
