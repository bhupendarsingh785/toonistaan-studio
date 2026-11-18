"""Conservative catalog matching for story sound events.

This is deterministic metadata matching, not semantic audio recognition. It
returns review candidates only and never inserts or downloads an asset.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib, json, re

SCHEMA = "astra-audio-asset-match-report/v1"
SYNONYMS = {
    "crying_sobbing": {"crying", "sobbing", "weep", "रोना", "रोने", "रोती", "रोता", "रोया", "रोई", "रोते", "सिसकी", "सिसकना"},
    "laughter": {"laugh", "laughter", "giggle", "हँसी", "हंसना", "ठहाका"},
    "conch": {"conch", "shankh", "शंख"},
    "bell_chime": {"bell", "chime", "घंटी", "घंटियाँ", "घंटियों", "घंटा"},
    "footsteps": {"footstep", "footsteps", "step", "walking", "कदम", "पैरों", "चलना"},
    "door": {"door", "gate", "दरवाज़ा", "दरवाजा", "द्वार", "फाटक"},
    "birds": {"bird", "birds", "चिड़िया", "पक्षी", "पंछी"},
    "peacock": {"peacock", "मोर"},
    "rain": {"rain", "बारिश", "वर्षा"},
    "wind": {"wind", "हवा", "आंधी"},
    "river": {"river", "water", "नदी", "पानी", "लहर"},
    "crowd": {"crowd", "people", "भीड़", "जनसमूह"},
    "horse": {"horse", "घोड़ा", "घोड़े"},
    "fire": {"fire", "flame", "आग", "लपट"},
    "heartbeat": {"heartbeat", "heart", "धड़कन"},
    "breathing": {"breath", "breathing", "सांस", "श्वास"},
    "thunder": {"thunder", "lightning", "बिजली", "गर्जना"},
    "temple_ambience": {"temple", "मंदिर", "आरती"},
    "forest_ambience": {"forest", "jungle", "जंगल", "वन"},
    "village_ambience": {"village", "गाँव", "गांव", "ग्रामीण"},
    "city_ambience": {"city", "street", "शहर", "सड़क", "बाज़ार", "बाजार"},
}
STOP = {"the","and","for","with","from","this","that","sound","effect","audio","का","की","के","में","और","एक","है","हैं","से","को","पर"}

def _tokens(value: Any) -> set[str]:
    text = str(value or "").lower().replace("_", " ").replace("-", " ")
    return {t for t in re.findall(r"[a-z0-9]+|[\u0900-\u097f]+", text) if len(t) > 1 and t not in STOP}

def _load_catalog(source: str | Path | dict | list) -> list[dict]:
    if isinstance(source, (str, Path)):
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    else:
        data = source
    assets = data.get("assets") if isinstance(data, dict) else data
    if not isinstance(assets, list):
        raise ValueError("Catalog must be a JSON object with an assets list or an assets list")
    clean = []
    for i, asset in enumerate(assets):
        if not isinstance(asset, dict):
            raise ValueError(f"Catalog asset #{i+1} must be an object")
        name = asset.get("asset_name") or asset.get("name") or asset.get("path")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Catalog asset #{i+1} requires asset_name/name/path")
        clean.append(asset)
    return clean

def _event_terms(event: dict) -> set[str]:
    terms = _tokens(" ".join(str(event.get(k, "")) for k in
        ("event_type","event","label","text","description","sound","setting","environment")))
    kind = str(event.get("event_type", "")).lower()
    for canonical, words in SYNONYMS.items():
        if kind == canonical or terms.intersection(words):
            terms.add(canonical)
            terms.update(words)
    return terms

def match_assets(events: list[dict], catalog_source: str | Path | dict | list,
                 min_score: float = 0.18, max_candidates: int = 5) -> dict:
    """Return ranked candidates; unknown licence/un-auditioned assets are review-only."""
    if not isinstance(events, list) or any(not isinstance(e, dict) for e in events):
        raise ValueError("events must be a list of objects")
    if not 0 <= float(min_score) <= 1:
        raise ValueError("min_score must be between 0 and 1")
    if not 1 <= int(max_candidates) <= 20:
        raise ValueError("max_candidates must be between 1 and 20")
    assets = _load_catalog(catalog_source)
    results = []
    for index, event in enumerate(events):
        terms = _event_terms(event)
        ranked = []
        for asset in assets:
            name = asset.get("asset_name") or asset.get("name") or asset.get("path")
            desc = asset.get("description", "")
            tags = list(asset.get("tags", [])) + list(asset.get("filename_category_hints", []))
            profile = asset.get("suggested_profile", "")
            searchable = _tokens(" ".join([str(name), str(desc), str(profile), " ".join(map(str,tags))]))
            overlap = terms.intersection(searchable)
            if not overlap:
                continue
            # Exact canonical event type and explicit tags weigh more than filename-only overlap.
            canonical = str(event.get("event_type", "")).lower()
            exact = canonical in searchable
            family_match = bool(canonical in SYNONYMS and overlap.intersection(SYNONYMS[canonical]))
            # For a typed event, do not let another event mentioned in the same
            # sentence hijack the match (e.g. a conch asset for a bell cue).
            if canonical in SYNONYMS and not family_match:
                continue
            score = min(1.0, (len(overlap) / max(3, min(6, len(terms)))) * 0.65
                        + (0.25 if exact else 0) + (0.25 if family_match else 0))
            if score < min_score:
                continue
            license_status = str(asset.get("license_status", "unknown_requires_verification"))
            approval = str(asset.get("approval_status", asset.get("production_status", "needs_user_audition_before_production")))
            licence_ok = license_status.lower() in {"cleared","licensed","approved","public_domain","cc0"}
            audition_ok = approval.lower() in {"approved","auditioned","production_approved"}
            ranked.append({
                "asset_id": asset.get("asset_id") or hashlib.sha256(str(name).encode()).hexdigest()[:16],
                "asset_name": name,
                "description": desc,
                "match_score": round(score, 3),
                "matched_terms": sorted(overlap),
                "license_status": license_status,
                "approval_status": approval,
                "eligible_for_commercial_auto_use": bool(licence_ok and audition_ok),
                "source_path": asset.get("path") or asset.get("source_path"),
                "decision": "eligible_for_reviewed_use" if licence_ok and audition_ok else "human_review_required",
            })
        ranked.sort(key=lambda x: (-x["match_score"], x["asset_name"]))
        results.append({
            "event_id": event.get("event_id", f"event-{index+1}"),
            "event": event,
            "status": "candidates_found" if ranked else "no_confident_candidate",
            "candidates": ranked[:max_candidates],
            "auto_inserted": False,
            "review_required": True,
            "note": "Metadata match only; audition and licence verification are mandatory. No sound was inserted.",
        })
    return {
        "schema": SCHEMA,
        "matching_method": "deterministic_metadata_token_overlap",
        "semantic_ai_used": False,
        "catalog_asset_count": len(assets),
        "event_count": len(events),
        "matched_event_count": sum(bool(r["candidates"]) for r in results),
        "results": results,
        "policy": {
            "never_auto_insert": True,
            "unknown_or_unverified_licence_blocked_for_commercial_auto_use": True,
            "human_audition_required": True,
            "source_assets_modified": False,
        },
    }


def make_workflow_adapter(catalog_source: str | Path | dict | list,
                          min_score: float = 0.18, max_candidates: int = 5):
    """Create an AudioWorkflow-compatible asset_matching adapter.

    The preceding story_understanding adapter must return its analysis report
    directly, or place it under context['story_analysis'].
    """
    def adapter(context: dict) -> dict:
        analysis = context.get("story_analysis")
        if analysis is None:
            prior = context.get("story_understanding")
            analysis = prior.get("analysis", prior) if isinstance(prior, dict) else None
        if not isinstance(analysis, dict) or not isinstance(analysis.get("scenes"), list):
            raise ValueError("asset_matching requires story_analysis with a scenes list")
        events = []
        for scene in analysis["scenes"]:
            if not isinstance(scene, dict):
                continue
            for cue in scene.get("sound_cues", []):
                if isinstance(cue, dict) and cue.get("cue_type") == "sound_event":
                    events.append({
                        "event_id": cue.get("cue_id"),
                        "event_type": cue.get("event"),
                        "text": cue.get("text_excerpt", ""),
                        "scene_id": scene.get("scene_id"),
                        "evidence": cue.get("evidence", []),
                        "confidence": cue.get("confidence"),
                    })
        return match_assets(events, catalog_source, min_score, max_candidates)
    return adapter
