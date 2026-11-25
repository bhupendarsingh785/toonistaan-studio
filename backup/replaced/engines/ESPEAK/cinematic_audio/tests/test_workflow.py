import pytest
from astra_audio.workflow import AudioWorkflow, STAGE_ORDER, WorkflowError


def test_readiness_reports_all_unconnected_stages():
    wf = AudioWorkflow()
    report = wf.readiness()
    assert report["ready_for_full_production"] is False
    assert report["missing_stages"] == list(STAGE_ORDER)


def test_full_workflow_runs_in_declared_order():
    wf = AudioWorkflow()
    seen = []
    for stage in STAGE_ORDER:
        wf.register(stage, lambda ctx, s=stage: (seen.append(s) or {"stage": s}))
    result = wf.execute({"story_id": "demo"})
    assert result["status"] == "completed"
    assert seen == list(STAGE_ORDER)
    assert [x["stage"] for x in result["stage_results"]] == list(STAGE_ORDER)


def test_missing_adapter_blocks_before_any_stage_runs():
    wf = AudioWorkflow()
    seen = []
    for stage in STAGE_ORDER[:-1]:
        wf.register(stage, lambda ctx, s=stage: (seen.append(s) or {}))
    with pytest.raises(WorkflowError, match="quality_gate"):
        wf.execute({})
    assert seen == []


def test_stage_failure_stops_following_stages():
    wf = AudioWorkflow()
    seen = []
    for stage in STAGE_ORDER:
        def adapter(ctx, s=stage):
            seen.append(s)
            if s == "asset_matching":
                raise RuntimeError("provider unavailable")
            return {}
        wf.register(stage, adapter)
    with pytest.raises(WorkflowError, match="asset_matching"):
        wf.execute({})
    assert seen == list(STAGE_ORDER[:4])


def test_duplicate_and_unknown_registration_rejected():
    wf = AudioWorkflow()
    wf.register(STAGE_ORDER[0], lambda ctx: {})
    with pytest.raises(ValueError):
        wf.register(STAGE_ORDER[0], lambda ctx: {})
    with pytest.raises(ValueError):
        wf.register("invented_stage", lambda ctx: {})
