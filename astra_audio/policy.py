"""Conservative context policy. Tags are hints, never automatic truth."""
from dataclasses import dataclass, asdict

@dataclass
class AudioPolicy:
    preserve_speech: bool = True
    preserve_emotion_and_breath: bool = True
    preserve_ambience: bool = True
    preserve_transients: bool = True
    allow_destructive_silence_trim: bool = False
    allow_source_separation: bool = False
    require_noise_only_profile_for_denoise: bool = True
    require_human_review_when_uncertain: bool = True

def build_policy(tags=(), user_context=""):
    tags={str(t).strip().lower() for t in tags}
    policy=AudioPolicy()
    # These tags only strengthen preservation. They never authorize deletion.
    if tags & {"wind","rain","forest","station_ambience","room_tone","traffic","nature"}:
        policy.preserve_ambience=True
    if tags & {"child_cry","crying","shouting","anger","fear","laughter","breathing","character_voice"}:
        policy.preserve_speech=True
        policy.preserve_emotion_and_breath=True
    if tags & {"footsteps","knock","impact","glass_break","door_break","metal_hit"}:
        policy.preserve_transients=True
    return {"policy":asdict(policy),
            "context_note":str(user_context)[:1000],
            "tag_hints":sorted(tags),
            "warning":"Tags are user hints; this version does not semantically verify them."}
