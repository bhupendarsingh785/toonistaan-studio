"""Validate, deduplicate and split ASTRA SFT data with provenance safeguards."""
from __future__ import annotations
import argparse, hashlib, json, random
from pathlib import Path
from typing import Any

REQUIRED = ("prompt", "response", "source", "license", "verified", "task_type", "group_id")

class DatasetError(ValueError):
    pass

def _canonical(row: dict[str, Any]) -> str:
    return json.dumps({k: row[k] for k in ("prompt", "response", "task_type")},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def load_and_validate(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    accepted, rejected, seen = [], [], set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise DatasetError("record must be an object")
            missing = [k for k in REQUIRED if k not in row]
            if missing:
                raise DatasetError("missing fields: " + ", ".join(missing))
            for key in ("prompt", "response", "source", "license", "task_type", "group_id"):
                if not isinstance(row[key], str) or not row[key].strip():
                    raise DatasetError(f"{key} must be a non-empty string")
            if row["verified"] is not True:
                raise DatasetError("only explicitly verified records may enter training")
            if row["license"].strip().lower() in {"unknown", "none", "n/a", "unlicensed"}:
                raise DatasetError("license/provenance is not established")
            key = hashlib.sha256(_canonical(row).encode("utf-8")).hexdigest()
            if key in seen:
                rejected.append({"line": line_no, "reason": "duplicate"})
                continue
            seen.add(key)
            accepted.append(row)
        except Exception as exc:
            rejected.append({"line": line_no, "reason": str(exc)})
    report = {"input": str(path), "accepted": len(accepted), "rejected": len(rejected),
              "rejections": rejected, "unique_groups": len({r["group_id"] for r in accepted})}
    return accepted, report

def split_by_group(rows: list[dict[str, Any]], seed: int = 42,
                   train_ratio: float = .8, validation_ratio: float = .1):
    if not 0 < train_ratio < 1 or not 0 < validation_ratio < 1 or train_ratio + validation_ratio >= 1:
        raise DatasetError("invalid split ratios")
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row["group_id"], []).append(row)
    keys = sorted(groups)
    if len(keys) < 3:
        raise DatasetError("at least 3 independent group_id values are required for leakage-safe splits")
    random.Random(seed).shuffle(keys)
    n = len(keys)
    n_train = max(1, int(n * train_ratio))
    n_val = max(1, int(n * validation_ratio))
    if n_train + n_val >= n:
        n_train, n_val = n - 2, 1
    assignments = {"train": keys[:n_train], "validation": keys[n_train:n_train+n_val], "test": keys[n_train+n_val:]}
    out = {name: [row for group in group_ids for row in groups[group]] for name, group_ids in assignments.items()}
    return out, {name: len(group_ids) for name, group_ids in assignments.items()}

def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)

def prepare(input_path: Path, output_dir: Path, seed: int = 42):
    rows, report = load_and_validate(input_path)
    if len(rows) < 3:
        raise DatasetError("fewer than 3 valid unique examples; refusing to create misleading splits")
    splits, group_counts = split_by_group(rows, seed=seed)
    for name, data in splits.items():
        write_jsonl(output_dir / f"{name}.jsonl", data)
    report.update({"split_examples": {k: len(v) for k, v in splits.items()},
                   "split_groups": group_counts, "seed": seed,
                   "warning": "A successful split does not certify correctness; review sources and labels."})
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dataset_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path); p.add_argument("output", type=Path); p.add_argument("--seed", type=int, default=42)
    a = p.parse_args(); print(json.dumps(prepare(a.input, a.output, a.seed), ensure_ascii=False, indent=2))
if __name__ == "__main__": main()
