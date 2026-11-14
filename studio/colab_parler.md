# Pocket FM jaisi awaaz: Indic Parler-TTS (free Google Colab GPU)
1. colab.research.google.com > New notebook > Runtime > Change runtime type > T4 GPU
2. Cell 1:
   !pip install -q git+https://github.com/huggingface/parler-tts.git
3. Cell 2:
```python
import torch, soundfile as sf
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer
m = ParlerTTSForConditionalGeneration.from_pretrained("ai4bharat/indic-parler-tts").to("cuda")
tok = AutoTokenizer.from_pretrained("ai4bharat/indic-parler-tts")
dtok = AutoTokenizer.from_pretrained(m.config.text_encoder._name_or_path)
def say(text, desc, out):
    d = dtok(desc, return_tensors="pt").to("cuda"); p = tok(text, return_tensors="pt").to("cuda")
    a = m.generate(input_ids=d.input_ids, attention_mask=d.attention_mask, prompt_input_ids=p.input_ids, prompt_attention_mask=p.attention_mask)
    sf.write(out, a.cpu().numpy().squeeze(), m.config.sampling_rate)
say("अरे मुन्नी, देखो! मैं उड़ सकता हूँ!", "Rohit speaks with an excited, cheerful tone, close-up recording, very clear audio.", "chhotu_01.wav")
```
4. Bani .wav files download karke Claude ko bhejo; voice/<line>.wav naam se lag jayengi.
Har kirdaar ka description (desc) series bible mein likha rehta hai, taaki awaaz har episode mein same rahe.
