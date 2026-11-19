# WEB-FIRST v1.2 — Release Notes

## Added
- Two bounded counter-research rounds by default after the primary Browser Agent run.
- Counter-evidence is fetched as separate research jobs and deduplicated by content SHA-256 before final review.
- Final cognition review is rerun over the combined evidence corpus.
- A transparent Browser Agent benchmark evaluates source provenance, domain diversity, primary-source coverage, query diversity, counter-research, skeptic output, decision gates, traceability, and testable acceptance criteria.
- `python app.py agent-benchmark` runs the benchmark evaluator's offline self-test.
- `python app.py agent-benchmark <research.json> --cognition <cognition.json>` evaluates an actual saved run.

## Important limits
- Benchmark score measures research-process coverage, not intelligence or semantic correctness.
- Offline mode is structured evidence triage; it is not deep semantic reasoning or neural learning.
- Live web success depends on network access, provider availability, robots rules, and rate limits.
- No retrieved source is executed, no model weights are downloaded, and no production behavior is changed automatically.
- All four engines retain independent research stores, memory, and test suites.
