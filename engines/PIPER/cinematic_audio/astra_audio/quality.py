"""Before/after quality gate: technical indicators only, not perceptual truth."""
def compare_reports(before: dict, after: dict) -> dict:
    flags=[]
    if after.get("clipped_sample_count",0)>0: flags.append("output_clipping")
    if after.get("finite_sample_ratio",1)<1: flags.append("non_finite_samples")
    if after.get("activity_ratio_estimate",0) < max(0.005, before.get("activity_ratio_estimate",0)*0.35):
        flags.append("activity_drop_check_for_overcleaning")
    if after.get("rms_dbfs",-120) < before.get("rms_dbfs",-120)-12:
        flags.append("large_loudness_drop")
    return {
        "schema":"astra-audio-quality-gate/v1",
        "technical_pass":not flags,
        "flags":flags,
        "note":"A technical pass does not prove that speech, ambience, emotion, or sound identity is perceptually preserved. Listen to original and processed audio."
    }
