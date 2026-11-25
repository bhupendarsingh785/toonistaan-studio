"""Action-chain Foley planner for story-driven physical interactions.

It converts explicit narrative evidence into ordered, reviewable Foley events.
It does not synthesize or insert audio and never treats a suggested cue as fact.
"""
from __future__ import annotations
import re
from typing import Any

SCHEMA = "astra-action-foley-chain/v1"

# Ordered rules: earliest matching rule is not exclusive; a sentence can produce
# several events. Patterns cover Hindi and English narrative wording.
RULES = [
    ("footsteps_leaves", [r"सूखे पत्तों पर.{0,20}(?:चला|चली|कदम|चलते)", r"पत्तों पर (?:चला|चली|कदम)", r"dry leaves underfoot", r"walked on dry leaves"],
     "leaf_crunch_footsteps", "dry_leaf_footsteps", "walking on leaves"),
    ("brush_through", [r"झाड़ियों से (?:निकला|निकली|बाहर आया|बाहर आई)", r"झाड़ियों को हटाकर", r"झाड़ियों में से गुजरा", r"pushed through (?:the )?bushes", r"emerged from (?:the )?bushes"],
     "foliage_body_contact", "body_through_brush", "moving through brush"),
    ("rope_uncoil", [r"रस्सी.{0,35}(?:खोली|निकाली|फैलायी|फैलायी)", r"रस्सी खोल", r"uncoil(?:ed|ing)? (?:the )?rope", r"unwound (?:the )?rope"],
     "rope_friction", "rope_uncoil_or_drag", "rope handling"),
    ("rope_wrap_anchor", [r"रस्सी.{0,45}(?:बाँधी|बांधी|लपेटी|अटकाई|अटकायी)", r"(?:हुक|ग्रिल|खूँटी|खूंटी|खंभे|खम्भे).{0,30}(?:रस्सी|बाँध|बांध)", r"tied (?:the )?rope", r"secured (?:the )?rope", r"wrapped (?:the )?rope around"],
     "rope_and_anchor", "rope_anchor_contact", "rope attachment"),
    ("knot_tighten", [r"गाँठ.{0,30}(?:लगाई|लगायी|बाँधी|बांधी|कसी|कसकर|कस दी|कस दिया)", r"गांठ.{0,30}(?:लगाई|लगायी|कसी)", r"गाँठ कस", r"कसकर गाँठ", r"tied a knot", r"tightened the knot", r"cinched the knot"],
     "rope_friction", "knot_tighten", "knot tying"),
    ("anchor_test", [r"(?:रस्सी|गाँठ|गांठ).{0,35}(?:खींचकर|खींचा|जाँचा|जांचा|परखा|आजमाया)", r"(?:खींचकर|खींचा).{0,25}(?:रस्सी|गाँठ|गांठ)", r"tested the (?:rope|knot|anchor)", r"pulled the rope taut"],
     "tension_foley", "rope_tension_test", "load check"),
    ("window_open", [r"खिड़की.{0,25}(?:खोली|खुली|सरकाई|धकेली)", r"window.{0,20}(?:opened|slid open|pushed open)"],
     "window_mechanism", "window_open_creak", "window interaction"),
    ("window_exit", [r"खिड़की से बाहर", r"खिड़की.{0,25}(?:बाहर निकला|बाहर निकली|पार किया|पार कर)", r"climbed out (?:of )?the window", r"through the window to the outside"],
     "body_cloth_contact", "window_sill_exit", "body crosses window sill"),
    ("rope_bear_weight", [r"रस्सी पर.{0,30}(?:लटका|लटकी|भार|वजन|झूला|झूली)", r"रस्सी.{0,30}(?:तन गई|तन गयी|खींच गई|खींच गयी)", r"put (?:his|her|their) weight on the rope", r"rope went taut"],
     "rope_tension", "rope_load_tension", "weight transfer"),
    ("rope_descend", [r"रस्सी से नीचे (?:उतरा|उतरी|उतरने|उतार)", r"रस्सी पकड़कर नीचे", r"रस्सी के सहारे नीचे", r"नीचे उतरता गया", r"descended (?:the )?rope", r"lowered (?:himself|herself|themself) down (?:the )?rope", r"climbed down (?:the )?rope"],
     "rope_slide_and_wall_contact", "rope_descent", "controlled descent"),
    ("rope_climb", [r"रस्सी से ऊपर (?:चढ़ा|चढ़ी|चढ़ने)", r"रस्सी पकड़कर ऊपर", r"ऊपर चढ़ता गया", r"climbed up (?:the )?rope", r"ascended (?:the )?rope"],
     "rope_grip_and_tension", "rope_climb", "upward climb"),
    ("wall_foot_contact", [r"पैर.{0,25}(?:दीवार|दीवार पर)", r"दीवार पर पैर", r"feet against the wall", r"braced (?:his|her|their) feet"],
     "shoe_wall_friction", "feet_brace_wall", "feet brace"),
    ("landing_ground", [r"(?:जमीन|ज़मीन|फर्श|धरती) पर (?:आकर|उतरकर|गिरकर|कूदा|कूदी|पैर रखा)", r"नीचे उतरकर (?:खड़ा|खड़ी)", r"landed on the (?:ground|floor)", r"feet hit the ground", r"hit the floor"],
     "body_impact_and_footwear", "landing_impact", "landing"),
    ("rope_release", [r"रस्सी (?:छोड़|छोड़ी|छोड़ दी)", r"हाथों से रस्सी छोड़ी", r"released the rope", r"let go of the rope"],
     "rope_release_friction", "rope_release", "rope release"),
    ("jump_window_in", [r"खिड़की से अंदर कूदा", r"खिड़की से भीतर कूदा", r"खिड़की के अंदर छलाँग", r"खिड़की के अंदर छलांग", r"jumped in through the window", r"leapt through the window"],
     "body_window_and_floor", "window_entry_jump", "jump entry"),
    ("jump_down", [r"(?:ऊपर से|ऊपर से नीचे).{0,20}(?:कूदा|कूदी|छलाँग|छलांग)", r"नीचे कूद", r"jumped down", r"leapt down", r"dropped to the ground"],
     "air_motion_and_landing", "jump_down", "jump"),
    ("ladder_climb", [r"सीढ़ी से (?:ऊपर|नीचे)", r"सीढ़ी पर चढ़", r"सीढ़ी उतर", r"climbed (?:up|down) the ladder", r"ladder rung"],
     "ladder_rung_and_hand_contact", "ladder_climb", "ladder movement"),
    ("door_handle", [r"दरवाजे? का हैंडल", r"कुंडी (?:घुमाई|खोली|खोला)", r"door handle", r"turned the handle", r"door latch"],
     "metal_or_wood_mechanism", "door_handle_latch", "door mechanism"),
    ("key_lock", [r"चाबी (?:घुमाई|लगाई|डाली)", r"ताला (?:खोला|खोला गया)", r"turned the key", r"unlocked the door", r"key in the lock"],
     "key_lock_mechanism", "key_lock", "lock interaction"),
    ("body_lift", [r"(?:उसे|उसे अपने हाथों से|उसका शरीर).{0,30}(?:उठाया|उठाकर)", r"कंधे पर उठा", r"lifted (?:him|her|them|the body)", r"carried (?:him|her|them)"],
     "cloth_body_weight_and_effort", "body_lift", "lifting another person"),
    ("water_entry", [r"पानी में (?:कूदा|कूदी|गिरा|गिरी)", r"छपाक", r"jumped into the water", r"fell into the water", r"splashed into"],
     "water_impact_and_submersion", "water_entry_splash", "water entry"),
]

def _find(patterns: list[str], text: str) -> list[str]:
    hits=[]
    for pat in patterns:
        if re.search(pat, text, flags=re.IGNORECASE):
            hits.append(pat)
    return hits

def analyze_action_chains(script_text: str, source_name: str="inline") -> dict[str, Any]:
    if not isinstance(script_text, str) or not script_text.strip():
        raise ValueError("Story script is empty")
    if len(script_text) > 2_000_000:
        raise ValueError("Story script exceeds 2 MB limit")
    lines=[(i+1, x.strip()) for i,x in enumerate(script_text.splitlines()) if x.strip()]
    chains=[]
    for line_no, line in lines:
        events=[]
        for event, patterns, sound_family, tag, action_label in RULES:
            hits=_find(patterns,line)
            if hits:
                events.append({
                    "event_id": f"line_{line_no:04d}_{event}",
                    "action": event,
                    "action_label": action_label,
                    "source_line": line_no,
                    "evidence_excerpt": line[:260],
                    "matched_patterns": hits,
                    "sound_family": sound_family,
                    "asset_search_tags": [tag],
                    "suggested_perspective": "character_relative_close",
                    "mix_guidance": "brief_event_synced; preserve_dialogue; natural_transient; no exaggerated impact",
                    "confidence": "explicit_text_match",
                    "requires_human_review": True
                })
        if events:
            chains.append({
                "chain_id": f"action_chain_line_{line_no:04d}",
                "source_line": line_no,
                "narrative_excerpt": line[:260],
                "events": events,
                "ordering": "listed order is a suggested causal order; use explicit story chronology if it differs",
                "concurrency": "foley may overlap only when the physical actions plausibly overlap",
                "review_required": True
            })
    return {
        "schema": SCHEMA,
        "source_name": source_name,
        "action_chain_count": len(chains),
        "event_count": sum(len(c["events"]) for c in chains),
        "action_chains": chains,
        "safety_and_realism": {
            "no_unmentioned_actions": True,
            "no_auto_asset_insertion": True,
            "no_auto_render": True,
            "source_audio_untouched": True,
            "uncertain_or_missing_steps": "do not invent; request editorial review",
            "mix_priority": ["dialogue", "foreground_action", "nearby_foley", "environment_bed", "music"]
        },
        "limitations": [
            "Evidence-based Hindi/English pattern recognition, not full semantic comprehension.",
            "Does not infer exact timing, force, material, rope type, anchor type or landing surface unless stated.",
            "Asset retrieval, audition, approval and final rendering are separate stages."
        ],
        "human_review_required": True
    }
