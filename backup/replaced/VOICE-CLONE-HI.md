# ASTRA Voice Clone v3.1 — Hindi guide

## Existing v2 flow retained
The existing extraction, enrollment, rendering and rough match scripts remain in place.

## New: long-script preparation
```bash
python tools/script_pipeline.py --in story.txt --out output/story_manifest.json --max-chars 280
```
The planner parses tags such as `[dukh]`, `[gussa]`, `[whisper]` and speaker prefixes such as `दादी: ...`, then splits long lines at sentence/clause boundaries. It preserves order and writes a JSON manifest.

**Important:** tags are planning metadata. The current IndicF5/XTTS adapter does not yet pass a verified emotion-control parameter to the model. Do not assume `[dukh]` automatically creates sad acting.

## v3.1: fail-closed consent, profile safety and reference validation
Enrollment writes `voices/<profile>/consent_record.json` with UTC timestamp and scope. Missing, corrupt, expired, revoked or out-of-scope consent blocks profile loading. Voice names are restricted to safe path characters. Reference media is decoded through FFmpeg into verified mono 24 kHz PCM WAV. The record remains an operator attestation, not independent identity/signature verification.
```bash
python tools/voice_clone.py revoke --name speaker
```
After revocation, loading that profile for future generation is blocked and the voices list marks it as blocked. This does not yet securely erase backups, caches, or already exported audio.

## v3.1: long-form generation hardening

`speak` now uses sentence/clause-aware chunks (default 220 characters), retries failed chunks, validates generated WAVs, stores `generation_manifest.json`, resumes verified chunks for the same script/profile/backend, and streams the master WAV without loading the full story into RAM. The final `master.wav` is created only if every chunk succeeds. Short 100 ms gaps are inserted between chunks; adjust `gap_ms` in `_stitch_wavs` if the pacing needs tuning.

Example:
```bash
python tools/voice_clone.py speak --name speaker --script story.txt --out output/speaker --max-chars 220 --retries 2
```

## Current honest capability boundary
- Media extraction: FFmpeg-based audio extraction and basic cleanup; no robust diarization/source separation yet.
- Voice clone: reference-conditioned generation only if a supported backend is installed and model access is configured.
- Emotion: parsed as metadata, not yet reliably synthesized as controlled acting.
- Voice match: rough pitch/timbre proxy, not identity verification.
- Long form: chunking, WAV validation, retries, resume manifest and streamed master stitching are implemented. Hour-scale stress testing and backend/model caching remain outstanding.

## Tests

Current local automated suite: 32 passing tests. This verifies software paths and mocked synthesis workflows, not real IndicF5/XTTS audio quality or multi-hour inference.
Run:
```bash
python -m pytest tests -q
```
See `docs/WORLD_RESEARCH_AND_ARCHITECTURE_HI.md` for the research review, model comparisons, licensing warnings, architecture and next milestones.


## v3.2 Long-form reliability
- XTTS model cache ek process/device par model ko reuse karta hai.
- Resume ab reference audio fingerprint, transcript, backend aur chunk size verify karta hai.
- Multiple speaker labels par abhi explicit error aata hai; bina mapping ke galat ek-hi-voice dialogue nahi banega.
- Naye run me chunk fail hone par purana master.wav hata diya jata hai.
- 35 automated unit tests pass hue; real model inference aur multi-hour stress testing alag se zaroori hai.


## V3.4 quality checks

Runtime preflight (dependency status only):

```bash
python tools/preflight.py
```

After a successful generation, evaluate every generated chunk's WAV integrity and optionally Hindi ASR text accuracy:

```bash
python tools/evaluate_generation.py --manifest output/clone/generation_manifest.json --out output/clone/quality_report.json
python tools/evaluate_generation.py --manifest output/clone/generation_manifest.json --out output/clone/quality_report_asr.json --asr-model small --device cpu
```

ASR scoring requires `faster-whisper`. WER/CER measure text intelligibility, not speaker identity, naturalness or emotional acting. See `docs/HUMAN_LISTENER_SCORECARD_HI.md`.


## v3.5: Deep-learning identity screening and emotional prompts

- Optional ECAPA-TDNN speaker similarity scoring is available with `python tools/speaker_verification.py`. It reports a raw score only; no universal threshold is applied because Hindi-domain calibration is not available.
- Emotion reference clips can be registered with `add-emotion-reference` after explicit consent and confirmation that the clip is the enrolled speaker. IndicF5 can use the selected clip plus exact transcript as a reference prompt. This may influence prosody but does not guarantee a specific emotion.
- XTTS continues using the base speaker reference; the adapter does not claim true emotion control.
- Emotion reference changes invalidate cached long-form chunks. Emotion reference paths cannot point outside the voice profile.
- No model fine-tuning has been performed in this increment. Real inference and multi-hour tests remain required on the target machine.
