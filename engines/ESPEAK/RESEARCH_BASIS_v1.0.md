# Research Basis — Agent Intelligence v1.0

This package uses these references as design inputs. They are not runtime dependencies unless explicitly installed.

   - Model card lists 4B parameters, Apache-2.0, multilingual support across 100+ languages, and reasoning/agent capabilities. These are publisher claims; actual Hindi task performance must be tested locally.
2. **Ollama OpenAI compatibility** — https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx
   - Enables a local model server to be called through a chat-completions-compatible interface.
3. **Playwright Python introduction** — https://playwright.dev/python/docs/intro
   - Supports modern browser engines and browser automation in Python.
4. **Playwright browser contexts** — https://playwright.dev/python/docs/browser-contexts
   - Isolated browser contexts help separate sessions; this package reuses one Chromium process/context per research batch and creates/closes pages per source.
5. **Playwright events/network** — https://playwright.dev/python/docs/events and https://playwright.dev/python/docs/network
   - Useful for future robust navigation, request observation, and page workflow development.
6. **LangGraph persistence and graph orchestration** — https://langchain-ai.github.io/langgraph/concepts/persistence/ and https://langchain-ai.github.io/langgraph/
   - Studied for durable state, checkpointing, and separating deterministic workflow steps from model-driven decisions. LangGraph is not a required dependency in this release.
7. **DSPy optimization and evaluation metrics** — https://github.com/stanfordnlp/dspy/blob/main/docs/docs/learn/optimization/optimizers.md
   - Supports the design principle that optimization requires explicit measurable metrics and training/evaluation examples. DSPy is not a required dependency in this release.

## Architecture choices
- Four independent engine copies and four independent knowledge stores are retained.
- Browser discovery, bounded extraction, and open-source background collection are separate from TTS rendering.
- Four-role analysis is a sequential debate workflow: Research Analyst, Hindi TTS Domain Expert, Skeptic, Evidence Judge.
- Every claim is expected to carry source IDs; unsupported claims must be marked unknown.
- All improvement outputs remain proposals; no fetched code executes and no production behavior or model weights change automatically.
- If no LLM endpoint is configured, the system deliberately reports `offline_extractive_only`; it does not pretend keyword extraction is deep reasoning.
- Real neural fine-tuning is not performed. It requires rights-cleared/consented speech-text data, clean speaker-disjoint splits, compute, and held-out listening evaluation.
