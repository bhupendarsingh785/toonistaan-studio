# Piper परियोजना — IndicF5 Neural Reference Voice (v1.6 incremental patch)

## यह बदलाव क्या है
यह **वैकल्पिक neural renderer adapter** है। यह मौजूदा Piper ONNX renderer को नहीं हटाता और न ही IndicF5 को Piper ONNX मॉडल बताता है। उपयोगकर्ता इसे अलग से चुनकर Hindi story voice render कर सकता है। पुराने Piper backend पर कोई बदलाव नहीं होता।

## इसे क्यों जोड़ा गया
आपके `engines-piper-story-fixed.mp3` sample की अवधि 13.166 सेकंड है। आपके test report में Piper के लिए naturalness को robot-जैसा कहा गया है और emotion को केवल analysis-plan बताया गया है। केवल pitch/speed बदलने से इस कमी का समाधान नहीं होता।

IndicF5 का आधिकारिक model card Hindi सहित 11 भारतीय भाषाएँ, 0.4B parameters, MIT license, और reference audio + exact transcript से speech generation बताता है। इससे हर पात्र और हर भाव के लिए अलग, अनुमति-प्राप्त reference sample देकर आवाज़ का रंग/अंदाज़ guide किया जा सकता है। यह reference voice/acting को हूबहू गारंटी नहीं देता।

## स्थापना
1. अलग virtual environment बनाएं; Piper की मौजूदा dependencies को न बदलें।
2. `pip install -r requirements-indicf5.txt`
3. Hugging Face पर `ai4bharat/IndicF5` की शर्तें स्वीकार करके login करें।
4. `profiles/indicf5_characters.example.json` को अपने profile में कॉपी करें।
5. `references/` में हर पात्र के अपने रिकॉर्ड किए हुए, अनुमति-प्राप्त sample रखें। हर sample कम-से-कम 2 सेकंड का हो। `text` में audio में बोले गए exact शब्द ही लिखें।
6. neutral, sad, pain, happy आदि के लिए अलग sample दें। कोई भाव sample न हो तो neutral fallback होगा और result warning देगा।
7. `IndicF5Backend.render(...)` को अपने app के explicit optional backend route से बुलाएं।

## उदाहरण
```python
from piper_indicf5_backend import IndicF5Backend
backend = IndicF5Backend(device="auto")
result = backend.render(
    text="माँ, मुझे बहुत दर्द हो रहा है।",
    profile_path="profiles/indicf5_characters.json",
    character="mother",
    emotion="pain",
    output_path="output/mother_pain.wav",
)
print(result)
```

## उच्चारण सुधार
- सामान्य लिखे हुए शब्दों को यह adapter अपने आप बदलता नहीं है।
- केवल profile में दिए गए `pronunciation_overrides` लागू होते हैं और result में उनका audit मिलता है।
- गलत नाम/शब्द का सही बोला हुआ रूप profile में जोड़ें; अनुमान से शब्द न बदलें।
- reference transcript को sample audio से अक्षरशः मिलाएँ।

## हार्डवेयर / सीमाएँ
- Model weights इस patch में शामिल नहीं हैं। पहली बार download के लिए इंटरनेट और Hugging Face access चाहिए।
- आधिकारिक card में model लगभग 0.4B parameters (F32) बताया गया है; वास्तविक RAM जरूरत runtime, audio length और device के अनुसार अधिक होगी। CPU पर inference धीमा हो सकता है; GPU auto-detect होता है।
- यह adapter Piper ONNX नहीं है; यह अलग backend है। इसे चुनने पर output IndicF5 से आएगा।
- Emotion के लिए text label अकेला काफी नहीं: emotion-specific reference clip देना जरूरी है। हँसी, सिसकी, साँस और sound effects स्वतः उत्पन्न होने की गारंटी नहीं।
- इस environment में असली IndicF5 model weights download/load नहीं हुए, इसलिए वास्तविक audio quality का दावा नहीं किया जा रहा।

## Sources
- IndicF5 model card: https://huggingface.co/ai4bharat/IndicF5
- IndicF5 official usage requires text + reference audio + its transcript.
