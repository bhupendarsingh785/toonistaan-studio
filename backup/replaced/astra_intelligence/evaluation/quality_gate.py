"""Compare candidate model reports against a baseline; fail closed on regressions."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class GateResult:
    accepted: bool
    reasons: list[str]

def compare_reports(baseline: dict, candidate: dict, min_overall_gain: float = 0.0,
                    max_metric_regression: float = 0.02) -> GateResult:
    reasons = []
    for name in ("overall", "reasoning", "hindi", "coding", "factuality", "instruction_following"):
        if name not in baseline or name not in candidate:
            reasons.append(f"missing benchmark metric: {name}")
            continue
        try:
            b, c = float(baseline[name]), float(candidate[name])
        except (TypeError, ValueError):
            reasons.append(f"non-numeric benchmark metric: {name}"); continue
        if not 0 <= b <= 1 or not 0 <= c <= 1:
            reasons.append(f"metric outside [0,1]: {name}"); continue
        if c < b - max_metric_regression:
            reasons.append(f"regression in {name}: {b:.4f} -> {c:.4f}")
    if "overall" in baseline and "overall" in candidate:
        if float(candidate["overall"]) < float(baseline["overall"]) + min_overall_gain:
            reasons.append("overall improvement threshold not met")
    return GateResult(not reasons, reasons)
