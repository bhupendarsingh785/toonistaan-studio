"""ASTRA Real World Engine (additive, non-invasive cue planner).

Turns story context into a conservative, time-aligned world-audio cue sheet.
It does not modify cinema.py, existing providers, library, or rendering behavior.
Actual asset playback is intentionally delegated to the existing ASTRA library/render pipeline.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

VERSION = "1.1.0"

# Only stable, explicitly supported environment labels are mapped. Unknown labels stay neutral.
ENV_BEDS = {
    "village": ["birds", "light_wind"],
    "jungle": ["forest_birds", "leaves", "light_wind", "insects"],
    "street": ["distant_traffic", "open_air"],
    "station": ["station_ambience"],
    "room": ["room_tone"],
    "hall": ["hall_room_tone"],
    "night": ["night_insects", "light_wind"],
    "temple": ["temple_ambient"],
    "cave": ["cave_drips", "low_wind"],
    "neutral": [],
}

# Regexes deliberately require an action, not a mere mention of an object.
RULES: Sequence[Tuple[str, str, str, str]] = (
    ("movement_start", r"(?:चलने लगा|चलने लगी|चल पड़ा|चल पड़ी|चल रहा था|चल रही थी|चल रहा है|चल रही है|आगे बढ़ा|आगे बढ़ी|पैदल चला|पैदल चली|टहलने लगा|टहलने लगी)", "footsteps", "continuous"),
    ("movement_run", r"(?:दौड़ने लगा|दौड़ने लगी|दौड़ा|दौड़ी|भागने लगा|भागने लगी|तेज़ी से भागा|तेजी से भागा)", "running_footsteps", "continuous"),
    ("movement_stop", r"(?:रुक गया|रुक गई|ठहर गया|ठहर गई|चलना बंद किया|कदम रोक दिए|खड़ा हो गया|खड़ी हो गई)", "movement_stop", "state"),
    ("sit", r"(?:बैठ गया|बैठ गई|बैठकर|कुर्सी पर बैठ|चौकी पर बैठ)", "chair_or_sit", "one_shot"),
    ("door_open", r"(?:दरवाज़ा|दरवाजा|गेट|द्वार).{0,24}(?:खोल|खुल)|(?:खोल|खुल).{0,24}(?:दरवाज़ा|दरवाजा|गेट|द्वार)", "door_open", "one_shot"),
    ("door_close", r"(?:दरवाज़ा|दरवाजा|गेट|द्वार).{0,24}(?:बंद|भीड़ दिया)|(?:बंद|भीड़ दिया).{0,24}(?:दरवाज़ा|दरवाजा|गेट|द्वार)", "door_close", "one_shot"),
    ("vehicle_pass", r"(?:(?:मोटरसाइकिल|मोटर साइकिल|बाइक|कार|बस|ट्रक|गाड़ी).{0,35}(?:पास से|बगल से|सामने से).{0,20}(?:गुज़र गई|गुजर गई|गुज़र गया|गुजर गया|गुज़री|गुजरी|गुज़रा|गुजरा|निकली|निकला)|(?:पास से|बगल से|सामने से).{0,35}(?:गुज़री|गुजरी|गुज़रा|गुजरा|निकली|निकला|दौड़ी|दौड़ा)|(?:गुज़रती|गुजरती|गुज़रता|गुजरता).{0,35}(?:मोटरसाइकिल|मोटर साइकिल|बाइक|कार|बस|ट्रक|गाड़ी))", "vehicle_pass_by", "one_shot"),
    ("vehicle_approach", r"(?:दूर से|धीरे-धीरे).{0,35}(?:आ रही|आ रहा|नज़दीक|नजदीक).{0,25}(?:मोटरसाइकिल|मोटर साइकिल|बाइक|कार|बस|ट्रक|गाड़ी)", "vehicle_approach", "one_shot"),
    ("bangles", r"(?:चूड़ियाँ|चूड़ियों|चूड़ी|कंगन).{0,30}(?:बजी|खनकी|खनक|खन्न|आवाज़|आवाज)|(?:बजी|खनकी|खनक|खन्न).{0,25}(?:चूड़ियाँ|चूड़ियों|चूड़ी|कंगन)", "bangles", "one_shot"),
    ("cloth", r"(?:कपड़े|कपड़ों|दुपट्टा|साड़ी|कुर्ता).{0,25}(?:सरसर|लहर|हिला|हिली|फड़फड़)|(?:सरसराया|सरसराई|कपड़ों की आवाज़|कपड़ों की आवाज)", "cloth_rustle", "one_shot"),
    ("breathing", r"(?:तेज़ साँस|तेज सांस|हांफने लगा|हाँफने लगा|हांफ रही|हाँफ रही|गहरी साँस|गहरी सांस|साँसें तेज़|सांसें तेज)", "breathing", "short_loop"),
    ("water_action", r"(?:पानी में|पानी पर).{0,20}(?:कूदा|कूदी|उतरा|उतरी|छपाक)|(?:पानी छलका|पानी गिरा|नल खोला|पानी बहने लगा)", "water_splash", "one_shot"),
    ("animal_dog", r"(?:कुत्ता|कुत्ते).{0,25}(?:भौंका|भौंकने लगा|भौंकी)|(?:भौंका|भौंकने लगा).{0,25}कुत्ता", "dog_bark", "one_shot"),
    ("bird_action", r"(?:पक्षी|चिड़िया|चिड़ियाँ).{0,25}(?:चहकी|चहचहाई|उड़ गई|उड़ गया)", "birds_call", "one_shot"),
    ("impact", r"(?:टकराया|टकराई|गिर पड़ा|गिर पड़ी|धड़ाम से गिरा|धड़ाम से गिरी)", "impact", "one_shot"),
)


def _line_parts(item: Any) -> Tuple[str, str, Optional[str]]:
    if isinstance(item, str):
        return "madhur", item, None
    if isinstance(item, dict):
        return str(item.get("voice", "madhur")), str(item.get("text", "")), item.get("emotion")
    if isinstance(item, (list, tuple)):
        voice = str(item[0]) if len(item) > 0 else "madhur"
        text = str(item[1]) if len(item) > 1 else ""
        emotion = item[2] if len(item) > 2 and isinstance(item[2], str) else None
        return voice, text, emotion
    return "madhur", "", None


def _duration_for(durations: Any, scene_i: int, line_i: int) -> Tuple[float, bool]:
    """Accept {(scene,line): seconds}, [[seconds]], or use explicit estimate."""
    value = None
    if isinstance(durations, dict):
        value = durations.get((scene_i, line_i), durations.get(f"{scene_i}:{line_i}"))
    elif isinstance(durations, list) and scene_i < len(durations):
        row = durations[scene_i]
        if isinstance(row, list) and line_i < len(row):
            value = row[line_i]
    try:
        v = float(value)
        if v > 0:
            return min(v, 300.0), False
    except (TypeError, ValueError):
        pass
    return 2.8, True


def _event_matches(text: str) -> List[Tuple[str, str, str]]:
    found = []
    for event, pattern, asset, mode in RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.append((event, asset, mode))
    return found


def plan_world(story: Dict[str, Any], line_durations: Any = None,
               include_ambient: bool = True) -> Dict[str, Any]:
    """Create an additive cue sheet. Timestamps are based on supplied TTS durations when available."""
    scenes_out = []
    global_time = 0.0
    for si, scene in enumerate(story.get("scenes") or []):
        env = str(scene.get("env", "neutral")).lower()
        if env not in ENV_BEDS:
            env = "neutral"
        lines_out = []
        cues: List[Dict[str, Any]] = []
        local = 0.0
        moving_by_speaker: Dict[str, bool] = {}
        active_movement_by_speaker: Dict[str, Dict[str, Any]] = {}
        movement_kind_by_speaker: Dict[str, str] = {}
        if include_ambient:
            for bed in ENV_BEDS[env]:
                cues.append({"type": "ambience", "asset": bed, "start": round(global_time, 3),
                             "end": None, "scope": "scene", "confidence": "environment_default",
                             "asset_status": "resolve_from_library_or_provider"})
        for li, item in enumerate(scene.get("lines") or []):
            voice, text, emotion = _line_parts(item)
            if not text.strip():
                continue
            dur, estimated = _duration_for(line_durations, si, li)
            line_start = global_time + local
            line_end = line_start + dur
            line_cues = []
            matches = _event_matches(text)
            for event, asset, mode in matches:
                speaker_key = voice or "madhur"
                if event in ("movement_start", "movement_run"):
                    movement_kind = "running_footsteps" if event == "movement_run" else "footsteps"
                    cue = {"type": "state_start", "event": event, "speaker": speaker_key,
                           "asset": movement_kind, "start": round(line_start, 3), "end": None,
                           "scope": "character_state", "confidence": "explicit_action",
                           "asset_status": "resolve_from_library_or_provider"}
                    cues.append(cue); line_cues.append(cue)
                    moving_by_speaker[speaker_key] = True
                    active_movement_by_speaker[speaker_key] = cue
                    movement_kind_by_speaker[speaker_key] = movement_kind
                elif event == "movement_stop":
                    moving_by_speaker[speaker_key] = False
                    active = active_movement_by_speaker.pop(speaker_key, None)
                    if active is not None:
                        active["end"] = round(line_start, 3)
                    cue = {"type": "state_stop", "event": event, "speaker": speaker_key,
                           "asset": movement_kind_by_speaker.get(speaker_key, "footsteps"),
                           "start": round(line_start, 3), "end": round(line_start, 3),
                           "scope": "character_state", "confidence": "explicit_action"}
                    cues.append(cue); line_cues.append(cue)
                else:
                    cue = {"type": "sfx", "event": event, "asset": asset,
                           "start": round(line_end + 0.03, 3), "end": None, "scope": "scene",
                           "confidence": "explicit_action", "asset_status": "resolve_from_library_or_provider"}
                    cues.append(cue); line_cues.append(cue)
            # Keep movement alive across lines until an explicit stop/sit/scene end.
            speaker_key = voice or "madhur"
            if moving_by_speaker.get(speaker_key, False) and not any(
                    e in ("movement_start", "movement_run", "movement_stop") for e, _, _ in matches):
                cue = {"type": "state_continue", "event": "movement_continues",
                       "speaker": speaker_key, "asset": movement_kind_by_speaker.get(speaker_key, "footsteps"),
                       "start": round(line_start, 3), "end": round(line_end, 3),
                       "scope": "character_state", "confidence": "inherited_from_previous_action",
                       "asset_status": "resolve_from_library_or_provider"}
                cues.append(cue); line_cues.append(cue)
            if any(e == "sit" for e, _, _ in matches):
                moving_by_speaker[speaker_key] = False
                active = active_movement_by_speaker.pop(speaker_key, None)
                if active is not None:
                    active["end"] = round(line_start, 3)
            lines_out.append({"line_index": li, "speaker": voice, "text": text,
                              "emotion": emotion, "start": round(line_start, 3),
                              "end": round(line_end, 3), "duration_estimated": estimated,
                              "cue_events": [c[0] for c in matches]})
            local += dur + float(scene.get("line_gap", 0.28) or 0.0)
        scene_end = global_time + max(local, 0.5)
        for speaker_key, active in list(active_movement_by_speaker.items()):
            active["end"] = round(scene_end, 3)
            cues.append({"type": "state_stop", "event": "scene_end", "speaker": speaker_key,
                         "asset": movement_kind_by_speaker.get(speaker_key, "footsteps"),
                         "start": round(scene_end, 3), "end": round(scene_end, 3),
                         "scope": "character_state", "confidence": "scene_boundary"})
        moving_by_speaker.clear()
        active_movement_by_speaker.clear()
        for cue in cues:
            if cue.get("end") is None:
                cue["end"] = round(scene_end, 3)
        scenes_out.append({"scene_index": si, "env": env, "start": round(global_time, 3),
                           "end": round(scene_end, 3), "movement_active_at_end": False,
                           "lines": lines_out, "cues": cues})
        global_time = scene_end + float(scene.get("scene_gap", 0.45) or 0.0)
    return {"engine": "ASTRA Real World Engine", "version": VERSION,
            "mode": "cue_plan_only_no_existing_renderer_modified",
            "title": story.get("title", ""), "duration": round(global_time, 3),
            "duration_note": "Line durations marked estimated must be replaced with actual TTS durations before final rendering.",
            "scenes": scenes_out}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build an additive ASTRA world-audio cue sheet")
    ap.add_argument("story", help="ASTRA story JSON")
    ap.add_argument("-o", "--output", default="world_cues.json")
    ap.add_argument("--durations", help="Optional JSON file: [[seconds per line], ...]")
    ap.add_argument("--no-ambient", action="store_true", help="Do not add conservative environment beds")
    args = ap.parse_args()
    story = json.loads(Path(args.story).read_text(encoding="utf-8"))
    durations = json.loads(Path(args.durations).read_text(encoding="utf-8")) if args.durations else None
    result = plan_world(story, durations, include_ambient=not args.no_ambient)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WORLD_CUES_OK scenes={len(result['scenes'])} duration={result['duration']}s output={args.output}")


if __name__ == "__main__":
    main()
