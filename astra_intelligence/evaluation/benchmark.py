"""Run deterministic exact-match benchmark over a model adapter command.

The command receives each prompt on stdin and must print one response to stdout.
No network/API access is performed by this runner.
"""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

def run(dataset: Path, command: list[str], output: Path):
    rows = [json.loads(x) for x in dataset.read_text(encoding="utf-8").splitlines() if x.strip()]
    results = []
    for i, row in enumerate(rows):
        proc = subprocess.run(command, input=row["prompt"], text=True, capture_output=True, timeout=180, check=False)
        answer = proc.stdout.strip()
        expected = row.get("expected_exact", "").strip()
        results.append({"id": row.get("id", i), "returncode": proc.returncode,
                        "exact_match": bool(expected) and answer.casefold() == expected.casefold(),
                        "answer": answer, "expected_exact": expected, "stderr": proc.stderr[-1000:]})
    total = len(results)
    report = {"examples": total, "exact_match_accuracy": sum(r["exact_match"] for r in results) / total if total else 0,
              "results": results, "warning": "Exact match is only one metric; human and task-specific evaluation are required."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser(); p.add_argument("dataset", type=Path); p.add_argument("output", type=Path); p.add_argument("command", nargs=argparse.REMAINDER)
    a=p.parse_args()
    if not a.command: p.error("provide model adapter command after --")
    print(json.dumps(run(a.dataset, a.command, a.output), ensure_ascii=False, indent=2))
if __name__ == "__main__": main()
