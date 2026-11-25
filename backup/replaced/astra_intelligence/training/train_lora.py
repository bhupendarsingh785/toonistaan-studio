"""Opt-in real LoRA/QLoRA SFT trainer. Requires a user-selected open-weight model.

This script never downloads a model implicitly: --model is mandatory. GPU is mandatory
for a real run. It saves an adapter only; it does not overwrite the base model.
"""
from __future__ import annotations
import argparse, json, inspect
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True, help="Explicit Hugging Face model ID or local model path")
    p.add_argument("--train", type=Path, required=True); p.add_argument("--validation", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-length", type=int, default=1024); p.add_argument("--epochs", type=float, default=1.0)
    p.add_argument("--batch-size", type=int, default=1); p.add_argument("--grad-accum", type=int, default=8)
    p.add_argument("--learning-rate", type=float, default=2e-4); p.add_argument("--qlora", action="store_true")
    p.add_argument("--trust-remote-code", action="store_true", help="Enable only after reviewing model code")
    p.add_argument("--min-examples", type=int, default=100, help="Minimum verified examples required for a real training run")
    a = p.parse_args()
    if a.max_length < 64 or a.max_length > 8192 or a.epochs <= 0 or a.batch_size < 1 or a.grad_accum < 1:
        p.error("invalid training parameters")
    if a.min_examples < 3:
        p.error("--min-examples must be at least 3")
    # Provenance gate before importing heavy ML libraries or allocating a GPU.
    from astra_intelligence.dataset.prepare import load_and_validate
    train_rows, train_report = load_and_validate(a.train)
    val_rows, val_report = load_and_validate(a.validation)
    if len(train_rows) < a.min_examples or len(val_rows) < 1:
        raise SystemExit(f"Insufficient verified data: train={len(train_rows)} (need {a.min_examples}), validation={len(val_rows)}")
    try:
        import torch
        from datasets import load_dataset
        from transformers import (AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments,
                                  DataCollatorForLanguageModeling)
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    except ImportError as exc:
        raise SystemExit(f"Training dependencies missing: {exc}. Install requirements-training.txt")
    if not torch.cuda.is_available():
        raise SystemExit("GPU not detected. Refusing full training on CPU; use CPU only for tests/inference.")
    a.output.mkdir(parents=True, exist_ok=False)
    tokenizer = AutoTokenizer.from_pretrained(a.model, trust_remote_code=a.trust_remote_code)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model_kwargs = {"trust_remote_code": a.trust_remote_code}
    if a.qlora:
        from transformers import BitsAndBytesConfig
        model_kwargs.update({"quantization_config": BitsAndBytesConfig(load_in_4bit=True,
            bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True), "device_map": "auto"})
    model = AutoModelForCausalLM.from_pretrained(a.model, **model_kwargs)
    if a.qlora:
        model = prepare_model_for_kbit_training(model)
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                      task_type="CAUSAL_LM", target_modules="all-linear")
    model = get_peft_model(model, lora)
    ds = load_dataset("json", data_files={"train": str(a.train), "validation": str(a.validation)})
    def tokenize(batch):
        texts = [f"### Instruction:\n{q}\n\n### Response:\n{r}{tokenizer.eos_token}" for q, r in zip(batch["prompt"], batch["response"])]
        return tokenizer(texts, truncation=True, max_length=a.max_length)
    tokenized = ds.map(tokenize, batched=True, remove_columns=ds["train"].column_names)
    training_kwargs = dict(output_dir=str(a.output / "checkpoints"), num_train_epochs=a.epochs,
        per_device_train_batch_size=a.batch_size, per_device_eval_batch_size=1,
        gradient_accumulation_steps=a.grad_accum, learning_rate=a.learning_rate,
        fp16=True, logging_steps=10, evaluation_strategy="steps", eval_steps=50,
        save_steps=50, save_total_limit=2, report_to="none", load_best_model_at_end=False,
        gradient_checkpointing=True, optim="paged_adamw_8bit" if a.qlora else "adamw_torch")
    # Transformers renamed evaluation_strategy to eval_strategy across releases.
    ta_params = inspect.signature(TrainingArguments.__init__).parameters
    if "eval_strategy" in ta_params:
        training_kwargs["eval_strategy"] = training_kwargs.pop("evaluation_strategy")
    args = TrainingArguments(**training_kwargs)
    trainer = Trainer(model=model, args=args, train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"], data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False))
    result = trainer.train()
    model.save_pretrained(a.output / "adapter")
    tokenizer.save_pretrained(a.output / "tokenizer")
    metadata = {"base_model": a.model, "method": "QLoRA" if a.qlora else "LoRA",
        "train_examples": len(tokenized["train"]), "validation_examples": len(tokenized["validation"]),
        "dataset_rejected_train": train_report["rejected"], "dataset_rejected_validation": val_report["rejected"],
        "train_loss": result.training_loss, "adapter_only": True,
        "note": "Not production-approved. Run held-out test benchmark and quality gate."}
    (a.output / "training_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))

if __name__ == "__main__": main()
