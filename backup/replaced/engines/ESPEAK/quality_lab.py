
"""Release gates: never infer audio quality from code tests."""
import json, time
from pathlib import Path
CHECKS = [
 "hindi_text_understanding", "hindi_pronunciation_audio", "speaker_detection",
 "age_voice_match", "voice_distinction", "emotion_acting", "character_consistency",
 "long_form_stability", "model_discovery_accuracy", "browser_source_quality", "offline_operation"
]
def blank_report(engine, run_id):
    return {
      "engine": engine, "run_id": run_id,
      "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
      "status": "NOT_EVALUATED",
      "checks": {k: {"status":"NOT_TESTED","score_0_to_5":None,"evidence":None} for k in CHECKS},
      "release_rule": "All checks need evidence; audio checks require listening review. No auto-pass."
    }
def evaluate(report, blockers):
    all_checks = report["checks"].values()
    if blockers:
        report["status"] = "BLOCKED_BY_OPEN_ERRORS"
    elif all(x["status"] == "PASS" and x["score_0_to_5"] is not None and x["evidence"] for x in all_checks):
        report["status"] = "PASS"
    elif any(x["status"] == "FAIL" for x in all_checks):
        report["status"] = "FAIL"
    else:
        report["status"] = "NOT_EVALUATED_OR_PARTIAL"
    report["open_error_count"] = len(blockers)
    return report
def save_report(report, path, blockers=None):
    report = evaluate(report, blockers or [])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
