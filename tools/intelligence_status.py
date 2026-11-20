#!/usr/bin/env python3
"""ASTRA Intelligence (training foundation) ka status — read-only.

Naya package `astra_intelligence/` khud ko production mein nahi jodta (jaan-boojh kar).
Yeh tool sirf batata hai: policy kya hai, dataset tayyar hai ya nahi, kitne verified
example hain, aur quality gate ke liye kya bacha hai. Kuch badalta nahi.

Use:
    python3 tools/intelligence_status.py
    python3 tools/intelligence_status.py --data /path/to/prepared --json

Seetal, 20 Nov 2026.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "training.json"
DEFAULT_DATA = ROOT / "data" / "prepared"


def _config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def status(data_dir: str | Path | None = None) -> dict:
    cfg = _config()
    data = Path(data_dir or DEFAULT_DATA)
    minimum = int(((cfg.get("dataset") or {}).get("minimum_verified_examples")) or 100)
    counts = {split: _count(data / f"{split}.jsonl") for split in ("train", "validation", "test")}
    total = sum(counts.values())

    gates = {
        "policy_free_only": (cfg.get("resource_policy") or {}).get("allow_paid") is False,
        "dataset_minimum_met": counts["train"] >= minimum,
        "has_validation": counts["validation"] > 0,
        "has_test": counts["test"] > 0,
        "no_auto_promotion": (cfg.get("deployment") or {}).get("automatic_production_promotion") is False,
        "license_review_required": bool((cfg.get("model") or {}).get("license_review_required")),
    }
    ready_to_train = gates["dataset_minimum_met"] and gates["has_validation"]
    return {
        "config_present": CONFIG.is_file(),
        "data_dir": str(data),
        "examples": counts,
        "total_examples": total,
        "minimum_train_required": minimum,
        "gates": gates,
        "ready_to_train": ready_to_train,
        "ready_to_promote": False,   # promotion ke liye benchmark + user approval chahiye
        "note": "Yeh training foundation hai. Iska matlab 'model seekh gaya' nahi — "
                "asli training GPU par chalti hai, aur promotion ke liye benchmark + approval chahiye.",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Intelligence/training status (read-only)")
    ap.add_argument("--data", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rep = status(a.data)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return
    print(f"config: {'mil gaya' if rep['config_present'] else 'nahi mila'} | data: {rep['data_dir']}")
    print(f"examples: train {rep['examples']['train']} / val {rep['examples']['validation']} / test {rep['examples']['test']}"
          f" (train ke liye kam se kam {rep['minimum_train_required']})")
    for k, v in rep["gates"].items():
        print(f"  {'OK  ' if v else 'NO  '} {k}")
    print(f"training ke liye tayyar: {'haan' if rep['ready_to_train'] else 'nahi'}")


if __name__ == "__main__":
    main()
