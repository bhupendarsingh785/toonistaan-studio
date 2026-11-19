# IndicF5 Render Fix — Installation (Hindi)

## Is patch mein pakka kiya gaya mukhya fix

Aapke purane `indicf5_render.py` mein `model.safetensors` ko `torch.load()` se khola ja raha tha. Yeh galat hai: `.safetensors` file ko `safetensors.torch.load_file()` se hi load karna chahiye. Naye script mein yeh theek hai.

Naya loader:
- `_orig_mod.` prefix ko safely hatata hai;
- `vocoder.*` tensors ko DiT model se alag rakhta hai;
- duplicate keys aur tensor shape mismatch par rukta hai;
- model aur checkpoint ke keys exact match na hon to random/partial model se awaaz banane ke bajay error deta hai;
- `strict=True` se weights load karta hai;
- output WAV likhne ke baad dobara read karke verify karta hai.

## Install (fresh virtual environment recommended)

### Linux / Google Colab CPU

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-indicf5-fixed.txt
python -m pip install --no-deps git+https://github.com/ai4bharat/IndicF5.git
python -m pip check
```

### GPU

Install a matching `torch` + `torchaudio` pair using the official PyTorch selector for the machine's CUDA version, then run the remaining commands above. Do not mix CPU and CUDA wheels.

### Hugging Face access

1. Sign in to Hugging Face and accept the `ai4bharat/IndicF5` model terms.
2. Create a Read token.
3. Set it as an environment secret; never paste it into source code or chat.

Linux:
```bash
export HF_TOKEN='hf_...'
```

PowerShell:
```powershell
$env:HF_TOKEN = 'hf_...'
```

## Environment check

```bash
python indicf5_render.py --check-only
```

This checks imports and prints whether a token is present. It does not download the model, verify Hugging Face access, load model weights, or prove that inference works.

## Render one sample

Use a clean 2–5 second Hindi reference recording and its exact transcript. The speaker must have consented to use of the recording.

```bash
python indicf5_render.py \
  --text "दादी ने कहा, बेटा, आ जा पास।" \
  --ref-audio reference.wav \
  --ref-text "नमस्ते, मैं दादी हूँ।" \
  --out output.wav \
  --device cpu
```

For a supported GPU, use `--device cuda`.

## Important limits

- The supplied problem report says the model is gated and needs a Hugging Face token.
- CPU inference was reported as 20+ minutes for a short line on the tested runner. GPU is strongly recommended for practical use.
- The model needs reference audio plus an exact transcript. This patch does not invent character reference recordings.
- No actual model inference was run while preparing this patch. Exact checkpoint key compatibility is checked at runtime and will fail loudly if upstream checkpoint architecture changes.
- Do not silently loosen strict checkpoint validation if it fails; capture the complete error and model revision first.
