# Agent Intelligence v1.1 — WEB-FIRST

## मुख्य निर्णय
किसी एक AI मॉडल का चयन, default या अनिवार्य dependency नहीं है। चारों agents की प्राथमिक सूचना-शक्ति World Wide Web, सार्वजनिक शोध-पत्र, आधिकारिक दस्तावेज़, GitHub repositories/issues, Hugging Face model cards/datasets और स्वतंत्र benchmarks से आएगी।

## रिसर्च और Browser
- DuckDuckGo HTML best-effort discovery; optional DDGS fallback।
- Optional self-hosted SearXNG (`SEARXNG_URL`) multi-engine discovery; API key नहीं चाहिए, लेकिन hosting/operator maintenance चाहिए।
- GitHub, Hugging Face, Crossref और arXiv जैसे अलग discovery endpoints।
- Primary sources से linked papers, datasets, issues, changelogs और benchmarks की bounded one-hop discovery।
- एक Chromium context प्रति research batch reuse; browser failure पर bounded HTTP fallback।
- robots.txt, timeouts, page-size limits, source hashes और provenance।

## चार दृष्टिकोण
1. Research Analyst — दावे और स्रोत-साक्ष्य सूचीबद्ध करना।
2. Domain Expert — हिंदी TTS, phonology, prosody, emotion, diarization और audio QA के प्रभाव पहचानना।
3. Skeptic — विरोधी प्रमाण, कमजोर स्रोत, stale जानकारी, license, failure cases और benchmark leakage पर सवाल।
4. Evidence Judge — निर्णय को proposal तक सीमित रखना; acceptance criteria, अगली जाँच और rollback तय करना।

मॉडल के बिना यह प्रणाली structured evidence triage, lexical conflict candidates और follow-up research queries देती है। इसे मानव-जैसी semantic reasoning नहीं कहा गया है। Web जानकारी देता है; अपने-आप reasoning engine नहीं बन जाता। किसी compatible reasoning endpoint को भविष्य में operator स्वयं चाहे तो वैकल्पिक रूप से configure कर सकता है।

## Free-first reality
SearXNG software open-source और self-hosted है; कोई hosted unlimited free search quota नहीं। DuckDuckGo/DDGS जैसे सार्वजनिक endpoints rate-limit या markup बदल सकते हैं। Browser agents fallback providers, caching और backoff से काम जारी रखने की कोशिश करेंगे; uninterrupted unlimited access की गारंटी नहीं है।

## Independence
हर engine का Browser Agent, research DB, evidence store, memory, reports और test suite अलग है। Svara केवल अनेक research sources में से एक है, runtime dependency नहीं। किसी दूसरे engine की memory या configuration पर स्वतः निर्भरता नहीं।

## सीखने और बदलाव की नीति
वेब से मिला code execute नहीं होगा; page instructions को निर्देश नहीं माना जाएगा; unreviewed सामग्री से model training या production configuration नहीं बदलेगी। हर स्वीकार किए गए निष्कर्ष को engine-specific reproducible test और जहाँ लागू हो held-out Hindi audio listening test से जोड़ना होगा। Neural deep learning/fine-tuning अलग training project है, स्वतः होने का दावा नहीं।

## Commands
```bash
python app.py research "Hindi TTS emotion prosody speaker consistency" --max-pages 16
python app.py intelligence-cycle --max-pages 12 --topics 3
python app.py intelligence-status
python app.py agent-backend
python -m unittest discover -s tests -v
```
