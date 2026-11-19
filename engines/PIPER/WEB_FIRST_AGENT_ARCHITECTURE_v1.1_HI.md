# WEB-FIRST Agent Architecture v1.1

## Default principle
No specific language model is selected, bundled, or required. Public web research is the primary information channel. Model endpoints are optional and operator-selected only.

## Search fabric
- DuckDuckGo HTML discovery (best-effort; may rate-limit or change markup).
- Optional DDGS Python package fallback.
- Optional self-hosted SearXNG via `SEARXNG_URL` (no API key; host/operator maintains it).
- Hugging Face model catalog, GitHub repository search, Crossref and arXiv discovery.
- Direct page extraction with robots checks, bounded sizes/timeouts, source hashes and provenance.

## Debate without a selected model
The no-model path creates analyst, domain-expert, skeptic and judge review records, extracts candidate statements, detects possible lexical conflicts across independent domains, generates counter-research queries, and refuses automatic promotion. This is deterministic evidence triage, not human-level semantic reasoning. A web page supplies information, not an inference engine.

## Independence and safety
Each engine stores its own research, memory, reports and proposals. Svara is only one optional source. Retrieved content is untrusted; no page instruction is followed, no downloaded code is executed, no weights are downloaded, and no production change is applied without tests and explicit approval.

## Speed
Search and research stay outside the TTS render path. Independent search queries run in a bounded worker pool (default 4, configurable up to 6; query count scales with requested page budget); each worker owns its HTTP session. One browser context is reused per batch; SearXNG is optional. Rate limits, robots rules and bounded fetches are respected.


## v1.2 benchmark addition
- Added a transparent Browser Agent research-process benchmark.
- Evaluates provenance, domain diversity, primary-source coverage, counter-research, skeptic output, decision gates and testable acceptance criteria.
- The score is explicitly not a semantic intelligence score.
