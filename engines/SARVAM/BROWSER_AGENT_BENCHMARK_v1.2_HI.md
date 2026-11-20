# Browser Agent Benchmark v1.2

यह benchmark शोध-प्रक्रिया की गुणवत्ता मापता है, बुद्धिमत्ता का दावा नहीं करता।

## चलाना
```bash
python app.py agent-benchmark
```
यह offline fixture पर benchmark evaluator को जाँचता है।

वास्तविक research report और cognition report पर:
```bash
python app.py agent-benchmark research/deep_research_<timestamp>.json --cognition reports/cognition/cognition_<timestamp>.json
```

## मापे जाने वाले संकेतक
- URL + SHA-256 provenance
- स्वतंत्र domains और primary sources
- query diversity और counter-research follow-ups
- skeptic review और decision/promotion gate
- acceptance criteria और source traceability
- limitations तथा measurable evaluation awareness

## सीमा
Score process coverage है। यह semantic correctness, source truth, human-level reasoning, TTS naturalness या live web success का प्रमाण नहीं है।
