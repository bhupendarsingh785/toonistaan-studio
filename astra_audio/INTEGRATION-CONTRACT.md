# ASTRA Integration Contract (future phase — NOT integrated)

Do not copy this module over existing ASTRA files. Keep it isolated until acceptance tests pass.

Suggested future adapter call:
```python
from astra_audio import analyze_audio, process_audio, ProcessingOptions

analysis = analyze_audio(input_path)
report = process_audio(
    input_path,
    output_path,
    ProcessingOptions(
        highpass_hz=55,
        hum_hz=50,
        preserve_ambience=True
    )
)
```

Expected future flow:
1. Intake stores immutable original.
2. Analysis report + human/context tags.
3. Policy decides allowed processing.
4. Processor creates a separate derivative.
5. Quality gate compares before/after and flags review.
6. Human listening approval before adding to ASTRA sound library.

The current engine does not expose a complete semantic model or ASTRA-specific callback contract. Do not wire it into Cinema/World Engine until those interfaces are agreed and tested.

## Future story-aware mix entry point (v0.4.0, still standalone)
```python
from astra_audio.story_mix import mix_story
report = mix_story("story-mix-spec.json", "story-mix.wav", "story-mix-report.json")
```
The spec assigns each user-supplied stem a role and optional `start_seconds`, fades and user `gain_db`; scene entries carry start/end, mood and intensity. Narration/dialogue activity drives smooth music/ambience ducking. Role-based level matching is bounded and reports when its requested correction hits a safety limit. The output path is explicitly prevented from overwriting an input stem.
This is metadata-driven mixing, not automatic script comprehension. Do not claim that the engine independently understands the story until a semantic script/scene model is implemented and validated.

## Story Intelligence v0.6 contract
- `analyze-script` is advisory and non-destructive; input script is never rewritten.
- Script analysis output is `astra-story-intelligence/v1` with source SHA-256, evidence, confidence and review flags.
- `build-story-spec` output is explicitly review-only. It is not a valid final render plan until scene timing and audio stem placement are supplied and reviewed.
- Never auto-assign assets solely from filenames or lexical cues; asset license and audition status must be checked separately.

## v0.7 hardening contract
- Review-only schema `astra-story-mix-spec-review/v1` MUST be rejected by `mix_story`.
- Audio source, story source, mix spec, output and report paths MUST be checked for collisions before writes.
- Existing render outputs/reports MUST NOT be replaced unless explicit overwrite is requested.
- Invalid floating-point controls and non-finite decoded samples MUST fail closed.
- Audio/JSON writes MUST be atomic.
- Mix memory use is estimated before summing; this remains an in-memory renderer, not a streaming long-form renderer.
- Current channel layout support is mono/stereo only. Do not silently pad multichannel stems into an assumed speaker layout.
- Explicit script timecodes are hints; scene intervals still require review and final alignment to the actual narration waveform.
- The processing pipeline MUST refuse to replace an existing derivative unless an explicit overwrite flag is supplied.
- Mix resource estimates MUST be calculated from metadata before decoding complete waveforms; unsupported multichannel input MUST be rejected, not guessed or silently remapped.
