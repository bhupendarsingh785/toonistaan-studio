"""World-general, reviewable story soundscape planner.

This module proposes sound layers from script evidence. It never fabricates assets,
never inserts unreviewed files, and marks uncertain/inferred cues for human approval.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from .io import save_json_atomic
from .action_foley import analyze_action_chains

SCHEMA = "astra-world-soundscape-plan/v1"
# Environment profiles are extensible data, not a closed list of supported worlds.
ENVIRONMENTS = {
 "forest": {"beds":["forest_wide_ambience","wind_in_canopy","distant_birds","insects"],"acoustics":"open_natural_scattering","avoid":["constant_loud_wind","dense_bird_layer_without_evidence"]},
 "cemetery": {"beds":["quiet_open_air","subtle_wind","distant_night_insects"],"acoustics":"open_sparse_reflections","avoid":["automatic_ghost_sounds","horror_stingers_without_story_cue"]},
 "deserted_road": {"beds":["open_air_tone","distant_traffic_if_contextual","light_wind"],"acoustics":"open_outdoor","avoid":["busy_city_traffic"]},
 "jungle": {"beds":["layered_forest_ambience","insects","distant_birds","foliage_movement"],"acoustics":"dense_natural_occlusion","avoid":["continuous_max_volume_animal_calls"]},
 "cave": {"beds":["cave_air_tone","drips_if_wet","footstep_reflections"],"acoustics":"long_early_reflections_and_reverb"},
 "village": {"beds":["rural_air","distant_domestic_activity","birds"],"acoustics":"open_mixed_environment"},
 "city_street": {"beds":["urban_air","traffic_wash","distant_people"],"acoustics":"street_reflections"},
 "railway_station": {"beds":["station_air","distant_crowd","announcements_if_present","rail_mechanical_bed"],"acoustics":"large_reflective_public_space"},
 "market": {"beds":["crowd_murmur","vendors_if_present","street_air"],"acoustics":"dense_public_space"},
 "home_interior": {"beds":["room_tone","subtle_household_activity_if_present"],"acoustics":"room_size_dependent_reflections"},
 "old_mansion": {"beds":["interior_room_tone","wood_settling_if_cued","distant_wind_if_exposed"],"acoustics":"large_or_empty_interior"},
 "hospital": {"beds":["clinical_room_tone","distant_corridor_activity_if_present"],"acoustics":"clean_hard_surface_reflections"},
 "temple": {"beds":["temple_room_tone","subtle_crowd_if_present","bells_or_chant_only_if_cued"],"acoustics":"stone_or_hall_reflections"},
 "river_or_sea": {"beds":["water_motion","shoreline_or_river_air","wind_if_present"],"acoustics":"open_waterfront"},
 "mountain": {"beds":["mountain_air","wind_exposure","distant_nature"],"acoustics":"open_exposed_outdoor"},
 "snowfield": {"beds":["cold_open_air","wind_if_present","snow_underfoot_if_walking"],"acoustics":"open_soft_ground"},
 "battlefield": {"beds":["open_battlefield_air","distant_activity_only_if_present"],"acoustics":"open_distant_transients"},
 "airport": {"beds":["terminal_air","distant_public_crowd","aircraft_only_if_scene_calls_for_it"],"acoustics":"large_terminal_reflections"},
 "ship": {"beds":["vessel_hull_tone","water_motion","wind_on_deck_if_exterior"],"acoustics":"confined_or_open_deck_dependent"},
 "underwater": {"beds":["underwater_lowpass_ambience","muffled_motion"],"acoustics":"strong_high_frequency_absorption"},
 "farm": {"beds":["rural_air","field_wind","farm_animals_only_if_present"],"acoustics":"open_rural"},
 "factory": {"beds":["industrial_room_tone","machine_bed_only_if_present"],"acoustics":"industrial_reflections"},
}
# Match explicit terms; preserve evidence and require review. Hindi and English variants.
ENV_TERMS = {
"forest":["जंगल","वन","पेड़ों के बीच","झाड़ियों","झाड़ी","jungle","forest","woods"],
"cemetery":["श्मशान","कब्रिस्तान","मसान","चिता स्थल","graveyard","cemetery","cremation ground"],
"deserted_road":["सुनसान रास्ता","खाली सड़क","निर्जन सड़क","अकेली सड़क","सूनी सड़क","deserted road","empty road","lonely road"],
"jungle":["घना जंगल","जंगल के भीतर","घने वन","deep jungle","dense jungle"],
"cave":["गुफा","कंदरा","cave","cavern"],
"village":["गाँव","गांव","देहात","चौपाल","village","rural"],
"city_street":["शहर की सड़क","सड़क","ट्रैफिक","शहर","street","city road","traffic"],
"railway_station":["रेलवे स्टेशन","प्लेटफॉर्म","स्टेशन","platform","railway station"],
"market":["बाजार","बाज़ार","मंडी","market","bazaar"],
"home_interior":["कमरे में","घर के भीतर","रसोई","आँगन","आंगन","inside the room","home interior"],
"old_mansion":["हवेली","खंडहर","पुरानी कोठी","abandoned mansion","ruins"],
"hospital":["अस्पताल","हॉस्पिटल","वार्ड","hospital","clinic"],
"temple":["मंदिर","देवालय","गर्भगृह","temple","shrine"],
"river_or_sea":["नदी किनारे","समुद्र तट","घाट","नदी","समुद्र","riverbank","seashore","ocean"],
"mountain":["पहाड़","पहाड़ी रास्ता","पर्वत","mountain","mountain trail"],
"snowfield":["बर्फ","हिमपात","हिमालय","snowfield","snowing","snow"],
"battlefield":["युद्धभूमि","रणभूमि","मैदान-ए-जंग","battlefield","war zone"],
"airport":["हवाई अड्डा","एयरपोर्ट","airport","terminal"],
"ship":["जहाज पर","नाव में","समुद्री जहाज","ship deck","boat","vessel"],
"underwater":["पानी के अंदर","समुद्र के भीतर","underwater","below the water"],
"farm":["खेत","खलिहान","फार्म","farm","field"],
"factory":["कारखाना","फैक्ट्री","मशीनों का शोर","factory","industrial plant"],
}
ACTION_RULES = [
("walk_leaves",["सूखे पत्तों","पत्तों पर","पत्तों की चरमराहट","dry leaves","leaves underfoot"],"close_foley","dry_leaf_footsteps"),
("walk_gravel",["कंकड़ पर चला","बजरी पर चला","पत्थरों पर चला","gravel footsteps","walking on gravel"],"close_foley","gravel_footsteps"),
("walk_mud",["कीचड़ में चला","दलदल में चला","mud footsteps","walking in mud"],"close_foley","mud_footsteps"),
("walk_snow",["बर्फ पर चला","बर्फ में कदम","snow footsteps","walking on snow"],"close_foley","snow_footsteps"),
("walk_wood",["लकड़ी के फर्श पर चला","लकड़ी की सीढ़ी","wooden floor footsteps","wood stairs"],"close_foley","wood_footsteps"),
("brush_through",["झाड़ियों से","झाड़ियों में","झाड़ियों को हटाया","पत्तों को चीरता","pushed through bushes","brushed through foliage"],"close_foley","body_through_brush"),
("branch_snap",["टहनी टूटी","टहनी टूट","सूखी डाल टूटी","branch snapped","twig snapped"],"close_foley","twig_snap"),
("cloth_move",["कपड़े सरसराए","कपड़ों की सरसराहट","दुपट्टा लहराया","clothes rustled","fabric movement"],"close_foley","cloth_rustle"),
("breath",["साँस तेज हुई","हांफने लगा","हांफने लगी","साँसें तेज","panting","breathing heavily"],"close_foley","human_breath"),
("run",["दौड़ने लगा","दौड़ने लगी","भागने लगा","भागने लगी","running","sprinted"],"close_foley","running_footsteps"),
("door_creak",["दरवाजा चरमराया","दरवाज़ा चरमराया","किवाड़ खुला","door creaked","creaking door"],"foreground_sfx","door_creak"),
("water_splash",["पानी में कूदा","छपाक","पानी उछला","splashed into water","water splash"],"foreground_sfx","water_splash"),
]

def _hits(text, terms):
    low=text.casefold(); found=[]
    for term in terms:
        t=term.casefold()
        if re.search(r"[a-z]",t):
            if re.search(r"(?<![a-z0-9_])"+re.escape(t)+r"(?![a-z0-9_])",low): found.append(term)
        elif t in low: found.append(term)
    return found

def plan_soundscape(script_text: str, source_name: str="inline") -> dict:
    if not isinstance(script_text,str) or not script_text.strip(): raise ValueError("Story script is empty")
    if len(script_text)>2_000_000: raise ValueError("Story script exceeds 2 MB limit")
    lines=[(i+1,x.strip()) for i,x in enumerate(script_text.splitlines()) if x.strip()]
    # Scene segmentation uses explicit scene headings where possible; otherwise one continuous scene.
    scenes=[]; current={"scene_id":"scene_001","heading":"Opening / unmarked scene","lines":[]}
    heading_re=re.compile(r"(?i)^(?:scene\b|दृश्य\b|अध्याय\b|INT\.|EXT\.)")
    for no,line in lines:
        if heading_re.match(line) and current["lines"]:
            scenes.append(current); current={"scene_id":f"scene_{len(scenes)+1:03d}","heading":line,"lines":[]}
        elif heading_re.match(line) and not current["lines"]: current["heading"]=line
        current["lines"].append({"line":no,"text":line})
    if current["lines"]: scenes.append(current)
    output=[]
    for scene in scenes:
        body="\n".join(x["text"] for x in scene["lines"]); full=scene["heading"]+"\n"+body
        env=[]
        heading_hits_by_env={}
        for label,terms in ENV_TERMS.items():
            hits=_hits(full,terms)
            heading_hits=_hits(scene["heading"],terms)
            if hits: env.append((len(hits)+2*len(heading_hits),label,hits)); heading_hits_by_env[label]=heading_hits
        env.sort(reverse=True)
        primary=env[0][1] if env else "unspecified_world_location"
        profile=ENVIRONMENTS.get(primary,{"beds":["contextual_location_tone","subtle_open_or_room_air_as_scene_requires"],"acoustics":"infer_only_after_review"})
        layers=[]
        for bed in profile["beds"]:
            layers.append({"layer_type":"environment_bed","asset_search_tags":[bed],"priority":"supporting","mix_guidance":"low_and_non_intrusive","evidence":"environment_profile","requires_asset_match_and_human_approval":True})
        for _,label,hits in env:
            layers.append({"layer_type":"environment_candidate","environment":label,"evidence":hits,"profile":ENVIRONMENTS[label],"confidence":"lexical_only","requires_human_review":True})
        actions=[]
        for entry in scene["lines"]:
            no,line=entry["line"],entry["text"]
            for event,terms,role,tag in ACTION_RULES:
                hits=_hits(line,terms)
                if hits:
                    actions.append({"event":event,"source_line":no,"text_excerpt":line[:220],"evidence":hits,"role":role,"asset_search_tags":[tag],"perspective":"character_relative_close_unless_story_says_otherwise","mix_guidance":"brief_natural_transient; preserve_dialogue; avoid_looping_unless_continuous_action","confidence":"lexical_only","requires_human_review":True})
        # Explicitly avoid hallucinating layers just because a setting is eerie or emotional.
        lower=full.casefold()
        mood="neutral"
        mood_terms={"fear":["डर","भय","कांप","काँप","खौफ","terrified","afraid"],"grief":["शोक","मृत्यु","मौत","विलाप","शव","grief","mourning"],"romantic":["प्रेम","प्यार","मोहब्बत","kiss","love"],"joy":["खुश","हँसा","हंसा","जश्न","happy","laugh"],"tension":["सन्नाटा","पीछा","खतरा","रहस्य","अचानक","silence","danger","stalked"],"sad":["उदास","दुख","रोया","रोई","sad","crying"]}
        scored=[(len(_hits(full,terms)),name) for name,terms in mood_terms.items()]; scored.sort(reverse=True)
        if scored and scored[0][0]: mood=scored[0][1]
        output.append({"scene_id":scene["scene_id"],"heading":scene["heading"],"source_lines":[x["line"] for x in scene["lines"]],"primary_environment":primary,"environment_alternatives":[{"environment":e,"evidence":h,"profile":ENVIRONMENTS[e],"confidence":"lexical_only"} for _,e,h in env],"acoustic_space":profile.get("acoustics","review_required"),"mood_candidate":mood,"environment_layers":layers,"action_foley":actions,"mixing_policy":{"dialogue_priority":"highest","ambience":"quiet_continuous_bed_only_when_scene_supports_it","foley":"short_and_event_synced","dynamic_range":"preserve_natural_distance_and_transients","noise_policy":"do_not_add_noise_as_texture_without_story_evidence","silence":"retain_intentional_silence"},"review_required":True})
    action_plan = analyze_action_chains(script_text, source_name)
    for scene in output:
        scene_lines = set(scene["source_lines"])
        scene["action_chains"] = [chain for chain in action_plan["action_chains"] if chain["source_line"] in scene_lines]
    return {"schema":SCHEMA,"source_name":source_name,"scene_count":len(output),"scenes":output,"action_chain_count":action_plan["action_chain_count"],"action_event_count":action_plan["event_count"],"coverage_note":"Extensible world/setting taxonomy with explicit evidence. Unknown settings receive a conservative generic plan; this is not omniscient semantic scene understanding.","asset_generation_performed":False,"audio_rendered":False,"human_review_required":True}

def plan_soundscape_file(input_path: str, report_path: str) -> dict:
    p=Path(input_path); result=plan_soundscape(p.read_text(encoding="utf-8"),p.name); save_json_atomic(report_path,result); return result
