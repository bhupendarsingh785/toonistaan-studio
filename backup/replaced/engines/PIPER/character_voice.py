
"""Character profile planning; does not fabricate unsupported voices."""
from pathlib import Path
import json
AGE_REQUIREMENTS = {
 "child_3_6": "genuinely age-appropriate licensed child voice model",
 "child_7_12": "age-appropriate youthful voice model",
 "teen_13_17": "age-appropriate teen voice model",
 "young_adult": "young adult voice model",
 "adult": "adult voice model",
 "elderly": "mature/elderly voice model",
 "unspecified": "manual selection required"
}
EMOTIONS = ["neutral","happy","sad","angry","fearful","surprised","curious","serious","whisper","shout","laughing","crying"]
def make_profiles(scan_result, overrides=None):
    overrides = overrides or {}
    out = {}
    for c in scan_result.get("characters", []):
        o = overrides.get(c["name"], {})
        age = o.get("age_group", c.get("age_group", "unspecified"))
        if age not in AGE_REQUIREMENTS: age = "unspecified"
        out[c["character_id"]] = {
            "character_id": c["character_id"], "name": c["name"],
            "age_group": age,
            "voice_presentation": o.get("voice_presentation", c.get("voice_presentation","unspecified")),
            "voice_id": o.get("voice_id"),
            "emotion_targets": o.get("emotions", ["neutral","happy","sad"]),
            "delivery_notes": o.get("delivery_notes",""),
            "required_model_capability": AGE_REQUIREMENTS[age],
            "verified_voice_match": False,
            "status": "PLANNED_NOT_GENERATED"
        }
    return out
def save_profiles(scan_result, path, overrides=None):
    profiles = make_profiles(scan_result, overrides)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    return profiles


# ---------------------------------------------------------------- awaaz ka shape
# Engine ke paas ek hi model ho tab bhi har kirdaar alag sune — umar aur ling
# ke hisaab se pitch/raftaar. (Yeh nakli "acting" nahi, sirf sur ka farq hai.)
VOICE_SHAPE = {
    ("child_3_6", "unspecified"): (1.45, 1.06),
    ("child_7_12", "unspecified"): (1.35, 1.04),
    ("teen_13_17", "female"): (1.15, 1.02),
    ("teen_13_17", "male"): (1.06, 1.02),
    ("young_adult", "female"): (1.10, 1.00),
    ("young_adult", "male"): (1.00, 1.00),
    ("adult", "female"): (1.05, 0.99),
    ("adult", "male"): (0.95, 0.99),
    ("adult", "unspecified"): (1.00, 1.00),
    ("young_adult", "unspecified"): (1.00, 1.00),
    ("teen_13_17", "unspecified"): (1.08, 1.02),
    ("elderly", "female"): (0.82, 0.92),
    ("elderly", "male"): (0.85, 0.93),
    ("elderly", "unspecified"): (0.84, 0.93),
}


def voice_shape(profile):
    """(pitch_guna, rate_guna) — profile se; pata na ho to (1.0, 1.0)."""
    if not profile:
        return (1.0, 1.0)
    age = profile.get("age_group", "unspecified")
    pres = profile.get("voice_presentation", "unspecified")
    if (age, pres) in VOICE_SHAPE:
        return VOICE_SHAPE[(age, pres)]
    # sirf umar pata ho
    for (a, p), v in VOICE_SHAPE.items():
        if a == age and (pres == "unspecified" or p == pres):
            return v
    return (1.0, 1.0)
