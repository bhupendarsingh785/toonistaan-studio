#!/usr/bin/env python3
"""Robust IndicF5 Hindi renderer.

Fixes the supplied implementation's critical checkpoint bug: model.safetensors
must be read with safetensors.torch.load_file, never torch.load. The loader also
validates checkpoint/model key and tensor-shape compatibility before inference.

Install dependencies from requirements-indicf5-fixed.txt, then install the
IndicF5 repository without allowing it to replace the pinned dependency set:
  pip install --no-deps git+https://github.com/ai4bharat/IndicF5.git

The gated Hugging Face model requires the user to accept its terms and provide
HF_TOKEN (or HUGGING_FACE_HUB_TOKEN) through the environment. Never put tokens
in source files or command-line arguments.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

MODEL_ID = "ai4bharat/IndicF5"
MODEL_CFG = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)


def _token() -> str | None:
    value = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    value = value.strip() if value else ""
    return value or None


def _import_check(module: str, label: str | None = None) -> tuple[bool, str]:
    try:
        mod = __import__(module)
        return True, str(getattr(mod, "__version__", "version unknown"))
    except Exception as exc:  # report import-time binary/version conflicts too
        return False, f"{type(exc).__name__}: {exc}"


def check_only(require_token: bool = False) -> int:
    """Check runtime without downloading the gated model or loading weights."""
    checks = [
        ("torch", "torch"),
        ("torchaudio", "torchaudio"),
        ("numpy", "numpy"),
        ("soundfile", "soundfile"),
        ("safetensors.torch", "safetensors"),
        ("vocos", "vocos"),
        ("f5_tts", "f5_tts"),
        ("huggingface_hub", "huggingface_hub"),
    ]
    failed = False
    for module, label in checks:
        ok, detail = _import_check(module)
        print(f"[{'OK' if ok else 'FAIL'}] {label}: {detail}")
        failed |= not ok

    token = _token()
    if token:
        print("[OK] Hugging Face token: present (value hidden)")
    else:
        required = bool(require_token)
        print(f"[{'FAIL' if required else 'WARN'}] Hugging Face token: not set; required only for gated model download")
        failed |= required

    try:
        import torch
        available = torch.cuda.is_available()
        print(f"[INFO] PyTorch: {torch.__version__}; CUDA available: {available}")
        try:
            import psutil  # optional diagnostic only
            print(f"[INFO] System RAM: {round(psutil.virtual_memory().total / (1024**3), 1)} GiB")
        except Exception:
            pass
    except Exception:
        pass

    if failed:
        print("\nResult: environment is not ready. Fix FAIL items above.")
        return 1
    print("\nResult: Python dependencies look ready. Model access/download and inference have NOT been tested by --check-only.")
    return 0


def _download_assets(token: str | None, revision: str | None = None) -> tuple[str, str]:
    from huggingface_hub import hf_hub_download

    kwargs: dict[str, Any] = {"repo_id": MODEL_ID, "token": token}
    if revision:
        kwargs["revision"] = revision
    ckpt = hf_hub_download(filename="model.safetensors", **kwargs)
    vocab = hf_hub_download(filename="checkpoints/vocab.txt", **kwargs)
    return ckpt, vocab


def _normalise_state_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Remove torch.compile prefix and non-DiT vocoder tensors safely."""
    state = raw
    # Support common wrapped checkpoint containers, while requiring tensor map.
    for key in ("model_state_dict", "state_dict", "model"):
        candidate = state.get(key) if isinstance(state, dict) else None
        if isinstance(candidate, dict):
            state = candidate
            break
    cleaned: dict[str, Any] = {}
    for original_key, value in state.items():
        if not isinstance(original_key, str):
            continue
        key = original_key
        while key.startswith("_orig_mod."):
            key = key[len("_orig_mod."):]
        if key.startswith("vocoder."):
            continue
        if key in cleaned:
            raise RuntimeError(f"Checkpoint key collision after prefix cleanup: {key}")
        cleaned[key] = value
    if not cleaned:
        raise RuntimeError("Checkpoint contains no usable model tensors.")
    return cleaned


def _load_safetensors(path: str, device: str) -> dict[str, Any]:
    # Critical correction: .safetensors is NOT a torch pickle file.
    from safetensors.torch import load_file
    return load_file(path, device=device)


def build_model(device: str, hf_token: str | None, revision: str | None = None):
    import torch
    from f5_tts.infer.utils_infer import load_model
    from f5_tts.model import DiT

    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA device requested, but torch.cuda.is_available() is False.")
    if device == "mps" and not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
        raise RuntimeError("MPS device requested, but PyTorch MPS is unavailable.")

    print("[1/4] Downloading/checking IndicF5 checkpoint and vocabulary…", flush=True)
    ckpt_path, vocab_path = _download_assets(hf_token, revision)
    print(f"      checkpoint: {Path(ckpt_path).name}; vocab: {Path(vocab_path).name}", flush=True)

    print("[2/4] Building model architecture…", flush=True)
    model = load_model(DiT, MODEL_CFG, mel_spec_type="vocos", vocab_file=vocab_path, device=device)

    print("[3/4] Loading safetensors weights and validating compatibility…", flush=True)
    state = _normalise_state_dict(_load_safetensors(ckpt_path, device))
    model_state = model.state_dict()
    missing_keys = sorted(set(model_state) - set(state))
    unexpected_keys = sorted(set(state) - set(model_state))
    shape_mismatches = [
        (key, tuple(state[key].shape), tuple(model_state[key].shape))
        for key in (set(model_state) & set(state))
        if hasattr(state[key], "shape") and tuple(state[key].shape) != tuple(model_state[key].shape)
    ]
    if shape_mismatches:
        sample = "; ".join(f"{k}: ckpt{a} != model{b}" for k, a, b in shape_mismatches[:5])
        raise RuntimeError(f"Checkpoint tensor shape mismatch ({len(shape_mismatches)}): {sample}")
    if missing_keys or unexpected_keys:
        raise RuntimeError(
            "Checkpoint/model keys do not match exactly; refusing a potentially random/partially loaded model. "
            f"missing={len(missing_keys)} {missing_keys[:8]}, "
            f"unexpected={len(unexpected_keys)} {unexpected_keys[:8]}. "
            "Check model revision/config before changing strictness."
        )
    model.load_state_dict(state, strict=True)
    model.eval()
    print(f"      loaded {len(state)} tensors; strict validation passed", flush=True)
    return model


def render(text: str, ref_audio: str, ref_text: str, out: str, device: str = "cpu", revision: str | None = None) -> int:
    token = _token()
    if not token:
        print("[FAIL] HF_TOKEN/HUGGING_FACE_HUB_TOKEN is missing. Set it as an environment secret; do not paste it into chat.")
        return 2
    if not text or not text.strip():
        print("[FAIL] --text is empty.")
        return 2
    ref_path = Path(ref_audio)
    if not ref_path.is_file():
        print(f"[FAIL] Reference audio not found: {ref_path}")
        return 2
    if not ref_text or not ref_text.strip():
        print("[FAIL] --ref-text is empty. It must exactly transcribe the spoken reference audio.")
        return 2

    try:
        import soundfile as sf
        from f5_tts.infer.utils_infer import load_vocoder, preprocess_ref_audio_text, infer_process
        model = build_model(device, token, revision)
        print("[4/4] Loading Vocos and preparing reference audio…", flush=True)
        vocoder = load_vocoder("vocos", is_local=False, device=device)
        ref_wav, ref_txt = preprocess_ref_audio_text(str(ref_path), ref_text, show_info=print)
        print("Generating audio… CPU inference may be very slow.", flush=True)
        result = infer_process(ref_wav, ref_txt, text, model, vocoder, show_info=print)
        if not isinstance(result, (tuple, list)) or len(result) < 2:
            raise RuntimeError("infer_process returned an unexpected result; expected (waveform, sample_rate, ...).")
        wav, sample_rate = result[0], int(result[1])
        if sample_rate <= 0 or wav is None or len(wav) == 0:
            raise RuntimeError("Inference returned empty audio or an invalid sample rate.")
        out_path = Path(out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out_path), wav, sample_rate, subtype="PCM_16")
        check, check_sr = sf.read(str(out_path), dtype="float32")
        if check.size == 0 or check_sr != sample_rate:
            raise RuntimeError("Output WAV verification failed after writing.")
        duration = len(check) / check_sr
        print(f"\nSUCCESS: {out_path.resolve()} ({duration:.2f}s @ {check_sr} Hz)")
        return 0
    except Exception as exc:
        print(f"\n[RENDER FAILED] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="IndicF5 Hindi renderer (strict checkpoint validation)")
    parser.add_argument("--text")
    parser.add_argument("--ref-audio")
    parser.add_argument("--ref-text", default="")
    parser.add_argument("--out", default="indicf5_out.wav")
    parser.add_argument("--device", default="cpu", help="cpu | cuda | cuda:0 | mps")
    parser.add_argument("--revision", default=None, help="Optional pinned Hugging Face model revision")
    parser.add_argument("--check-only", action="store_true", help="Check dependencies without model download")
    parser.add_argument("--require-token", action="store_true", help="Make missing HF token a check-only failure")
    args = parser.parse_args()
    if args.check_only:
        return check_only(require_token=args.require_token)
    if not (args.text and args.ref_audio):
        parser.error("--text and --ref-audio are required (or use --check-only)")
    return render(args.text, args.ref_audio, args.ref_text, args.out, args.device, args.revision)


if __name__ == "__main__":
    raise SystemExit(main())
