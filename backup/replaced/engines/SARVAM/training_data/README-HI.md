# SARVAM — अलग Deep Learning Dataset

इस फ़ोल्डर का डेटा केवल SARVAM engine के लिए है। दूसरे engine का audio,
transcript, speaker identity या training output यहाँ copy न करें।

1. `audio/` में अपने/लाइसेंस-प्राप्त WAV clips रखें।
2. `manifest.example.csv` की copy `manifest.csv` नाम से बनाएँ।
3. हर पंक्ति में सही transcript, speaker ID, language (`hi`) और split (`train`, `validation`, `test`) भरें।
4. वक्ता की सहमति, dataset license और transcript accuracy स्वयं verify करें।
5. Audit चलाएँ: `python tools/deep_learning_readiness.py --engine sarvam`

**महत्वपूर्ण:** Audit पास होना model training की अनुमति/गारंटी नहीं है।
SARVAM के लिए उपयुक्त architecture, tokenizer/phonemizer, training recipe,
compute budget और held-out audio evaluation अलग से तय होने के बाद ही
वास्तविक neural fine-tuning शुरू होगी। अभी कोई model weight बदला नहीं जाता।
