# IndicF5 — Jo chahiye (build spec)

19 Nov 2026 · Yeh list test se nikli hai: GitHub Actions par 16 run, har ek ka error note kiya gaya.
Neeche jo likha hai, bilkul wahi kaam karta hai — aur jo "mat karo" likha hai, wahi 6 baar fail hua.

---

## 1. Environment (copy-paste)

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -U pip setuptools wheel

# torch CPU (GPU ho to CUDA wheel)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# IndicF5 ka package — --no-deps ZAROORI hai (warna uska numpy pin sab tod deta hai)
pip install --no-deps git+https://github.com/ai4bharat/IndicF5.git

# baaki set (pins matter karte hain)
pip install "numpy==1.26.4" "datasets==2.14.0" "pyarrow==15.0.2" \
  accelerate vocos soundfile cached_path ema_pytorch hydra-core jieba librosa \
  matplotlib pydub pypinyin safetensors tomli torchdiffeq tqdm x_transformers \
  transformers_stream_generator click wandb huggingface_hub torchcodec

pip check   # conflict dikhe to aage mat badho
```

**Kyun yeh exact pins:** IndicF5 `numpy<=1.26.4` maangta hai, par naya `pyarrow` (jo `datasets` laata hai)
`numpy>=2` maangta hai → dono ek saath kabhi nahi chalte. `datasets==2.14.0` + `pyarrow==15.0.2` hi wo jodi hai
jo numpy 1.26 ke saath chalti hai. `torchcodec` chahiye kyunki `torchaudio 2.11+` audio load usi se karta hai.

---

## 2. Model access

1. HF par `ai4bharat/IndicF5` ki terms accept karo (gated model).
2. **Read** token banao.
3. Token sirf environment me: `export HF_TOKEN=hf_...` — code ya chat me kabhi nahi.

---

## 3. Repo me jo tuta hua hai (6 cheezein — inhe theek karna hai)

| # | Kya galat hai | Kya karna hai |
|---|---|---|
| 1 | `f5_tts/api.py` `load_model()` ko 8 argument deta hai, function 7 leta hai → `TypeError` | `api.py` use mat karo; seedha `f5_tts.infer.utils_infer` ke function bulao |
| 2 | `utils_infer.load_model()` me checkpoint load line **comment** hai → khaali model | weights khud load karo (neeche code) |
| 3 | `.safetensors` ko `torch.load()` se kholna galat | `safetensors.torch.load_file()` |
| 4 | Checkpoint keys par **do** prefix: `ema_model._orig_mod.` | dono hatao (loop me), warna 364 keys match nahi hoti |
| 5 | `vocoder.*` tensors DiT me nahi jaate | unhe chhod do |
| 6 | `AutoModel.from_pretrained(..., trust_remote_code=True)` par `Tensor on device cpu is not on the expected device meta!` | transformers ka rasta chhodo, `f5_tts` rasta use karo |

---

## 4. Chalne wala recipe (~25 line)

```python
import os, torch, soundfile as sf
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file
from f5_tts.infer.utils_infer import load_model, load_vocoder, preprocess_ref_audio_text, infer_process
from f5_tts.model import DiT

tok  = os.environ["HF_TOKEN"]
ckpt = hf_hub_download("ai4bharat/IndicF5", "model.safetensors", token=tok)
vocab= hf_hub_download("ai4bharat/IndicF5", "checkpoints/vocab.txt", token=tok)

CFG = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
model = load_model(DiT, CFG, mel_spec_type="vocos", vocab_file=vocab, device="cpu")

sd = load_file(ckpt)                                  # safetensors, torch.load nahi
clean = {}
for k, v in sd.items():
    key = k
    changed = True
    while changed:                                    # ema_model. + _orig_mod. dono
        changed = False
        for p in ("ema_model.", "model.", "_orig_mod."):
            if key.startswith(p):
                key = key[len(p):]; changed = True
    if key.startswith("vocoder."):
        continue
    clean[key] = v
model.load_state_dict(clean, strict=True)             # 364 tensors — exact match
model.eval()

vocoder  = load_vocoder("vocos", is_local=False, device="cpu")
ref_wav, ref_txt = preprocess_ref_audio_text("meri_dadi.wav", "नमस्ते, मैं दादी हूँ।", show_info=print)
wav, sr, _ = infer_process(ref_wav, ref_txt, "दादी ने कहा, बेटा, आ जा पास।", model, vocoder, show_info=print)
sf.write("dadi.wav", wav, sr)
```

---

## 5. Verification — "ho gaya" ka matlab

- [ ] `pip check` — koi conflict nahi
- [ ] `--check-only` — sab `[OK]`, token `[OK]`
- [ ] load par **`loaded 364 tensors; strict validation passed`** (kam/zyada = galat checkpoint)
- [ ] `dadi.wav` bane, lambai **0.5 s se zyada**, NaN/Inf na ho
- [ ] sun kar check: awaaz reference jaisi hai (warna reference badlo)

---

## 6. Mujhe (system ko) kya chahiye tumse

1. **Reference recording** — har kirdaar ke liye: 2-5 second, saaf, bina shor, akela aadmi/aurat, **apni ya ijazat wali awaaz**.
2. **Exact transcript** — recording me jo bola gaya, bilkul wahi shabd (ek shabd ka farq bhi quality gira deta hai).
3. Bhaav chahiye to **har bhaav ka alag sample** (neutral / dukh / khushi / gussa).
4. 25 kirdaar × 4 bhaav = ~100 recordings. Kam se shuru karo: 3 kirdaar × 1 bhaav.

---

## 7. Speed (sach)

- GitHub runner (7 GB, CPU): ek chhoti line par **15-20 minute** (model download alag).
- Colab free T4 / Kaggle GPU: **10-20 second** per line — practical yahi hai.
- 2 GB RAM wali machine par chalega hi nahi (model F32 ~1.6 GB).

## 8. Model card ki apni salah
Wahi log kehte hain: behtar vikalp **Indic-Speak** hai (22 languages, behtar TTS).
Isliye IndicF5 par bahut mehnat se pehle Indic-Speak ka demo sun lena samajhdari hogi.
