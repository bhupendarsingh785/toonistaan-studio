#!/usr/bin/env python3
"""IndicF5 se Hindi awaaz — ek hi file, saaf-saaf.

Kyun yeh file hai:
  ai4bharat/IndicF5 ka apna code abhi tuta hua hai (3 cheezein):
    1. api.py -> load_model() ko 8 argument deta hai, par load_model sirf 7 leta hai.
    2. utils_infer.load_model() ke andar checkpoint load karne wali line COMMENT hai
       (# model = load_checkpoint(...)) — yani bina weight wala khaali model banta hai.
    3. Checkpoint ki keys "_orig_mod." prefix ke saath hain (torch.compile ka nishan),
       isliye seedha load_state_dict fail hota hai.
  Isliye yahan model khud banaya, weights khud load kiye (prefix hata kar),
  aur vocoder + reference audio se render kiya jata hai.

Chalane se pehle (ek baar):
  pip install -r requirements-indicf5-fixed.txt
  export HF_TOKEN=hf_xxx        # HF par IndicF5 ki terms accept ho chuki hon

Misal:
  python indicf5_render.py \
    --text "दादी ने कहा, बेटा, आ जा पास।" \
    --ref-audio meri_dadi.wav --ref-text "नमस्ते, मैं दादी हूँ।" \
    --out dadi.wav

Sirf jaanch (kuch download nahi):
  python indicf5_render.py --check-only
"""
from __future__ import annotations

import argparse
import os
import sys

MODEL_ID = "ai4bharat/IndicF5"
MODEL_CFG = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)


def _need(mod, hint):
    try:
        return __import__(mod)
    except Exception as exc:
        print(f"[x] '{mod}' nahi mila — {hint}")
        print(f"    (asli error: {exc})")
        sys.exit(2)


def check_only():
    """Bina model download kiye, environment ki jaanch."""
    ok = True
    for mod, hint in [
        ("torch", "pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu"),
        ("numpy", "pip install numpy==1.26.4"),
        ("soundfile", "pip install soundfile"),
        ("pydub", "pip install pydub"),
        ("vocos", "pip install vocos"),
        ("f5_tts", "pip install --no-deps git+https://github.com/ai4bharat/IndicF5.git"),
        ("huggingface_hub", "pip install huggingface_hub"),
    ]:
        try:
            m = __import__(mod)
            v = getattr(m, "__version__", "")
            print(f"[ok] {mod} {v}")
        except Exception as exc:
            ok = False
            print(f"[x] {mod} — {hint}  ({exc})")
    tok = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    print(f"[{'ok' if tok else 'x'}] HF_TOKEN {'mila' if tok else 'nahi mila (export HF_TOKEN=hf_...)'}")
    if not ok or not tok:
        print("\nNateeja: abhi render nahi hoga — upar wali lines theek karo.")
        return 1
    print("\nNateeja: sab taiyar hai. Ab --text/--ref-audio/--ref-text de kar chalao.")
    return 0


def build_model(device: str, hf_token: str | None):
    """Model banao aur asli weights load karo."""
    import torch
    from huggingface_hub import hf_hub_download
    from f5_tts.infer.utils_infer import load_model
    from f5_tts.model import DiT

    print("[1/4] checkpoint aur vocab la rahe hain…", flush=True)
    ckpt = hf_hub_download(MODEL_ID, "model.safetensors", token=hf_token)
    vocab = hf_hub_download(MODEL_ID, "checkpoints/vocab.txt", token=hf_token)

    print("[2/4] model bana rahe hain…", flush=True)
    model = load_model(DiT, MODEL_CFG, mel_spec_type="vocos", vocab_file=vocab, device=device)

    print("[3/4] weights load kar rahe hain (_orig_mod prefix hata kar)…", flush=True)
    ck = torch.load(ckpt, map_location=device, weights_only=False)
    sd = ck.get("model_state_dict", ck)
    sd = {(k[len("_orig_mod."):] if k.startswith("_orig_mod.") else k): v for k, v in sd.items()}
    sd = {k: v for k, v in sd.items() if not k.startswith("vocoder.")}
    missing, unexpected = model.load_state_dict(sd, strict=False)
    if len(missing) > 20:
        raise RuntimeError(
            f"weights theek se nahi baithe — missing {len(missing)}, unexpected {len(unexpected)}. "
            "Iska matlab checkpoint ka format badal gaya hai."
        )
    print(f"      theek: missing {len(missing)}, unexpected {len(unexpected)}", flush=True)
    model.eval()
    return model


def render(text, ref_audio, ref_text, out, device="cpu"):
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not hf_token:
        print("[x] HF_TOKEN nahi mila. Pehle export HF_TOKEN=hf_... karo.")
        return 1
    if not os.path.exists(ref_audio):
        print(f"[x] reference audio nahi mila: {ref_audio}")
        return 1
    if not ref_text.strip():
        print("[x] --ref-text khali hai. Reference audio me jo bola gaya hai, wahi likho.")
        return 1

    import soundfile as sf
    from f5_tts.infer.utils_infer import (load_vocoder, preprocess_ref_audio_text, infer_process)

    model = build_model(device, hf_token)
    print("[4/4] vocoder + reference taiyar…", flush=True)
    vocoder = load_vocoder("vocos", is_local=False, device=device)
    ref_wav, ref_txt = preprocess_ref_audio_text(ref_audio, ref_text, show_info=print)

    print("render ho raha hai (CPU par thoda time lagega)…", flush=True)
    wav, sr, _ = infer_process(ref_wav, ref_txt, text, model, vocoder, show_info=print)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    sf.write(out, wav, sr)
    print(f"\nBAN GAYA: {out}  ({round(len(wav)/sr, 2)} s @ {sr} Hz)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="IndicF5 Hindi render (fixed)")
    ap.add_argument("--text")
    ap.add_argument("--ref-audio")
    ap.add_argument("--ref-text", default="")
    ap.add_argument("--out", default="indicf5_out.wav")
    ap.add_argument("--device", default="cpu", help="cpu | cuda | mps")
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()

    if a.check_only:
        sys.exit(check_only())
    if not (a.text and a.ref_audio):
        ap.error("--text aur --ref-audio dono chahiye (ya --check-only)")
    sys.exit(render(a.text, a.ref_audio, a.ref_text, a.out, a.device))


if __name__ == "__main__":
    main()
