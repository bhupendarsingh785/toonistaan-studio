# EDGE Independent Hindi Voice Intelligence — v0.7

This engine is fully separate from the other three. It has its own browser collector, local model inventory, Hindi scanner, character profiles, error memory, quality reports and TTS adapter.

## Honest capability statement
Online voice adapter. Requires edge-tts; service availability is external and not guaranteed.

This package is a tested engineering foundation, not a finished high-quality Hindi voice model. It does not invent age-accurate voices, emotion support or model capabilities. Model discovery inventories local files; it does not download arbitrary models or infer capabilities from a filename. Real voice quality requires an actual compatible model and human listening tests.

## Safe setup
Python 3.10 or newer recommended.
```bash
python -m venv .venv
# activate the environment
pip install -r requirements.txt
```
Optional own browser:
```bash
pip install playwright
playwright install chromium
```
Optional audio inspection:
```bash
pip install soundfile numpy
```
Optional local Hindi ASR:
```bash
pip install faster-whisper
```

## Commands
```bash
python app.py preflight
python app.py scan examples/story.txt
python app.py models ./models
python app.py profiles examples/story.txt --overrides profiles/overrides.example.json
python app.py new-report --run-id first-audio-check
python app.py render examples/story.txt
python -m unittest discover -s tests -v
```

## Error prevention
- Every engine has its own persistent `memory/error_ledger.json`.
- Known error reappearing reopens the issue and blocks release.
- Reports never pass automatically; audio tests require human-reviewed evidence.
- Install/model/API preflight occurs before claiming a render is ready.
- Existing project files are not modified.

## Research/browser safety
Only collect text from URLs allowed by robots.txt. Optional `allowed_domains` in config narrows access. Respect website terms, privacy and copyright. Internet research does not train the speech model.

## Age and voice safety
Age profiles are production requirements. A real 3-year-old-sounding fictional voice requires an age-appropriate licensed model. Pitch-shifting an adult voice is not equivalent. Never clone a real person's voice without permission.

Known error workflow:
```bash
python app.py errors
python app.py resolve-error FINGERPRINT --evidence "Regression test name and observed passing output"
```
Do not close an error without actually rerunning the referenced test.

## v0.6 performance and dialogue controls
New modules:
- `performance.py`: speaker/emotion markup, explicit word stretch and pause planning.
- `dialogue_renderer.py`: per-character voice routing, chunk rendering, manifest and optional final assembly.
- `audio_assembly.py`: optional FFmpeg normalization/concatenation.
- `tests/test_performance.py`: regression tests for dialogue and prosody markup.

Example syntax:
```text
आरव [भाव:खुश]: अरे वाह!
माँ [भाव:गंभीर]: अब घर चलना चाहिए।
आरव: नहीं, [खींचें:नहीं] अभी पाँच मिनट और!
[विराम:500ms]
```
Only text inside `[खींचें:...]` is intentionally slowed. Ordinary words are not stretched by the planner. Punctuation produces bounded pause metadata. The exact audible result still depends on backend and voice model.

Set per-character voices in `profiles/characters.json`. Profile fields:
- `voice_id` for Edge/ElevenLabs
- `piper_model` for a character-specific Piper ONNX model
- `espeak_voice` for installed eSpeak voice variants

Run:
```bash
python app.py render-story examples/story_performance.txt --profiles profiles/characters.json
```
If no character profile is configured, the engine default voice is used and a warning is written. This is not considered successful multi-character voice differentiation.

Emotion controls are backend-specific. Eleven v4 audio tags are used where configured; Edge, standard Piper and eSpeak do not receive invented emotion capability. See `tts_engine.CAPABILITIES`.

Missing optional voice profiles are warnings, not render failures; successful chunks can still be assembled. A failed synthesis chunk blocks final assembly.


## v0.6 autonomous browser research agent
The engine now includes its own `browser_agent.py` (no cross-engine sharing). It creates search queries, discovers public sources, checks each source's robots.txt, extracts readable text, deduplicates by content hash, ranks candidates lexically, writes a timestamped evidence record, and hands a traceable digest to this engine's `knowledge_inbox/`. It does **not** silently train models or claim lexical relevance proves truth. Search-provider blocking/network failure is recorded, not hidden.

Run a research task:
```bash
python app.py research "Hindi TTS natural prosody speaker diarization model" --max-pages 12
python app.py agent-status
```
Each engine stores independent records in its own `research/`, `knowledge_inbox/`, and `reports/browser_agent_status.json`. Review evidence before importing claims into production configuration. The agent does not bypass paywalls, logins, robots rules, or website restrictions.


Engine-local maintenance check (read-only):
```bash
python app.py health-check
```
It checks required files, local storage writability, selected engine dependencies/model or credential configuration, browser-agent status, and pending research handoffs. It does not silently repair files, run continuously in the background, or train a model.


## v0.6 Deep Intelligence (engine-local)
This release adds an engine-private SQLite memory, feedback-driven research planner, foreground autopilot loop, and conservative Hindi story analysis for characters, emotion markup, candidate places/names, and unresolved relationship mentions. The four engines have separate databases and separate code copies.

Commands:
```bash
python app.py deep-analyze examples/story_performance.txt
python app.py feedback pronunciation "Hindi nasalization error in word ..." --severity high
python app.py intelligence-cycle --max-pages 8 --topics 2
python app.py autopilot --cycles 4 --interval 3600 --max-pages 8 --topics 2
# continuous foreground research loop (stop with Ctrl+C)
python app.py autopilot --continuous --interval 3600 --max-pages 8 --topics 2
python app.py intelligence-status
python -m unittest discover -s tests -v
```
Autopilot runs in the foreground and stops when the process/device stops. It is not an invisible always-on service. New web evidence is stored as pending evidence; it does not silently change model weights or production rules. Model training is intentionally deferred.


## Capability boundaries (important)
- The agent now uses federated public discovery providers (DuckDuckGo HTML, Hugging Face model catalogue, GitHub repository search, and Wikipedia search API), with provider errors recorded separately. Playwright is used when installed; bounded HTTP extraction is the fallback. robots.txt is checked before fetching pages.
- The continuous loop is a foreground process. It will not keep running after Android/Windows terminates the process or the device sleeps.
- This release improves persistent evidence memory and research planning. It does not train neural weights, synthesize new voices, or make unsupported backends gain emotion capabilities.
- Hindi entity/character analysis is evidence-conservative: explicit speaker labels and metadata are recognized; uncertain age, gender, relationships, names, and locations remain unknown/candidates rather than being guessed.
- Emotion detection without explicit `[भाव:...]` tags is heuristic, not a validated Hindi emotion model.


## v0.7 Hindi phonology and prosody intelligence
New independent modules `hindi_phonology.py` and `prosody_intelligence.py` inspect Devanagari aksharas, vowels, matras, consonants, aspiration, nasal marks and conjunct clusters, then create a sentence-level performance plan with emotion evidence, confidence, pace, pitch contour, energy and pause targets.

Run:
```bash
python app.py phonology examples/story.txt
python app.py prosody-analyze examples/story_performance.txt
python -m unittest discover -s tests -v
```

Important: this is an inspectable rule-based frontend, not a trained Hindi phoneme recognizer or emotional TTS model. It can improve analysis and expose ambiguity; it cannot make eSpeak sound human, add unsupported emotion control to Edge or standard Piper, or guarantee expressive output. The actual audio backend must support the requested voice and prosody.


## Release v0.7: sentence-level prosody and Hindi sound analysis
The v0.7 render pipeline now runs the sentence-level Hindi prosody planner and passes its delivery targets into the selected adapter. The phonology report exposes Devanagari aksharas, independent vowels, matras, inherent-schwa estimates, consonants, aspiration, nasal marks and conjunct clusters.

**Important limitation:** the planner is rule-based, not a deep neural language/emotion model. Edge and Piper only receive limited rate/pitch/duration adjustments; standard Piper does not gain expressive emotion controls. eSpeak remains a formant synthesizer and will still sound synthetic. ElevenLabs emotion tags depend on the selected model and configured voice. This release must not be described as human-realistic without listening tests on real configured voices.


## v0.8 upgrade
See `ADVANCED_AUDIO_AND_BROWSER_v0.8_HI.md` for the upgraded federated browser agent, story soundscape/Foley planning, audio QA and optional deep vocal analysis.


## Open-source learning connector (v0.9)

The Browser Agent queues a documentation-only research refresh in a daemon worker. It checks Svara-TTS v1 (Hugging Face model card, Kenpath inference repository and maintainer open-source page) alongside independent Indic-TTS / Indic-Parler project references. It never downloads model weights, starts a Svara inference server, or routes production TTS through Svara. The browser research call does not wait for this worker.

Collected evidence is stored under `knowledge_inbox/open_source/` with source URL, retrieval time and SHA-256. All items remain `UNVERIFIED_PENDING_REVIEW`; no fetched code is executed and no production config/model weights are automatically changed. If every Svara URL is unavailable, the other sources and the four TTS engines continue independently. Check progress with `python app.py open-source-status`.


## v1.0 Agent Intelligence rebuild
See `AGENT_INTELLIGENCE_v1.0_HI.md`. Research now includes model-planned query decomposition (when configured), reused browser session per batch, four-role evidence-grounded debate, skeptic review, and proposal-only improvement memory.


## WEB-FIRST Agent v1.1 (no selected AI model)
No LLM is preselected or required. Research uses public web sources first. For a self-hosted search fabric, run SearXNG (Docker required):

```bash
docker run -d --name searxng -p 8888:8080 searxng/searxng
```

Then set `SEARXNG_URL=http://localhost:8888` in `.env`. Leave it blank to use best-effort DuckDuckGo/GitHub/Hugging Face/Crossref/arXiv discovery. Optional DDGS fallback: `pip install -r requirements-browser-optional.txt`. Public engines may rate-limit; no unlimited hosted free quota is promised.

Search queries run in a bounded worker pool (`RESEARCH_SEARCH_WORKERS`, default 4, max 6). Research is separate from the TTS render path. Model-free debate creates evidence inventories, skeptic questions, possible lexical conflicts and follow-up queries; it does not claim human-level semantic reasoning.
