# Changelog

## 0.8.0 — Story cue and environment analysis refinement
- Added separate `conch`, `crying_sobbing`, and `laughter` sound-event candidates; conch is no longer merged into the bell category.
- Expanded Hindi crying/sobbing emotion evidence so grief scenes are less likely to be missed by the lexical hint layer.
- Added scene environment candidates for village, temple, forest, palace, old mansion, hospital, railway station, city street, river/sea and home interior.
- Added summary counts for environment candidates and performance directions.
- Added regression tests for conch/bell separation, crying cues and environment candidates.
- These remain evidence-backed lexical candidates requiring review; this release does not claim semantic story understanding or automatic SFX asset assignment/insertion.

## 0.4.0
- Added story-aware adaptive stem mixing for narration/dialogue, music, ambience, room tone, SFX and Foley.
- Added bounded role-aware active-level matching (up to -24 dB attenuation / +6 dB boost depending on role), user gain offsets, smooth dialogue-driven music/ambience ducking, and scene mood/intensity automation.
- Added modest optional creative mix adjustments for peaceful, tense, action, sad and neutral scenes; no new sounds are fabricated or downloaded.
- Added `mix-story` CLI, example JSON spec and four story-mixer tests.
- Added per-track cue placement (`start_seconds`) and optional fades for story-timed effects.
- Added a global peak safety guard and a JSON mix report. Original source tracks remain untouched.
- The story mood and track roles are user-supplied metadata; no automatic script comprehension or semantic sound recognition is claimed.

## 0.3.0
- Added deeper acoustic diagnostics: approximate true peak, per-channel levels, DC offset, stereo correlation, crest factor, zero-crossing rate, spectral centroid/bandwidth/flux.
- Added 1-second review timeline and deterministic acoustic change map. These are explicitly non-semantic and never identify a sound source.
- Added recursive batch audit with SHA-256 fingerprints and non-destructive source verification.
- Expanded automated tests. No changes to ASTRA core; standalone module only.

## 0.2.0
- Added explicit asset profiles and blocked default denoising for non-speech/unknown audio.
- Added 20-item example audio catalog and preservation policy.

## 0.1.0
- Initial standalone ingestion, analysis, conservative processing and reports.

## 0.5.0
- Added a non-destructive post-render quality gate (`qa`) for sample peak, 4x oversampled estimated true peak, RMS, DC offset, near-silence, near-full-scale samples, stereo correlation and channel balance.
- Added machine-readable JSON QA reports and explicit review warnings.
- QA never edits source audio. True-peak and perceptual-listening limitations are stated in each report.

## 0.6.0
- Added local, deterministic Story Intelligence: explicit scene segmentation, screenplay-style speaker extraction, keyword-supported emotion/performance hints, and sound-event cue candidates.
- Added review-only story mix spec generation. Scene timing is intentionally unresolved until aligned to audio.
- Added script SHA-256 provenance, input size guard, confidence/evidence fields, human-review flags and explicit limitations.
- No external model/API is required; no assets are assigned or inserted automatically.

- v0.6.0 refinement: narrator lines are counted separately from character dialogue; character profiles include per-character lexical delivery hints and an explicit voice-continuity rule without identity inference.

## 0.7.0 — Hardening and regression safety
- Review-only story plans are now rejected by the render command until replaced with a render-ready spec.
- Added path-collision guards so audio outputs/reports cannot overwrite source audio, source scripts, or the mix specification.
- Existing render outputs/reports are protected by default; `--overwrite` is an explicit opt-in for mix-story.
- WAV output is atomic and rejects NaN/Inf rather than silently converting invalid samples to silence; JSON reports are atomic and reject non-standard NaN/Infinity values.
- Added finite-number, scene timing, track count, channel-layout, fade, gain, ducking and memory-budget validation.
- Added a preflight in-memory working-set estimate; very large mixes fail early instead of risking uncontrolled memory exhaustion.
- Stereo activity detection now uses channel RMS to avoid cancellation on anti-phase stereo dialogue.
- True-peak estimation now works in bounded chunks.
- Added explicit scene timecode parsing (`@MM:SS.mmm`, `[MM:SS]`, `[HH:MM:SS.mmm]`) and propagation to review plans when adjacent markers define a scene interval.
- Expanded Hindi/English sound-event vocabulary and tightened English whole-word matching.
- No original ASTRA integration; this remains a standalone engine.
- v0.7.0 refinement: `process_audio` and the `process` CLI also protect existing derivatives by default; replacement requires explicit `overwrite=True` / `--overwrite`.
- v0.7.0 refinement: metadata-only preflight estimates the working set before waveform decoding; multichannel audio is rejected rather than silently padded into an incorrect speaker layout.

## 0.9.0 — Standalone workflow architecture
- Added a fail-closed workflow orchestrator with explicit ordered stage IDs, adapter registration, readiness reporting, and stop-on-failure behavior.
- Added comprehensive Hindi standalone architecture and connector contracts covering story, voice, alignment, asset intelligence, music, spatial audio, mixing, QA, human review, and export.
- Explicitly documented which capabilities are currently implemented versus which require real AI/provider adapters; no unsupported production-complete claim.

## 0.10.0
- Added deterministic, explainable story-cue-to-catalog asset candidate matching.
- Added review-only CLI `match-assets`; no automatic insertion or downloads.
- Added licence/audition gating and tests for false assumptions and no-match behavior.
- Added `make_workflow_adapter()` so Story Understanding output feeds the asset-matching workflow stage directly.

## 0.11.0
- Added real-file audio library indexing with SHA-256 and acoustic descriptors.
- Added one-command `produce` pipeline: library scan, story analysis, approved cue decisions, mix render and technical QA.
- Added explicit omission decisions; unresolved cue timestamps or approvals block production.
- Added Sarvam Bulbul REST TTS adapter with per-character speaker continuity, long-text chunking, output validation and secret-safe API-key handling.
- Added mock-transport tests; live provider synthesis requires the user's valid API key and quota.
- Added `make_workflow_adapter()` for registering Sarvam TTS in the workflow voice-generation stage.
- Sarvam TTS now assembles generated line clips into a dialogue master with per-line timing metadata and configurable pauses.
- Sarvam TTS generation now rolls back only files created by a failed invocation, allowing safe retries after provider/network errors.
