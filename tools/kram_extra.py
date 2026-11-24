'''kram_extra.py — naye module aur nayi functions ka level (bada naksha chhede bina).'''

EXTRA = {
 "1_shabd": {
  "asr_check.py": [
   "main"
  ],
  "audio_decode.py": [
   "decode"
  ],
  "narration_clean.py": [
   "strip_sounds",
   "clean_script",
   "main"
  ],
  "audio_pro.py": [
   "denoise",
   "restore",
   "occlude",
   "stream_chunks",
   "diarize",
   "adr",
   "_frames",
   "adr_dtw",
   "_test"
  ],
  "voice_train.py": [
   "_piper",
   "_load",
   "_shift",
   "feats",
   "tts_rows",
   "real_rows",
   "decide",
   "main"
  ]
 },
 "5_duniya": {
  "loop_reference.py": [
   "features",
   "main"
  ],
  "loop_maker.py": [
   "pink",
   "_band_mask",
   "retint",
   "walk",
   "reverb",
   "_norm",
   "_seamless",
   "reference",
   "features",
   "_bed",
   "room",
   "wind",
   "rain",
   "river",
   "fire",
   "crickets",
   "leaves",
   "wood_steps",
   "birds",
   "make",
   "judge",
   "make_checked",
   "main"
  ],
  "build_content_index.py": [
   "_load",
   "main"
  ],
  "drama/scene_audio.py": [
   "_content_index",
   "_from_content",
   "find_or_make",
   "make_loop"
  ],
  "agent_brief.py": [
   "_run",
   "_last_manifest",
   "build",
   "queries",
   "main"
  ],
  "agent_intel.py": [
   "main"
  ],
  "space.py": [
   "_band",
   "air_cutoff",
   "_air_absorb",
   "_late_reverb",
   "_early",
   "place_acoustic",
   "place_acoustic_3d",
   "place_moving",
   "measure",
   "_burst",
   "_test",
   "_demo",
   "main"
  ],
  "world/duniya.py": [
   "db2a",
   "a2db",
   "sos_bp",
   "sos_lp",
   "sos_hp",
   "filt",
   "pink",
   "smooth_rand",
   "env_ar",
   "add_at",
   "pan_mono",
   "place",
   "place_wide",
   "outdoor_reverb",
   "syn_river",
   "syn_wind",
   "syn_leaves",
   "syn_rain",
   "syn_crickets",
   "_tone",
   "syn_bird",
   "syn_koel",
   "syn_thunder",
   "syn_step",
   "decode",
   "loop_to",
   "load_map",
   "detect",
   "space_for",
   "_dist_for",
   "plan_scene",
   "render_world",
   "apply_emotion",
   "render_fx",
   "smooth_env",
   "place_env",
   "indoor_muffle",
   "apply_weather",
   "sound_for",
   "situation_at",
   "render_sheet",
   "phone_voice",
   "pause_after",
   "is_scene_start",
   "repace_lines",
   "auto_repace",
   "voice_chain",
   "_peaking",
   "follow",
   "mix",
   "_lufs_of",
   "master",
   "main"
  ],
  "creature_train.py": [
   "keywords",
   "decode",
   "features_multi",
   "features",
   "build",
   "train",
   "main"
  ],
  "sound_resolver.py": [
   "_index",
   "_tag_for",
   "from_library",
   "from_synth",
   "verify_audio",
   "from_web",
   "resolve",
   "demo",
   "main"
  ],
  "private_train.py": [
   "load_clips",
   "decode",
   "feats",
   "train",
   "main"
  ],
  "auto_label.py": [
   "decode",
   "asr_has_words",
   "evidence",
   "decide",
   "main"
  ]
 },
 "6_harkat": {
  "engine_router.py": [
   "active_order",
   "_ffmpeg",
   "_which",
   "engine_status",
   "ready_engines",
   "choose_engine",
   "load_voices",
   "parse_story",
   "build_plan",
   "_call_provider",
   "_fix_format",
   "_guarded",
   "render_line",
   "render_story_parallel",
   "render_story",
   "cmd_status",
   "problems",
   "cmd_problems",
   "cmd_plan",
   "main",
   "EngineState",
   "Plan"
  ],
  "sarvam_story.py": [
   "_ff",
   "load",
   "trim",
   "piper_line",
   "sarvam_line",
   "river_bed",
   "main"
  ]
 },
 "0_neev": {
  "sutradhar.py": [
   "_shape"
  ],
  "kram.py": [
   "_merge_extra"
  ],
  "system_doctor.py": [
   "c_bug_hunt",
   "c_sarvam"
  ],
  "kram_extra.py": [
   "EXTRA"
  ],
  "ffbin.py": [
   "_bundled",
   "_make_shim",
   "ensure"
  ],
  "regression.py": [
   "add",
   "check_space",
   "check_narration",
   "check_structure",
   "check_render",
   "main"
  ],
  "coverage_audio.py": [
   "sources",
   "funcs_of",
   "has_func",
   "check_real",
   "check",
   "main"
  ],
  "fetch_real_audio.py": [
   "_curl",
   "_get",
   "search",
   "fetch",
   "main"
  ],
  "test_real_audio.py": [
   "load",
   "pick",
   "rms",
   "floor_db",
   "test_denoise",
   "test_restore",
   "test_occlude",
   "test_diarize",
   "test_adr",
   "test_stream",
   "test_spatial",
   "main"
  ]
 }
}
