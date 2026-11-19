from __future__ import annotations
from pathlib import Path
import json, re, hashlib
from typing import Any
from .io import save_json_atomic

SCHEMA = "astra-story-intelligence/v1"
EMOTION_LEXICON = {
    "fear": ["डर", "भय", "घबर", "कांप", "काँप", "चीख", "सहमा", "खौफ", "डरा", "डरी", "fear", "afraid", "terrified", "panic", "scream"],
    "sad": ["रोया", "रोई", "रोना", "रोने", "रो रही", "रो रहा", "रोते", "सिसक", "आँसू", "आंसू", "दुख", "उदास", "विरह", "टूट गया", "टूट गई", "sad", "cry", "crying", "sobbing", "tears", "grief", "heartbroken"],
    "anger": ["गुस्सा", "क्रोध", "चिल्लाया", "चिल्लाई", "गरजा", "झल्ला", "नफरत", "angry", "rage", "furious", "shouted"],
    "joy": ["हँसा", "हंसा", "मुस्कुर", "खुश", "प्रसन्न", "आनंद", "जश्न", "हँसी", "happy", "laugh", "smile", "joy", "celebrate"],
    "tension": ["सन्नाटा", "खतरा", "रहस्य", "पीछा", "अचानक", "धीरे-धीरे", "कदमों की आहट", "दरवाजा चरमर", "छाया", "संदेह", "danger", "mystery", "footsteps", "suddenly", "silence"],
    "peaceful": ["शांत", "सुकून", "सुबह", "प्रकृति", "हवा", "पक्षी", "नदी", "चाँदनी", "peaceful", "calm", "breeze", "birds", "river"]
}
EVENTS = [
    ("footsteps", ["कदम", "पैरों की आहट", "चलने लगा", "चलने लगी", "दौड़ा", "दौड़ी", "दौड़ पड़ा", "दौड़ पड़ी", "भागा", "भागी", "footsteps", "walked", "running", "ran"]),
    ("door", ["दरवाजा", "दरवाज़ा", "द्वार", "गेट", "खटखट", "किवाड़", "door", "gate", "knock"]),
    ("rain", ["बारिश", "वर्षा", "बूंद", "बूँद", "मेघ", "बादल गरजे", "rain", "thunderstorm", "raindrops"]),
    ("wind", ["हवा चली", "तेज हवा", "आंधी", "आँधी", "झोंका", "wind", "breeze", "gust"]),
    ("vehicle", ["गाड़ी", "गाड़ी", "कार", "मोटर", "इंजन", "बाइक", "ट्रक", "vehicle", "car", "engine", "motorcycle", "truck"]),
    ("crowd", ["भीड़", "भीड़भाड़", "लोगों का शोर", "तालियाँ", "तालियां", "crowd", "applause", "cheering"]),
    ("animal_bird", ["पक्षी", "चिड़िया", "चिड़िया", "मोर", "कुत्ता", "भौंका", "गाय", "घोड़ा", "घोड़ा", "bird", "peacock", "dog", "horse", "cow"]),
    ("fire", ["आग", "लपट", "जल रहा", "जल रही", "चिता", "fire", "flames", "burning"]),
    ("water", ["नदी", "समुद्र", "तालाब", "पानी में", "लहर", "छपाक", "water", "river", "sea", "waves", "splash"]),
    ("breathing", ["साँस", "सांस", "हांफ", "हाँफ", "दम फूल", "breathing", "panting", "gasp"]),
    ("clothing_jewellery", ["कपड़ों की सरसराहट", "कपड़े की आवाज", "चूड़ी", "चूड़ियाँ", "चूड़ियां", "पायल", "घुंघरू", "कंगन", "cloth rustle", "fabric rustle", "bangles", "anklet"]),
    ("foliage", ["पत्तों की सरसराहट", "पत्ते हिले", "पेड़ों की पत्तियाँ", "झाड़ियाँ", "झाड़ियां", "leaves rustling", "foliage", "tree branches"]),
    ("bell_chime", ["घंटी", "घंटियाँ", "घंटियां", "मंदिर की घंटी", "bell", "chime", "temple bells"]),
    ("conch", ["शंख", "शंखनाद", "conch", "conch shell"]),
    ("crying_sobbing", ["सिसक", "फूट-फूटकर रो", "रोने लगी", "रोने लगा", "रो पड़ी", "रो पड़ा", "आँसू बह", "आंसू बह", "सुबुक", "crying", "sobbing", "weeping"]),
    ("laughter", ["हँस पड़ा", "हंस पड़ा", "हँस पड़ी", "हंस पड़ी", "ठहाका", "खिलखिला", "हँसी गूँजी", "laughing", "giggle", "chuckle"]),
    ("metal_glass", ["कांच", "काँच", "शीशा", "धातु", "लोहे की", "बर्तन", "glass breaking", "metal clang", "metallic", "clinking"]),
    ("impact", ["धमाका", "धड़ाम", "धड़ाम", "टकराया", "गिर पड़ा", "गिर पड़ी", "गोली", "explosion", "crash", "impact", "gunshot"]),
]

ENVIRONMENT_LEXICON = [
    ("village", ["गाँव", "गांव", "देहात", "चौपाल", "village", "rural"]),
    ("temple", ["मंदिर", "देवालय", "आरती", "पूजा-स्थल", "temple", "shrine"]),
    ("forest", ["जंगल", "वन क्षेत्र", "वनप्रदेश", "घना जंगल", "पेड़ों के बीच", "forest", "woods", "jungle"]),
    ("palace", ["महल", "राजमहल", "दरबार", "palace", "royal court"]),
    ("old_mansion", ["हवेली", "पुरानी कोठी", "खंडहर", "mansion", "abandoned house"]),
    ("hospital", ["अस्पताल", "हॉस्पिटल", "वार्ड", "आईसीयू", "hospital", "clinic"]),
    ("railway_station", ["रेलवे स्टेशन", "स्टेशन", "प्लेटफॉर्म", "रेलगाड़ी", "रेलगाड़ी", "railway station", "platform"]),
    ("city_street", ["शहर", "सड़क", "बाजार", "बाज़ार", "ट्रैफिक", "city", "street", "market"]),
    ("river_or_sea", ["नदी किनारा", "समुद्र तट", "घाट", "नदी", "समुद्र", "riverbank", "seashore"]),
    ("home_interior", ["घर के भीतर", "कमरा", "रसोई", "आँगन", "आंगन", "घर", "room", "kitchen", "home"]),
]

def _environment(text: str) -> list[dict[str, Any]]:
    """Return lexical setting candidates; not verified acoustic scene recognition."""
    found = []
    for label, terms in ENVIRONMENT_LEXICON:
        hits = _matches(text, terms)
        if hits:
            found.append({"environment": label, "evidence": hits,
                          "confidence": min(0.75, 0.4 + 0.1 * len(hits)),
                          "requires_human_review": True})
    return found

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())

def _matches(text: str, terms: list[str]) -> list[str]:
    low = text.casefold()
    found = []
    for term in terms:
        needle = term.casefold()
        if re.search(r"[a-z]", needle):
            pattern = r"(?<![a-z0-9_])" + re.escape(needle) + r"(?![a-z0-9_])"
            if re.search(pattern, low):
                found.append(term)
        elif needle in low:
            found.append(term)
    return found

def _emotion(text: str) -> tuple[str, float, list[str]]:
    scores = {k: _matches(text, v) for k, v in EMOTION_LEXICON.items()}
    ranked = sorted(((len(v), k, v) for k, v in scores.items()), reverse=True)
    if not ranked or ranked[0][0] == 0:
        return "neutral", 0.25, []
    count, label, hits = ranked[0]
    # This is lexical evidence only, not psychological interpretation.
    confidence = min(0.78, 0.35 + 0.12 * count)
    if len(ranked) > 1 and ranked[1][0] == count:
        return "mixed", 0.35, hits + ranked[1][2]
    return label, confidence, hits

def _scene_heading(line: str) -> bool:
    s = line.strip()
    return bool(re.match(r"(?i)^(?:scene\b|दृश्य\b|अध्याय\b|अंदर\s*/\s*बाहर|INT\.|EXT\.|INT/EXT\.|EXT/INT\.)", s))

def _timecode_seconds(line: str) -> float | None:
    """Read explicit [MM:SS], [HH:MM:SS.mmm] or @MM:SS.mmm scene markers."""
    match = re.search(r"(?:@\s*|\[\s*)(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)\s*\]?", line)
    if not match:
        return None
    token = match.group(1).replace(",", ".")
    parts = token.split(":")
    try:
        seconds_part = float(parts[-1])
        if len(parts) == 2:
            value = int(parts[0]) * 60 + seconds_part
        else:
            value = int(parts[0]) * 3600 + int(parts[1]) * 60 + seconds_part
    except (ValueError, IndexError):
        return None
    return value if value >= 0 else None

def _speaker_line(line: str) -> tuple[str, str] | None:
    # Explicit screenplay-like "Name: dialogue" or "Name - dialogue".
    m = re.match(r"^\s*([\w\u0900-\u097F][\w\u0900-\u097F .'-]{0,35})\s*(?:\[[^\]]{1,80}\])?\s*[:：]\s*(.{2,})$", line)
    if not m:
        m = re.match(r"^\s*([\w\u0900-\u097F][\w\u0900-\u097F .'-]{0,35})\s+[—–-]\s+(.{2,})$", line)
    if not m:
        return None
    name, speech = _norm(m.group(1)), _norm(m.group(2))
    ignored_labels = {"नोट", "note", "narrator", "narration", "वाचक", "सूत्रधार",
                      "नैरेटर", "स्थान", "location", "ध्वनि", "sfx", "bgm",
                      "वातावरण", "नोट्स", "दृश्य", "scene", "अध्याय", "chapter"}
    if len(name.split()) > 4 or name.casefold() in ignored_labels:
        return None
    return name, speech

def analyze_script_text(script: str, source_name: str = "inline") -> dict:
    if not isinstance(script, str) or not script.strip():
        raise ValueError("Story script is empty")
    if len(script) > 2_000_000:
        raise ValueError("Script exceeds 2 MB safety limit")
    raw_lines = script.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    nonempty = [(i + 1, _norm(line)) for i, line in enumerate(raw_lines) if line.strip()]
    if not nonempty:
        raise ValueError("Story script has no readable lines")
    scenes: list[dict[str, Any]] = []
    current = {"scene_id": "scene_001", "heading": "Opening / scene not explicitly marked",
               "lines": [], "source_line_start": nonempty[0][0], "source_line_end": nonempty[0][0],
               "start_time_seconds": None}
    for line_no, line in nonempty:
        if _scene_heading(line) and current["lines"]:
            scenes.append(current)
            current = {"scene_id": f"scene_{len(scenes)+1:03d}", "heading": line,
                       "lines": [], "source_line_start": line_no, "source_line_end": line_no,
                       "start_time_seconds": _timecode_seconds(line)}
        elif _scene_heading(line) and not current["lines"] and current["heading"].startswith("Opening"):
            current["heading"] = line
            current["source_line_start"] = line_no
            current["start_time_seconds"] = _timecode_seconds(line)
        current["lines"].append({"line": line_no, "text": line})
        current["source_line_end"] = line_no
    if current["lines"]:
        scenes.append(current)

    characters: dict[str, dict[str, Any]] = {}
    scene_results = []
    cue_id = 0
    for scene in scenes:
        joined = "\n".join(x["text"] for x in scene["lines"])
        mood, mood_conf, mood_hits = _emotion(joined)
        environment_candidates = _environment(scene["heading"] + "\n" + joined)
        dialogue_count = 0
        narration_count = 0
        speakers = []
        scene_cues = []
        for entry in scene["lines"]:
            line = entry["text"]
            narrator_match = None if _scene_heading(line) else re.match(r"^\s*(?:वाचक|सूत्रधार|नैरेटर|narrator|narration)\s*[:：]\s*(.+)$", line, re.I)
            if narrator_match:
                narration_count += 1
            speaker = None if _scene_heading(line) else _speaker_line(line)
            if speaker:
                name, speech = speaker
                dialogue_count += 1
                if name not in characters:
                    characters[name] = {"name": name, "dialogue_lines": 0, "first_seen_line": entry["line"],
                                         "emotion_hint_counts": {}, "voice_continuity_rule": "Keep the same voice identity across scenes; do not infer age, gender or accent from the name."}
                characters[name]["dialogue_lines"] += 1
                if name not in speakers:
                    speakers.append(name)
                em, conf, hits = _emotion(speech)
                if em != "neutral":
                    characters[name]["emotion_hint_counts"][em] = characters[name]["emotion_hint_counts"].get(em, 0) + 1
                # Dialogue emotion is a cue for direction, not a forced voice transformation.
                if em != "neutral":
                    scene_cues.append({
                        "cue_type": "performance_direction", "label": f"{name}: {em}",
                        "source_line": entry["line"], "confidence": conf,
                        "evidence": hits, "requires_human_review": True
                    })
            for event, terms in EVENTS:
                hits = _matches(line, terms)
                if hits:
                    cue_id += 1
                    scene_cues.append({
                        "cue_id": f"cue_{cue_id:04d}", "cue_type": "sound_event",
                        "event": event, "suggested_role": "foley" if event in {"footsteps","breathing"} else "sfx",
                        "source_line": entry["line"], "text_excerpt": line[:220],
                        "evidence": hits, "confidence": min(0.82, 0.4 + 0.1*len(hits)),
                        "requires_human_review": True,
                        "timing": "align_to_story_event_not_known_from_text_alone"
                    })
        # infer a mood for the mixer only when confidence is adequate; mixed/neutral is neutral.
        if mood in {"tension", "fear", "anger"}:
            mix_mood = "tense"
        elif mood in {"peaceful", "joy"}:
            mix_mood = "peaceful"
        elif mood == "sad":
            mix_mood = "sad"
        else:
            mix_mood = "neutral"
        scene_results.append({
            "scene_id": scene["scene_id"], "heading": scene["heading"],
            "source_line_start": scene["source_line_start"], "source_line_end": scene["source_line_end"],
            "start_time_seconds": scene.get("start_time_seconds"),
            "source_text": "\n".join(x["text"] for x in scene["lines"]),
            "speakers": speakers, "dialogue_line_count": dialogue_count,
            "narration_line_count": narration_count,
            "lexical_mood": mood, "mood_confidence": mood_conf, "mood_evidence": mood_hits,
            "mixer_mood_suggestion": mix_mood,
            "environment_candidates": environment_candidates,
            "sound_cues": scene_cues,
            "needs_review": (mood_conf < 0.55 or mood in {"mixed","neutral"} or any(c.get("requires_human_review") for c in scene_cues))
        })
    digest = hashlib.sha256(script.encode("utf-8")).hexdigest()
    return {
        "schema": SCHEMA, "source_name": source_name, "script_sha256": digest,
        "language_hint": "hi" if re.search(r"[\u0900-\u097F]", script) else "en_or_other",
        "line_count": len(raw_lines), "nonempty_line_count": len(nonempty),
        "scene_count": len(scene_results), "characters": list(characters.values()),
        "scenes": scene_results,
        "summary": {
            "dialogue_line_count": sum(s["dialogue_line_count"] for s in scene_results),
            "narration_line_count": sum(s["narration_line_count"] for s in scene_results),
            "sound_event_candidate_count": sum(sum(c["cue_type"] == "sound_event" for c in s["sound_cues"]) for s in scene_results),
            "review_scene_count": sum(bool(s["needs_review"]) for s in scene_results),
            "environment_candidate_count": sum(len(s.get("environment_candidates", [])) for s in scene_results),
            "performance_direction_count": sum(sum(c["cue_type"] == "performance_direction" for c in s["sound_cues"]) for s in scene_results)
        },
        "policy": {
            "analysis_mode": "local_heuristic_no_external_model",
            "claims_full_story_understanding": False,
            "automatic_asset_assignment": False,
            "automatic_sfx_insertion": False,
            "automatic_environment_asset_selection": False,
            "source_script_modified": False,
            "lexical_emotion_is_not_psychological_truth": True,
            "cue_timing_requires_human_or_alignment_input": True
        },
        "limitations": [
            "Scene and speaker detection are strongest when the script uses explicit scene headings and Name: dialogue format.",
            "Emotion, setting and sound-event candidates are keyword-based; metaphor, sarcasm, implied events and context may be missed.",
            "The engine does not synthesize voices, recognize speaker identity from audio, or align words to exact audio timestamps.",
            "Human review is required before production cue approval."
        ]
    }

def analyze_script_file(path: str | Path, report_path: str | Path | None = None) -> dict:
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"Script file not found: {src}")
    if src.stat().st_size > 2_000_000:
        raise ValueError("Script exceeds 2 MB safety limit")
    text = src.read_text(encoding="utf-8-sig")
    result = analyze_script_text(text, src.name)
    if report_path:
        out = Path(report_path).resolve()
        if out == src.resolve():
            raise ValueError("Report path must not overwrite the original story script")
        save_json_atomic(out, result)
    return result

def build_reviewable_mix_spec(analysis: dict, track_paths: dict[str, str] | None = None,
                              sample_rate: int = 48000, creativity: float = 0.35) -> dict:
    if analysis.get("schema") != SCHEMA:
        raise ValueError("Unsupported story analysis schema")
    if not 8000 <= int(sample_rate) <= 192000:
        raise ValueError("sample_rate must be 8000..192000")
    if not 0 <= float(creativity) <= 1:
        raise ValueError("creativity must be 0..1")
    tracks = []
    for role, path in (track_paths or {}).items():
        if role not in {"dialogue","narration","music","ambience","sfx","foley","room_tone"}:
            raise ValueError(f"Unsupported track role: {role}")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"Invalid path for role {role}")
        tracks.append({"path": path, "role": role, "auto_level": True})
    scenes = []
    source_scenes = analysis.get("scenes", [])
    for i, scene in enumerate(source_scenes):
        start = scene.get("start_time_seconds")
        next_start = source_scenes[i+1].get("start_time_seconds") if i+1 < len(source_scenes) else None
        valid_interval = (isinstance(start, (int, float)) and
                          isinstance(next_start, (int, float)) and next_start > start)
        scenes.append({
            "scene_id": scene["scene_id"],
            "start_seconds": float(start) if isinstance(start, (int, float)) else 0.0,
            "end_seconds": float(next_start) if valid_interval else 0.0,
            "mood": scene["mixer_mood_suggestion"], "intensity": 0.35,
            "timing_status": "START_AND_END_FROM_EXPLICIT_ADJACENT_MARKERS" if valid_interval
                             else "UNRESOLVED_NEEDS_AUDIO_ALIGNMENT"
        })
    return {
        "schema": "astra-story-mix-spec-review/v1", "sample_rate": int(sample_rate),
        "creativity": float(creativity), "tracks": tracks, "scenes": scenes,
        "story_analysis_sha256": analysis["script_sha256"],
        "review_required": True,
        "warning": "This is a review template only. Scene times are placeholders and must be aligned before using mix-story."
    }
