# Changelog — IndicF5 Render Fix

## Fixed
1. Critical: `model.safetensors` was passed to `torch.load()` (pickle loader). Replaced with `safetensors.torch.load_file()`.
2. Checkpoint extraction supports common `model_state_dict`, `state_dict`, and `model` wrappers.
3. `_orig_mod.` prefixes are removed repeatedly; duplicate cleaned keys cause an error.
4. `vocoder.*` keys are excluded from the DiT model state.
5. Removed permissive `missing <= 20` rule. Tensor shapes and exact key sets are validated; weights load with `strict=True`.
6. `--check-only` no longer incorrectly treats a missing Hugging Face token as a missing Python dependency. Token is WARN by default; use `--require-token` to make it mandatory.
7. Device availability is checked before model creation.
8. Empty text/reference, missing file, empty inference output, and invalid sample rate are handled explicitly.
9. Output is written as PCM-16 WAV and read back for a basic file integrity check.
10. Errors are reported without exposing the Hugging Face token.

## Not claimed
- No full IndicF5 model download or real speech generation was run in this environment.
- This patch does not provide the required speaker reference recordings.
- No naturalness, pronunciation, emotion, or latency score is claimed.
