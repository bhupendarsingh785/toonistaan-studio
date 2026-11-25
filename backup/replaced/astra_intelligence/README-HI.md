# ASTRA Intelligence Evolution Engine — Free-first v1

**स्थिति:** स्वतंत्र add-on / staging package. यह मौजूदा ASTRA Master, Hybrid v26, LLM Upgrade v2, Audio Agents या Browser Agents की files को modify नहीं करता। इसे production में जोड़ने वाला adapter इस release में जानबूझकर disabled/absent है।

## उद्देश्य

ASTRA के लिए एक वास्तविक, परीक्षण योग्य LLM learning foundation:
- verified और licensed dataset intake;
- duplicate rejection और group-wise train/validation/test split;
- Free-only resource guard;
- GPU-only LoRA/QLoRA supervised fine-tuning;
- adapter-only output (base model untouched);
- model benchmark और regression quality gate;
- local inference और future ASTRA integration के लिए पृथक staging boundary.

यह v1 पूर्ण autonomous intelligence या अपने-आप हर ज्ञान सीखने वाला सिस्टम नहीं है। यह नियंत्रित training/evaluation foundation है।

## मुख्य सिद्धांत

1. **Free-first, fail-closed:** Paid tier resource को block किया जाता है। Free quota unavailable हो तो job रोकें।
2. **Local-first inference:** Trained adapter को license और runtime compatibility के बाद local runtime पर चलाया जा सकता है। Ollama/llama.cpp deployment adapter conversion इस release में शामिल नहीं है।
3. **No silent learning:** केवल `verified=true`, source और license वाले examples training में स्वीकार होते हैं।
4. **Leakage protection:** split `group_id` के आधार पर होता है ताकि एक ही समूह के उदाहरण train/test में न फैलें।
5. **No production overwrite:** trainer adapter अलग output directory में बनाता है; base model नहीं बदलता।
6. **No automatic promotion:** quality gate और user approval के बिना नया model सक्रिय नहीं होता।

## Dataset JSONL schema

हर line एक JSON object:

```json
{"prompt":"भारत में जल चक्र समझाइए","response":"जल चक्र...","source":"reviewed-source-id","license":"CC-BY-4.0","verified":true,"task_type":"education","group_id":"chapter-water-cycle"}
```

- `source`: स्पष्ट स्रोत पहचान
- `license`: dataset/record उपयोग की वास्तविक अनुमति; `unknown` स्वीकार नहीं
- `verified`: केवल boolean `true`
- `group_id`: एक ही मूल सामग्री/वार्तालाप/कार्य से जुड़े उदाहरणों के लिए समान ID
- निजी credentials, निजी user conversations या बिना अनुमति copyrighted text न डालें।

## Dataset तैयारी

```bash
python -m astra_intelligence.dataset.prepare data/raw.jsonl data/prepared
```

कम-से-कम 3 स्वतंत्र group IDs चाहिए। यह tool data quality की गारंटी नहीं देता; यह केवल संरचना, provenance, verification, deduplication और split leakage को जाँचता है।

## वास्तविक GPU Fine-tuning

केवल disposable Colab/Kaggle free GPU session में:

```bash
pip install -r requirements-training.txt
python -m astra_intelligence.training.train_lora \
  --model <LICENSE-REVIEWED-OPEN-WEIGHT-MODEL> \
  --train data/prepared/train.jsonl \
  --validation data/prepared/validation.jsonl \
  --output runs/adapter-v1 \
  --qlora
```

- Default minimum: 100 verified train examples.
- GPU mandatory; CPU training intentionally refused.
- `--trust-remote-code` default off; only after reviewing model code.
- Model ID mandatory; no model is downloaded automatically.
- The test split must remain untouched until final evaluation.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests cover verified data filtering, group split leakage, paid-resource blocking and regression gate. These are software tests, **not** a live model training result.

## Current limitations (transparent)

- No model weights are bundled.
- No training has been run in this environment.
- No GPU session or model license has been verified here.
- No live inference/API test has been run.
- No automatic Colab/Kaggle account operation is included.
- Optimizer-state resume across interrupted sessions is not implemented in v1; copy finished checkpoints/adapters to persistent storage manually.
- Full Deep Reasoning orchestration, tool execution, DPO/RL, distillation, continual learning and ASTRA production integration are later phases, not falsely claimed as complete.

## Compatibility / integration

Keep this folder separate. Once tests and a real training run pass, integration should be done through a narrow adapter that calls the existing LLM Bridge interface. Do not overwrite existing provider logic or touch independent agents. Require a baseline benchmark, candidate benchmark, approval and rollback plan.
