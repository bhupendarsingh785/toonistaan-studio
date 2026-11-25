# IndicF5 — Problem kya hai (saaf-saaf, saboot ke saath)

Date: 19 Nov 2026 · Test kiya: GitHub Actions (7 GB RAM, CPU) par 14 run · Model: `ai4bharat/IndicF5` (0.4B, F32, MIT, gated)

## Ek line me
Model **accha hai**, par uska **code aur dependency-set tuta hua** hai — isliye "install karo aur chalao" wala rasta kaam nahi karta. Neeche har problem, uska asli error, aur uska hal.

---

## P1. Repo ka `api.py` khud se hi mismatch hai
`f5_tts/api.py` `load_model()` ko **8 argument** deta hai, par `utils_infer.load_model()` sirf **7** leta hai.
> `TypeError: load_model() takes from 2 to 7 positional arguments but 8 were given`

**Hal:** `api.py` ko chhodo, seedha `utils_infer` ke function bulao.

## P2. Checkpoint load karne wali line COMMENT hai
`utils_infer.py` me:
```python
# model = load_checkpoint(model, ckpt_path, device, dtype=dtype, use_ema=use_ema)
```
Yani jo model banta hai wo **khaali (random weights)** hota hai. Isse awaaz bakwaas aati — bina error ke.
**Hal:** weights khud load karo (P3 ke saath).

## P3. Checkpoint ki keys me `_orig_mod.` prefix hai
torch.compile se save hua checkpoint seedha load nahi hota:
> `RuntimeError: Error(s) in loading state_dict for CFM: Missing key(s) ... "transformer.time_embed.time_mlp.0.weight" ...`

**Hal:** keys se `_orig_mod.` hatao, `vocoder.*` keys chhod do, phir `load_state_dict(..., strict=False)`.

## P4. Dependencies aapas me takrati hain (asli headache)
- IndicF5 ka apna pin: `numpy<=1.26.4`
- `datasets` → naya `pyarrow` → jo maangta hai `numpy>=2.0`
> `ImportError: pyarrow requires NumPy 2.0 or newer, found 1.26.4`
> aur ulta: `AttributeError: module 'pyarrow' has no attribute 'json_'`

**Hal (test kiya):** `numpy==1.26.4` + `datasets==2.14.0` + `pyarrow==15.0.2`, aur `f5_tts` ko `--no-deps` se install karo.

## P5. Transformers ka rasta (AutoModel) kaam nahi karta
Model card `AutoModel.from_pretrained(..., trust_remote_code=True)` kehta hai. Har combination par:
> `RuntimeError: Tensor on device cpu is not on the expected device meta!`
(5 load variants try kiye — device_map="cpu", low_cpu_mem_usage=False, float32, sab fail)

**Hal:** transformers ka rasta chhodo; `f5_tts` ka `utils_infer` rasta use karo (P2/P3 ke fix ke saath).

## P6. Model "gated" hai — token ke bina 401
Terms accept karne ke baad bhi token chahiye. Bina token:
> `LocalProtocolError: Illegal header value b'Bearer '` (khaali token)

**Hal:** HF par Read token banao → GitHub secret `HF_TOKEN` me daalo (kabhi chat me nahi).

## P7. Machine ki seema (yahan)
Sandbox me **2 GB RAM** hai; model F32 me ~1.6 GB + torch runtime → load hi nahi hoga.
**Hal:** 8 GB+ RAM (GitHub runner 7 GB par chal jata hai, par dheema).

## P8. Har awaaz ke liye reference recording chahiye
Model ko **reference audio + uska exact transcript** dena padta hai.
25 kirdaar × 4 bhaav = **~100 recordings**. Ye main nahi de sakti — tumhari/kisi ki apni awaaz + ijazat chahiye.

## P9. CPU par bahut dheema
GitHub runner par ek chhoti line par **20+ minute** lag gaye (model download alag).
**Hal:** GPU (Colab free T4 / Kaggle) — wahan 10-20 second.

---

## Jo cheezein THEEK nikli (taaki sirf galtiyan na dikhein)
- Model ka license **MIT** hai, 11 Indian languages, 40k+ downloads.
- Aapke bheje **v1.6 patch ke 13/13 tests pass**, aur engine ke 81/81 tests pass.
- Upar ke P1–P5 hal karne ke baad ka **chalne wala program** taiyar hai:
  `indicf5_render.py` (isi folder me) — `--check-only` se environment jaanch sakte ho.
- Model card khud kehta hai: behtar vikalp **Indic-Speak** (22 languages) hai.

## Aage ka seedha rasta
1. Laptop/Colab (8 GB+) par `requirements-indicf5-fixed.txt` install karo.
2. `python indicf5_render.py --check-only` — sab ok dikhna chahiye.
3. Ek reference clip (2-5 sec, Hindi, apni awaaz) + uska transcript do.
4. `python indicf5_render.py --text "..." --ref-audio clip.wav --ref-text "..." --out test.wav`
5. Awaaz sun ke faisla: pasand aayi to engine me jodenge, warna Indic-Speak dekhenge.
