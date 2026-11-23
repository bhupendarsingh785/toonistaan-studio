#!/usr/bin/env python3
"""
kram.py — Seetal/ASTRA ka poora naksha: 100 module, 896 function, har ek apne level par.
Koi function chhoota nahi, kuch delete nahi.

Rakhne ki jagah: tools/kram.py   (sutradhar.py ke saath)

  python tools/kram.py naksha          # kaunsa level, kaunse module, kitne function
  python tools/kram.py jaanch          # har module import + har function sach me hai? naye function naksha me nahi?
  python tools/kram.py purana          # purani copies ko purana/ me le jaane ka PLAN (kuch hilta nahi)
  python tools/kram.py purana --karo   # sach me purana/ me le jao (delete nahi, move)
  python tools/kram.py maalik          # ek kaam kitni jagah likha hai, maalik kaun
"""
import importlib, inspect, shutil, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Kram: kahani isi order me banti hai. A_ (agents) Level 5 ko khilate hain. T_, K_, P_ kahani ke raaste me nahi.
LEVELS = {
 "0_neev": {
  "kaam": "Neev: jagah, keys, cache, sehat",
  "modules": {
   "system_audit.py": [
    "mods",
    "_name",
    "parse",
    "imports_of",
    "graph",
    "referenced",
    "reachable",
    "collisions",
    "wires",
    "smoke",
    "_toplevel_imports",
    "cycles",
    "level_order",
    "signature_check",
    "main",
   ],
   "sutradhar.py": [
    "Hisaab",
    "get_fn",
    "wire",
    "_db",
    "_mono",
    "loop_score",
    "_lufs_ffmpeg",
    "lufs_target",
    "_channels",
    "_lufs_approx",
    "pakki_jaanch",
    "_stage",
    "StageFail",
    "space_voice",
    "time_of_day",
    "_wav",
    "run",
    "check",
    "selftest",
   ],
   "kram.py": [
    "maalik_report",
    "_modname",
    "naksha",
    "jaanch",
    "purana",
   ],
   "worktmp.py": [
    "work_tmp",
    "clean",
    "free_mb"
   ],
   "preflight.py": [
    "_has",
    "report",
    "main"
   ],
   "system_check.py": [
    "_row",
    "check_engines",
    "check_bus",
    "check_cache",
    "check_library",
    "check_modules",
    "check_tests",
    "run_all",
    "main"
   ],
   "system_doctor.py": [
    "add",
    "c_voices",
    "c_brain",
    "c_smooth",
    "c_ground",
    "c_world",
    "c_catalog",
    "c_model",
    "c_engines",
    "c_tools",
    "c_qa_thresholds",
    "c_judge_smoke",
    "c_selftest",
    "c_world_engine",
    "c_collision",
    "c_world_version",
    "c_realtime",
    "c_bhaav_kaam",
    "c_shabd",
    "c_activate",
    "c_agents",
    "c_self_improve",
    "c_praat",
    "c_sfx",
    "main",
   ],
   "system_activate.py": [
    "modules",
    "text_of",
    "audit",
    "main"
   ],
   "key_guard.py": [
    "tracked_files",
    "scan",
    "main"
   ],
   "intelligence_status.py": [
    "_config",
    "_count",
    "status",
    "main"
   ],
   "engine_setup.py": [
    "_pip",
    "ensure_piper_model",
    "test_piper",
    "test_espeak",
    "test_edge",
    "test_free",
    "test_elevenlabs",
    "setup",
    "main"
   ],
   "engine_sync.py": [
    "main"
   ],
   "consent.py": [
    "_atomic_json",
    "record_consent",
    "revoke_consent",
    "assert_consent_active"
   ],
   "sarvam_keys.py": [
    "_hash",
    "all_keys",
    "_load",
    "_save",
    "order",
    "mark_ok",
    "mark_quota_dead",
    "reset",
    "status",
    "main"
   ],
   "render_cache.py": [
    "key_for",
    "_load",
    "_save",
    "_usable",
    "get",
    "put",
    "stats",
    "clear",
    "main"
   ],
   "tts_guard.py": [
    "BadAudio",
    "audio_ok",
    "render",
    "main"
   ]
  }
 },
 "1_shabd": {
  "kaam": "Script aur Hindi shabd",
  "modules": {
   "script_pipeline.py": [
    "_strip_emotion",
    "parse_script_line",
    "_graphemes",
    "_hard_split_token",
    "_split_oversize",
    "prepare_script",
    "prepare_file",
    "main"
   ],
   "local_story/hindi_shabd.py": [
    "_syllables",
    "check",
    "respell",
    "report"
   ],
   "local_story/respell.py": [
    "respell"
   ],
   "realtime/akshar.py": [
    "is_cons",
    "is_matra",
    "is_vowel",
    "is_mod",
    "normalize",
    "split_akshar",
    "tokens",
    "parts",
    "classify",
    "classify_all",
    "_sub_cost",
    "align",
    "_merge_schwa",
    "compare",
    "matra_units"
   ],
   "realtime/sudhaar.py": [
    "Lexicon",
    "_replace_first_akshar",
    "candidates",
    "order_by_learning",
    "apply_word"
   ],
   "pronounce_test.py": [
    "main",
   ]
  }
 },
 "2_bhaav": {
  "kaam": "Bhaav (emotion)",
  "modules": {
   "local_story/prosody_plan.py": [
    "_is_content",
    "plan_line",
    "plan_script",
   ],
   "drama/prosody.py": [
    "plan",
    "plan_all",
   ],
   "bhavna.py": [
    "detect",
    "prosody",
    "style",
    "list_all",
    "show",
    "main"
   ],
   "realtime/bhaav.py": [
    "rules",
    "_has",
    "target",
    "prosody",
    "deviation",
    "estimate",
    "word_spans",
    "word_measure",
    "judge_words",
    "correction",
    "sculpt",
    "end_contour",
    "BhaavYaad",
    "analyse",
    "describe"
   ],
   "emotion_read.py": [
    "ffmpeg",
    "decode",
    "f0_med",
    "modulation",
    "emotion_scored",
    "emotion_of",
    "read",
    "main"
   ],
   "teacher_student.py": [
    "_ff",
    "measure",
    "plan",
    "collect",
    "learn",
    "dry_run",
    "main"
   ],
   "voice_learn.py": [
    "engine_settings",
    "check",
    "main"
   ],
   "voice_provider.py": [
    "eleven_key",
    "have_eleven",
    "_post",
    "_load_voices",
    "_kism",
    "age_filters",
    "fit_to_target",
    "shape_age",
    "voice_cast",
    "sarvam_keys",
    "sarvam_key",
    "_piper_dir",
    "have_piper",
    "_piper_model",
    "_piper_gender",
    "_piper_session",
    "_piper_inprocess",
    "_piper_parallel_long",
    "piper_tts",
    "_edge_transcode",
    "edge_tts",
    "have_edge",
    "have_espeak",
    "_espeak_init",
    "espeak_tts",
    "have_sarvam",
    "_learned_style",
    "clean_text",
    "has_words",
    "_bhaav_style",
    "prep_text",
    "sarvam_tts",
    "_measure_pitch",
    "_tune_to_target",
    "_naturalize",
    "_dur_seconds",
    "list_voices",
    "pick_voice",
    "eleven_tts"
   ],
   "engine_bus.py": [
    "_wav_ok",
    "probe_piper",
    "probe_espeak",
    "probe_edge",
    "probe_elevenlabs",
    "route",
    "bus_send",
    "bus_demo",
    "main"
   ],
   "free_api.py": [
    "_ff",
    "_style",
    "_chunks",
    "_apply_style",
    "_has_words",
    "google",
    "have",
    "speak",
    "main"
   ],
   "awaaz.py": [
    "clean_af",
    "ffmpeg",
    "_cache_path",
    "_providers",
    "engine_report",
    "_edge",
    "_chunks",
    "_pause_for",
    "bolo",
    "bolo_natural",
    "main"
   ],
   "voice_clone.py": [
    "_atomic_json",
    "ConsentMissing",
    "Voice",
    "backend_status",
    "pick_backend",
    "reference_quality",
    "_voice_dir",
    "_normalise_reference",
    "enroll_from_media",
    "enroll",
    "list_voices",
    "load_voice",
    "clear_backend_cache",
    "_get_xtts_model",
    "_canonical_emotion",
    "add_emotion_reference",
    "_render_line",
    "parse_line",
    "_wav_info",
    "_stitch_wavs",
    "_voice_fingerprint",
    "speak",
    "cmd_backends",
    "cmd_audit",
    "cmd_voices",
    "main"
   ],
   "voice_extract.py": [
    "_ff",
    "_load",
    "extract_audio",
    "clean_audio",
    "best_window",
    "transcribe",
    "best_windows",
    "run",
    "main"
   ],
   "speaker_verification.py": [
    "_load_model",
    "_waveform",
    "cosine_similarity",
    "main"
   ],
   "voice_match.py": [
    "_load",
    "f0_median",
    "mfcc_cosine",
    "speech_ratio",
    "check",
    "main"
   ],
   "voice_ab.py": [
    "_keys",
    "_render",
    "_measure",
    "main"
   ],
   "voice_preview.py": [
    "_ff",
    "_say",
    "_speak_natural",
    "make",
    "main"
   ],
   "voice_guru.py": [
    "teach",
    "export",
    "qa",
    "main"
   ],
   "local_story/voice_fx.py": [
    "_stft",
    "_istft",
    "_envelope",
    "formant_shift",
    "_sola",
    "pitch_shift_sola",
    "pitch_shift_formant",
    "humanize",
    "breath",
    "warm",
    "room",
    "smooth_chain",
    "pitch_resample",
    "trim_silence",
    "compress_silences",
    "crossfade_join",
    "prosody_contour",
    "de_buzz"
   ],
   "realtime/live.py": [
    "log",
    "EspeakTTS",
    "PiperTTS",
    "post",
    "_bh_slim",
    "LiveChecker",
    "main"
   ],
   "realtime/kaan.py": [
    "FasterWhisperEar",
    "CacheEar",
    "SimulatedEar",
    "make_ear"
   ],
   "realtime/gates.py": [
    "_frames",
    "db",
    "f0_period",
    "echo_score",
    "centroid_voiced",
    "inner_gaps",
    "presence",
    "allowed_gaps",
    "excess_gaps",
    "check",
    "apply_fix"
   ],
   "realtime/nirantarta.py": [
    "features",
    "Profiles"
   ],
   "realtime/bahi.py": [
    "Bahi"
   ],
   "llm_bridge.py": [
    "ProviderState",
    "_spec",
    "_key",
    "_valid_base",
    "_request",
    "_probe",
    "status",
    "ready_providers",
    "_post",
    "_content",
    "_retryable",
    "_attempt_chat",
    "chat",
    "remember",
    "cmd_status",
    "cmd_chat",
    "main"
   ]
  }
 },
 "4_spotting": {
  "kaam": "Script se duniya ka plan: kya, kab, kahan, andar/bahar, mausam",
  "modules": {
   "drama/script_parse.py": [
    "parse",
    "load",
   ],
   "story_scene.py": [
    "_has",
    "plan",
    "main"
   ],
   "story_soundmap.py": [
    "find",
    "analyse",
    "main"
   ]
  }
 },
 "5_duniya": {
  "kaam": "Duniya ki awaazein: library, seekhna, naye roop, bed",
  "modules": {
   "world/spotting.py": [
    "load_events",
    "_rx",
    "_pos",
    "has",
    "first_pos",
    "t_at",
    "find_stop",
    "spot_rules",
    "place_timeline",
    "weather_timeline",
    "spot_llm",
    "parse_llm",
    "merge",
    "log_missing",
    "spot",
   ],
   "world/harkat.py": [
    "_bp",
    "_lp",
    "_hp",
    "F",
    "norm",
    "crackle",
    "step",
    "scuff",
    "paw_cycle",
    "twig",
    "fall",
    "jump",
    "splash",
    "wolf_howl",
    "growl",
    "thunder",
    "heartbeat",
    "panting",
    "_pos",
    "has",
    "act",
    "word_time",
    "emotion_of",
    "surface_of",
    "plan_actions",
   ],
   "local_story/nat_story.py": [
    "voice",
    "say",
    "load",
    "trim",
    "bed",
    "main",
   ],
   "drama/scene_audio.py": [
    "_ff",
    "find",
    "load",
    "loop_to",
    "build",
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
    "Library",
    "loop_to",
    "load_map",
    "detect",
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
    "main",
   ],
   "world/awaazein.py": [
    "_bp",
    "_lp",
    "_hp",
    "F",
    "norm",
    "T",
    "sil",
    "modal",
    "phone_ring_old",
    "mobile_ring",
    "phone_vibrate",
    "phone_pickup",
    "phone_hangup",
    "message_tone",
    "door_knock",
    "door_creak",
    "door_close",
    "door_open",
    "clock_tick",
    "wall_clock_chime",
    "utensils",
    "pressure_cooker",
    "water_pour",
    "tap_water",
    "drip",
    "paper_page",
    "cloth_rustle",
    "typing",
    "glass_break",
    "fire_crackle",
    "wood_chop",
    "chair_drag",
    "clap",
    "temple_bell",
    "school_bell",
    "cycle_bell",
    "car_horn",
    "vehicle_pass",
    "bike_engine",
    "dog_bark",
    "rooster",
    "frog"
   ],
   "world/rachna.py": [
    "rules",
    "load_learned",
    "is_learned",
    "all_embeds",
    "situation_from_text",
    "params_for",
    "repitch",
    "tilt",
    "fade",
    "make_events",
    "make_texture",
    "fingerprint",
    "novelty",
    "load_limits",
    "update_limits",
    "variant",
    "combinations"
   ],
   "world/seekho.py": [
    "load",
    "trim",
    "embed",
    "similarity",
    "embed_fmax",
    "analyse",
    "learn",
    "learn_library"
   ],
   "local_story/ambience.py": [
    "_noise",
    "rain",
    "wind",
    "crickets",
    "river",
    "pad_chords",
    "birds",
    "footsteps",
    "air",
    "_band",
    "_steps",
    "steps_dirt",
    "steps_concrete",
    "steps_leaves",
    "steps_grass",
    "steps_wood",
    "steps_mud",
    "steps_gravel",
    "leaves"
   ],
   "local_story/real_bed.py": [
    "find",
    "_ff",
    "load_mono",
    "loop_to",
    "band",
    "speech_like",
    "make_bed",
   ],
   "sound_synth.py": [
    "ffmpeg",
    "_band",
    "wolf_growl",
    "dog_bark",
    "cricket",
    "rain",
    "river",
    "leaves_steps",
    "main"
   ],
   "sfx.py": [
    "t",
    "noise",
    "lowpass",
    "wind",
    "music"
   ],
   "library_add.py": [
    "_ff",
    "_sha",
    "library_hashes",
    "slug",
    "convert",
    "duration",
    "fingerprint",
    "similarity",
    "find_duplicate",
    "register",
    "add",
    "check",
    "main"
   ],
   "sound_catalog.py": [
    "ffmpeg",
    "feats",
    "cat_of",
    "quality",
    "main"
   ],
   "sound_pick.py": [
    "pick"
   ],
   "sound_id3.py": [
    "ffmpeg",
    "load",
    "_fb",
    "features",
    "knn",
    "main"
   ],
   "music_make2.py": [
    "ffmpeg",
    "kick",
    "snare",
    "hat",
    "tabla",
    "pluck",
    "pad_chord",
    "riser",
    "impact",
    "shelf",
    "hpf",
    "compress",
    "stereo_widen",
    "_fftconv",
    "reverb_stereo",
    "build",
    "write",
    "main"
   ]
  }
 },
 "6_harkat": {
  "kaam": "Harkat: kadam, daudna, jaanwar",
  "modules": {
   "render_river.py": [
    "voice",
    "load",
    "trim",
    "loop",
    "river_bed",
    "main",
   ],
   "render_final.py": [
    "voice",
    "load",
    "synth",
    "trim",
    "contour_for",
    "micro",
    "river_bed",
    "main",
   ],
   "local_story/psola.py": [
    "f0_track",
    "shift",
   ],
   "local_story/praat_pitch.py": [
    "_praat",
    "f0_track",
    "measure",
    "apply_curve",
    "syllable_curve",
    "selftest",
   ],
   "drama/drama.py": [
    "_ff",
    "load",
    "voice",
    "say",
    "trim",
    "main",
   ],}
 },
 "8_jaanch": {
  "kaam": "Pakki jaanch: suno, naapo, PASS/FAIL",
  "modules": {
   "bug_hunt.py": [
    "files",
    "_inside_with",
    "_depth",
    "check",
    "load_base",
    "save_base",
    "fix_file",
    "main",
   ],
   "audio_learn.py": [
    "advice",
    "main",
   ],
   "self_improve.py": [
    "load",
    "_f0",
    "_env",
    "_speech_mask",
    "deep",
    "cpp",
    "lra_db",
    "flux",
    "formant_track",
    "diagnose",
    "_delta",
    "log_run",
    "learn",
    "_vec",
    "train_model",
    "suggest",
    "build_target",
    "apply_learned",
    "selftest",
    "main",
   ],
   "local_story/shabd_live.py": [
    "risky",
    "variants",
    "_model",
    "_say",
    "_hear",
    "_cer",
    "best",
    "main",
   ],
   "audio_judge.py": [
    "ffmpeg",
    "decode",
    "voice_only",
    "f0_track",
    "acoustics",
    "background",
    "asr_words",
    "norm_words",
    "wer",
    "judge",
    "main"
   ],
   "asr_gate.py": [
    "_ffmpeg",
    "load16k",
    "model",
    "_phone_dist",
    "cer",
    "judge",
    "main"
   ],
   "asr_cache.py": [
    "ffmpeg",
    "decode",
    "transcribe",
    "main"
   ],
   "self_listen.py": [
    "ffmpeg",
    "decode",
    "norm",
    "words",
    "wer",
    "f0_of",
    "_f0_frame",
    "acoustics",
    "asr",
    "run",
    "main"
   ],
   "evaluate_generation.py": [
    "_norm",
    "_edit_distance",
    "text_scores",
    "evaluate",
    "main"
   ],
   "world/world_qa.py": [
    "decode",
    "lufs",
    "tri",
    "judge"
   ],
   "render_manifest.py": [
    "sha",
    "qa_audio",
    "build",
    "check",
    "main"
   ],
   "audio_qa.py": [
    "inspect_wav"
   ],
   "voice_validate.py": [
    "check",
    "main"
   ],
   "audio_profile.py": [
    "ffmpeg",
    "load",
    "f0_track",
    "profile",
    "main"
   ],
   "audio_read6.py": [
    "ffmpeg",
    "decode",
    "stft",
    "event_features",
    "classify",
    "learn_event",
    "knn_label",
    "vad",
    "f0_of",
    "f0_track",
    "emotion",
    "read",
    "selftest",
    "main"
   ],
   "song_read.py": [
    "ffmpeg",
    "decode",
    "spec",
    "tempo",
    "chroma_of",
    "key_scale",
    "drum_pattern",
    "structure",
    "vocal_f0",
    "read",
    "main"
   ],
   "horror_read.py": [
    "ffmpeg",
    "decode",
    "block_stats",
    "mode_of",
    "read",
    "main"
   ]
  }
 },
 "A_agents": {
  "kaam": "Agents + research: kami wali awaaz/jaankari dhoondhna (Level 5 ko khilate hain)",
  "modules": {
   "research_connect.py": [
    "_get",
    "_clean",
    "search_ddg",
    "search_wiki",
    "search_github",
    "search_arxiv",
    "wiki_extract",
    "search_news",
    "search_wiki_hi",
    "search_ddg_lite",
    "search_bing",
    "search_all",
    "search_for_agent",
    "health",
    "search",
    "fetch",
    "_relevant",
    "research",
    "main",
   ],
   "browser_mesh.py": [
    "negotiate",
    "_run_agent",
    "mesh",
    "main"
   ]
  }
 },
 "T_test": {
  "kaam": "Test: kahani ke beech nahi, alag chalte hain",
  "modules": {
   "deep_audit.py": [
    "_sha",
    "t_fuzz",
    "t_idempotent",
    "t_race",
    "t_injection",
    "t_import",
    "t_leak",
    "t_disk",
    "main"
   ],
   "world_tests.py": [
    "_probe",
    "differential",
    "soak",
    "pairwise",
    "mutation_lite",
    "regression",
    "risk_based",
    "main"
   ],
   "test_matrix.py": [
    "_probe",
    "make_cases",
    "run_case",
    "metamorphic",
    "golden_master",
    "main"
   ],
   "selftest_suite.py": [
    "wav",
    "results",
    "main"
   ],
   "engine_stress.py": [
    "_ff",
    "_audio",
    "_render",
    "stress_engine",
    "main"
   ],
   "engine_load.py": [
    "_dur_rms",
    "run",
    "main"
   ],
   "engine_bench.py": [
    "bench",
    "main"
   ],
   "engine_adopt.py": [
    "ffmpeg",
    "load",
    "measure",
    "verdict",
    "main"
   ],
   "listen.py": [
    "main"
   ],
   "build_system_doc.py": [
    "table",
    "bullets",
    "code"
   ]
  }
 },
 "K_khazana": {
  "kaam": "Khazana: build()/main() purana raasta, par andar ke functions upar ke levels use karte hain",
  "modules": {
   "local_story/story_local.py": [
    "ffmpeg_bin",
    "breath",
    "_hp",
    "_stereo",
    "line_emotion",
    "breath_plan",
    "_presence",
    "room_tone",
    "bhaav_prosody",
    "_voice",
    "line_check",
    "synth_line",
    "load",
    "group_script",
    "build"
   ],
   "local_story/horror_story.py": [
    "ffmpeg",
    "synth_line",
    "trim",
    "compress_gaps",
    "eq_warm",
    "build"
   ],
   "awaaz_studio.py": [
    "sh",
    "dur_of",
    "read_wav",
    "write_wav",
    "breath",
    "ambience",
    "music_bed",
    "sunao",
    "main"
   ],
   "story_audio.py": [
    "_ff",
    "_dur",
    "merge_lines",
    "_trim_silence",
    "render_single",
    "render_lines",
    "build",
    "main"
   ],
   "local_story/ground_demo.py": [
    "main",
   ],
   "world_scape.py": [
    "_hits",
    "plan_scene",
    "duck_curve",
    "build",
    "main"
   ]
  }
 },
 "P_purana": {
  "kaam": "Purani copy: purana/ folder me (delete NAHI), naya version upar hai",
  "modules": {
   "story_local.py": [
    "ffmpeg_bin",
    "breath",
    "_hp",
    "_stereo",
    "line_emotion",
    "breath_plan",
    "_presence",
    "room_tone",
    "bhaav_prosody",
    "_voice",
    "line_check",
    "synth_line",
    "load",
    "group_script",
    "build"
   ],
   "audio_read.py": [
    "ffmpeg",
    "decode",
    "frames",
    "f0_frame",
    "segments",
    "speakers",
    "events",
    "bed_timeline",
    "read",
    "timeline_text",
    "main"
   ],
   "audio_read3.py": [
    "ffmpeg",
    "decode",
    "mel_fb",
    "stft_mag",
    "mfcc",
    "f0_of",
    "lpc_formants",
    "kmeans",
    "read",
    "timeline",
    "main"
   ],
   "audio_read4.py": [
    "ffmpeg",
    "decode",
    "stft",
    "istft",
    "stems",
    "chroma",
    "tempo_of",
    "vad",
    "f0_of",
    "emotion_of",
    "read",
    "main"
   ],
   "audio_read5.py": [
    "ffmpeg",
    "decode",
    "stft",
    "istft",
    "separate",
    "vad_merge",
    "f0_of",
    "lpc_formants",
    "chroma_key",
    "tempo_of",
    "events_of",
    "emotion",
    "read",
    "selftest",
    "main"
   ],
   "sound_id.py": [
    "ffmpeg",
    "load",
    "features",
    "train",
    "identify",
    "main"
   ],
   "sound_id2.py": [
    "ffmpeg",
    "load",
    "_mel_filterbank",
    "features",
    "train",
    "knn",
    "main"
   ],
   "music_make.py": [
    "ffmpeg",
    "kick",
    "snare",
    "hat",
    "tabla",
    "pluck",
    "pad",
    "reverb",
    "scale_freqs",
    "build",
    "write_audio",
    "main"
   ]
  }
 }
}

KRAM = ["0_neev", "1_shabd", "2_bhaav", "3_awaaz", "4_spotting", "5_duniya", "6_harkat", "7_mix", "8_jaanch"]


# Ek kaam = ek maalik. Baaki jagah wale same-kaam functions isi ko bulaayein (dheere-dheere badlo, delete nahi).
EK_MAALIK = {
    "ffmpeg dhundhna":  ("engine_router.py", "_ffmpeg",  ["ffmpeg", "_ffmpeg", "_ff", "ffmpeg_bin"]),
    "audio padhna":     ("world/duniya.py", "decode",    ["decode", "load", "_load", "load16k", "load_mono", "_waveform"]),
    "sur (F0) naapna":  ("audio_read6.py", "f0_track",   ["f0_of", "f0_track", "f0_med", "f0_median", "f0_frame", "_f0_frame", "vocal_f0", "f0_period", "_measure_pitch"]),
    "STFT":             ("local_story/voice_fx.py", "_stft", ["stft", "_stft", "stft_mag"]),
    "saans":            ("local_story/story_local.py", "breath", ["breath"]),
    "kadam":            ("world/harkat.py", "step",  ["step", "syn_step", "_steps", "footsteps", "leaves_steps"] + [f"steps_{k}" for k in ("dirt","concrete","leaves","grass","wood","mud","gravel")]),
    "loop banana":      ("world/duniya.py", "loop_to", ["loop_to"]),
    "line ka bhaav":    ("realtime/bhaav.py", "target", ["detect", "line_emotion", "emotion_of", "bhaav_prosody"]),
    "loudness":         ("world/world_qa.py", "lufs", ["lufs"]),
}


def maalik_report():
    print("Ek kaam, kai jagah (maalik ko chhod kar baaki ko maalik se jodna hai):")
    for kaam, (m, f, names) in EK_MAALIK.items():
        where = [f"{mm}:{fn}" for lv in LEVELS.values() for mm, fs in lv["modules"].items()
                 for fn in fs if fn in names and not (mm == m and fn == f)]
        print(f"\n  {kaam}: maalik = {m}:{f}   ({len(where)} doosri jagah)")
        for w in where:
            print("     -", w)


def _modname(path):
    return path[:-3].replace("/", ".")


def naksha():
    tot_m = tot_f = 0
    for k, v in LEVELS.items():
        nf = sum(len(f) for f in v["modules"].values())
        tot_m += len(v["modules"]); tot_f += nf
        flag = "  -> kahani ka kram" if k in KRAM else ""
        print(f"\n[{k}] {v['kaam']}  ({len(v['modules'])} module, {nf} function){flag}")
        for m, fs in v["modules"].items():
            print(f"    {m:<32} {len(fs):>3}")
    print(f"\nKul: {tot_m} module, {tot_f} function")


def jaanch():
    bad = 0; t0 = time.time(); seen = set()
    for k, v in LEVELS.items():
        for m, fs in v["modules"].items():
            seen.add(m)
            if k == "P_purana" and not (HERE / m).exists():
                continue  # purana/ me ja chuka
            t = time.time()
            try:
                mod = importlib.import_module(_modname(m))
            except Exception as e:  # noqa: BLE001
                bad += 1; print(f"  XX [{k}] {m}: import nahi hua -> {type(e).__name__}: {e}"); continue
            gone = [f for f in fs if not hasattr(mod, f)]
            have = {n for n, o in vars(mod).items()
                    if (inspect.isfunction(o) or inspect.isclass(o)) and getattr(o, "__module__", "") == mod.__name__}
            new = sorted(have - set(fs))
            slow = time.time() - t
            msg = f"  {'OK' if not gone else 'XX'} [{k}] {m}  ({len(fs)} fn, import {slow:.2f}s)"
            if gone: bad += 1; msg += f"\n       gayab: {gone}"
            if new: msg += f"\n       naye (naksha me jodo): {new}"
            if slow > 2: msg += "\n       DHEEMA import: bhaari model/library ko function ke andar load karo"
            print(msg)
    # disk par aise .py jo naksha me hi nahi
    loose = [str(p.relative_to(HERE)) for p in HERE.rglob("*.py")
             if "purana" not in p.parts and p.name not in ("kram.py", "sutradhar.py", "__init__.py")
             and str(p.relative_to(HERE)) not in seen]
    if loose:
        print("\nNaksha se bahar ki files (inka level tay karo):"); [print("   ", x) for x in loose]
    print(f"\n{'SAB THEEK' if not bad else f'{bad} module me dikkat'}  ({time.time()-t0:.1f}s)")
    return 1 if bad else 0


def purana(karo=False):
    dest = HERE / "purana"
    for m in LEVELS["P_purana"]["modules"]:
        src = HERE / m
        if not src.exists():
            print(f"  --  {m} (pehle hi hat chuka)"); continue
        to = dest / m
        print(f"  {'MOVE' if karo else 'plan'}  {m}  ->  purana/{m}")
        if karo:
            to.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(src), str(to))
    if not karo:
        print("\nKuch nahi hila. Sach me karne ke liye:  python tools/kram.py purana --karo")


if __name__ == "__main__":
    a = sys.argv[1:] or ["naksha"]
    if a[0] == "naksha": naksha()
    elif a[0] == "jaanch": sys.exit(jaanch())
    elif a[0] == "purana": purana("--karo" in a)
    elif a[0] == "maalik": maalik_report()
    else: print(__doc__)
