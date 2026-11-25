"""Fail-closed orchestration contracts for the standalone ASTRA audio workflow.

This module coordinates adapters; it does not pretend that absent AI providers
(TTS, semantic understanding, alignment, asset search, etc.) are installed.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

STAGE_ORDER = (
    "story_understanding",
    "voice_generation",
    "dialogue_alignment",
    "asset_matching",
    "music_design",
    "spatial_design",
    "mix_render",
    "quality_gate",
)

@dataclass(frozen=True)
class StageResult:
    stage: str
    status: str
    output: dict[str, Any]

class WorkflowError(RuntimeError):
    pass

class AudioWorkflow:
    """Register stage adapters and execute them in a deterministic, audited order.

    Each adapter receives a fresh shallow copy of the accumulated context and
    must return a dict. A missing stage or invalid result stops execution.
    Adapters must write derivatives only; source preservation remains mandatory.
    """
    def __init__(self) -> None:
        self._adapters: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register(self, stage: str, adapter: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        if stage not in STAGE_ORDER:
            raise ValueError(f"Unknown workflow stage: {stage}")
        if not callable(adapter):
            raise TypeError("adapter must be callable")
        if stage in self._adapters:
            raise ValueError(f"Adapter already registered: {stage}")
        self._adapters[stage] = adapter

    def readiness(self) -> dict[str, Any]:
        available = [s for s in STAGE_ORDER if s in self._adapters]
        missing = [s for s in STAGE_ORDER if s not in self._adapters]
        return {
            "schema": "astra-audio-workflow-readiness/v1",
            "workflow": "standalone_audio_production",
            "ready_for_full_production": not missing,
            "available_stages": available,
            "missing_stages": missing,
            "stage_order": list(STAGE_ORDER),
        }

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(context, dict):
            raise TypeError("context must be a dict")
        readiness = self.readiness()
        if not readiness["ready_for_full_production"]:
            raise WorkflowError(
                "Full production blocked; adapters not connected: "
                + ", ".join(readiness["missing_stages"])
            )
        state = dict(context)
        results: list[dict[str, Any]] = []
        for stage in STAGE_ORDER:
            try:
                output = self._adapters[stage](dict(state))
            except Exception as exc:
                raise WorkflowError(f"Stage '{stage}' failed; later stages were not run: {exc}") from exc
            if not isinstance(output, dict):
                raise WorkflowError(f"Stage '{stage}' must return a dict")
            state[stage] = output
            results.append({"stage": stage, "status": "completed", "output": output})
        return {
            "schema": "astra-audio-workflow-run/v1",
            "status": "completed",
            "stage_results": results,
            "context": state,
        }
