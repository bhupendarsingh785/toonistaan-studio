"""Single-pass story-to-audio review planner.

Joins script analysis, world soundscape, physical-action Foley chains and
metadata-only library candidate search into one auditable report. It never
inserts audio, chooses a final take, guesses exact timing, or renders a mix.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib
from .story_intelligence import analyze_script_text
from .soundscape_planner import plan_soundscape
from .action_foley import analyze_action_chains
from .asset_matching import match_assets
from .io import save_json_atomic

SCHEMA = "astra-story-audio-review-pack/v1"

def prepare_story_audio(script_text: str, source_name: str = "inline",
                        catalog: str | Path | dict | list | None = None,
                        min_score: float = 0.18, max_candidates: int = 5) -> dict[str, Any]:
    if not isinstance(script_text, str) or not script_text.strip():
        raise ValueError("Story script is empty")
    digest = hashlib.sha256(script_text.encode("utf-8")).hexdigest()
    story = analyze_script_text(script_text, source_name)
    world = plan_soundscape(script_text, source_name)
    actions = analyze_action_chains(script_text, source_name)

    search_events: list[dict[str, Any]] = []
    # Story-intelligence sound cues (dialogue/emotion/event hints).
    for scene in story.get("scenes", []):
        for cue in scene.get("sound_cues", []):
            if cue.get("cue_type") == "sound_event":
                search_events.append({
                    "event_id": cue.get("cue_id"), "event_type": cue.get("event"),
                    "text": cue.get("text_excerpt", ""), "scene_id": scene.get("scene_id"),
                    "source_line": cue.get("source_line"), "source_stage": "story_intelligence",
                    "confidence": cue.get("confidence"),
                })
    # World beds: de-duplicate same layer within one scene, but retain across scenes.
    for scene in world.get("scenes", []):
        seen: set[str] = set()
        for layer in scene.get("environment_layers", []):
            tags = layer.get("asset_search_tags", [])
            tag = str(tags[0]) if tags else ""
            if not tag or tag in seen:
                continue
            seen.add(tag)
            search_events.append({
                "event_id": f"{scene['scene_id']}_bed_{tag}",
                "event_type": "environment_bed", "event": tag,
                "asset_search_tags": tags, "text": scene.get("heading", ""),
                "scene_id": scene.get("scene_id"), "source_line": None,
                "source_stage": "world_soundscape", "confidence": "profile_suggestion",
            })
    # Map action source lines back to their containing world scene.
    line_to_scene = {line: scene.get("scene_id") for scene in world.get("scenes", []) for line in scene.get("source_lines", [])}
    # Action Foley: individual physical interactions, not one generic action sound.
    for chain in actions.get("action_chains", []):
        for event in chain.get("events", []):
            search_events.append({
                "event_id": event["event_id"], "event_type": event["action"],
                "event": event["action_label"], "action": event["action"],
                "action_label": event["action_label"], "sound_family": event["sound_family"],
                "asset_search_tags": event.get("asset_search_tags", []),
                "text": event.get("evidence_excerpt", ""),
                "scene_id": line_to_scene.get(event.get("source_line")), "source_line": event.get("source_line"),
                "source_stage": "action_foley", "confidence": event.get("confidence"),
            })

    matching = match_assets(search_events, catalog, min_score, max_candidates) if catalog is not None else None
    counts = {
        "scenes": story["scene_count"],
        "characters": len(story.get("characters", [])),
        "story_event_cues": story["summary"]["sound_event_candidate_count"],
        "action_chains": actions["action_chain_count"],
        "physical_action_events": actions["event_count"],
        "environment_bed_suggestions": sum(len(s.get("environment_layers", [])) for s in world.get("scenes", [])),
        "asset_search_events": len(search_events),
        "asset_events_with_candidates": matching["matched_event_count"] if matching else 0,
    }
    return {
        "schema": SCHEMA, "source_name": source_name, "script_sha256": digest,
        "counts": counts,
        "stages": {
            "story_intelligence": {"status": "completed_advisory", "analysis": story},
            "world_soundscape": {"status": "completed_advisory", "plan": world},
            "action_foley": {"status": "completed_advisory", "plan": actions},
            "asset_matching": {"status": "completed_candidates_only" if matching else "not_run_no_catalog", "report": matching},
            "timeline_alignment": {"status": "blocked_needs_audio_alignment", "reason": "Story text does not provide reliable exact event timestamps; use forced alignment or manual review."},
            "mix_render": {"status": "blocked_needs_approved_assets_and_timing", "reason": "No assets are auto-selected or inserted; explicit audition, licence, approval and cue timing are required."},
            "human_listening_qa": {"status": "not_run", "reason": "Requires rendered audio and human audition."},
        },
        "policy": {
            "review_only": True, "auto_asset_insertion": False,
            "auto_timeline_guessing": False, "auto_render": False,
            "source_audio_or_script_modified": False,
            "unknown_assets_or_licences_not_cleared_for_commercial_use": True,
        },
        "known_limitations": [
            "Story, mood and action understanding are evidence/lexicon based, not unrestricted semantic reasoning.",
            "Asset matching is metadata/token matching, not audio-embedding semantic retrieval or human audition.",
            "Exact action micro-timing, material, force, direction and distance need narration alignment and review.",
            "A cue can be missed when phrased outside known Hindi/English patterns; unknown cues are not invented.",
            "The report is not a final audio mix and cannot certify artistic quality.",
        ],
        "next_required_gates": [
            "Review scene and action interpretation", "Audition candidate recordings",
            "Verify asset licence and production permission", "Align cues to actual narration waveform",
            "Approve final cue list and mix", "Render stems and master", "Run technical QA and human listening QA",
        ],
    }

def prepare_story_audio_file(script_path: str | Path, report_path: str | Path,
                             catalog_path: str | Path | None = None,
                             min_score: float = 0.18, max_candidates: int = 5) -> dict[str, Any]:
    src = Path(script_path).resolve()
    out = Path(report_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(src)
    if src.stat().st_size > 2_000_000:
        raise ValueError("Story script exceeds 2 MB safety limit")
    if out == src:
        raise ValueError("Report must not overwrite the source script")
    if catalog_path and out == Path(catalog_path).resolve():
        raise ValueError("Report must not overwrite the asset catalog")
    result = prepare_story_audio(src.read_text(encoding="utf-8-sig"), src.name, catalog_path,
                                 min_score, max_candidates)
    save_json_atomic(out, result)
    return result
