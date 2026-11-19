# ELEVENLABS Voice Intelligence v0.8 — अतिरिक्त क्षमताएँ

## Browser Agent v0.8
- Federated discovery: DuckDuckGo, Hugging Face model API, GitHub, Crossref, arXiv.
- Optional Playwright Chromium page rendering, bounded scroll, extracted links, one-hop relevant link crawl.
- Robots.txt, response-size caps, domain diversity, duplicate hashing, evidence provenance, source class and review-only handoff.
- Browser agent स्वतः model weights नहीं बदलता; evidence `knowledge_inbox/` में PENDING review रहती है।

## Hindi Voice Director
- v0.7 का phonology/prosody analysis बरकरार।
- नया lexicon `data/hindi_pronunciation_lexicon.json` मानव-समीक्षित उच्चारण नियमों के लिए।
- Devanagari schwa deletion को बिना प्रमाण अनुमान से लागू नहीं किया जाता।
- Edge/Piper/eSpeak में true emotion acting की backend सीमा बनी रहती है; केवल pitch/rate को human acting नहीं कहा जाएगा। ElevenLabs tags model-dependent हैं।


## Svara-TTS: research-only knowledge source (v0.9)
Svara-TTS v1 is connected to this engine's Browser Agent as an optional, non-blocking documentation source. It is **not** a TTS backend in this build. Keep `expressive_backend` set to `native`; attempting to select `svara` in the renderer is rejected. No model weights are downloaded.

The isolated background worker reads the Svara Hugging Face model card, Kenpath inference documentation and maintainer open-source page, plus independent Indic-TTS / Indic-Parler references. It stores source URL, timestamp, SHA-256 and extracted text in `knowledge_inbox/open_source/`. Evidence remains pending human review; fetched code is never executed and cannot change model weights or production configuration.

Start a normal research run with `python app.py research "Hindi expressive TTS pronunciation"`. Check the separate learner with `python app.py open-source-status`. If Svara or any other source is offline, the four engines and normal browser research continue without waiting for it.

Official references: https://huggingface.co/kenpath/svara-tts-v1 · https://github.com/Kenpath/svara-tts-inference · https://kenpathlabs.com/open-source

## Cinematic Audio + Deep Vocal QA
Install: `pip install -r requirements-audio-optional.txt`

- `python app.py story-audio-plan story.txt --report reports/story_audio_review_pack.json`
- `python app.py soundscape-plan story.txt`
- `python app.py action-foley-plan story.txt`
- `python app.py audio-qa output/story_final.wav`
- `python app.py vocal-backends`
- `python app.py vocal-audit output/story_final.wav --asr-model small`
- `python app.py vocal-audit output/story_final.wav --diarization --hf-token YOUR_HF_TOKEN`
- `python app.py mix-story --spec approved_mix_spec.json --out output/story_mix.wav`
- `python app.py index-audio-library ./my_sound_library --report reports/audio_library_index.json`
- `python app.py produce-story story.txt ./my_sound_library approvals.json --narration output/story_final.wav --out-dir output/production`

`story-audio-plan` एक review pack बनाता है: scene mood, environment beds, sound events, physical-action Foley chains और asset candidates. It does not invent or auto-insert unapproved audio. `mix-story` तभी render करेगा जब वास्तविक approved stems और exact timing वाला spec दिया जाए।

## Naturalness limits
A voice director cannot turn a non-expressive backend into a human actor. Standard Piper CLI has no emotion conditioning; Edge TTS exposes limited controls; eSpeak NG remains formant synthesis. Realistic emotion requires a compatible expressive neural TTS model/voice. ElevenLabs support varies by model.

## Browser setup
`pip install -r requirements.txt`
Optional: `pip install playwright pymupdf && playwright install chromium`

## Research candidates (not silently installed)
- Svara-TTS v1: Hindi + 18 other Indic languages, sentence-end emotion/style tags; model card states 3B parameters and Apache-2.0. Check hardware and inference instructions before deployment.
- Svara Hindi fine-tune: 3B and ~6.6 GB model artifact; reported A100 fine-tuning. Not suitable to assume CPU/mobile speed.
- Fish Audio S2 Pro: expressive free-form tags, but Research License limits commercial use absent separate license.

All claims require on-device evaluation. Passing software tests is not a naturalness certification.
