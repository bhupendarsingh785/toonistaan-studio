#!/usr/bin/env python3
"""
ASTRA LOCAL LIBRARY — asli recordings jo hum khud rakhte hain (best quality, sabse pehle).

  library.fetch("scream")                 -> wav path ya None
  library.fetch("footsteps", "हवेली में")  -> context se indoor/outdoor
  library.fetch("gate_open", "दरवाज़ा धीरे से खुला")  -> speed 0.88 (dheema)

Naya sound jodna:
  1. mp3 ko astra/library/<folder>/<naam>.mp3 me rakho
  2. niche DEFAULT_INDEX me entry likho (file, tags, license)
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library")
CACHE = os.path.join(HERE, "cache", "lib")
INDEX = os.path.join(LIB, "library.json")
os.makedirs(CACHE, exist_ok=True)

DEFAULT_INDEX = {
 "horror_intro": {
  "file": "horror/horror_intro.mp3",
  "tags": [
   "horror",
   "intro",
   "drone",
   "डरावना",
   "शुरुआत"
  ],
  "license": "Pixabay"
 },
 "horror_pad_crowd": {
  "file": "horror/horror_pad_crowd.mp3",
  "tags": [
   "horror",
   "pad",
   "crowd",
   "भीड़",
   "डर"
  ],
  "license": "Pixabay"
 },
 "monster_lurk": {
  "file": "horror/monster_lurk.mp3",
  "tags": [
   "monster",
   "rakshas",
   "राक्षस",
   "भूत",
   "darr"
  ],
  "license": "Pixabay"
 },
 "scary_sting": {
  "file": "horror/scary_sting.mp3",
  "tags": [
   "scary",
   "sting",
   "jump",
   "डर",
   "चौंक"
  ],
  "license": "Pixabay"
 },
 "horror_hit": {
  "file": "horror/horror_hit.mp3",
  "tags": [
   "hit",
   "impact",
   "dhamaka",
   "धमाका",
   "टकराव"
  ],
  "license": "Pixabay"
 },
 "horror_ambience": {
  "file": "horror/horror_ambience.mp3",
  "tags": [
   "ambience",
   "horror",
   "mahaul",
   "माहौल",
   "डर"
  ],
  "license": "Pixabay"
 },
 "ghost": {
  "file": "horror/ghost.mp3",
  "tags": [
   "ghost",
   "bhoot",
   "भूत",
   "आत्मा",
   "spirit"
  ],
  "license": "Pixabay"
 },
 "scream_woman": {
  "file": "horror/scream_woman.mp3",
  "tags": [
   "scream",
   "cheekh",
   "चीख",
   "chillana",
   "aurat"
  ],
  "license": "Pixabay"
 },
 "crowd_applause": {
  "file": "crowd/crowd_applause.mp3",
  "tags": [
   "crowd",
   "applause",
   "tali",
   "ताली",
   "khushi",
   "भीड़"
  ],
  "license": "Pixabay"
 },
 "crowd_panic": {
  "file": "crowd/crowd_panic.mp3",
  "tags": [
   "crowd",
   "panic",
   "bhagdad",
   "भगदड़",
   "scream",
   "भीड़"
  ],
  "license": "Pixabay"
 },
 "footsteps_parquet": {
  "file": "footsteps/footsteps_parquet.mp3",
  "tags": [
   "footsteps",
   "kadam",
   "कदम",
   "parquet",
   "boots",
   "indoor",
   "ghar",
   "घर"
  ],
  "license": "Pixabay"
 },
 "footsteps_hallway": {
  "file": "footsteps/footsteps_hallway.mp3",
  "tags": [
   "footsteps",
   "kadam",
   "कदम",
   "hallway",
   "corridor",
   "हवेली",
   "indoor"
  ],
  "license": "Pixabay"
 },
 "footsteps_concrete": {
  "file": "footsteps/footsteps_concrete.mp3",
  "tags": [
   "footsteps",
   "kadam",
   "कदम",
   "concrete",
   "road",
   "सड़क",
   "bahar",
   "outdoor"
  ],
  "license": "Pixabay"
 },
 "footsteps_walk": {
  "file": "footsteps/footsteps_walk.mp3",
  "tags": [
   "footsteps",
   "walking",
   "kadam",
   "कदम",
   "chalna"
  ],
  "license": "Pixabay"
 },
 "door_open_a": {
  "file": "door/door_open_a.mp3",
  "tags": [
   "door",
   "open",
   "दरवाज़ा",
   "darwaza",
   "khulna"
  ],
  "license": "Pixabay"
 },
 "door_open_b": {
  "file": "door/door_open_b.mp3",
  "tags": [
   "door",
   "open",
   "दरवाज़ा",
   "darwaza",
   "khulna"
  ],
  "license": "Pixabay"
 },
 "door_open_c": {
  "file": "door/door_open_c.mp3",
  "tags": [
   "door",
   "open",
   "दरवाज़ा",
   "darwaza",
   "khulna"
  ],
  "license": "Pixabay"
 },
 "door_close_a": {
  "file": "door/door_close_a.mp3",
  "tags": [
   "door",
   "close",
   "दरवाज़ा",
   "darwaza",
   "band"
  ],
  "license": "Pixabay"
 },
 "door_close_b": {
  "file": "door/door_close_b.mp3",
  "tags": [
   "door",
   "close",
   "दरवाज़ा",
   "darwaza",
   "band"
  ],
  "license": "Pixabay"
 },
 "door_close_c": {
  "file": "door/door_close_c.mp3",
  "tags": [
   "door",
   "close",
   "दरवाज़ा",
   "darwaza",
   "band"
  ],
  "license": "Pixabay"
 },
 "man_scream": {
  "file": "voices/man_scream.mp3",
  "tags": [
   "scream",
   "cheekh",
   "चीख",
   "aadmi",
   "man"
  ],
  "license": "Pixabay"
 },
 "man_laugh": {
  "file": "voices/man_laugh.mp3",
  "tags": [
   "laugh",
   "hansi",
   "हँसी",
   "हंसी",
   "aadmi"
  ],
  "license": "Pixabay"
 },
 "man_angry": {
  "file": "voices/man_angry.mp3",
  "tags": [
   "angry",
   "gussa",
   "गुस्सा",
   "chilla",
   "aadmi"
  ],
  "license": "Pixabay"
 },
 "man_yell": {
  "file": "voices/man_yell.mp3",
  "tags": [
   "yell",
   "chillana",
   "चिल्लाना",
   "shout",
   "गुस्सा"
  ],
  "license": "Pixabay"
 },
 "man_fall": {
  "file": "voices/man_fall.mp3",
  "tags": [
   "fall",
   "girna",
   "गिरना",
   "gir",
   "thud"
  ],
  "license": "Pixabay"
 },
 "man_grunt": {
  "file": "voices/man_grunt.mp3",
  "tags": [
   "grunt",
   "struggle",
   "karahna",
   "कराहना",
   "dard"
  ],
  "license": "Pixabay"
 },
 "man_wazzup": {
  "file": "voices/man_wazzup.mp3",
  "tags": [
   "hello",
   "wazzup",
   "namaste",
   "दोस्त"
  ],
  "license": "Pixabay"
 },
 "talk_crowd_1": {
  "file": "voices/talk_crowd_1.mp3",
  "tags": [
   "talk",
   "baat",
   "बात",
   "log",
   "crowd",
   "bheed"
  ],
  "license": "Pixabay"
 },
 "talk_crowd_2": {
  "file": "voices/talk_crowd_2.mp3",
  "tags": [
   "talk",
   "baat",
   "बात",
   "log",
   "crowd",
   "bheed"
  ],
  "license": "Pixabay"
 },
 "braam_dark": {
  "file": "horror/braam_dark.mp3",
  "tags": [
   "impact",
   "braam",
   "dark",
   "डर",
   "dhamaka",
   "bhaari"
  ],
  "license": "Pixabay"
 },
 "man_death_scream": {
  "file": "voices/man_death_scream.mp3",
  "tags": [
   "scream",
   "death",
   "cheekh",
   "चीख",
   "maut"
  ],
  "license": "Pixabay"
 },
 "vampire_shriek": {
  "file": "voices/vampire_shriek.mp3",
  "tags": [
   "vampire",
   "shriek",
   "chudail",
   "चुड़ैल",
   "supernatural"
  ],
  "license": "Pixabay"
 },
 "man_fall_scream": {
  "file": "voices/man_fall_scream.mp3",
  "tags": [
   "fall",
   "girna",
   "गिरना",
   "scream",
   "chillana"
  ],
  "license": "Pixabay"
 },
 "man_sigh": {
  "file": "voices/man_sigh.mp3",
  "tags": [
   "sigh",
   "saans",
   "साँस",
   "dukh",
   "thakan"
  ],
  "license": "Pixabay"
 },
 "man_cry": {
  "file": "voices/man_cry.mp3",
  "tags": [
   "cry",
   "rona",
   "रोना",
   "dukh",
   "aansu"
  ],
  "license": "Pixabay"
 },
 "man_sniffle": {
  "file": "voices/man_sniffle.mp3",
  "tags": [
   "sniffle",
   "sinkna",
   "सिसकना",
   "rona"
  ],
  "license": "Pixabay"
 },
 "man_scream_2": {
  "file": "voices/man_scream_2.mp3",
  "tags": [
   "scream",
   "cheekh",
   "चीख",
   "aadmi"
  ],
  "license": "Pixabay"
 },
 "vampire_gaze": {
  "file": "voices/vampire_gaze.mp3",
  "tags": [
   "vampire",
   "tension",
   "डर",
   "supernatural"
  ],
  "license": "Pixabay"
 },
 "vampire_line": {
  "file": "voices/vampire_line.mp3",
  "tags": [
   "vampire",
   "voice",
   "raat",
   "रात",
   "supernatural"
  ],
  "license": "Pixabay"
 },
 "man_cough": {
  "file": "voices/man_cough.mp3",
  "tags": [
   "cough",
   "khaansi",
   "खांसी",
   "beemar"
  ],
  "license": "Pixabay"
 },
 "man_scream_3": {
  "file": "voices/man_scream_3.mp3",
  "tags": [
   "scream",
   "cheekh",
   "चीख",
   "aadmi"
  ],
  "license": "Pixabay"
 },
 "man_scream_pathetic": {
  "file": "voices/man_scream_pathetic.mp3",
  "tags": [
   "scream",
   "cheekh",
   "चीख",
   "dard"
  ],
  "license": "Pixabay"
 },
 "man_laugh_2": {
  "file": "voices/man_laugh_2.mp3",
  "tags": [
   "laugh",
   "hansi",
   "हँसी",
   "ठहाका"
  ],
  "license": "Pixabay"
 },
 "vampire_line_hunger": {
  "file": "voices/vampire_line_hunger.mp3",
  "tags": [
   "vampire",
   "line",
   "chudail",
   "चुड़ैल",
   "raat"
  ],
  "license": "Pixabay"
 },
 "vampire_line_humans": {
  "file": "voices/vampire_line_humans.mp3",
  "tags": [
   "vampire",
   "line",
   "chudail",
   "insaan"
  ],
  "license": "Pixabay"
 },
 "vampire_line_soul": {
  "file": "voices/vampire_line_soul.mp3",
  "tags": [
   "vampire",
   "line",
   "aatma",
   "आत्मा"
  ],
  "license": "Pixabay"
 },
 "vampire_hiss_attack": {
  "file": "voices/vampire_hiss_attack.mp3",
  "tags": [
   "vampire",
   "hiss",
   "attack",
   "hamla",
   "हमला"
  ],
  "license": "Pixabay"
 },
 "vampire_hiss": {
  "file": "voices/vampire_hiss.mp3",
  "tags": [
   "vampire",
   "hiss",
   "chudail",
   "डर"
  ],
  "license": "Pixabay"
 },
 "vampire_growl": {
  "file": "voices/vampire_growl.mp3",
  "tags": [
   "vampire",
   "growl",
   "dahad",
   "दहाड़"
  ],
  "license": "Pixabay"
 },
 "vampire_laugh": {
  "file": "voices/vampire_laugh.mp3",
  "tags": [
   "vampire",
   "laugh",
   "hansi",
   "चुड़ैल",
   "evil"
  ],
  "license": "Pixabay"
 },
 "doctor_brain_damage": {
  "file": "voices/doctor_brain_damage.mp3",
  "tags": [
   "doctor",
   "report",
   "brain",
   "dimaag",
   "दिमाग",
   "hospital"
  ],
  "license": "Pixabay"
 },
 "doctor_no_disease": {
  "file": "voices/doctor_no_disease.mp3",
  "tags": [
   "doctor",
   "report",
   "bimari",
   "बीमारी",
   "hospital"
  ],
  "license": "Pixabay"
 },
 "vampire_laugh_2": {
  "file": "voices/vampire_laugh_2.mp3",
  "tags": [
   "vampire",
   "laugh",
   "hansi",
   "चुड़ैल"
  ],
  "license": "Pixabay"
 },
 "vampire_laugh_3": {
  "file": "voices/vampire_laugh_3.mp3",
  "tags": [
   "vampire",
   "laugh",
   "hansi",
   "चुड़ैल"
  ],
  "license": "Pixabay"
 },
 "vampire_hum": {
  "file": "voices/vampire_hum.mp3",
  "tags": [
   "vampire",
   "hum",
   "goonj",
   "डर"
  ],
  "license": "Pixabay"
 },
 "vampire_voice_2": {
  "file": "voices/vampire_voice_2.mp3",
  "tags": [
   "vampire",
   "voice",
   "chudail",
   "चुड़ैल"
  ],
  "license": "Pixabay"
 },
 "vampire_hiss_2": {
  "file": "voices/vampire_hiss_2.mp3",
  "tags": [
   "vampire",
   "hiss",
   "hamla",
   "हमला"
  ],
  "license": "Pixabay"
 },
 "vampire_hiss_3": {
  "file": "voices/vampire_hiss_3.mp3",
  "tags": [
   "vampire",
   "hiss",
   "pyaas",
   "प्यास"
  ],
  "license": "Pixabay"
 },
 "screech": {
  "file": "horror/screech.mp3",
  "tags": [
   "screech",
   "cheekh",
   "चीख",
   "daravana"
  ],
  "license": "Pixabay"
 },
 "transition_swoosh": {
  "file": "horror/transition_swoosh.mp3",
  "tags": [
   "transition",
   "swoosh",
   "dhadkan",
   "badlav"
  ],
  "license": "Pixabay"
 },
 "aarti_ganga": {
  "file": "ambience/aarti_ganga_small.mp3",
  "tags": [
   "aarti",
   "गंगा",
   "मंदिर",
   "mandir",
   "ceremony",
   "puja",
   "भजन"
  ],
  "license": "Pixabay"
 },
 "ambience_general": {
  "file": "ambience/ambience_general.mp3",
  "tags": [
   "ambience",
   "mahaul",
   "माहौल",
   "general"
  ],
  "license": "Pixabay"
 },
 "temple_ambient": {
  "file": "ambience/temple_ambient.mp3",
  "tags": [
   "temple",
   "मंदिर",
   "sacral",
   "puja",
   "goonj"
  ],
  "license": "Pixabay"
 },
 "christmas_magic": {
  "file": "ambience/christmas_magic.mp3",
  "tags": [
   "christmas",
   "magic",
   "जादू",
   "festival"
  ],
  "license": "Pixabay"
 },
 "holy_aura": {
  "file": "ambience/holy_aura.mp3",
  "tags": [
   "holy",
   "magic",
   "जादू",
   "energy",
   "chamak"
  ],
  "license": "Pixabay"
 },
 "angel_choir": {
  "file": "ambience/angel_choir.mp3",
  "tags": [
   "angel",
   "choir",
   "swarg",
   "स्वर्ग",
   "sacred"
  ],
  "license": "Pixabay"
 },
 "temple_bell": {
  "file": "ambience/temple_bell.mp3",
  "tags": [
   "bell",
   "घंटी",
   "temple",
   "मंदिर"
  ],
  "license": "Pixabay"
 },
 "church_ambience": {
  "file": "ambience/church_ambience.mp3",
  "tags": [
   "church",
   "गिरजा",
   "prayer",
   "ambience"
  ],
  "license": "Pixabay"
 },
 "shofar": {
  "file": "ambience/shofar.mp3",
  "tags": [
   "shofar",
   "horn",
   "सींग",
   "call"
  ],
  "license": "Pixabay"
 },
 "vampire_bite": {
  "file": "voices/vampire_bite.mp3",
  "tags": [
   "vampire",
   "bite",
   "kata",
   "काटा",
   "chudail"
  ],
  "license": "Pixabay"
 },
 "heal_spell": {
  "file": "ambience/heal_spell.mp3",
  "tags": [
   "heal",
   "magic",
   "जादू",
   "mystic",
   "forest"
  ],
  "license": "Pixabay"
 },
 "ghost_past_2": {
  "file": "ambience/ghost_past_2.mp3",
  "tags": [
   "ghost",
   "भूत",
   "past",
   "daravana"
  ],
  "license": "Pixabay"
 },
 "sacral_chant": {
  "file": "ambience/sacral_chant.mp3",
  "tags": [
   "chant",
   "mantra",
   "मंत्र",
   "sacral"
  ],
  "license": "Pixabay"
 },
 "spirit_gain": {
  "file": "ambience/spirit_gain.mp3",
  "tags": [
   "spirit",
   "aatma",
   "आत्मा",
   "gain"
  ],
  "license": "Pixabay"
 },
 "choir_short": {
  "file": "ambience/choir_short.mp3",
  "tags": [
   "choir",
   "swarg",
   "स्वर्ग",
   "angel"
  ],
  "license": "Pixabay"
 },
 "atmos_texture": {
  "file": "ambience/atmos_texture.mp3",
  "tags": [
   "atmos",
   "texture",
   "mahaul",
   "माहौल"
  ],
  "license": "Pixabay"
 },
 "holy_chorus": {
  "file": "ambience/holy_chorus.mp3",
  "tags": [
   "chorus",
   "holy",
   "prayer",
   "प्रार्थना"
  ],
  "license": "Pixabay"
 },
 "tanpura": {
  "file": "ambience/tanpura.mp3",
  "tags": [
   "tanpura",
   "indian",
   "सितार",
   "classical",
   "mandir"
  ],
  "license": "Pixabay"
 },
 "sound_of_god": {
  "file": "ambience/sound_of_god.mp3",
  "tags": [
   "god",
   "bhagwan",
   "भगवान",
   "divine"
  ],
  "license": "Pixabay"
 },
 "radio_quran": {
  "file": "ambience/radio_quran.mp3",
  "tags": [
   "quran",
   "radio",
   "azan",
   "masjid",
   "मस्जिद"
  ],
  "license": "Pixabay"
 },
 "monk_om": {
  "file": "ambience/monk_om.mp3",
  "tags": [
   "om",
   "monk",
   "sadhu",
   "ॐ",
   "chant",
   "mandir"
  ],
  "license": "Pixabay"
 },
 "incant": {
  "file": "ambience/incant.mp3",
  "tags": [
   "incant",
   "mantra",
   "जादू",
   "spell",
   "tantrik"
  ],
  "license": "Pixabay"
 },
 "ghosts_past": {
  "file": "ambience/ghosts_past.mp3",
  "tags": [
   "ghost",
   "भूत",
   "past",
   "yaad"
  ],
  "license": "Pixabay"
 },
 "light_magic": {
  "file": "ambience/light_magic.mp3",
  "tags": [
   "magic",
   "जादू",
   "light",
   "chamak"
  ],
  "license": "Pixabay"
 },
 "light_magic_2": {
  "file": "ambience/light_magic_2.mp3",
  "tags": [
   "magic",
   "जादू",
   "light"
  ],
  "license": "Pixabay"
 },
 "sacral_pad": {
  "file": "ambience/sacral_pad.mp3",
  "tags": [
   "sacral",
   "temple",
   "मंदिर",
   "pad"
  ],
  "license": "Pixabay"
 },
 "cathedral_organ": {
  "file": "ambience/cathedral_organ.mp3",
  "tags": [
   "organ",
   "church",
   "गिरजा"
  ],
  "license": "Pixabay"
 },
 "christmas_bells": {
  "file": "ambience/christmas_bells.mp3",
  "tags": [
   "christmas",
   "bells",
   "घंटी"
  ],
  "license": "Pixabay"
 },
 "psalm23": {
  "file": "ambience/psalm23.mp3",
  "tags": [
   "psalm",
   "prayer",
   "प्रार्थना"
  ],
  "license": "Pixabay"
 },
 "ramazan_drum": {
  "file": "ambience/ramazan_drum.mp3",
  "tags": [
   "ramazan",
   "drum",
   "dhol"
  ],
  "license": "Pixabay"
 },
 "jungle_nature": {
  "file": "nature/jungle_nature.mp3",
  "tags": [
   "jungle",
   "forest",
   "जंगल",
   "nature",
   "birds",
   "ambience"
  ],
  "license": "Pixabay"
 },
 "rain_on_glass": {
  "file": "ambience/rain_on_glass.mp3",
  "tags": [
   "rain",
   "baarish",
   "बारिश",
   "glass",
   "thunder"
  ],
  "license": "Pixabay"
 },
 "heal_spell_2": {
  "file": "ambience/heal_spell_2.mp3",
  "tags": [
   "heal",
   "magic",
   "जादू",
   "spell"
  ],
  "license": "Pixabay"
 },
 "water_relax": {
  "file": "ambience/water_relax.mp3",
  "tags": [
   "water",
   "paani",
   "पानी",
   "relax",
   "nadi"
  ],
  "license": "Pixabay"
 },
 "rune_seal": {
  "file": "ambience/rune_seal.mp3",
  "tags": [
   "rune",
   "magic",
   "जादू",
   "seal",
   "mantra"
  ],
  "license": "Pixabay"
 },
 "holy_magic_short": {
  "file": "ambience/holy_magic_short.mp3",
  "tags": [
   "holy",
   "magic",
   "जादू",
   "chamak"
  ],
  "license": "Pixabay"
 },
 "rain_gentle_1": {
  "file": "ambience/rain_gentle_1.mp3",
  "tags": [
   "rain",
   "baarish",
   "बारिश",
   "gentle",
   "halki"
  ],
  "license": "Pixabay"
 },
 "village_ambience": {
  "file": "ambience/village_ambience.mp3",
  "tags": [
   "village",
   "gaon",
   "गाँव",
   "ambience",
   "mahol"
  ],
  "license": "Pixabay"
 },
 "birds_in_rain": {
  "file": "ambience/birds_in_rain.mp3",
  "tags": [
   "birds",
   "chidiya",
   "चिड़िया",
   "rain"
  ],
  "license": "Pixabay"
 },
 "thunderstorm": {
  "file": "ambience/thunderstorm.mp3",
  "tags": [
   "thunder",
   "bijli",
   "बिजली",
   "storm",
   "toofan",
   "rain"
  ],
  "license": "Pixabay"
 },
 "rain_midday": {
  "file": "ambience/rain_midday.mp3",
  "tags": [
   "rain",
   "baarish",
   "बारिश",
   "dopahar"
  ],
  "license": "Pixabay"
 },
 "steps_frozen_grass": {
  "file": "footsteps/steps_frozen_grass.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "grass",
   "frozen",
   "bahar"
  ],
  "license": "Pixabay"
 },
 "steps_gravel": {
  "file": "footsteps/steps_gravel.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "gravel",
   "kankad",
   "रोड़ी"
  ],
  "license": "Pixabay"
 },
 "steps_stairs_up": {
  "file": "footsteps/steps_stairs_up.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "stairs",
   "seedhi",
   "सीढ़ी"
  ],
  "license": "Pixabay"
 },
 "steps_stairs_down": {
  "file": "footsteps/steps_stairs_down.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "stairs",
   "seedhi",
   "सीढ़ी",
   "wood"
  ],
  "license": "Pixabay"
 },
 "steps_grass_to_stairs": {
  "file": "footsteps/steps_grass_to_stairs.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "grass",
   "stairs"
  ],
  "license": "Pixabay"
 },
 "rain_tent": {
  "file": "ambience/rain_tent.mp3",
  "tags": [
   "rain",
   "baarish",
   "बारिश",
   "tent",
   "tambu"
  ],
  "license": "Pixabay"
 },
 "rain_tin_metal": {
  "file": "ambience/rain_tin_metal.mp3",
  "tags": [
   "rain",
   "baarish",
   "बारिश",
   "tin",
   "metal",
   "chhat"
  ],
  "license": "Pixabay"
 },
 "rain_window": {
  "file": "ambience/rain_window.mp3",
  "tags": [
   "rain",
   "baarish",
   "बारिश",
   "window",
   "khidki"
  ],
  "license": "Pixabay"
 },
 "rain_tin_roof": {
  "file": "ambience/rain_tin_roof.mp3",
  "tags": [
   "rain",
   "baarish",
   "बारिश",
   "tin",
   "roof",
   "chhat"
  ],
  "license": "Pixabay"
 },
 "rain_gentle_7": {
  "file": "ambience/rain_gentle_7.mp3",
  "tags": [
   "rain",
   "baarish",
   "बारिश",
   "gentle",
   "halki"
  ],
  "license": "Pixabay"
 },
 "steps_a": {
  "file": "footsteps/steps_a.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "walk"
  ],
  "license": "Pixabay"
 },
 "steps_b": {
  "file": "footsteps/steps_b.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "pasos"
  ],
  "license": "Pixabay"
 },
 "steps_c": {
  "file": "footsteps/steps_c.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम"
  ],
  "license": "Pixabay"
 },
 "steps_d": {
  "file": "footsteps/steps_d.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम"
  ],
  "license": "Pixabay"
 },
 "steps_shoe": {
  "file": "footsteps/steps_shoe.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "shoe",
   "joota",
   "जूता"
  ],
  "license": "Pixabay"
 },
 "steps_soil": {
  "file": "footsteps/steps_soil.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "soil",
   "mitti",
   "मिट्टी"
  ],
  "license": "Pixabay"
 },
 "steps_gravel_2": {
  "file": "footsteps/steps_gravel_2.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "gravel",
   "kankad"
  ],
  "license": "Pixabay"
 },
 "steps_forest_road": {
  "file": "footsteps/steps_forest_road.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "forest",
   "jangal",
   "जंगल"
  ],
  "license": "Pixabay"
 },
 "steps_puddle": {
  "file": "footsteps/steps_puddle.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "puddle",
   "paani",
   "पानी",
   "keechad"
  ],
  "license": "Pixabay"
 },
 "steps_muddy_road": {
  "file": "footsteps/steps_muddy_road.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "muddy",
   "keechad",
   "कीचड़"
  ],
  "license": "Pixabay"
 },
 "horse_neigh": {
  "file": "animals/horse_neigh.mp3",
  "tags": [
   "horse",
   "ghoda",
   "घोड़ा",
   "hihina",
   "neigh"
  ],
  "license": "Pixabay"
 },
 "horse_neigh_2": {
  "file": "animals/horse_neigh_2.mp3",
  "tags": [
   "horse",
   "ghoda",
   "घोड़ा",
   "neigh"
  ],
  "license": "Pixabay"
 },
 "horse_walk": {
  "file": "animals/horse_walk.mp3",
  "tags": [
   "horse",
   "ghoda",
   "घोड़ा",
   "walk",
   "chaal"
  ],
  "license": "Pixabay"
 },
 "horse_walk_2": {
  "file": "animals/horse_walk_2.mp3",
  "tags": [
   "horse",
   "ghoda",
   "घोड़ा",
   "walk"
  ],
  "license": "Pixabay"
 },
 "horse_hooves": {
  "file": "animals/horse_hooves.mp3",
  "tags": [
   "hooves",
   "khure",
   "खुर",
   "horse",
   "ghoda"
  ],
  "license": "Pixabay"
 },
 "horse_gallop": {
  "file": "animals/horse_gallop.mp3",
  "tags": [
   "gallop",
   "horse",
   "daud",
   "दौड़",
   "ghoda"
  ],
  "license": "Pixabay"
 },
 "horse_snort": {
  "file": "animals/horse_snort.mp3",
  "tags": [
   "snort",
   "horse",
   "ghoda",
   "saans"
  ],
  "license": "Pixabay"
 },
 "steps_muddy_road_2": {
  "file": "footsteps/steps_muddy_road_2.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "muddy",
   "puddle"
  ],
  "license": "Pixabay"
 },
 "steps_fine_gravel": {
  "file": "footsteps/steps_fine_gravel.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "gravel",
   "fine"
  ],
  "license": "Pixabay"
 },
 "steps_dirt": {
  "file": "footsteps/steps_dirt.mp3",
  "tags": [
   "steps",
   "kadam",
   "कदम",
   "dirt",
   "mitti",
   "मिट्टी"
  ],
  "license": "Pixabay"
 },
 "horse_steps_1": {
  "file": "animals/horse_steps_1.mp3",
  "tags": [
   "horse",
   "ghoda",
   "घोड़ा",
   "steps",
   "hooves"
  ],
  "license": "Pixabay"
 },
 "horse_walk_3": {
  "file": "animals/horse_walk_3.mp3",
  "tags": [
   "horse",
   "ghoda",
   "घोड़ा",
   "walk"
  ],
  "license": "Pixabay"
 },
 "horse_walk_4": {
  "file": "animals/horse_walk_4.mp3",
  "tags": [
   "horse",
   "ghoda",
   "घोड़ा",
   "walk"
  ],
  "license": "Pixabay"
 },
 "fire_crackle_1": {
  "file": "fire/fire_crackle_1.mp3",
  "tags": [
   "fire",
   "aag",
   "आग",
   "crackle",
   "jalna"
  ],
  "license": "Pixabay"
 },
 "fire_whoosh": {
  "file": "fire/fire_whoosh.mp3",
  "tags": [
   "fire",
   "aag",
   "आग",
   "whoosh",
   "winds"
  ],
  "license": "Pixabay"
 },
 "fireplace": {
  "file": "fire/fireplace.mp3",
  "tags": [
   "fire",
   "aag",
   "आग",
   "fireplace",
   "chulha",
   "alav"
  ],
  "license": "Pixabay"
 },
 "crackle_1": {
  "file": "fire/crackle_1.mp3",
  "tags": [
   "crackle",
   "chirchirahat",
   "aag"
  ],
  "license": "Pixabay"
 },
 "crackle_2": {
  "file": "fire/crackle_2.mp3",
  "tags": [
   "crackle",
   "chirchirahat",
   "aag"
  ],
  "license": "Pixabay"
 },
 "vinyl_crackle": {
  "file": "fire/vinyl_crackle.mp3",
  "tags": [
   "vinyl",
   "crackle",
   "purana",
   "radio",
   "record"
  ],
  "license": "Pixabay"
 },
 "vinyl_loop": {
  "file": "fire/vinyl_loop.mp3",
  "tags": [
   "vinyl",
   "loop",
   "purana",
   "radio"
  ],
  "license": "Pixabay"
 },
 "bubbles": {
  "file": "water/bubbles.mp3",
  "tags": [
   "bubbles",
   "bulbule",
   "paani",
   "पानी"
  ],
  "license": "Pixabay"
 },
 "lava_loop": {
  "file": "water/lava_loop.mp3",
  "tags": [
   "lava",
   "aag",
   "आग",
   "loop"
  ],
  "license": "Pixabay"
 },
 "pour_drink": {
  "file": "water/pour_drink.mp3",
  "tags": [
   "pour",
   "dalna",
   "drink",
   "paani"
  ],
  "license": "Pixabay"
 },
 "boiling": {
  "file": "water/boiling.mp3",
  "tags": [
   "boil",
   "ubalna",
   "उबलना",
   "paani"
  ],
  "license": "Pixabay"
 },
 "fizzy_pour": {
  "file": "water/fizzy_pour.mp3",
  "tags": [
   "fizzy",
   "cold drink",
   "soda",
   "pour"
  ],
  "license": "Pixabay"
 },
 "underwater": {
  "file": "water/underwater.mp3",
  "tags": [
   "underwater",
   "paani ke neeche",
   "डूब"
  ],
  "license": "Pixabay"
 },
 "tea_boil": {
  "file": "water/tea_boil.mp3",
  "tags": [
   "tea",
   "chai",
   "चाय",
   "boil"
  ],
  "license": "Pixabay"
 },
 "pour_glass": {
  "file": "water/pour_glass.mp3",
  "tags": [
   "pour",
   "glass",
   "गिलास",
   "paani"
  ],
  "license": "Pixabay"
 },
 "kettle_pour": {
  "file": "water/kettle_pour.mp3",
  "tags": [
   "kettle",
   "ketli",
   "केटली",
   "pour"
  ],
  "license": "Pixabay"
 },
 "kettle_cup": {
  "file": "water/kettle_cup.mp3",
  "tags": [
   "kettle",
   "cup",
   "chai",
   "pour"
  ],
  "license": "Pixabay"
 },
 "cooker_1": {
  "file": "kitchen/cooker_1.mp3",
  "tags": [
   "cooker",
   "कुकर",
   "pressure",
   "seeti",
   "सीटी"
  ],
  "license": "Pixabay"
 },
 "cooker_2": {
  "file": "kitchen/cooker_2.mp3",
  "tags": [
   "cooker",
   "कुकर",
   "pressure"
  ],
  "license": "Pixabay"
 },
 "cooker_release": {
  "file": "kitchen/cooker_release.mp3",
  "tags": [
   "cooker",
   "release",
   "bhaap",
   "भाप"
  ],
  "license": "Pixabay"
 },
 "cooker_low": {
  "file": "kitchen/cooker_low.mp3",
  "tags": [
   "cooker",
   "dheema",
   "low"
  ],
  "license": "Pixabay"
 },
 "cooker_whistle": {
  "file": "kitchen/cooker_whistle.mp3",
  "tags": [
   "cooker",
   "whistle",
   "सीटी",
   "seeti"
  ],
  "license": "Pixabay"
 },
 "bubbling_sauce": {
  "file": "kitchen/bubbling_sauce.mp3",
  "tags": [
   "bubble",
   "sauce",
   "tarkari",
   "सब्जी"
  ],
  "license": "Pixabay"
 },
 "boil_2": {
  "file": "kitchen/boil_2.mp3",
  "tags": [
   "boil",
   "ubalna",
   "उबलना"
  ],
  "license": "Pixabay"
 },
 "boil_3": {
  "file": "kitchen/boil_3.mp3",
  "tags": [
   "boil",
   "ubalna",
   "उबलना"
  ],
  "license": "Pixabay"
 },
 "heavy_bubbles": {
  "file": "kitchen/heavy_bubbles.mp3",
  "tags": [
   "bubbles",
   "bulbule",
   "गाढ़ा"
  ],
  "license": "Pixabay"
 },
 "boil_long": {
  "file": "kitchen/boil_long.mp3",
  "tags": [
   "boil",
   "loop",
   "ubalna"
  ],
  "license": "Pixabay"
 },
 "paper_1": {
  "file": "foley/paper_1.mp3",
  "tags": [
   "paper",
   "kagaz",
   "कागज़",
   "chitthi",
   "पन्ने"
  ],
  "license": "Pixabay"
 },
 "paper_2": {
  "file": "foley/paper_2.mp3",
  "tags": [
   "paper",
   "kagaz",
   "कागज़"
  ],
  "license": "Pixabay"
 },
 "paper_rip_2": {
  "file": "foley/paper_rip_2.mp3",
  "tags": [
   "paper",
   "rip",
   "fatna",
   "फटना"
  ],
  "license": "Pixabay"
 },
 "paper_rip_fast": {
  "file": "foley/paper_rip_fast.mp3",
  "tags": [
   "paper",
   "rip",
   "fatna",
   "tez"
  ],
  "license": "Pixabay"
 },
 "paper_slide": {
  "file": "foley/paper_slide.mp3",
  "tags": [
   "paper",
   "slide",
   "khisakna"
  ],
  "license": "Pixabay"
 },
 "paper_riser": {
  "file": "foley/paper_riser.mp3",
  "tags": [
   "paper",
   "riser",
   "tension"
  ],
  "license": "Pixabay"
 },
 "paper_turn": {
  "file": "foley/paper_turn.mp3",
  "tags": [
   "paper",
   "turn",
   "palatna",
   "kitab"
  ],
  "license": "Pixabay"
 },
 "paper_tear": {
  "file": "foley/paper_tear.mp3",
  "tags": [
   "paper",
   "tear",
   "phadna",
   "फाड़ना"
  ],
  "license": "Pixabay"
 },
 "paper_cut": {
  "file": "foley/paper_cut.mp3",
  "tags": [
   "paper",
   "cut",
   "katna",
   "काटना"
  ],
  "license": "Pixabay"
 },
 "paper_flutter": {
  "file": "foley/paper_flutter.mp3",
  "tags": [
   "paper",
   "flutter",
   "hawa",
   "udna"
  ],
  "license": "Pixabay"
 },
 "dhol_1": {
  "file": "music/dhol_1.mp3",
  "tags": [
   "dhol",
   "ढोल",
   "drum",
   "shaadi",
   "tyohar"
  ],
  "license": "Pixabay"
 },
 "dhol_shadi": {
  "file": "music/dhol_shadi.mp3",
  "tags": [
   "dhol",
   "shaadi",
   "शादी",
   "baraat"
  ],
  "license": "Pixabay"
 },
 "dhol_bass": {
  "file": "music/dhol_bass.mp3",
  "tags": [
   "dhol",
   "bass",
   "ढोल"
  ],
  "license": "Pixabay"
 },
 "dhol_wedding": {
  "file": "music/dhol_wedding.mp3",
  "tags": [
   "dhol",
   "wedding",
   "shaadi",
   "baraat"
  ],
  "license": "Pixabay"
 },
 "indian_beats_1": {
  "file": "music/indian_beats_1.mp3",
  "tags": [
   "beats",
   "indian",
   "music",
   "dholak"
  ],
  "license": "Pixabay"
 },
 "indian_beats_5": {
  "file": "music/indian_beats_5.mp3",
  "tags": [
   "beats",
   "indian",
   "music",
   "dholak"
  ],
  "license": "Pixabay"
 },
 "mehndi_beat": {
  "file": "music/mehndi_beat.mp3",
  "tags": [
   "mehndi",
   "shaadi",
   "beat",
   "music"
  ],
  "license": "Pixabay"
 },
 "indian_drum_loop": {
  "file": "music/indian_drum_loop.mp3",
  "tags": [
   "drum",
   "loop",
   "indian",
   "dholak"
  ],
  "license": "Pixabay"
 },
 "paper_handling": {
  "file": "foley/paper_handling.mp3",
  "tags": [
   "paper",
   "kagaz",
   "कागज़",
   "page",
   "turn"
  ],
  "license": "Pixabay"
 },
 "paper_crumple": {
  "file": "foley/paper_crumple.mp3",
  "tags": [
   "paper",
   "crumple",
   "kuchalna",
   "कागज़"
  ],
  "license": "Pixabay"
 },
 "dhol_2": {
  "file": "music/dhol_2.mp3",
  "tags": [
   "dhol",
   "ढोल",
   "drum"
  ],
  "license": "Pixabay"
 },
 "dhol_beats": {
  "file": "music/dhol_beats.mp3",
  "tags": [
   "dhol",
   "beats",
   "ढोल",
   "shaadi"
  ],
  "license": "Pixabay"
 },
 "ding_backwards": {
  "file": "bells/ding_backwards.mp3",
  "tags": [
   "ding",
   "bell",
   "reverse",
   "daravana"
  ],
  "license": "Pixabay"
 },
 "clock_bell_1": {
  "file": "bells/clock_bell_1.mp3",
  "tags": [
   "clock",
   "bell",
   "घड़ी",
   "ghanti"
  ],
  "license": "Pixabay"
 },
 "bell_chime": {
  "file": "bells/bell_chime.mp3",
  "tags": [
   "bell",
   "chime",
   "घंटी",
   "mandir"
  ],
  "license": "Pixabay"
 },
 "clock_twelve": {
  "file": "bells/clock_twelve.mp3",
  "tags": [
   "clock",
   "twelve",
   "12",
   "घड़ी",
   "raat"
  ],
  "license": "Pixabay"
 },
 "clock_tower_12": {
  "file": "bells/clock_tower_12.mp3",
  "tags": [
   "clock",
   "tower",
   "12",
   "ghanta"
  ],
  "license": "Pixabay"
 },
 "westminster_hour": {
  "file": "bells/westminster_hour.mp3",
  "tags": [
   "clock",
   "hour",
   "bell",
   "ghanta"
  ],
  "license": "Pixabay"
 },
 "clock_11pm_rain": {
  "file": "bells/clock_11pm_rain.mp3",
  "tags": [
   "clock",
   "rain",
   "raat",
   "11"
  ],
  "license": "Pixabay"
 },
 "bells_saw": {
  "file": "bells/bells_saw.mp3",
  "tags": [
   "bell",
   "saw",
   "scream",
   "daravana"
  ],
  "license": "Pixabay"
 },
 "grandfather_12": {
  "file": "bells/grandfather_12.mp3",
  "tags": [
   "clock",
   "grandfather",
   "12",
   "घड़ी",
   "chime"
  ],
  "license": "Pixabay"
 },
 "grandfather_half": {
  "file": "bells/grandfather_half.mp3",
  "tags": [
   "clock",
   "half",
   "घड़ी",
   "chime"
  ],
  "license": "Pixabay"
 },
 "old_clock_chime": {
  "file": "bells/old_clock_chime.mp3",
  "tags": [
   "clock",
   "old",
   "purani",
   "घड़ी"
  ],
  "license": "Pixabay"
 },
 "tower_westminster_2": {
  "file": "bells/tower_westminster_2.mp3",
  "tags": [
   "clock",
   "tower",
   "westminster"
  ],
  "license": "Pixabay"
 },
 "clock_bell_chime": {
  "file": "bells/clock_bell_chime.mp3",
  "tags": [
   "clock",
   "bell",
   "घंटी"
  ],
  "license": "Pixabay"
 },
 "timer_chime": {
  "file": "bells/timer_chime.mp3",
  "tags": [
   "timer",
   "chime",
   "alarm"
  ],
  "license": "Pixabay"
 },
 "clock_chime_short": {
  "file": "bells/clock_chime_short.mp3",
  "tags": [
   "clock",
   "chime",
   "छोटा"
  ],
  "license": "Pixabay"
 },
 "cuckoo_clock": {
  "file": "bells/cuckoo_clock.mp3",
  "tags": [
   "cuckoo",
   "clock",
   "koel",
   "घड़ी"
  ],
  "license": "Pixabay"
 },
 "bell_music": {
  "file": "bells/bell_music.mp3",
  "tags": [
   "bell",
   "music",
   "घंटी",
   "sacred"
  ],
  "license": "Pixabay"
 },
 "door_pounding": {
  "file": "door/door_pounding.mp3",
  "tags": [
   "door",
   "pounding",
   "khatkhatana",
   "दरवाज़ा",
   "थाप"
  ],
  "license": "Pixabay"
 },
 "knock_1": {
  "file": "door/knock_1.mp3",
  "tags": [
   "knock",
   "khatkhatana",
   "दरवाज़ा",
   "थाप"
  ],
  "license": "Pixabay"
 },
 "knock_2": {
  "file": "door/knock_2.mp3",
  "tags": [
   "knock",
   "khatkhatana",
   "दरवाज़ा"
  ],
  "license": "Pixabay"
 },
 "knock_3": {
  "file": "door/knock_3.mp3",
  "tags": [
   "knock",
   "दरवाज़ा",
   "थाप"
  ],
  "license": "Pixabay"
 },
 "knock_4": {
  "file": "door/knock_4.mp3",
  "tags": [
   "knock",
   "दरवाज़ा",
   "थाप"
  ],
  "license": "Pixabay"
 },
 "knock_5": {
  "file": "door/knock_5.mp3",
  "tags": [
   "knock",
   "दरवाज़ा"
  ],
  "license": "Pixabay"
 },
 "knock_6": {
  "file": "door/knock_6.mp3",
  "tags": [
   "knock",
   "दरवाज़ा"
  ],
  "license": "Pixabay"
 },
 "knock_fast": {
  "file": "door/knock_fast.mp3",
  "tags": [
   "knock",
   "fast",
   "तेज़",
   "जल्दी"
  ],
  "license": "Pixabay"
 },
 "knock_intense": {
  "file": "door/knock_intense.mp3",
  "tags": [
   "knock",
   "intense",
   "zor",
   "गुस्सा"
  ],
  "license": "Pixabay"
 },
 "door_bang_echo": {
  "file": "door/door_bang_echo.mp3",
  "tags": [
   "door",
   "bang",
   "echo",
   "धम्म",
   "goonj"
  ],
  "license": "Pixabay"
 },
 "door_generic": {
  "file": "door/door_generic.mp3",
  "tags": [
   "door",
   "दरवाज़ा",
   "general"
  ],
  "license": "Pixabay"
 },
 "dog_bark_1": {
  "file": "animals/dog_bark_1.mp3",
  "tags": [
   "dog",
   "kutta",
   "कुत्ता",
   "bark",
   "bhaunkna"
  ],
  "license": "Pixabay"
 },
 "dog_bark_2": {
  "file": "animals/dog_bark_2.mp3",
  "tags": [
   "dog",
   "kutta",
   "कुत्ता",
   "bark"
  ],
  "license": "Pixabay"
 },
 "dog_bark_3": {
  "file": "animals/dog_bark_3.mp3",
  "tags": [
   "dog",
   "kutta",
   "कुत्ता",
   "bark"
  ],
  "license": "Pixabay"
 },
 "dog_bark_4": {
  "file": "animals/dog_bark_4.mp3",
  "tags": [
   "dog",
   "kutta",
   "कुत्ता",
   "bark"
  ],
  "license": "Pixabay"
 },
 "dog_bark_small": {
  "file": "animals/dog_bark_small.mp3",
  "tags": [
   "dog",
   "kutta",
   "puppy",
   "bark"
  ],
  "license": "Pixabay"
 },
 "dogs_howl": {
  "file": "animals/dogs_howl.mp3",
  "tags": [
   "dogs",
   "howl",
   "kutta",
   "रोना",
   "raat"
  ],
  "license": "Pixabay"
 },
 "dog_variety": {
  "file": "animals/dog_variety.mp3",
  "tags": [
   "dog",
   "kutta",
   "bark",
   "yelp",
   "breath"
  ],
  "license": "Pixabay"
 },
 "knock_7": {
  "file": "door/knock_7.mp3",
  "tags": [
   "knock",
   "दरवाज़ा",
   "थाप"
  ],
  "license": "Pixabay"
 },
 "knock_8": {
  "file": "door/knock_8.mp3",
  "tags": [
   "knock",
   "दरवाज़ा",
   "थाप"
  ],
  "license": "Pixabay"
 },
 "knock_9": {
  "file": "door/knock_9.mp3",
  "tags": [
   "knock",
   "दरवाज़ा",
   "थाप"
  ],
  "license": "Pixabay"
 },
 "dog_bark_5": {
  "file": "animals/dog_bark_5.mp3",
  "tags": [
   "dog",
   "kutta",
   "कुत्ता",
   "bark"
  ],
  "license": "Pixabay"
 },
 "dog_bark_6": {
  "file": "animals/dog_bark_6.mp3",
  "tags": [
   "dog",
   "kutta",
   "कुत्ता",
   "bark"
  ],
  "license": "Pixabay"
 },
 "dog_bark_7": {
  "file": "animals/dog_bark_7.mp3",
  "tags": [
   "dog",
   "kutta",
   "कुत्ता",
   "bark"
  ],
  "license": "Pixabay"
 },
 "dog_bark_8": {
  "file": "animals/dog_bark_8.mp3",
  "tags": [
   "dog",
   "kutta",
   "कुत्ता",
   "bark"
  ],
  "license": "Pixabay"
 },
 "dog_barking_long": {
  "file": "animals/dog_barking_long.mp3",
  "tags": [
   "dog",
   "kutta",
   "barking",
   "long"
  ],
  "license": "Pixabay"
 },
 "breakup_theme": {
  "file": "music/breakup_theme.mp3",
  "tags": [
   "music",
   "breakup",
   "sad",
   "dukh",
   "रोना"
  ],
  "license": "Pixabay"
 },
 "romantic_guitar": {
  "file": "music/romantic_guitar.mp3",
  "tags": [
   "music",
   "romantic",
   "pyaar",
   "प्यार",
   "guitar"
  ],
  "license": "Pixabay"
 },
 "happy_folk": {
  "file": "music/happy_folk.mp3",
  "tags": [
   "music",
   "happy",
   "khushi",
   "folk",
   "gaon"
  ],
  "license": "Pixabay"
 },
 "piano_logo": {
  "file": "music/piano_logo.mp3",
  "tags": [
   "music",
   "piano",
   "logo",
   "intro"
  ],
  "license": "Pixabay"
 },
 "man_death_2": {
  "file": "voices/man_death_2.mp3",
  "tags": [
   "scream",
   "death",
   "maut",
   "चीख"
  ],
  "license": "Pixabay"
 },
 "heartbeat_1": {
  "file": "voices/heartbeat_1.mp3",
  "tags": [
   "heartbeat",
   "dhadkan",
   "धड़कन",
   "dar"
  ],
  "license": "Pixabay"
 },
 "kiss_1": {
  "file": "voices/kiss_1.mp3",
  "tags": [
   "kiss",
   "chumma",
   "चुम्मा",
   "pyaar"
  ],
  "license": "Pixabay"
 },
 "kiss_2": {
  "file": "voices/kiss_2.mp3",
  "tags": [
   "kiss",
   "chumma",
   "pyaar"
  ],
  "license": "Pixabay"
 },
 "smoke_breath": {
  "file": "voices/smoke_breath.mp3",
  "tags": [
   "smoke",
   "saans",
   "सिगरेट",
   "breath"
  ],
  "license": "Pixabay"
 },
 "station_ambience": {
  "file": "vehicles/station_ambience.mp3",
  "tags": [
   "station",
   "रेलवे",
   "train",
   "bheed",
   "ambience"
  ],
  "license": "Pixabay"
 },
 "train_horn_1": {
  "file": "vehicles/train_horn_1.mp3",
  "tags": [
   "train",
   "horn",
   "रेलगाड़ी",
   "सीटी"
  ],
  "license": "Pixabay"
 },
 "train_horn_2": {
  "file": "vehicles/train_horn_2.mp3",
  "tags": [
   "train",
   "horn",
   "tuktuk"
  ],
  "license": "Pixabay"
 },
 "train_signal": {
  "file": "vehicles/train_signal.mp3",
  "tags": [
   "train",
   "signal",
   "रेल"
  ],
  "license": "Pixabay"
 },
 "train_pass_1": {
  "file": "vehicles/train_pass_1.mp3",
  "tags": [
   "train",
   "pass",
   "guzarna"
  ],
  "license": "Pixabay"
 },
 "train_running": {
  "file": "vehicles/train_running.mp3",
  "tags": [
   "train",
   "running",
   "chalti"
  ],
  "license": "Pixabay"
 },
 "toy_train": {
  "file": "vehicles/toy_train.mp3",
  "tags": [
   "toy",
   "train",
   "whistle",
   "bachche"
  ],
  "license": "Pixabay"
 },
 "horn_1": {
  "file": "vehicles/horn_1.mp3",
  "tags": [
   "horn",
   "car",
   "गाड़ी",
   "सड़क"
  ],
  "license": "Pixabay"
 },
 "drum_sehnai": {
  "file": "music/drum_sehnai.mp3",
  "tags": [
   "sehnai",
   "shaadi",
   "शादी",
   "dhol",
   "khushi"
  ],
  "license": "Pixabay"
 },
 "intro_1": {
  "file": "music/intro_1.mp3",
  "tags": [
   "intro",
   "music",
   "shuruaat"
  ],
  "license": "Pixabay"
 },
 "train_horn_3": {
  "file": "vehicles/train_horn_3.mp3",
  "tags": [
   "train",
   "horn",
   "सीटी"
  ],
  "license": "Pixabay"
 },
 "train_approaching": {
  "file": "vehicles/train_approaching.mp3",
  "tags": [
   "train",
   "approaching",
   "aa rahi"
  ],
  "license": "Pixabay"
 },
 "train_crossing": {
  "file": "vehicles/train_crossing.mp3",
  "tags": [
   "train",
   "crossing",
   "fatak",
   "level"
  ],
  "license": "Pixabay"
 },
 "train_pass_2": {
  "file": "vehicles/train_pass_2.mp3",
  "tags": [
   "train",
   "pass",
   "guzarna"
  ],
  "license": "Pixabay"
 },
 "train_pass_3": {
  "file": "vehicles/train_pass_3.mp3",
  "tags": [
   "train",
   "pass",
   "guzarna"
  ],
  "license": "Pixabay"
 },
 "airchime": {
  "file": "vehicles/airchime.mp3",
  "tags": [
   "airchime",
   "horn",
   "train",
   "station"
  ],
  "license": "Pixabay"
 },
 "train_distant_birds": {
  "file": "vehicles/train_distant_birds.mp3",
  "tags": [
   "train",
   "distant",
   "door",
   "birds",
   "ambience"
  ],
  "license": "Pixabay"
 },
 "train_horn_4": {
  "file": "vehicles/train_horn_4.mp3",
  "tags": [
   "train",
   "horn",
   "diesel"
  ],
  "license": "Pixabay"
 },
 "train_horn_distant": {
  "file": "vehicles/train_horn_distant.mp3",
  "tags": [
   "train",
   "horn",
   "door",
   "distant"
  ],
  "license": "Pixabay"
 },
 "train_departure": {
  "file": "vehicles/train_departure.mp3",
  "tags": [
   "train",
   "departure",
   "chalna",
   "station"
  ],
  "license": "Pixabay"
 },
 "train_passing_cars": {
  "file": "vehicles/train_passing_cars.mp3",
  "tags": [
   "train",
   "passing",
   "cars",
   "gadi"
  ],
  "license": "Pixabay"
 },
 "train_horn_lofi": {
  "file": "vehicles/train_horn_lofi.mp3",
  "tags": [
   "train",
   "horn",
   "lofi",
   "purana"
  ],
  "license": "Pixabay"
 },
 "train_loud": {
  "file": "vehicles/train_loud.mp3",
  "tags": [
   "train",
   "loud",
   "tez",
   "zor"
  ],
  "license": "Pixabay"
 },
 "train_rural_india": {
  "file": "vehicles/train_rural_india.mp3",
  "tags": [
   "train",
   "india",
   "gaon",
   "rural",
   "coach"
  ],
  "license": "Pixabay"
 },
 "train_horn_comical": {
  "file": "vehicles/train_horn_comical.mp3",
  "tags": [
   "train",
   "horn",
   "comedy",
   "mazak"
  ],
  "license": "Pixabay"
 },
 "steam_train": {
  "file": "vehicles/steam_train.mp3",
  "tags": [
   "steam",
   "train",
   "purani",
   "seeti",
   "भाप"
  ],
  "license": "Pixabay"
 },
 "train_horn_5": {
  "file": "vehicles/train_horn_5.mp3",
  "tags": [
   "train",
   "horn",
   "सीटी"
  ],
  "license": "Pixabay"
 },
 "train_musical": {
  "file": "vehicles/train_musical.mp3",
  "tags": [
   "train",
   "musical",
   "melody"
  ],
  "license": "Pixabay"
 },
 "diesel_horn": {
  "file": "vehicles/diesel_horn.mp3",
  "tags": [
   "diesel",
   "horn",
   "truck",
   "gaadi"
  ],
  "license": "Pixabay"
 },
 "train_horn_pass_distant": {
  "file": "vehicles/train_horn_pass_distant.mp3",
  "tags": [
   "train",
   "horn",
   "distant",
   "pass"
  ],
  "license": "Pixabay"
 },
 "train_horn_passing": {
  "file": "vehicles/train_horn_passing.mp3",
  "tags": [
   "train",
   "horn",
   "passing"
  ],
  "license": "Pixabay"
 },
 "train_horn_asia": {
  "file": "vehicles/train_horn_asia.mp3",
  "tags": [
   "train",
   "horn",
   "asia",
   "india"
  ],
  "license": "Pixabay"
 },
 "train_horn_lofi_2": {
  "file": "vehicles/train_horn_lofi_2.mp3",
  "tags": [
   "train",
   "horn",
   "lofi",
   "purana"
  ],
  "license": "Pixabay"
 },
 "train_horn_6": {
  "file": "vehicles/train_horn_6.mp3",
  "tags": [
   "train",
   "horn",
   "सीटी"
  ],
  "license": "Pixabay"
 },
 "steam_train_2": {
  "file": "vehicles/steam_train_2.mp3",
  "tags": [
   "steam",
   "train",
   "purani",
   "भाप"
  ],
  "license": "Pixabay"
 },
 "train_horn_blast": {
  "file": "vehicles/train_horn_blast.mp3",
  "tags": [
   "train",
   "horn",
   "blast",
   "flyby",
   "zor"
  ],
  "license": "Pixabay"
 },
 "grinder_axe": {
  "file": "machines/grinder_axe.mp3",
  "tags": [
   "grinder",
   "machine",
   "axe",
   "kharad"
  ],
  "license": "Pixabay"
 },
 "grinder_start": {
  "file": "machines/grinder_start.mp3",
  "tags": [
   "grinder",
   "machine",
   "start"
  ],
  "license": "Pixabay"
 },
 "mixer_beater": {
  "file": "machines/mixer_beater.mp3",
  "tags": [
   "mixer",
   "beater",
   "machine",
   "rasoi"
  ],
  "license": "Pixabay"
 },
 "coffee_grinder": {
  "file": "machines/coffee_grinder.mp3",
  "tags": [
   "grinder",
   "coffee",
   "machine"
  ],
  "license": "Pixabay"
 },
 "horrible_sound": {
  "file": "horror/horrible_sound.mp3",
  "tags": [
   "horror",
   "daravana",
   "bura",
   "डर"
  ],
  "license": "Pixabay"
 },
 "vinyl_dj_pause": {
  "file": "horror/vinyl_dj_pause.mp3",
  "tags": [
   "vinyl",
   "dj",
   "pause",
   "purana"
  ],
  "license": "Pixabay"
 },
 "train_horn_fade": {
  "file": "vehicles/train_horn_fade.mp3",
  "tags": [
   "train",
   "horn",
   "fade"
  ],
  "license": "Pixabay"
 },
 "train_horn_horror": {
  "file": "vehicles/train_horn_horror.mp3",
  "tags": [
   "train",
   "horn",
   "horror",
   "dar"
  ],
  "license": "Pixabay"
 },
 "train_horn_7": {
  "file": "vehicles/train_horn_7.mp3",
  "tags": [
   "train",
   "horn",
   "सीटी"
  ],
  "license": "Pixabay"
 },
 "train_horn_8": {
  "file": "vehicles/train_horn_8.mp3",
  "tags": [
   "train",
   "horn",
   "loud",
   "zor"
  ],
  "license": "Pixabay"
 },
 "vinyl_scratch": {
  "file": "machines/vinyl_scratch.mp3",
  "tags": [
   "vinyl",
   "scratch",
   "dj",
   "purana"
  ],
  "license": "Pixabay"
 },
 "food_mixer": {
  "file": "machines/food_mixer.mp3",
  "tags": [
   "mixer",
   "food",
   "rasoi",
   "grinder"
  ],
  "license": "Pixabay"
 },
 "mixer_2": {
  "file": "machines/mixer_2.mp3",
  "tags": [
   "mixer",
   "machine"
  ],
  "license": "Pixabay"
 },
 "coffee_machine": {
  "file": "machines/coffee_machine.mp3",
  "tags": [
   "coffee",
   "machine",
   "nespresso"
  ],
  "license": "Pixabay"
 },
 "coffee_grinder_2": {
  "file": "machines/coffee_grinder_2.mp3",
  "tags": [
   "coffee",
   "grinder"
  ],
  "license": "Pixabay"
 },
 "coffee_grinder_3": {
  "file": "machines/coffee_grinder_3.mp3",
  "tags": [
   "coffee",
   "grinder"
  ],
  "license": "Pixabay"
 },
 "coffee_grinder_4": {
  "file": "machines/coffee_grinder_4.mp3",
  "tags": [
   "coffee",
   "grinder"
  ],
  "license": "Pixabay"
 },
 "coffee_stir": {
  "file": "machines/coffee_stir.mp3",
  "tags": [
   "coffee",
   "stir",
   "chammach",
   "cup"
  ],
  "license": "Pixabay"
 },
 "concrete_mixer": {
  "file": "machines/concrete_mixer.mp3",
  "tags": [
   "concrete",
   "mixer",
   "construction",
   "building"
  ],
  "license": "Pixabay"
 },
 "metal_scrape": {
  "file": "machines/metal_scrape.mp3",
  "tags": [
   "metal",
   "scrape",
   "khurachna",
   "loha"
  ],
  "license": "Pixabay"
 },
 "blender_1": {
  "file": "machines/blender_1.mp3",
  "tags": [
   "blender",
   "mixer",
   "juicer",
   "rasoi"
  ],
  "license": "Pixabay"
 },
 "blender_2": {
  "file": "machines/blender_2.mp3",
  "tags": [
   "blender",
   "mixer",
   "juicer"
  ],
  "license": "Pixabay"
 },
 "blender_3": {
  "file": "machines/blender_3.mp3",
  "tags": [
   "blender",
   "mixer"
  ],
  "license": "Pixabay"
 },
 "blender_4": {
  "file": "machines/blender_4.mp3",
  "tags": [
   "blender",
   "mixer"
  ],
  "license": "Pixabay"
 },
 "mixer_inside": {
  "file": "machines/mixer_inside.mp3",
  "tags": [
   "mixer",
   "inside",
   "machine"
  ],
  "license": "Pixabay"
 },
 "coffee_grinder_5": {
  "file": "machines/coffee_grinder_5.mp3",
  "tags": [
   "coffee",
   "grinder",
   "electric"
  ],
  "license": "Pixabay"
 },
 "dragon_roar": {
  "file": "animals/dragon_roar.mp3",
  "tags": [
   "dragon",
   "roar",
   "dahad",
   "ड्रैगन"
  ],
  "license": "Pixabay"
 },
 "dinosaur_roar": {
  "file": "animals/dinosaur_roar.mp3",
  "tags": [
   "dinosaur",
   "roar",
   "dahad"
  ],
  "license": "Pixabay"
 },
 "alien_roar": {
  "file": "animals/alien_roar.mp3",
  "tags": [
   "alien",
   "spaceship",
   "roar",
   "एलियन"
  ],
  "license": "Pixabay"
 },
 "dragon_growl": {
  "file": "animals/dragon_growl.mp3",
  "tags": [
   "dragon",
   "growl",
   "tiger",
   "elephant",
   "गुर्राना"
  ],
  "license": "Pixabay"
 },
 "tiger_roar_1": {
  "file": "animals/tiger_roar_1.mp3",
  "tags": [
   "tiger",
   "sher",
   "शेर",
   "roar",
   "dahad"
  ],
  "license": "Pixabay"
 },
 "tiger_roar_2": {
  "file": "animals/tiger_roar_2.mp3",
  "tags": [
   "tiger",
   "sher",
   "roar"
  ],
  "license": "Pixabay"
 },
 "tiger_roar_3": {
  "file": "animals/tiger_roar_3.mp3",
  "tags": [
   "tiger",
   "sher",
   "roar"
  ],
  "license": "Pixabay"
 },
 "tiger_roar_4": {
  "file": "animals/tiger_roar_4.mp3",
  "tags": [
   "tiger",
   "monster",
   "roar"
  ],
  "license": "Pixabay"
 },
 "monster_roar_1": {
  "file": "animals/monster_roar_1.mp3",
  "tags": [
   "monster",
   "rakshas",
   "राक्षस",
   "roar"
  ],
  "license": "Pixabay"
 },
 "monster_roar_2": {
  "file": "animals/monster_roar_2.mp3",
  "tags": [
   "monster",
   "warrior",
   "roar"
  ],
  "license": "Pixabay"
 },
 "monster_roar_3": {
  "file": "animals/monster_roar_3.mp3",
  "tags": [
   "monster",
   "beast",
   "roar",
   "attack"
  ],
  "license": "Pixabay"
 },
 "monster_growl_1": {
  "file": "animals/monster_growl_1.mp3",
  "tags": [
   "monster",
   "growl",
   "गुर्राना"
  ],
  "license": "Pixabay"
 },
 "roar_1": {
  "file": "animals/roar_1.mp3",
  "tags": [
   "roar",
   "dahad",
   "डर"
  ],
  "license": "Pixabay"
 },
 "wolf_growl": {
  "file": "animals/wolf_growl.mp3",
  "tags": [
   "wolf",
   "bhediya",
   "भेड़िया",
   "growl"
  ],
  "license": "Pixabay"
 },
 "tiger_attack": {
  "file": "animals/tiger_attack.mp3",
  "tags": [
   "tiger",
   "attack",
   "hamla",
   "शेर"
  ],
  "license": "Pixabay"
 },
 "tiger_roar_5": {
  "file": "animals/tiger_roar_5.mp3",
  "tags": [
   "tiger",
   "roar",
   "loud"
  ],
  "license": "Pixabay"
 },
 "tiger_roar_6": {
  "file": "animals/tiger_roar_6.mp3",
  "tags": [
   "tiger",
   "roar"
  ],
  "license": "Pixabay"
 },
 "tiger_roar_light": {
  "file": "animals/tiger_roar_light.mp3",
  "tags": [
   "tiger",
   "roar",
   "halka"
  ],
  "license": "Pixabay"
 },
 "big_cats_mix": {
  "file": "animals/big_cats_mix.mp3",
  "tags": [
   "tiger",
   "lion",
   "leopard",
   "werewolf",
   "roar"
  ],
  "license": "Pixabay"
 },
 "cat_meow_1": {
  "file": "animals/cat_meow_1.mp3",
  "tags": [
   "cat",
   "billi",
   "बिल्ली",
   "meow",
   "myau"
  ],
  "license": "Pixabay"
 },
 "cat_meow_2": {
  "file": "animals/cat_meow_2.mp3",
  "tags": [
   "cat",
   "billi",
   "meow"
  ],
  "license": "Pixabay"
 },
 "cat_meow_3": {
  "file": "animals/cat_meow_3.mp3",
  "tags": [
   "cat",
   "billi",
   "meow"
  ],
  "license": "Pixabay"
 },
 "cat_meow_4": {
  "file": "animals/cat_meow_4.mp3",
  "tags": [
   "cat",
   "billi",
   "meow"
  ],
  "license": "Pixabay"
 },
 "cat_meow_5": {
  "file": "animals/cat_meow_5.mp3",
  "tags": [
   "cat",
   "billi",
   "meow"
  ],
  "license": "Pixabay"
 },
 "cat_meow_6": {
  "file": "animals/cat_meow_6.mp3",
  "tags": [
   "cat",
   "billi",
   "बिल्ली",
   "meow",
   "myau"
  ],
  "license": "Pixabay"
 },
 "cat_meow_7": {
  "file": "animals/cat_meow_7.mp3",
  "tags": [
   "cat",
   "billi",
   "बिल्ली",
   "meow",
   "myau"
  ],
  "license": "Pixabay"
 },
 "cat_meow_8": {
  "file": "animals/cat_meow_8.mp3",
  "tags": [
   "cat",
   "billi",
   "बिल्ली",
   "meow",
   "myau"
  ],
  "license": "Pixabay"
 },
 "cat_meow_9": {
  "file": "animals/cat_meow_9.mp3",
  "tags": [
   "cat",
   "billi",
   "बिल्ली",
   "meow",
   "myau"
  ],
  "license": "Pixabay"
 },
 "cat_meow_10": {
  "file": "animals/cat_meow_10.mp3",
  "tags": [
   "cat",
   "billi",
   "बिल्ली",
   "meow",
   "myau"
  ],
  "license": "Pixabay"
 },
 "chick_1": {
  "file": "voices/chick_1.mp3",
  "tags": [
   "chick",
   "chidiya",
   "चूजा",
   "bird"
  ],
  "license": "Pixabay"
 },
 "baby_moan": {
  "file": "voices/baby_moan.mp3",
  "tags": [
   "baby",
   "bachcha",
   "moan",
   "rona"
  ],
  "license": "Pixabay"
 },
 "baby_laugh_1": {
  "file": "voices/baby_laugh_1.mp3",
  "tags": [
   "baby",
   "bachcha",
   "laugh",
   "hansi",
   "khushi"
  ],
  "license": "Pixabay"
 },
 "baby_babble": {
  "file": "voices/baby_babble.mp3",
  "tags": [
   "baby",
   "babble",
   "bachcha",
   "gugu"
  ],
  "license": "Pixabay"
 },
 "baby_cry_1": {
  "file": "voices/baby_cry_1.mp3",
  "tags": [
   "baby",
   "bachcha",
   "cry",
   "rona",
   "रोना"
  ],
  "license": "Pixabay"
 },
 "baby_cry_2": {
  "file": "voices/baby_cry_2.mp3",
  "tags": [
   "baby",
   "cry",
   "rona"
  ],
  "license": "Pixabay"
 },
 "baby_cry_3": {
  "file": "voices/baby_cry_3.mp3",
  "tags": [
   "baby",
   "cry",
   "rona"
  ],
  "license": "Pixabay"
 },
 "child_cry_1": {
  "file": "voices/child_cry_1.mp3",
  "tags": [
   "child",
   "bachcha",
   "cry",
   "rona"
  ],
  "license": "Pixabay"
 },
 "man_cry_2": {
  "file": "voices/man_cry_2.mp3",
  "tags": [
   "man",
   "cry",
   "rona",
   "dukh"
  ],
  "license": "Pixabay"
 },
 "baby_zombie": {
  "file": "voices/baby_zombie.mp3",
  "tags": [
   "zombie",
   "baby",
   "horror",
   "daravana"
  ],
  "license": "Pixabay"
 },
 "baby_giggle_1": {
  "file": "voices/baby_giggle_1.mp3",
  "tags": [
   "baby",
   "giggle",
   "hansi",
   "bachcha"
  ],
  "license": "Pixabay"
 },
 "baby_giggle_2": {
  "file": "voices/baby_giggle_2.mp3",
  "tags": [
   "baby",
   "giggle",
   "hansi"
  ],
  "license": "Pixabay"
 },
 "baby_laugh_2": {
  "file": "voices/baby_laugh_2.mp3",
  "tags": [
   "baby",
   "laugh",
   "hansi",
   "khushi"
  ],
  "license": "Pixabay"
 },
 "baby_noises": {
  "file": "voices/baby_noises.mp3",
  "tags": [
   "baby",
   "noise",
   "babble",
   "bachcha"
  ],
  "license": "Pixabay"
 },
 "soft_cry_1": {
  "file": "voices/soft_cry_1.mp3",
  "tags": [
   "cry",
   "soft",
   "rona",
   "dukh"
  ],
  "license": "Pixabay"
 },
 "woman_cry_1": {
  "file": "voices/woman_cry_1.mp3",
  "tags": [
   "woman",
   "cry",
   "aurat",
   "rona"
  ],
  "license": "Pixabay"
 },
 "woman_cry_2": {
  "file": "voices/woman_cry_2.mp3",
  "tags": [
   "woman",
   "cry",
   "aurat",
   "rona"
  ],
  "license": "Pixabay"
 },
 "monster_girl_cry": {
  "file": "voices/monster_girl_cry.mp3",
  "tags": [
   "monster",
   "girl",
   "cry",
   "sobbing",
   "horror"
  ],
  "license": "Pixabay"
 },
 "kitten_1": {
  "file": "voices/kitten_1.mp3",
  "tags": [
   "kitten",
   "billi",
   "बिल्ली",
   "cat",
   "meow"
  ],
  "license": "Pixabay"
 },
 "man_cry_3": {
  "file": "voices/man_cry_3.mp3",
  "tags": [
   "man",
   "cry",
   "rona"
  ],
  "license": "Pixabay"
 },
 "shankh": {
  "file": "temple/shankh.mp3",
  "tags": [
   "shankh",
   "शंख",
   "conch",
   "puja",
   "aarti",
   "mandir"
  ],
  "license": "Pixabay"
 },
 "bhajan_maithili": {
  "file": "music/bhajan_maithili.mp3",
  "tags": [
   "bhajan",
   "भजन",
   "maithili",
   "ram",
   "dholak",
   "harmonium"
  ],
  "license": "Pixabay"
 },
 "bhajan_rajasthani": {
  "file": "music/bhajan_rajasthani.mp3",
  "tags": [
   "bhajan",
   "krishna",
   "rajasthani",
   "sarangi",
   "khattal"
  ],
  "license": "Pixabay"
 },
 "bhajan_desert": {
  "file": "music/bhajan_desert.mp3",
  "tags": [
   "bhajan",
   "shyam",
   "desert",
   "algoza",
   "folk"
  ],
  "license": "Pixabay"
 },
 "bhajan_vishnu": {
  "file": "music/bhajan_vishnu.mp3",
  "tags": [
   "bhajan",
   "vishnu",
   "spiritual",
   "mantra"
  ],
  "license": "Pixabay"
 },
 "meditation_indian": {
  "file": "music/meditation_indian.mp3",
  "tags": [
   "meditation",
   "dhyan",
   "शांति",
   "indian"
  ],
  "license": "Pixabay"
 },
 "indian_fusion": {
  "file": "music/indian_fusion.mp3",
  "tags": [
   "fusion",
   "indian",
   "traditional",
   "modern"
  ],
  "license": "Pixabay"
 },
 "india_bgm": {
  "file": "music/india_bgm.mp3",
  "tags": [
   "bgm",
   "india",
   "background",
   "music"
  ],
  "license": "Pixabay"
 },
 "traditional_melody": {
  "file": "music/traditional_melody.mp3",
  "tags": [
   "traditional",
   "melody",
   "soft",
   "music"
  ],
  "license": "Pixabay"
 },
 "folk_song_marathi": {
  "file": "music/folk_song_marathi.mp3",
  "tags": [
   "folk",
   "marathi",
   "song",
   "lavani"
  ],
  "license": "Pixabay"
 },
 "world_atlas": {
  "file": "music/world_atlas.mp3",
  "tags": [
   "world",
   "atlas",
   "cinematic"
  ],
  "license": "Pixabay"
 },
 "mantra_lakshmi": {
  "file": "mantra/mantra_lakshmi.mp3",
  "tags": [
   "mantra",
   "lakshmi",
   "लक्ष्मी",
   "wealth",
   "paisa"
  ],
  "license": "Pixabay"
 },
 "mantra_krishna_love": {
  "file": "mantra/mantra_krishna_love.mp3",
  "tags": [
   "mantra",
   "krishna",
   "कृष्ण",
   "love",
   "pyaar"
  ],
  "license": "Pixabay"
 },
 "mantra_kali": {
  "file": "mantra/mantra_kali.mp3",
  "tags": [
   "mantra",
   "kali",
   "काली",
   "shakti",
   "tantra"
  ],
  "license": "Pixabay"
 },
 "mantra_mrityunjaya": {
  "file": "mantra/mantra_mrityunjaya.mp3",
  "tags": [
   "mantra",
   "shiva",
   "मृत्युंजय",
   "mahamrityunjaya",
   "deep"
  ],
  "license": "Pixabay"
 },
 "mantra_shivaya": {
  "file": "mantra/mantra_shivaya.mp3",
  "tags": [
   "mantra",
   "shiva",
   "ॐ नमः शिवाय",
   "om"
  ],
  "license": "Pixabay"
 },
 "mantra_govinda": {
  "file": "mantra/mantra_govinda.mp3",
  "tags": [
   "mantra",
   "govinda",
   "गोविंदा",
   "vishnu",
   "bhakti"
  ],
  "license": "Pixabay"
 },
 "sitar_raaga": {
  "file": "music/sitar_raaga.mp3",
  "tags": [
   "sitar",
   "raaga",
   "tabla",
   "meditation",
   "spa"
  ],
  "license": "Pixabay"
 },
 "sacred_whispers_1": {
  "file": "music/sacred_whispers_1.mp3",
  "tags": [
   "sacred",
   "whispers",
   "mystic",
   "temple"
  ],
  "license": "Pixabay"
 },
 "sacred_whispers_3": {
  "file": "music/sacred_whispers_3.mp3",
  "tags": [
   "sacred",
   "whispers",
   "mystic",
   "temple"
  ],
  "license": "Pixabay"
 },
 "mandala_groove": {
  "file": "music/mandala_groove.mp3",
  "tags": [
   "mandala",
   "groove",
   "hypnotic",
   "loop"
  ],
  "license": "Pixabay"
 },
 "mantra_gayatri": {
  "file": "mantra/mantra_gayatri.mp3",
  "tags": [
   "gayatri",
   "गायत्री",
   "mantra",
   "sandhya"
  ],
  "license": "Pixabay"
 },
 "mantra_gayatri_chorus": {
  "file": "mantra/mantra_gayatri_chorus.mp3",
  "tags": [
   "gayatri",
   "chorus",
   "mantra",
   "group"
  ],
  "license": "Pixabay"
 },
 "mantra_gayatri_soft": {
  "file": "mantra/mantra_gayatri_soft.mp3",
  "tags": [
   "gayatri",
   "soft",
   "mantra",
   "shaant"
  ],
  "license": "Pixabay"
 },
 "mantra_gayatri_meaning": {
  "file": "mantra/mantra_gayatri_meaning.mp3",
  "tags": [
   "gayatri",
   "meaning",
   "arth",
   "mantra"
  ],
  "license": "Pixabay"
 },
 "mantra_tryambakam": {
  "file": "mantra/mantra_tryambakam.mp3",
  "tags": [
   "tryambakam",
   "shiva",
   "मंत्र",
   "healing"
  ],
  "license": "Pixabay"
 },
 "mantra_krishna_intense": {
  "file": "mantra/mantra_krishna_intense.mp3",
  "tags": [
   "krishna",
   "intense",
   "mantra",
   "bhakti"
  ],
  "license": "Pixabay"
 },
 "mauna_meditation": {
  "file": "music/mauna_meditation.mp3",
  "tags": [
   "mauna",
   "silence",
   "meditation",
   "dhyan"
  ],
  "license": "Pixabay"
 },
 "sleep_meditation": {
  "file": "music/sleep_meditation.mp3",
  "tags": [
   "sleep",
   "meditation",
   "raat",
   "shaant"
  ],
  "license": "Pixabay"
 },
 "sitar_charukeshi": {
  "file": "music/sitar_charukeshi.mp3",
  "tags": [
   "sitar",
   "charukeshi",
   "calm",
   "raaga"
  ],
  "license": "Pixabay"
 },
 "mantra_ram": {
  "file": "mantra/mantra_ram.mp3",
  "tags": [
   "ram",
   "राम",
   "mantra",
   "श्री रामाय"
  ],
  "license": "Pixabay"
 },
 "mantra_ram_loop": {
  "file": "mantra/mantra_ram_loop.mp3",
  "tags": [
   "ram",
   "loop",
   "mantra",
   "chant"
  ],
  "license": "Pixabay"
 },
 "mantra_waheguru": {
  "file": "mantra/mantra_waheguru.mp3",
  "tags": [
   "waheguru",
   "वाहेगुरु",
   "sikh",
   "gurudwara"
  ],
  "license": "Pixabay"
 },
 "mantra_gayatri_om": {
  "file": "mantra/mantra_gayatri_om.mp3",
  "tags": [
   "gayatri",
   "om",
   "मंत्र"
  ],
  "license": "Pixabay"
 },
 "mantra_gayatri_minimal": {
  "file": "mantra/mantra_gayatri_minimal.mp3",
  "tags": [
   "gayatri",
   "minimal",
   "chant"
  ],
  "license": "Pixabay"
 },
 "mantra_shivaya_slow": {
  "file": "mantra/mantra_shivaya_slow.mp3",
  "tags": [
   "shivaya",
   "slow",
   "meditation",
   "ॐ नमः शिवाय"
  ],
  "license": "Pixabay"
 },
 "mantra_shivaya_432": {
  "file": "mantra/mantra_shivaya_432.mp3",
  "tags": [
   "shivaya",
   "432hz",
   "healing"
  ],
  "license": "Pixabay"
 },
 "mantra_dark": {
  "file": "mantra/mantra_dark.mp3",
  "tags": [
   "dark",
   "mantra",
   "tantra",
   "horror"
  ],
  "license": "Pixabay"
 },
 "mantra_mrityunjaya_2": {
  "file": "mantra/mantra_mrityunjaya_2.mp3",
  "tags": [
   "mrityunjaya",
   "sangat",
   "group"
  ],
  "license": "Pixabay"
 },
 "mantra_432hz": {
  "file": "music/mantra_432hz.mp3",
  "tags": [
   "432hz",
   "meditation",
   "soul",
   "chant"
  ],
  "license": "Pixabay"
 },
 "baby_laughs_2": {
  "file": "voices/baby_laughs_2.mp3",
  "tags": [
   "baby",
   "laugh",
   "hansi",
   "bachcha"
  ],
  "license": "Pixabay"
 },
 "baby_giggle_3": {
  "file": "voices/baby_giggle_3.mp3",
  "tags": [
   "baby",
   "giggle",
   "hansi"
  ],
  "license": "Pixabay"
 },
 "baby_babble_2": {
  "file": "voices/baby_babble_2.mp3",
  "tags": [
   "baby",
   "babble",
   "bachcha",
   "gugu"
  ],
  "license": "Pixabay"
 },
 "baby_talk": {
  "file": "voices/baby_talk.mp3",
  "tags": [
   "baby",
   "talk",
   "bachcha",
   "bolna"
  ],
  "license": "Pixabay"
 },
 "girl_cry_1": {
  "file": "voices/girl_cry_1.mp3",
  "tags": [
   "girl",
   "cry",
   "ladki",
   "rona"
  ],
  "license": "Pixabay"
 },
 "child_cry_2": {
  "file": "voices/child_cry_2.mp3",
  "tags": [
   "child",
   "cry",
   "bachcha",
   "rona"
  ],
  "license": "Pixabay"
 },
 "man_cry_4": {
  "file": "voices/man_cry_4.mp3",
  "tags": [
   "man",
   "cry",
   "aadmi",
   "rona"
  ],
  "license": "Pixabay"
 },
 "human_roar": {
  "file": "voices/human_roar.mp3",
  "tags": [
   "roar",
   "growl",
   "insaan",
   "gussa"
  ],
  "license": "Pixabay"
 },
 "plors_sob": {
  "file": "voices/plors_sob.mp3",
  "tags": [
   "sob",
   "siskna",
   "rona",
   "dukh"
  ],
  "license": "Pixabay"
 },
 "mantra_ambient": {
  "file": "mantra/mantra_ambient.mp3",
  "tags": [
   "mantra",
   "ambient",
   "chant",
   "spiritual"
  ],
  "license": "Pixabay"
 },
 "peacock": {
  "file": "animals/peacock.mp3",
  "tags": [
   "peacock",
   "mor",
   "मोर",
   "bird",
   "barsaat"
  ],
  "license": "Pixabay"
 },
 "coin_drop_1": {
  "file": "foley/coin_drop_1.mp3",
  "tags": [
   "coin",
   "sikka",
   "सिक्का",
   "drop",
   "money"
  ],
  "license": "Pixabay"
 },
 "coin_drop_2": {
  "file": "foley/coin_drop_2.mp3",
  "tags": [
   "coin",
   "sikka",
   "spin",
   "money"
  ],
  "license": "Pixabay"
 },
 "coins_dropping": {
  "file": "foley/coins_dropping.mp3",
  "tags": [
   "coins",
   "sikke",
   "paisa",
   "gullak"
  ],
  "license": "Pixabay"
 },
 "baby_cry_4": {
  "file": "voices/baby_cry_4.mp3",
  "tags": [
   "baby",
   "cry",
   "bachcha",
   "rona"
  ],
  "license": "Pixabay"
 },
 "baby_cry_5": {
  "file": "voices/baby_cry_5.mp3",
  "tags": [
   "baby",
   "cry",
   "rona"
  ],
  "license": "Pixabay"
 },
 "baby_cry_6": {
  "file": "voices/baby_cry_6.mp3",
  "tags": [
   "baby",
   "cry",
   "rona"
  ],
  "license": "Pixabay"
 },
 "baby_cry_angry": {
  "file": "voices/baby_cry_angry.mp3",
  "tags": [
   "baby",
   "angry",
   "cry",
   "gussa"
  ],
  "license": "Pixabay"
 },
 "baby_shout": {
  "file": "voices/baby_shout.mp3",
  "tags": [
   "baby",
   "shout",
   "chillana"
  ],
  "license": "Pixabay"
 },
 "cry_1": {
  "file": "voices/cry_1.mp3",
  "tags": [
   "cry",
   "rona",
   "dukh"
  ],
  "license": "Pixabay"
 },
 "cry_2": {
  "file": "voices/cry_2.mp3",
  "tags": [
   "cry",
   "rona",
   "sad"
  ],
  "license": "Pixabay"
 },
 "coin_clatter": {
  "file": "foley/coin_clatter.mp3",
  "tags": [
   "coin",
   "sikka",
   "clatter",
   "girna"
  ],
  "license": "Pixabay"
 },
 "coins_falling_1": {
  "file": "foley/coins_falling_1.mp3",
  "tags": [
   "coins",
   "girna",
   "paisa"
  ],
  "license": "Pixabay"
 },
 "coins_rattle": {
  "file": "foley/coins_rattle.mp3",
  "tags": [
   "coins",
   "rattle",
   "khankhana"
  ],
  "license": "Pixabay"
 },
 "coins_jingle": {
  "file": "foley/coins_jingle.mp3",
  "tags": [
   "coins",
   "jingle",
   "khankhna"
  ],
  "license": "Pixabay"
 },
 "coins_counting": {
  "file": "foley/coins_counting.mp3",
  "tags": [
   "coins",
   "count",
   "ginna",
   "paisa"
  ],
  "license": "Pixabay"
 },
 "coins_spilled": {
  "file": "foley/coins_spilled.mp3",
  "tags": [
   "coins",
   "spill",
   "girna",
   "bikharna"
  ],
  "license": "Pixabay"
 },
 "coins_on_plate": {
  "file": "foley/coins_on_plate.mp3",
  "tags": [
   "coins",
   "plate",
   "thali",
   "paisa"
  ],
  "license": "Pixabay"
 },
 "coins_in_bowl": {
  "file": "foley/coins_in_bowl.mp3",
  "tags": [
   "coins",
   "bowl",
   "matka",
   "gullak"
  ],
  "license": "Pixabay"
 },
 "coins_burst": {
  "file": "foley/coins_burst.mp3",
  "tags": [
   "coins",
   "burst",
   "jackpot"
  ],
  "license": "Pixabay"
 },
 "jackpot_coins": {
  "file": "foley/jackpot_coins.mp3",
  "tags": [
   "coins",
   "jackpot",
   "jeet"
  ],
  "license": "Pixabay"
 },
 "coin_drop_3": {
  "file": "foley/coin_drop_3.mp3",
  "tags": [
   "coin",
   "sikka",
   "drop"
  ],
  "license": "Pixabay"
 },
 "coin_drop_4": {
  "file": "foley/coin_drop_4.mp3",
  "tags": [
   "coin",
   "drop",
   "single"
  ],
  "license": "Pixabay"
 },
 "coin_drop_5": {
  "file": "foley/coin_drop_5.mp3",
  "tags": [
   "coin",
   "drop",
   "game"
  ],
  "license": "Pixabay"
 },
 "coin_spin": {
  "file": "foley/coin_spin.mp3",
  "tags": [
   "coin",
   "spin",
   "chakra",
   "table"
  ],
  "license": "Pixabay"
 },
 "coins_wooden_box": {
  "file": "foley/coins_wooden_box.mp3",
  "tags": [
   "coins",
   "wooden",
   "box",
   "gullak"
  ],
  "license": "Pixabay"
 },
 "coins_bag": {
  "file": "foley/coins_bag.mp3",
  "tags": [
   "coins",
   "bag",
   "thaila",
   "paisa"
  ],
  "license": "Pixabay"
 },
 "coins_spill_2": {
  "file": "foley/coins_spill_2.mp3",
  "tags": [
   "coins",
   "spill",
   "bikharna"
  ],
  "license": "Pixabay"
 },
 "coins_counting_2": {
  "file": "foley/coins_counting_2.mp3",
  "tags": [
   "coins",
   "counting",
   "ginna"
  ],
  "license": "Pixabay"
 },
 "desert_wind": {
  "file": "ambience/desert_wind.mp3",
  "tags": [
   "desert",
   "wind",
   "registan",
   "hawa"
  ],
  "license": "Pixabay"
 },
 "wind_blowing": {
  "file": "ambience/wind_blowing.mp3",
  "tags": [
   "wind",
   "hawa",
   "blowing",
   "toofan"
  ],
  "license": "Pixabay"
 },
 "wind_eerie": {
  "file": "horror/wind_eerie.mp3",
  "tags": [
   "wind",
   "eerie",
   "horror",
   "hawa",
   "dar"
  ],
  "license": "Pixabay"
 },
 "wind_howl_window": {
  "file": "ambience/wind_howl_window.mp3",
  "tags": [
   "wind",
   "howl",
   "window",
   "khidki",
   "toofan"
  ],
  "license": "Pixabay"
 },
 "wind_shaking_windows": {
  "file": "ambience/wind_shaking_windows.mp3",
  "tags": [
   "wind",
   "windows",
   "storm",
   "khidki"
  ],
  "license": "Pixabay"
 },
 "wind_winter": {
  "file": "ambience/wind_winter.mp3",
  "tags": [
   "winter",
   "cold",
   "wind",
   "sardi"
  ],
  "license": "Pixabay"
 },
 "wind_cold": {
  "file": "ambience/wind_cold.mp3",
  "tags": [
   "cold",
   "wind",
   "bitter",
   "thand"
  ],
  "license": "Pixabay"
 },
 "war_horn": {
  "file": "ambience/war_horn.mp3",
  "tags": [
   "war",
   "horn",
   "yuddh",
   "battle",
   "singing"
  ],
  "license": "Pixabay"
 },
 "fog_horn_1": {
  "file": "ambience/fog_horn_1.mp3",
  "tags": [
   "fog",
   "horn",
   "ship",
   "samundar"
  ],
  "license": "Pixabay"
 },
 "fog_horn_2": {
  "file": "ambience/fog_horn_2.mp3",
  "tags": [
   "fog",
   "horn",
   "ship",
   "dhundh"
  ],
  "license": "Pixabay"
 },
 "ghost_howl_1": {
  "file": "horror/ghost_howl_1.mp3",
  "tags": [
   "ghost",
   "howl",
   "bhoot",
   "chillana"
  ],
  "license": "Pixabay"
 },
 "ghost_howl_2": {
  "file": "horror/ghost_howl_2.mp3",
  "tags": [
   "ghost",
   "howl",
   "bhoot",
   "dar"
  ],
  "license": "Pixabay"
 },
 "car_horn_3": {
  "file": "vehicles/car_horn_3.mp3",
  "tags": [
   "car",
   "horn",
   "gaadi",
   "hunkar"
  ],
  "license": "Pixabay"
 },
 "car_horn_4": {
  "file": "vehicles/car_horn_4.mp3",
  "tags": [
   "car",
   "horn",
   "traffic",
   "gaadi"
  ],
  "license": "Pixabay"
 },
 "train_interior_indian": {
  "file": "vehicles/train_interior_indian.mp3",
  "tags": [
   "train",
   "interior",
   "indian",
   "dibba",
   "andhar"
  ],
  "license": "Pixabay"
 },
 "train_interior_old": {
  "file": "vehicles/train_interior_old.mp3",
  "tags": [
   "train",
   "interior",
   "old",
   "purani gaadi"
  ],
  "license": "Pixabay"
 },
 "train_interior_old_2": {
  "file": "vehicles/train_interior_old_2.mp3",
  "tags": [
   "train",
   "interior",
   "old",
   "coach"
  ],
  "license": "Pixabay"
 },
 "train_whistle": {
  "file": "vehicles/train_whistle.mp3",
  "tags": [
   "train",
   "whistle",
   "seeti",
   "horn"
  ],
  "license": "Pixabay"
 },
 "boat_horn": {
  "file": "vehicles/boat_horn.mp3",
  "tags": [
   "boat",
   "horn",
   "nav",
   "ship"
  ],
  "license": "Pixabay"
 },
 "horn_dramatic": {
  "file": "horror/horn_dramatic.mp3",
  "tags": [
   "horn",
   "dramatic",
   "war",
   "yuddh"
  ],
  "license": "Pixabay"
 },
 "war_horn_horror": {
  "file": "horror/war_horn_horror.mp3",
  "tags": [
   "war",
   "horn",
   "horror",
   "battle"
  ],
  "license": "Pixabay"
 },
 "mega_horn": {
  "file": "vehicles/mega_horn.mp3",
  "tags": [
   "horn",
   "mega",
   "siren",
   "war",
   "trailer"
  ],
  "license": "Pixabay"
 },
 "mega_horn_2": {
  "file": "vehicles/mega_horn_2.mp3",
  "tags": [
   "horn",
   "mega",
   "siren",
   "dramatic"
  ],
  "license": "Pixabay"
 },
 "ship_horn": {
  "file": "vehicles/ship_horn.mp3",
  "tags": [
   "ship",
   "horn",
   "cargo",
   "samundar"
  ],
  "license": "Pixabay"
 },
 "car_horn_5": {
  "file": "vehicles/car_horn_5.mp3",
  "tags": [
   "car",
   "horn",
   "gaadi"
  ],
  "license": "Pixabay"
 },
 "car_horn_6": {
  "file": "vehicles/car_horn_6.mp3",
  "tags": [
   "car",
   "horn",
   "traffic"
  ],
  "license": "Pixabay"
 },
 "locomotive_horn": {
  "file": "vehicles/locomotive_horn.mp3",
  "tags": [
   "train",
   "locomotive",
   "horn",
   "engine"
  ],
  "license": "Pixabay"
 },
 "train_passing_2": {
  "file": "vehicles/train_passing_2.mp3",
  "tags": [
   "train",
   "passing",
   "guzarti",
   "patti"
  ],
  "license": "Pixabay"
 },
 "train_fast_indian": {
  "file": "vehicles/train_fast_indian.mp3",
  "tags": [
   "train",
   "fast",
   "indian",
   "tez"
  ],
  "license": "Pixabay"
 },
 "train_horn_faux": {
  "file": "vehicles/train_horn_faux.mp3",
  "tags": [
   "train",
   "horn",
   "seeti"
  ],
  "license": "Pixabay"
 },
 "city_train_depot": {
  "file": "vehicles/city_train_depot.mp3",
  "tags": [
   "city",
   "depot",
   "train",
   "ambience",
   "bheed"
  ],
  "license": "Pixabay"
 },
 "monster_death_scream": {
  "file": "horror/monster_death_scream.mp3",
  "tags": [
   "monster",
   "death",
   "scream",
   "rakshas"
  ],
  "license": "Pixabay"
 },
 "sirenhead_death": {
  "file": "horror/sirenhead_death.mp3",
  "tags": [
   "sirenhead",
   "death",
   "monster"
  ],
  "license": "Pixabay"
 },
 "dark_knight_death": {
  "file": "horror/dark_knight_death.mp3",
  "tags": [
   "death",
   "dark",
   "cinematic"
  ],
  "license": "Pixabay"
 },
 "man_falling_death": {
  "file": "horror/man_falling_death.mp3",
  "tags": [
   "falling",
   "death",
   "girna",
   "chillana"
  ],
  "license": "Pixabay"
 },
 "scraped_death": {
  "file": "horror/scraped_death.mp3",
  "tags": [
   "scrape",
   "death",
   "horror"
  ],
  "license": "Pixabay"
 },
 "siren_voice_line": {
  "file": "voices/siren_voice_line.mp3",
  "tags": [
   "siren",
   "voice",
   "female",
   "monster"
  ],
  "license": "Pixabay"
 },
 "siren_menace": {
  "file": "voices/siren_menace.mp3",
  "tags": [
   "siren",
   "menace",
   "threat",
   "female"
  ],
  "license": "Pixabay"
 },
 "boss_attack_vocal": {
  "file": "voices/boss_attack_vocal.mp3",
  "tags": [
   "boss",
   "attack",
   "vocal",
   "roar"
  ],
  "license": "Pixabay"
 },
 "female_attack_vocal": {
  "file": "voices/female_attack_vocal.mp3",
  "tags": [
   "female",
   "attack",
   "vocal",
   "chillana"
  ],
  "license": "Pixabay"
 },
 "darts": {
  "file": "foley/darts.mp3",
  "tags": [
   "darts",
   "throw",
   "fenkna",
   "teer"
  ],
  "license": "Pixabay"
 },
 "male_death_scream": {
  "file": "horror/male_death_scream.mp3",
  "tags": [
   "male",
   "death",
   "scream",
   "aadmi"
  ],
  "license": "Pixabay"
 },
 "insect_death": {
  "file": "horror/insect_death.mp3",
  "tags": [
   "insect",
   "death",
   "keeda",
   "monster"
  ],
  "license": "Pixabay"
 },
 "necromancer_spell": {
  "file": "horror/necromancer_spell.mp3",
  "tags": [
   "necromancer",
   "spell",
   "jaadu",
   "mantra"
  ],
  "license": "Pixabay"
 },
 "dark_evil_code": {
  "file": "horror/dark_evil_code.mp3",
  "tags": [
   "dark",
   "evil",
   "code",
   "horror"
  ],
  "license": "Pixabay"
 },
 "disappear": {
  "file": "horror/disappear.mp3",
  "tags": [
   "disappear",
   "gayab",
   "magic"
  ],
  "license": "Pixabay"
 },
 "battle_end": {
  "file": "horror/battle_end.mp3",
  "tags": [
   "battle",
   "end",
   "yuddh",
   "jeet"
  ],
  "license": "Pixabay"
 },
 "female_death_vocal": {
  "file": "voices/female_death_vocal.mp3",
  "tags": [
   "female",
   "death",
   "vocal",
   "maut"
  ],
  "license": "Pixabay"
 },
 "siren_laugh_evil": {
  "file": "voices/siren_laugh_evil.mp3",
  "tags": [
   "siren",
   "laugh",
   "evil",
   "hansi"
  ],
  "license": "Pixabay"
 },
 "siren_laugh_2": {
  "file": "voices/siren_laugh_2.mp3",
  "tags": [
   "siren",
   "laugh",
   "kill",
   "hansi"
  ],
  "license": "Pixabay"
 },
 "fall_impact": {
  "file": "foley/fall_impact.mp3",
  "tags": [
   "fall",
   "impact",
   "girna",
   "takkar"
  ],
  "license": "Pixabay"
 },
 "insect_death_2": {
  "file": "horror/insect_death_2.mp3",
  "tags": [
   "insect",
   "death",
   "keeda"
  ],
  "license": "Pixabay"
 },
 "insect_death_3": {
  "file": "horror/insect_death_3.mp3",
  "tags": [
   "insect",
   "death",
   "monster"
  ],
  "license": "Pixabay"
 },
 "death_whistle": {
  "file": "horror/death_whistle.mp3",
  "tags": [
   "death",
   "whistle",
   "seeti",
   "horror"
  ],
  "license": "Pixabay"
 },
 "male_scream_2": {
  "file": "voices/male_scream_2.mp3",
  "tags": [
   "male",
   "scream",
   "chillana",
   "dar"
  ],
  "license": "Pixabay"
 },
 "metalscrape_2": {
  "file": "foley/metalscrape_2.mp3",
  "tags": [
   "metal",
   "scrape",
   "khurachna",
   "talwar"
  ],
  "license": "Pixabay"
 },
 "drum_loop_slap": {
  "file": "music/drum_loop_slap.mp3",
  "tags": [
   "drum",
   "loop",
   "slap",
   "beat"
  ],
  "license": "Pixabay"
 },
 "hand_grinder": {
  "file": "kitchen/hand_grinder.mp3",
  "tags": [
   "grinder",
   "chakki",
   "silbatta",
   "masala"
  ],
  "license": "Pixabay"
 },
 "food_processor": {
  "file": "machines/food_processor.mp3",
  "tags": [
   "processor",
   "machine",
   "mixer"
  ],
  "license": "Pixabay"
 },
 "stirring_tea": {
  "file": "kitchen/stirring_tea.mp3",
  "tags": [
   "stirring",
   "tea",
   "chai",
   "chammach"
  ],
  "license": "Pixabay"
 },
 "field_recording_1": {
  "file": "ambience/field_recording_1.mp3",
  "tags": [
   "field",
   "ambience",
   "outside",
   "bahar"
  ],
  "license": "Pixabay"
 },
 "electric_gate_open": {
  "file": "door/electric_gate_open.mp3",
  "tags": [
   "gate",
   "electric",
   "open",
   "khulna"
  ],
  "license": "Pixabay"
 },
 "gate_close_2": {
  "file": "door/gate_close_2.mp3",
  "tags": [
   "gate",
   "close",
   "band",
   "darwaza"
  ],
  "license": "Pixabay"
 },
 "door_creaky_steel_wood": {
  "file": "door/door_creaky_steel_wood.mp3",
  "tags": [
   "door",
   "creaky",
   "steel",
   "wood",
   "chirana"
  ],
  "license": "Pixabay"
 },
 "iron_gate_courtyard": {
  "file": "door/iron_gate_courtyard.mp3",
  "tags": [
   "iron",
   "gate",
   "courtyard",
   "aangan"
  ],
  "license": "Pixabay"
 },
 "door_lock_open": {
  "file": "door/door_lock_open.mp3",
  "tags": [
   "lock",
   "key",
   "chaabi",
   "darwaza"
  ],
  "license": "Pixabay"
 },
 "door_iron_creak_old": {
  "file": "door/door_iron_creak_old.mp3",
  "tags": [
   "iron",
   "door",
   "creak",
   "purana",
   "haveli"
  ],
  "license": "Pixabay"
 },
 "door_iron_creak_2": {
  "file": "door/door_iron_creak_2.mp3",
  "tags": [
   "iron",
   "door",
   "creak",
   "chirana"
  ],
  "license": "Pixabay"
 },
 "iron_door_open_2": {
  "file": "door/iron_door_open_2.mp3",
  "tags": [
   "iron",
   "door",
   "open",
   "khulna"
  ],
  "license": "Pixabay"
 },
 "car_interior": {
  "file": "vehicles/car_interior.mp3",
  "tags": [
   "car",
   "interior",
   "andhar",
   "gaadi"
  ],
  "license": "Pixabay"
 },
 "coffee_machine_2": {
  "file": "machines/coffee_machine_2.mp3",
  "tags": [
   "coffee",
   "machine",
   "nespresso",
   "kitchen"
  ],
  "license": "Pixabay"
 },
 "halloween_bgm": {
  "file": "music/halloween_bgm.mp3",
  "tags": [
   "halloween",
   "spooky",
   "horror",
   "bgm"
  ],
  "license": "Pixabay"
 },
 "halloween_scary": {
  "file": "music/halloween_scary.mp3",
  "tags": [
   "halloween",
   "scary",
   "horror",
   "dark"
  ],
  "license": "Pixabay"
 },
 "forest_whispers": {
  "file": "music/forest_whispers.mp3",
  "tags": [
   "forest",
   "jungle",
   "whispers",
   "mystic"
  ],
  "license": "Pixabay"
 },
 "forest_morning_mist": {
  "file": "music/forest_morning_mist.mp3",
  "tags": [
   "forest",
   "morning",
   "mist",
   "calm"
  ],
  "license": "Pixabay"
 },
 "forest_pathway": {
  "file": "music/forest_pathway.mp3",
  "tags": [
   "forest",
   "path",
   "journey",
   "calm"
  ],
  "license": "Pixabay"
 },
 "forest_spirits_piano": {
  "file": "music/forest_spirits_piano.mp3",
  "tags": [
   "forest",
   "piano",
   "nostalgic",
   "sad"
  ],
  "license": "Pixabay"
 },
 "forest_relax": {
  "file": "music/forest_relax.mp3",
  "tags": [
   "forest",
   "relax",
   "calm",
   "sleep"
  ],
  "license": "Pixabay"
 },
 "forest_scent": {
  "file": "music/forest_scent.mp3",
  "tags": [
   "forest",
   "nature",
   "peaceful"
  ],
  "license": "Pixabay"
 },
 "forest_harp": {
  "file": "music/forest_harp.mp3",
  "tags": [
   "forest",
   "harp",
   "magic",
   "fairy"
  ],
  "license": "Pixabay"
 },
 "forest_adventure": {
  "file": "music/forest_adventure.mp3",
  "tags": [
   "forest",
   "adventure",
   "journey",
   "action"
  ],
  "license": "Pixabay"
 },
 "piano_inspiring": {
  "file": "music/piano_inspiring.mp3",
  "tags": [
   "piano",
   "inspiring",
   "emotional",
   "hope"
  ],
  "license": "Pixabay"
 },
 "forest_lofi_piano": {
  "file": "music/forest_lofi_piano.mp3",
  "tags": [
   "lofi",
   "piano",
   "forest",
   "memories",
   "chill"
  ],
  "license": "Pixabay"
 },
 "forest_enchanted": {
  "file": "music/forest_enchanted.mp3",
  "tags": [
   "enchanted",
   "forest",
   "magic",
   "fairy"
  ],
  "license": "Pixabay"
 },
 "forest_reflections": {
  "file": "music/forest_reflections.mp3",
  "tags": [
   "forest",
   "reflections",
   "calm",
   "thought"
  ],
  "license": "Pixabay"
 },
 "night_quiet": {
  "file": "music/night_quiet.mp3",
  "tags": [
   "night",
   "quiet",
   "raat",
   "calm"
  ],
  "license": "Pixabay"
 },
 "forest_epic_ballad": {
  "file": "music/forest_epic_ballad.mp3",
  "tags": [
   "epic",
   "ballad",
   "forest",
   "journey"
  ],
  "license": "Pixabay"
 },
 "forest_morning_harp": {
  "file": "music/forest_morning_harp.mp3",
  "tags": [
   "harp",
   "morning",
   "forest",
   "soft"
  ],
  "license": "Pixabay"
 },
 "forest_guitar": {
  "file": "music/forest_guitar.mp3",
  "tags": [
   "guitar",
   "forest",
   "folk",
   "warm"
  ],
  "license": "Pixabay"
 },
 "nature_bed": {
  "file": "ambience/nature_bed.mp3",
  "tags": [
   "nature",
   "ambience",
   "outside",
   "jungle"
  ],
  "license": "Pixabay"
 },
 "forest_river_bed": {
  "file": "ambience/forest_river_bed.mp3",
  "tags": [
   "forest",
   "river",
   "nature",
   "water"
  ],
  "license": "Pixabay"
 },
 "forest_relax_2": {
  "file": "music/forest_relax_2.mp3",
  "tags": [
   "forest",
   "relax",
   "calm",
   "sleep"
  ],
  "license": "Pixabay"
 },
 "forest_folk_song": {
  "file": "music/forest_folk_song.mp3",
  "tags": [
   "folk",
   "acoustic",
   "forest",
   "song"
  ],
  "license": "Pixabay"
 },
 "halloween_spooky": {
  "file": "music/halloween_spooky.mp3",
  "tags": [
   "halloween",
   "spooky",
   "dark",
   "horror"
  ],
  "license": "Pixabay"
 },
 "halloween_bgm_2": {
  "file": "music/halloween_bgm_2.mp3",
  "tags": [
   "halloween",
   "bgm",
   "mystery"
  ],
  "license": "Pixabay"
 },
 "forest_celtic_mystic": {
  "file": "music/forest_celtic_mystic.mp3",
  "tags": [
   "celtic",
   "mystic",
   "forest",
   "magic"
  ],
  "license": "Pixabay"
 },
 "haunting_bgm": {
  "file": "music/haunting_bgm.mp3",
  "tags": [
   "haunting",
   "bhoot",
   "dark",
   "sad"
  ],
  "license": "Pixabay"
 },
 "forest_dark_ambient": {
  "file": "music/forest_dark_ambient.mp3",
  "tags": [
   "dark",
   "ambient",
   "forest",
   "horror"
  ],
  "license": "Pixabay"
 },
 "forest_tales_orchestral": {
  "file": "music/forest_tales_orchestral.mp3",
  "tags": [
   "orchestral",
   "forest",
   "story",
   "cinematic"
  ],
  "license": "Pixabay"
 },
 "forest_tales_halloween": {
  "file": "music/forest_tales_halloween.mp3",
  "tags": [
   "orchestral",
   "halloween",
   "dark"
  ],
  "license": "Pixabay"
 },
 "forest_morning_birds": {
  "file": "ambience/forest_morning_birds.mp3",
  "tags": [
   "morning",
   "forest",
   "birds",
   "subah"
  ],
  "license": "Pixabay"
 },
 "birds_forest_1": {
  "file": "ambience/birds_forest_1.mp3",
  "tags": [
   "birds",
   "forest",
   "chidiyan",
   "jungle"
  ],
  "license": "Pixabay"
 },
 "birds_forest_2": {
  "file": "ambience/birds_forest_2.mp3",
  "tags": [
   "birds",
   "forest",
   "chidiyan"
  ],
  "license": "Pixabay"
 },
 "birds_chirp_1": {
  "file": "ambience/birds_chirp_1.mp3",
  "tags": [
   "birds",
   "chirping",
   "subah",
   "chidiyan"
  ],
  "license": "Pixabay"
 },
 "birds_chirp_2": {
  "file": "ambience/birds_chirp_2.mp3",
  "tags": [
   "birds",
   "chirping",
   "morning"
  ],
  "license": "Pixabay"
 },
 "bird_chirp_3": {
  "file": "ambience/bird_chirp_3.mp3",
  "tags": [
   "bird",
   "chirp",
   "chidiya"
  ],
  "license": "Pixabay"
 },
 "birds_forest_chirp": {
  "file": "ambience/birds_forest_chirp.mp3",
  "tags": [
   "birds",
   "forest",
   "chirping"
  ],
  "license": "Pixabay"
 },
 "forest_birds_river": {
  "file": "ambience/forest_birds_river.mp3",
  "tags": [
   "forest",
   "birds",
   "river",
   "nature"
  ],
  "license": "Pixabay"
 },
 "forest_celtic_mystic_2": {
  "file": "music/forest_celtic_mystic_2.mp3",
  "tags": [
   "celtic",
   "mystic",
   "forest"
  ],
  "license": "Pixabay"
 },
 "forest_walk_band": {
  "file": "music/forest_walk_band.mp3",
  "tags": [
   "forest",
   "walk",
   "band",
   "folk"
  ],
  "license": "Pixabay"
 },
 "forest_hiding_place": {
  "file": "music/forest_hiding_place.mp3",
  "tags": [
   "forest",
   "suspense",
   "hiding",
   "tension"
  ],
  "license": "Pixabay"
 },
 "chicken_coop": {
  "file": "animals/chicken_coop.mp3",
  "tags": [
   "chicken",
   "murgi",
   "मुर्गी",
   "hen",
   "coop",
   "murga",
   "gaon"
  ],
  "license": "Pixabay"
 },
 "bird_chirps_4": {
  "file": "ambience/bird_chirps_4.mp3",
  "tags": [
   "birds",
   "chirps",
   "chidiyan"
  ],
  "license": "Pixabay"
 },
 "lullaby_baby": {
  "file": "music/lullaby_baby.mp3",
  "tags": [
   "lullaby",
   "baby",
   "lori",
   "sleep",
   "bachcha"
  ],
  "license": "Pixabay"
 },
 "romantic_crazy_love": {
  "file": "music/romantic_crazy_love.mp3",
  "tags": [
   "romantic",
   "love",
   "pyaar",
   "crazy"
  ],
  "license": "Pixabay"
 },
 "fun_guitar": {
  "file": "music/fun_guitar.mp3",
  "tags": [
   "fun",
   "guitar",
   "happy",
   "comedy"
  ],
  "license": "Pixabay"
 },
 "epic_hybrid_orchestra": {
  "file": "music/epic_hybrid_orchestra.mp3",
  "tags": [
   "epic",
   "orchestra",
   "hybrid",
   "trailer",
   "hero"
  ],
  "license": "Pixabay"
 },
 "trailer_lacrimosa": {
  "file": "music/trailer_lacrimosa.mp3",
  "tags": [
   "trailer",
   "lacrimosa",
   "epic",
   "sad",
   "cinematic"
  ],
  "license": "Pixabay"
 },
 "cinematic_redline": {
  "file": "music/cinematic_redline.mp3",
  "tags": [
   "cinematic",
   "cue",
   "action",
   "tension"
  ],
  "license": "Pixabay"
 },
 "countdown_action": {
  "file": "music/countdown_action.mp3",
  "tags": [
   "countdown",
   "action",
   "trailer",
   "blockbuster"
  ],
  "license": "Pixabay"
 },
 "deep_breath_epic": {
  "file": "music/deep_breath_epic.mp3",
  "tags": [
   "epic",
   "breath",
   "trailer",
   "hero"
  ],
  "license": "Pixabay"
 },
 "trailer_teaser": {
  "file": "music/trailer_teaser.mp3",
  "tags": [
   "trailer",
   "teaser",
   "cinematic",
   "build"
  ],
  "license": "Pixabay"
 },
 "fun_banana_slip": {
  "file": "music/fun_banana_slip.mp3",
  "tags": [
   "fun",
   "comedy",
   "slip",
   "cartoon"
  ],
  "license": "Pixabay"
 },
 "tense_horror_1": {
  "file": "horror/tense_horror_1.mp3",
  "tags": [
   "tense",
   "horror",
   "tension",
   "dar"
  ],
  "license": "Pixabay"
 },
 "cyber_crash": {
  "file": "transitions/cyber_crash.mp3",
  "tags": [
   "transition",
   "crash",
   "cyber",
   "impact"
  ],
  "license": "Pixabay"
 },
 "system_failure": {
  "file": "transitions/system_failure.mp3",
  "tags": [
   "transition",
   "failure",
   "glitch",
   "machine"
  ],
  "license": "Pixabay"
 },
 "choir_transition": {
  "file": "transitions/choir_transition.mp3",
  "tags": [
   "transition",
   "choir",
   "swell",
   "epic"
  ],
  "license": "Pixabay"
 },
 "tonal_riser_1": {
  "file": "transitions/tonal_riser_1.mp3",
  "tags": [
   "riser",
   "build",
   "transition",
   "tension"
  ],
  "license": "Pixabay"
 },
 "tonal_riser_3": {
  "file": "transitions/tonal_riser_3.mp3",
  "tags": [
   "riser",
   "build",
   "transition"
  ],
  "license": "Pixabay"
 },
 "tonal_riser_smooth_2": {
  "file": "transitions/tonal_riser_smooth_2.mp3",
  "tags": [
   "riser",
   "smooth",
   "transition"
  ],
  "license": "Pixabay"
 },
 "tonal_riser_smooth_7": {
  "file": "transitions/tonal_riser_smooth_7.mp3",
  "tags": [
   "riser",
   "smooth",
   "transition"
  ],
  "license": "Pixabay"
 },
 "tonal_riser_smooth_8": {
  "file": "transitions/tonal_riser_smooth_8.mp3",
  "tags": [
   "riser",
   "smooth",
   "transition"
  ],
  "license": "Pixabay"
 },
 "tonal_riser_cinematic_8": {
  "file": "transitions/tonal_riser_cinematic_8.mp3",
  "tags": [
   "riser",
   "cinematic",
   "transition"
  ],
  "license": "Pixabay"
 },
 "whoosh_reverse_low": {
  "file": "transitions/whoosh_reverse_low.mp3",
  "tags": [
   "whoosh",
   "reverse",
   "transition",
   "deep"
  ],
  "license": "Pixabay"
 },
 "logo_sting_synthwave": {
  "file": "transitions/logo_sting_synthwave.mp3",
  "tags": [
   "sting",
   "logo",
   "synthwave",
   "reveal"
  ],
  "license": "Pixabay"
 },
 "ui_click_cyber": {
  "file": "transitions/ui_click_cyber.mp3",
  "tags": [
   "click",
   "ui",
   "cyber",
   "interface"
  ],
  "license": "Pixabay"
 },
 "fast_beat": {
  "file": "music/fast_beat.mp3",
  "tags": [
   "fast",
   "beat",
   "action",
   "tez",
   "chase"
  ],
  "license": "Pixabay"
 },
 "final_stand": {
  "file": "music/final_stand.mp3",
  "tags": [
   "final",
   "stand",
   "battle",
   "epic",
   "climax"
  ],
  "license": "Pixabay"
 },
 "tension_trailer_bed": {
  "file": "music/tension_trailer_bed.mp3",
  "tags": [
   "tension",
   "trailer",
   "bed",
   "suspense"
  ],
  "license": "Pixabay"
 },
 "aggressive_trailer_intro": {
  "file": "music/aggressive_trailer_intro.mp3",
  "tags": [
   "aggressive",
   "trailer",
   "intro",
   "action"
  ],
  "license": "Pixabay"
 },
 "horror_intro_dark": {
  "file": "horror/horror_intro_dark.mp3",
  "tags": [
   "horror",
   "intro",
   "dark",
   "tension"
  ],
  "license": "Pixabay"
 },
 "logo_snap_tech": {
  "file": "transitions/logo_snap_tech.mp3",
  "tags": [
   "sting",
   "logo",
   "snap",
   "tech"
  ],
  "license": "Pixabay"
 },
 "whoosh_reverse_8": {
  "file": "transitions/whoosh_reverse_8.mp3",
  "tags": [
   "whoosh",
   "reverse",
   "transition"
  ],
  "license": "Pixabay"
 },
 "crystal_swell": {
  "file": "transitions/crystal_swell.mp3",
  "tags": [
   "swell",
   "ethereal",
   "magic",
   "transition"
  ],
  "license": "Pixabay"
 },
 "tonal_riser_cinematic_7": {
  "file": "transitions/tonal_riser_cinematic_7.mp3",
  "tags": [
   "riser",
   "cinematic",
   "transition"
  ],
  "license": "Pixabay"
 },
 "tonal_riser_cinematic_3": {
  "file": "transitions/tonal_riser_cinematic_3.mp3",
  "tags": [
   "riser",
   "cinematic",
   "transition"
  ],
  "license": "Pixabay"
 },
 "suspense_tense": {
  "file": "music/suspense_tense.mp3",
  "tags": [
   "suspense",
   "tension",
   "tense",
   "suspenseful"
  ],
  "license": "Pixabay"
 },
 "build_up_riser": {
  "file": "music/build_up_riser.mp3",
  "tags": [
   "build",
   "up",
   "riser",
   "climax"
  ],
  "license": "Pixabay"
 },
 "inspirational_epic_riser": {
  "file": "music/inspirational_epic_riser.mp3",
  "tags": [
   "inspirational",
   "epic",
   "riser",
   "hope"
  ],
  "license": "Pixabay"
 },
 "inspirational_epic_2": {
  "file": "music/inspirational_epic_2.mp3",
  "tags": [
   "inspirational",
   "epic",
   "uplift"
  ],
  "license": "Pixabay"
 },
 "soft_music": {
  "file": "music/soft_music.mp3",
  "tags": [
   "soft",
   "calm",
   "gentle",
   "narm"
  ],
  "license": "Pixabay"
 },
 "sub_bass_drop": {
  "file": "transitions/sub_bass_drop.mp3",
  "tags": [
   "sub",
   "bass",
   "drop",
   "impact",
   "hit"
  ],
  "license": "Pixabay"
 },
 "tonal_riser_smooth_1": {
  "file": "transitions/tonal_riser_smooth_1.mp3",
  "tags": [
   "riser",
   "smooth",
   "transition"
  ],
  "license": "Pixabay"
 },
 "tonal_riser_smooth_6": {
  "file": "transitions/tonal_riser_smooth_6.mp3",
  "tags": [
   "riser",
   "smooth",
   "transition"
  ],
  "license": "Pixabay"
 },
 "tonal_riser_cinematic_4": {
  "file": "transitions/tonal_riser_cinematic_4.mp3",
  "tags": [
   "riser",
   "cinematic",
   "transition"
  ],
  "license": "Pixabay"
 },
 "whoosh_1": {
  "file": "transitions/whoosh_1.mp3",
  "tags": [
   "whoosh",
   "swoosh",
   "transition"
  ],
  "license": "Pixabay"
 },
 "whoosh_2": {
  "file": "transitions/whoosh_2.mp3",
  "tags": [
   "whoosh",
   "swoosh",
   "transition"
  ],
  "license": "Pixabay"
 },
 "trailer_hit_marker": {
  "file": "transitions/trailer_hit_marker.mp3",
  "tags": [
   "hit",
   "impact",
   "marker",
   "trailer"
  ],
  "license": "Pixabay"
 },
 "tension_riser_atlas": {
  "file": "transitions/tension_riser_atlas.mp3",
  "tags": [
   "riser",
   "tension",
   "build"
  ],
  "license": "Pixabay"
 },
 "tension_riser_2": {
  "file": "transitions/tension_riser_2.mp3",
  "tags": [
   "riser",
   "tension",
   "suspense"
  ],
  "license": "Pixabay"
 },
 "epic_transition": {
  "file": "transitions/epic_transition.mp3",
  "tags": [
   "epic",
   "transition",
   "swell"
  ],
  "license": "Pixabay"
 },
 "time_transition": {
  "file": "transitions/time_transition.mp3",
  "tags": [
   "time",
   "transition",
   "warp"
  ],
  "license": "Pixabay"
 },
 "trailer_slam_hit": {
  "file": "transitions/trailer_slam_hit.mp3",
  "tags": [
   "slam",
   "hit",
   "trailer",
   "impact"
  ],
  "license": "Pixabay"
 },
 "quartz_drift": {
  "file": "transitions/quartz_drift.mp3",
  "tags": [
   "drift",
   "transition",
   "ethereal"
  ],
  "license": "Pixabay"
 },
 "riser_inspirational": {
  "file": "music/riser_inspirational.mp3",
  "tags": [
   "riser",
   "inspirational",
   "hope",
   "build"
  ],
  "license": "Pixabay"
 },
 "dramatic_whoosh_hit": {
  "file": "transitions/dramatic_whoosh_hit.mp3",
  "tags": [
   "whoosh",
   "dramatic",
   "hit",
   "impact"
  ],
  "license": "Pixabay"
 },
 "whoosh_cine_1": {
  "file": "transitions/whoosh_cine_1.mp3",
  "tags": [
   "whoosh",
   "cinematic",
   "transition"
  ],
  "license": "Pixabay"
 },
 "whoosh_cine_2": {
  "file": "transitions/whoosh_cine_2.mp3",
  "tags": [
   "whoosh",
   "cinematic",
   "transition"
  ],
  "license": "Pixabay"
 },
 "whoosh_cine_3": {
  "file": "transitions/whoosh_cine_3.mp3",
  "tags": [
   "whoosh",
   "cinematic",
   "transition"
  ],
  "license": "Pixabay"
 },
 "whoosh_cine_4": {
  "file": "transitions/whoosh_cine_4.mp3",
  "tags": [
   "whoosh",
   "cinematic",
   "transition"
  ],
  "license": "Pixabay"
 },
 "whoosh_cine_5": {
  "file": "transitions/whoosh_cine_5.mp3",
  "tags": [
   "whoosh",
   "cinematic",
   "transition"
  ],
  "license": "Pixabay"
 },
 "whoosh_cine_6": {
  "file": "transitions/whoosh_cine_6.mp3",
  "tags": [
   "whoosh",
   "cinematic",
   "transition"
  ],
  "license": "Pixabay"
 },
 "riser_leberch": {
  "file": "music/riser_leberch.mp3",
  "tags": [
   "riser",
   "build",
   "tension"
  ],
  "license": "Pixabay"
 },
 "riser_music_leberch": {
  "file": "music/riser_music_leberch.mp3",
  "tags": [
   "riser",
   "music",
   "build"
  ],
  "license": "Pixabay"
 },
 "tension_riser_leberch": {
  "file": "music/tension_riser_leberch.mp3",
  "tags": [
   "riser",
   "tension",
   "suspense"
  ],
  "license": "Pixabay"
 },
 "ambient_dark_dreamscape": {
  "file": "music/ambient_dark_dreamscape.mp3",
  "tags": [
   "ambient",
   "dark",
   "dreamscape",
   "mystic"
  ],
  "license": "Pixabay"
 },
 "ambient_piano": {
  "file": "music/ambient_piano.mp3",
  "tags": [
   "ambient",
   "piano",
   "soft",
   "calm"
  ],
  "license": "Pixabay"
 },
 "drone_deep": {
  "file": "music/drone_deep.mp3",
  "tags": [
   "drone",
   "deep",
   "dark",
   "bed"
  ],
  "license": "Pixabay"
 },
 "ambient_business": {
  "file": "music/ambient_business.mp3",
  "tags": [
   "ambient",
   "business",
   "clean",
   "background"
  ],
  "license": "Pixabay"
 },
 "tibetan_dreams": {
  "file": "music/tibetan_dreams.mp3",
  "tags": [
   "tibetan",
   "meditation",
   "spiritual",
   "bowl"
  ],
  "license": "Pixabay"
 },
 "ambient_soft": {
  "file": "music/ambient_soft.mp3",
  "tags": [
   "ambient",
   "soft",
   "calm",
   "bed"
  ],
  "license": "Pixabay"
 },
 "drone_cyberpunk": {
  "file": "music/drone_cyberpunk.mp3",
  "tags": [
   "drone",
   "cyberpunk",
   "tech",
   "dark"
  ],
  "license": "Pixabay"
 },
 "ambient_dark_2": {
  "file": "music/ambient_dark_2.mp3",
  "tags": [
   "ambient",
   "dark",
   "tension",
   "bed"
  ],
  "license": "Pixabay"
 },
 "ambient_dreamy": {
  "file": "music/ambient_dreamy.mp3",
  "tags": [
   "ambient",
   "dreamy",
   "soft",
   "romantic"
  ],
  "license": "Pixabay"
 },
 "ambient_clean": {
  "file": "music/ambient_clean.mp3",
  "tags": [
   "ambient",
   "clean",
   "neutral",
   "bed"
  ],
  "license": "Pixabay"
 },
 "ambient_inspiration": {
  "file": "music/ambient_inspiration.mp3",
  "tags": [
   "ambient",
   "inspiration",
   "hope",
   "uplift"
  ],
  "license": "Pixabay"
 },
 "ambient_dystopian": {
  "file": "music/ambient_dystopian.mp3",
  "tags": [
   "ambient",
   "dystopian",
   "dark",
   "future"
  ],
  "license": "Pixabay"
 },
 "ambient_horror_creepy": {
  "file": "music/ambient_horror_creepy.mp3",
  "tags": [
   "ambient",
   "horror",
   "creepy",
   "dark"
  ],
  "license": "Pixabay"
 },
 "drone_tanpura_divine": {
  "file": "music/drone_tanpura_divine.mp3",
  "tags": [
   "tanpura",
   "drone",
   "divine",
   "mandir"
  ],
  "license": "Pixabay"
 },
 "ambient_leberch": {
  "file": "music/ambient_leberch.mp3",
  "tags": [
   "ambient",
   "bed",
   "calm"
  ],
  "license": "Pixabay"
 },
 "timelapse_bg": {
  "file": "music/timelapse_bg.mp3",
  "tags": [
   "timelapse",
   "background",
   "journey"
  ],
  "license": "Pixabay"
 },
 "ambient_soft_2": {
  "file": "music/ambient_soft_2.mp3",
  "tags": [
   "ambient",
   "soft",
   "calm",
   "sleep"
  ],
  "license": "Pixabay"
 },
 "drone_tanpura_432": {
  "file": "music/drone_tanpura_432.mp3",
  "tags": [
   "tanpura",
   "drone",
   "432hz",
   "meditation"
  ],
  "license": "Pixabay"
 },
 "ambient_landscape": {
  "file": "music/ambient_landscape.mp3",
  "tags": [
   "ambient",
   "landscape",
   "nature",
   "wide"
  ],
  "license": "Pixabay"
 },
 "drone_ambient": {
  "file": "music/drone_ambient.mp3",
  "tags": [
   "drone",
   "ambient",
   "bed",
   "tension"
  ],
  "license": "Pixabay"
 },
 "drone_mirostar": {
  "file": "music/drone_mirostar.mp3",
  "tags": [
   "drone",
   "ambient",
   "bed"
  ],
  "license": "Pixabay"
 },
 "tanpura_deep_space": {
  "file": "music/tanpura_deep_space.mp3",
  "tags": [
   "tanpura",
   "raga",
   "ethereal",
   "space"
  ],
  "license": "Pixabay"
 },
 "ambient_calm_dreamscape": {
  "file": "music/ambient_calm_dreamscape.mp3",
  "tags": [
   "ambient",
   "calm",
   "dreamscape"
  ],
  "license": "Pixabay"
 },
 "drone_horror_cinematic": {
  "file": "music/drone_horror_cinematic.mp3",
  "tags": [
   "drone",
   "horror",
   "cinematic",
   "dark"
  ],
  "license": "Pixabay"
 },
 "drone_atlas": {
  "file": "music/drone_atlas.mp3",
  "tags": [
   "drone",
   "ambient",
   "bed"
  ],
  "license": "Pixabay"
 },
 "phonk_instrumental": {
  "file": "music/phonk_instrumental.mp3",
  "tags": [
   "phonk",
   "instrumental",
   "beat",
   "modern"
  ],
  "license": "Pixabay"
 },
 "dynamic_instrumental": {
  "file": "music/dynamic_instrumental.mp3",
  "tags": [
   "dynamic",
   "instrumental",
   "action"
  ],
  "license": "Pixabay"
 },
 "drone_subclair": {
  "file": "music/drone_subclair.mp3",
  "tags": [
   "drone",
   "deep",
   "bed"
  ],
  "license": "Pixabay"
 },
 "motivation": {
  "file": "music/motivation.mp3",
  "tags": [
   "motivation",
   "uplift",
   "hope",
   "sports"
  ],
  "license": "Pixabay"
 },
 "phonk_sport": {
  "file": "music/phonk_sport.mp3",
  "tags": [
   "phonk",
   "sport",
   "beat",
   "energy"
  ],
  "license": "Pixabay"
 },
 "chill_instrumental": {
  "file": "music/chill_instrumental.mp3",
  "tags": [
   "chill",
   "instrumental",
   "lofi",
   "relax"
  ],
  "license": "Pixabay"
 },
 "club_instrumental": {
  "file": "music/club_instrumental.mp3",
  "tags": [
   "club",
   "instrumental",
   "dance",
   "party"
  ],
  "license": "Pixabay"
 },
 "sport_instrumental": {
  "file": "music/sport_instrumental.mp3",
  "tags": [
   "sport",
   "instrumental",
   "energy"
  ],
  "license": "Pixabay"
 },
 "afrobeat_instrumental": {
  "file": "music/afrobeat_instrumental.mp3",
  "tags": [
   "afrobeat",
   "instrumental",
   "groove"
  ],
  "license": "Pixabay"
 },
 "phonk_2": {
  "file": "music/phonk_2.mp3",
  "tags": [
   "phonk",
   "instrumental",
   "beat"
  ],
  "license": "Pixabay"
 },
 "phonk_drift": {
  "file": "music/phonk_drift.mp3",
  "tags": [
   "phonk",
   "drift",
   "beat"
  ],
  "license": "Pixabay"
 },
 "energy_instrumental": {
  "file": "music/energy_instrumental.mp3",
  "tags": [
   "energy",
   "instrumental",
   "action"
  ],
  "license": "Pixabay"
 },
 "luxury_instrumental": {
  "file": "music/luxury_instrumental.mp3",
  "tags": [
   "luxury",
   "instrumental",
   "rich",
   "style"
  ],
  "license": "Pixabay"
 },
 "instrumental_bg": {
  "file": "music/instrumental_bg.mp3",
  "tags": [
   "instrumental",
   "background",
   "bed"
  ],
  "license": "Pixabay"
 },
 "latin_instrumental": {
  "file": "music/latin_instrumental.mp3",
  "tags": [
   "latin",
   "instrumental",
   "groove"
  ],
  "license": "Pixabay"
 },
 "summer_instrumental": {
  "file": "music/summer_instrumental.mp3",
  "tags": [
   "summer",
   "instrumental",
   "happy",
   "light"
  ],
  "license": "Pixabay"
 },
 "energy_2": {
  "file": "music/energy_2.mp3",
  "tags": [
   "energy",
   "instrumental",
   "action"
  ],
  "license": "Pixabay"
 },
 "travel_instrumental": {
  "file": "music/travel_instrumental.mp3",
  "tags": [
   "travel",
   "journey",
   "instrumental"
  ],
  "license": "Pixabay"
 },
 "upbeat_1": {
  "file": "music/upbeat_1.mp3",
  "tags": [
   "upbeat",
   "happy",
   "instrumental"
  ],
  "license": "Pixabay"
 },
 "upbeat_2": {
  "file": "music/upbeat_2.mp3",
  "tags": [
   "upbeat",
   "happy",
   "energy"
  ],
  "license": "Pixabay"
 },
 "aggressive_bass": {
  "file": "music/aggressive_bass.mp3",
  "tags": [
   "aggressive",
   "bass",
   "beat",
   "fight"
  ],
  "license": "Pixabay"
 },
 "france_instrumental": {
  "file": "music/france_instrumental.mp3",
  "tags": [
   "france",
   "instrumental",
   "chanson"
  ],
  "license": "Pixabay"
 },
 "gaming_instrumental": {
  "file": "music/gaming_instrumental.mp3",
  "tags": [
   "gaming",
   "instrumental",
   "action",
   "fast"
  ],
  "license": "Pixabay"
 },
 "trap_instrumental": {
  "file": "music/trap_instrumental.mp3",
  "tags": [
   "trap",
   "instrumental",
   "beat",
   "modern"
  ],
  "license": "Pixabay"
 },
 "bass_music": {
  "file": "music/bass_music.mp3",
  "tags": [
   "bass",
   "music",
   "groove"
  ],
  "license": "Pixabay"
 },
 "cybernetic_flow": {
  "file": "music/cybernetic_flow.mp3",
  "tags": [
   "cybernetic",
   "edm",
   "tech",
   "flow"
  ],
  "license": "Pixabay"
 },
 "chill_edm": {
  "file": "music/chill_edm.mp3",
  "tags": [
   "chill",
   "edm",
   "relax",
   "modern"
  ],
  "license": "Pixabay"
 },
 "faith_loop": {
  "file": "music/faith_loop.mp3",
  "tags": [
   "faith",
   "loop",
   "hopeful",
   "spiritual"
  ],
  "license": "Pixabay"
 },
 "deep_breath_edm": {
  "file": "music/deep_breath_edm.mp3",
  "tags": [
   "deep",
   "breath",
   "edm",
   "calm"
  ],
  "license": "Pixabay"
 },
 "jazz_fusion": {
  "file": "music/jazz_fusion.mp3",
  "tags": [
   "jazz",
   "fusion",
   "bass",
   "classy"
  ],
  "license": "Pixabay"
 },
 "dnb": {
  "file": "music/dnb.mp3",
  "tags": [
   "dnb",
   "drum",
   "bass",
   "fast",
   "chase"
  ],
  "license": "Pixabay"
 },
 "uk_bass": {
  "file": "music/uk_bass.mp3",
  "tags": [
   "uk",
   "bass",
   "beat",
   "modern"
  ],
  "license": "Pixabay"
 },
 "future_bass": {
  "file": "music/future_bass.mp3",
  "tags": [
   "future",
   "bass",
   "edm",
   "sneakers"
  ],
  "license": "Pixabay"
 },
 "the_fast_way": {
  "file": "music/the_fast_way.mp3",
  "tags": [
   "fast",
   "edm",
   "drive",
   "action"
  ],
  "license": "Pixabay"
 },
 "elli": {
  "file": "music/elli.mp3",
  "tags": [
   "electronic",
   "edm",
   "groove"
  ],
  "license": "Pixabay"
 },
 "zynth_syza": {
  "file": "music/zynth_syza.mp3",
  "tags": [
   "synth",
   "electronic",
   "tech"
  ],
  "license": "Pixabay"
 },
 "pulse_drift": {
  "file": "music/pulse_drift.mp3",
  "tags": [
   "pulse",
   "drift",
   "electronic",
   "tension"
  ],
  "license": "Pixabay"
 },
 "stings_bings": {
  "file": "music/stings_bings.mp3",
  "tags": [
   "sting",
   "electronic",
   "alert"
  ],
  "license": "Pixabay"
 },
 "iron_loop": {
  "file": "music/iron_loop.mp3",
  "tags": [
   "iron",
   "loop",
   "industrial",
   "dark"
  ],
  "license": "Pixabay"
 },
 "brass_trap": {
  "file": "music/brass_trap.mp3",
  "tags": [
   "brass",
   "trap",
   "energy",
   "swagger"
  ],
  "license": "Pixabay"
 },
 "hiphop_energy": {
  "file": "music/hiphop_energy.mp3",
  "tags": [
   "hiphop",
   "energy",
   "beat",
   "modern"
  ],
  "license": "Pixabay"
 },
 "low_signal": {
  "file": "music/low_signal.mp3",
  "tags": [
   "low",
   "signal",
   "dark",
   "mystery"
  ],
  "license": "Pixabay"
 },
 "ignition_fire": {
  "file": "music/ignition_fire.mp3",
  "tags": [
   "ignition",
   "fire",
   "soul",
   "motivation"
  ],
  "license": "Pixabay"
 },
 "bach_air": {
  "file": "music/bach_air.mp3",
  "tags": [
   "bach",
   "classical",
   "soft",
   "sad",
   "elegant"
  ],
  "license": "Pixabay"
 },
 "adult_chill": {
  "file": "music/adult_chill.mp3",
  "tags": [
   "chill",
   "lounge",
   "calm",
   "evening"
  ],
  "license": "Pixabay"
 },
 "dreams": {
  "file": "music/dreams.mp3",
  "tags": [
   "dreams",
   "soft",
   "dreamy",
   "calm"
  ],
  "license": "Pixabay"
 },
 "smoothy_evening": {
  "file": "music/smoothy_evening.mp3",
  "tags": [
   "evening",
   "smooth",
   "lounge",
   "shaam"
  ],
  "license": "Pixabay"
 },
 "submerged_focus": {
  "file": "music/submerged_focus.mp3",
  "tags": [
   "focus",
   "drift",
   "ambient",
   "underwater"
  ],
  "license": "Pixabay"
 },
 "oriental_techno": {
  "file": "music/oriental_techno.mp3",
  "tags": [
   "oriental",
   "techno",
   "indian",
   "modern"
  ],
  "license": "Pixabay"
 },
 "gymnopedie": {
  "file": "music/gymnopedie.mp3",
  "tags": [
   "satie",
   "classical",
   "piano",
   "sad",
   "elegant"
  ],
  "license": "Pixabay"
 },
 "alpha_state_drift": {
  "file": "music/alpha_state_drift.mp3",
  "tags": [
   "alpha",
   "drift",
   "ambient",
   "focus"
  ],
  "license": "Pixabay"
 },
 "action_trap": {
  "file": "music/action_trap.mp3",
  "tags": [
   "action",
   "trap",
   "dynamic",
   "fight"
  ],
  "license": "Pixabay"
 },
 "cold_current": {
  "file": "music/cold_current.mp3",
  "tags": [
   "cold",
   "current",
   "dark",
   "tech"
  ],
  "license": "Pixabay"
 },
 "mono_shadow": {
  "file": "music/mono_shadow.mp3",
  "tags": [
   "shadow",
   "dark",
   "ambient",
   "mystery"
  ],
  "license": "Pixabay"
 },
 "static_bloom": {
  "file": "music/static_bloom.mp3",
  "tags": [
   "static",
   "bloom",
   "texture",
   "dark"
  ],
  "license": "Pixabay"
 },
 "aggressive_trap": {
  "file": "music/aggressive_trap.mp3",
  "tags": [
   "aggressive",
   "trap",
   "fight",
   "energy"
  ],
  "license": "Pixabay"
 },
 "deep_work": {
  "file": "music/deep_work.mp3",
  "tags": [
   "focus",
   "deep",
   "work",
   "ambient"
  ],
  "license": "Pixabay"
 },
 "submerged_beta_focus": {
  "file": "music/submerged_beta_focus.mp3",
  "tags": [
   "beta",
   "focus",
   "underwater",
   "ambient"
  ],
  "license": "Pixabay"
 },
 "strong_female": {
  "file": "music/strong_female.mp3",
  "tags": [
   "strong",
   "female",
   "power",
   "uplift"
  ],
  "license": "Pixabay"
 },
 "pink_noise_rain": {
  "file": "music/pink_noise_rain.mp3",
  "tags": [
   "pink noise",
   "rain",
   "bed",
   "calm"
  ],
  "license": "Pixabay"
 },
 "cognitive_flow": {
  "file": "music/cognitive_flow.mp3",
  "tags": [
   "focus",
   "flow",
   "ambient",
   "study"
  ],
  "license": "Pixabay"
 },
 "oriental_hard_techno": {
  "file": "music/oriental_hard_techno.mp3",
  "tags": [
   "oriental",
   "hard",
   "techno",
   "indian"
  ],
  "license": "Pixabay"
 },
 "industrial_flow": {
  "file": "music/industrial_flow.mp3",
  "tags": [
   "industrial",
   "flow",
   "machine",
   "dark"
  ],
  "license": "Pixabay"
 },
 "countdown_teaser": {
  "file": "music/countdown_teaser.mp3",
  "tags": [
   "countdown",
   "teaser",
   "trailer",
   "build"
  ],
  "license": "Pixabay"
 },
 "bond_theme": {
  "file": "music/bond_theme.mp3",
  "tags": [
   "bond",
   "spy",
   "theme",
   "thriller"
  ],
  "license": "Pixabay"
 },
 "phonk_trap": {
  "file": "music/phonk_trap.mp3",
  "tags": [
   "phonk",
   "trap",
   "beat",
   "energy"
  ],
  "license": "Pixabay"
 },
 "phonk_house": {
  "file": "music/phonk_house.mp3",
  "tags": [
   "phonk",
   "house",
   "beat",
   "dance"
  ],
  "license": "Pixabay"
 },
 "afro_bongo_loop": {
  "file": "music/afro_bongo_loop.mp3",
  "tags": [
   "afro",
   "bongo",
   "tribal",
   "loop"
  ],
  "license": "Pixabay"
 },
 "intense_drum_loop": {
  "file": "music/intense_drum_loop.mp3",
  "tags": [
   "drum",
   "intense",
   "loop",
   "action"
  ],
  "license": "Pixabay"
 },
 "glitch_bass": {
  "file": "music/glitch_bass.mp3",
  "tags": [
   "glitch",
   "bass",
   "stutter",
   "tech"
  ],
  "license": "Pixabay"
 },
 "groovy_bass_trap": {
  "file": "music/groovy_bass_trap.mp3",
  "tags": [
   "groovy",
   "bass",
   "trap",
   "swagger"
  ],
  "license": "Pixabay"
 },
 "giddy_uploop": {
  "file": "music/giddy_uploop.mp3",
  "tags": [
   "giddy",
   "upbeat",
   "loop",
   "fun"
  ],
  "license": "Pixabay"
 },
 "pirate_bay_loop": {
  "file": "music/pirate_bay_loop.mp3",
  "tags": [
   "pirate",
   "adventure",
   "loop",
   "sea"
  ],
  "license": "Pixabay"
 },
 "hypnotic_hiphop": {
  "file": "music/hypnotic_hiphop.mp3",
  "tags": [
   "hiphop",
   "hypnotic",
   "beat",
   "urban"
  ],
  "license": "Pixabay"
 },
 "jazzy_loop": {
  "file": "music/jazzy_loop.mp3",
  "tags": [
   "jazz",
   "laid back",
   "loop",
   "classy"
  ],
  "license": "Pixabay"
 },
 "caribbean_happy": {
  "file": "music/caribbean_happy.mp3",
  "tags": [
   "caribbean",
   "happy",
   "summer",
   "loop"
  ],
  "license": "Pixabay"
 },
 "fiddle_ballad": {
  "file": "music/fiddle_ballad.mp3",
  "tags": [
   "fiddle",
   "ballad",
   "folk",
   "village"
  ],
  "license": "Pixabay"
 },
 "afro_bongo_fast": {
  "file": "music/afro_bongo_fast.mp3",
  "tags": [
   "afro",
   "bongo",
   "fast",
   "tribal"
  ],
  "license": "Pixabay"
 },
 "lamento_ninfa": {
  "file": "music/lamento_ninfa.mp3",
  "tags": [
   "lamento",
   "sad",
   "remix",
   "classical"
  ],
  "license": "Pixabay"
 },
 "happy_joy_loop": {
  "file": "music/happy_joy_loop.mp3",
  "tags": [
   "happy",
   "joy",
   "loop",
   "fun"
  ],
  "license": "Pixabay"
 },
 "mythical_moments": {
  "file": "music/mythical_moments.mp3",
  "tags": [
   "mythical",
   "magic",
   "fantasy",
   "epic"
  ],
  "license": "Pixabay"
 },
 "fusion_drum_110": {
  "file": "music/fusion_drum_110.mp3",
  "tags": [
   "drum",
   "loop",
   "fusion",
   "110bpm"
  ],
  "license": "Pixabay"
 },
 "rock_melody": {
  "file": "music/rock_melody.mp3",
  "tags": [
   "rock",
   "distorted",
   "melody",
   "energy"
  ],
  "license": "Pixabay"
 },
 "edm_132_cmajor": {
  "file": "music/edm_132_cmajor.mp3",
  "tags": [
   "edm",
   "loop",
   "132bpm",
   "dance"
  ],
  "license": "Pixabay"
 },
 "drums_claps": {
  "file": "music/drums_claps.mp3",
  "tags": [
   "drums",
   "claps",
   "beat",
   "loop"
  ],
  "license": "Pixabay"
 },
 "rock_guitar_loop": {
  "file": "music/rock_guitar_loop.mp3",
  "tags": [
   "rock",
   "guitar",
   "loop",
   "energy"
  ],
  "license": "Pixabay"
 },
 "house_rap": {
  "file": "music/house_rap.mp3",
  "tags": [
   "house",
   "rap",
   "theme",
   "urban"
  ],
  "license": "Pixabay"
 },
 "race_loop": {
  "file": "music/race_loop.mp3",
  "tags": [
   "race",
   "fast",
   "loop",
   "chase"
  ],
  "license": "Pixabay"
 },
 "fighting_spirit": {
  "file": "music/fighting_spirit.mp3",
  "tags": [
   "fight",
   "spirit",
   "battle",
   "motivation"
  ],
  "license": "Pixabay"
 },
 "fashion_abstract": {
  "file": "music/fashion_abstract.mp3",
  "tags": [
   "fashion",
   "abstract",
   "modern",
   "style"
  ],
  "license": "Pixabay"
 },
 "michaelavon_short": {
  "file": "music/michaelavon_short.mp3",
  "tags": [
   "theme",
   "urban",
   "rap",
   "short"
  ],
  "license": "Pixabay"
 },
 "coach_theme": {
  "file": "music/coach_theme.mp3",
  "tags": [
   "coach",
   "sport",
   "motivation",
   "theme"
  ],
  "license": "Pixabay"
 },
 "dnb_synapse": {
  "file": "music/dnb_synapse.mp3",
  "tags": [
   "dnb",
   "drum",
   "bass",
   "fast"
  ],
  "license": "Pixabay"
 },
 "ceremonial_dance": {
  "file": "music/ceremonial_dance.mp3",
  "tags": [
   "ceremonial",
   "tribal",
   "dance",
   "ritual"
  ],
  "license": "Pixabay"
 },
 "dnb_slow": {
  "file": "music/dnb_slow.mp3",
  "tags": [
   "dnb",
   "slow",
   "bass",
   "dark"
  ],
  "license": "Pixabay"
 },
 "countdown_cook": {
  "file": "music/countdown_cook.mp3",
  "tags": [
   "countdown",
   "tension",
   "build"
  ],
  "license": "Pixabay"
 },
 "upbeat_drums": {
  "file": "music/upbeat_drums.mp3",
  "tags": [
   "drums",
   "upbeat",
   "beat",
   "loop"
  ],
  "license": "Pixabay"
 },
 "dub_reggae_78": {
  "file": "music/dub_reggae_78.mp3",
  "tags": [
   "dub",
   "reggae",
   "groove",
   "78bpm"
  ],
  "license": "Pixabay"
 }
}

# hamare SFX naam -> library naam
ALIAS = {
    "scream": "scream_woman", "man_scream": "man_scream", "laugh": "man_laugh",
    "angry": "man_angry", "yell": "man_yell", "fall": "man_fall", "grunt": "man_grunt",
    "talk": "talk_crowd_1", "braam": "braam_dark", "monster": "monster_lurk",
    "chair": "knock_1", "plate": "paper_1", "bed": "steps_parquet",
    "stairs": "steps_stairs_up", "run": "steps_parquet",
    "gate_open": "door_open_a", "gate_close": "door_close_a", "panic": "crowd_panic", "sting": "scary_sting", "hit": "horror_hit",
    "horror": "horror_ambience", "rain": "rain", "wind": "wind",
}

# ek hi tarah ki kai awaazein — baari-baari
VARIANTS = {
    "ambient": ["ambient_calm_dreamscape", "ambient_soft_2", "ambient_leberch", "ambient_landscape", "ambient_inspiration", "ambient_dystopian", "ambient_horror_creepy", "timelapse_bg", "ambient_soft", "ambient_clean", "ambient_dreamy", "ambient_piano",
                "ambient_dark_2", "ambient_dark_dreamscape", "ambient_business"],
    "drone": ["drone_horror_cinematic", "drone_mirostar", "drone_atlas", "drone_subclair", "drone_tanpura_divine", "drone_tanpura_432", "drone_ambient", "drone_deep", "drone_cyberpunk", "ambient_dark_dreamscape"],
    "meditation": ["tibetan_dreams", "meditation_indian", "mauna_meditation"],
    "transition": ["whoosh_1", "whoosh_2", "trailer_slam_hit", "trailer_hit_marker", "epic_transition", "time_transition", "quartz_drift", "tension_riser_atlas", "tension_riser_2", "sub_bass_drop", "whoosh_reverse_8", "crystal_swell", "tonal_riser_cinematic_7", "tonal_riser_cinematic_3", "logo_snap_tech", "tonal_riser_1", "tonal_riser_3", "tonal_riser_smooth_2", "tonal_riser_smooth_7",
                   "tonal_riser_smooth_8", "tonal_riser_cinematic_8", "whoosh_reverse_low",
                   "choir_transition", "cyber_crash"],
    "riser": ["riser_leberch", "riser_music_leberch", "tension_riser_leberch", "tonal_riser_1", "tonal_riser_3", "tonal_riser_cinematic_8"],
    "whoosh": ["dramatic_whoosh_hit", "whoosh_cine_1", "whoosh_cine_2", "whoosh_cine_3", "whoosh_cine_4", "whoosh_cine_5", "whoosh_cine_6", "whoosh_1", "whoosh_2", "whoosh_reverse_low", "whoosh_reverse_8"],
    "sting": ["logo_sting_synthwave", "cyber_crash"],
    "epic": ["final_stand", "aggressive_trailer_intro", "epic_hybrid_orchestra", "deep_breath_epic", "countdown_action", "trailer_lacrimosa", "trailer_teaser"],
    "trailer": ["trailer_teaser", "trailer_lacrimosa", "countdown_action"],
    "comedy": ["fun_banana_slip", "fun_guitar"],
    "chicken": ["chicken_coop"],
    "murgi": ["chicken_coop"],
    "lullaby": ["lullaby_baby"],
    "romantic": ["romantic_crazy_love", "romantic_guitar"],
    "fun": ["fun_guitar"],
    "forest": ["forest_celtic_mystic_2", "forest_walk_band", "forest_hiding_place", "forest_relax_2", "forest_folk_song", "forest_celtic_mystic", "forest_dark_ambient", "forest_tales_orchestral", "forest_tales_halloween", "forest_lofi_piano", "forest_enchanted", "forest_reflections", "forest_epic_ballad", "forest_morning_harp", "forest_guitar", "forest_whispers", "forest_morning_mist", "forest_pathway", "forest_spirits_piano", "forest_relax", "forest_scent", "forest_harp", "forest_adventure"],
    "halloween": ["halloween_bgm", "halloween_bgm_2", "halloween_scary", "halloween_spooky", "forest_tales_halloween"],
    "gate_open": ["door_open_a", "door_open_b", "door_open_c"],
    "door": ["electric_gate_open", "gate_close_2", "door_creaky_steel_wood", "iron_gate_courtyard", "door_lock_open", "door_iron_creak_old", "door_iron_creak_2", "iron_door_open_2", "door_open_a", "door_open_b", "door_open_c"],
    "gate_close": ["door_close_a", "door_close_b", "door_close_c"],
    "talk": ["talk_crowd_1", "talk_crowd_2"],
    "death": ["monster_death_scream", "sirenhead_death", "dark_knight_death", "man_falling_death", "scraped_death"],
    "siren": ["siren_voice_line", "siren_menace", "siren_laugh_evil", "siren_laugh_2"],
    "magic": ["necromancer_spell", "disappear", "dark_evil_code"],
    "_siren_old": ["siren_voice_line", "siren_menace"],
    "scream": ["scream_woman", "man_scream", "man_scream_2", "man_death_scream"],
    "cry": ["man_cry", "man_sniffle", "man_cry_2"],
    "girl_cry": ["girl_cry_1", "child_cry_2"],
    "coins": ["coin_drop_1", "coin_drop_2", "coins_dropping", "coin_clatter", "coins_falling_1", "coins_rattle", "coins_jingle", "coins_counting", "coins_spilled", "coins_on_plate", "coins_in_bowl", "coins_burst", "jackpot_coins"],
    "_old_coins": ["coin_drop_1", "coin_drop_2", "coins_dropping", "coins_1" if False else "coin_drop_1"],
    "baby": ["baby_cry_1", "baby_cry_2", "baby_cry_3", "baby_laugh_1", "baby_laugh_2", "baby_giggle_1", "baby_giggle_2", "baby_babble", "baby_moan", "baby_noises"],
    "woman_cry": ["woman_cry_1", "woman_cry_2", "soft_cry_1"],
    "kitten": ["kitten_1"],
    "child": ["child_cry_1", "baby_cry_1"],
    "zombie": ["baby_zombie"],
    "vampire": ["vampire_hiss", "vampire_hiss_2", "vampire_growl", "vampire_laugh", "vampire_laugh_2", "vampire_shriek"],
    "vampire_line": ["vampire_line_hunger", "vampire_line_humans", "vampire_line_soul", "vampire_line"],
    "screech": ["screech"],
    "transition": ["transition_swoosh"],
    "shankh": ["shankh"],
    "temple": ["temple_ambient", "temple_bell", "aarti_ganga", "monk_om", "sacral_pad", "tanpura", "sacral_chant"],
    "magic": ["holy_aura", "christmas_magic", "angel_choir", "light_magic", "incant", "heal_spell", "sound_of_god"],
    "church": ["church_ambience", "cathedral_organ", "psalm23"],
    "choir": ["holy_chorus", "choir_short", "angel_choir"],
    "howl": ["ghost_howl_1", "ghost_howl_2", "wind_howl_window"],
    "ghost": ["ghost", "ghosts_past", "ghost_past_2"],
    "bell": ["temple_bell", "shofar"],
    "jungle": ["jungle_nature"],
    "train": ["train_passing_2", "train_fast_indian", "train_horn_faux", "locomotive_horn", "city_train_depot", "train_running", "train_interior_indian", "train_interior_old", "train_interior_old_2", "train_whistle", "train_pass_1", "train_pass_2", "train_pass_3", "train_running", "train_approaching", "train_crossing", "train_horn_1", "train_horn_2", "train_horn_3", "train_horn_4", "train_horn_distant", "train_horn_lofi", "train_horn_comical", "train_departure", "train_passing_cars", "train_loud", "train_rural_india", "train_distant_birds", "steam_train", "steam_train_2", "train_horn_5", "train_horn_6", "train_horn_pass_distant", "train_horn_passing", "train_horn_asia", "train_horn_lofi_2", "train_horn_blast", "train_musical", "diesel_horn", "train_horn_7", "train_horn_8", "train_horn_fade", "train_horn_horror", "station_ambience"],
    "machine": ["grinder_axe", "grinder_start", "mixer_beater", "coffee_grinder", "food_mixer", "mixer_2", "coffee_machine", "coffee_grinder_2", "concrete_mixer", "metal_scrape"],
    "vinyl": ["vinyl_scratch", "vinyl_crackle", "vinyl_loop"],
    "blender": ["blender_1", "blender_2", "blender_3", "blender_4"],
    "dragon": ["dragon_roar", "dragon_growl", "dinosaur_roar"],
    "tiger": ["tiger_roar_1", "tiger_roar_2", "tiger_roar_3", "tiger_roar_4", "tiger_roar_5", "tiger_roar_6", "tiger_attack", "big_cats_mix"],
    "cat": ["cat_meow_1", "cat_meow_2", "cat_meow_3", "cat_meow_4", "cat_meow_5", "cat_meow_6", "cat_meow_7", "cat_meow_8", "cat_meow_9", "cat_meow_10"],
    "monster": ["monster_roar_1", "monster_roar_2", "monster_roar_3", "monster_growl_1", "monster_lurk"],
    "wolf": ["wolf_growl"],
    "roar": ["roar_1", "tiger_roar_1", "monster_roar_1"],
    "alien": ["alien_roar"],
    "coffee": ["coffee_machine", "coffee_grinder_2", "coffee_grinder_3", "coffee_stir"],
    "horn": ["horn_1"],
    "sehnai": ["drum_sehnai"],
    "gayatri": ["mantra_gayatri", "mantra_gayatri_chorus", "mantra_gayatri_soft", "mantra_gayatri_meaning"],
    "ram": ["mantra_ram", "mantra_ram_loop"],
    "waheguru": ["mantra_waheguru"],
    "mantra": ["mantra_lakshmi", "mantra_krishna_love", "mantra_kali", "mantra_mrityunjaya", "mantra_shivaya", "mantra_govinda"],
    "sitar": ["sitar_raaga"],
    "bhajan": ["bhajan_maithili", "bhajan_rajasthani", "bhajan_desert", "bhajan_vishnu"],
    "meditation": ["meditation_indian"],
    "folk": ["folk_song_marathi", "bhajan_desert"],
    "dhol": ["dhol_1", "dhol_2", "dhol_shadi", "dhol_wedding", "dhol_bass", "dhol_beats"],
    "knock": ["knock_1", "knock_2", "knock_3", "knock_4", "knock_5", "knock_6", "knock_7", "knock_8", "knock_9", "door_pounding"],
    "peacock": ["peacock"],
    "dog": ["dog_bark_1", "dog_bark_2", "dog_bark_3", "dog_bark_4", "dog_bark_5", "dog_bark_6", "dog_bark_7", "dog_bark_8", "dog_bark_small", "dogs_howl", "dog_variety", "dog_barking_long"],
    "knock_fast": ["knock_fast"],
    "bang": ["door_bang_echo"],
    "clock": ["grandfather_12", "old_clock_chime", "cuckoo_clock", "clock_twelve", "clock_tower_12", "westminster_hour", "clock_bell_1", "clock_11pm_rain"],
    "bell": ["bell_chime", "temple_bell", "shofar", "clock_bell_1"],
    "shaadi": ["dhol_wedding", "dhol_shadi", "mehndi_beat"],
    "paper": ["paper_1", "paper_2", "paper_turn", "paper_rip_2", "paper_flutter"],
    "paper_rip": ["paper_rip_2", "paper_rip_fast", "paper_tear"],
    "rain": ["rain_gentle_1", "rain_gentle_7", "rain_midday", "rain_window", "rain_on_glass", "thunderstorm"],
    "rain_tin": ["rain_tin_roof", "rain_tin_metal", "rain_tent"],
    "stairs": ["steps_stairs_up", "steps_stairs_down", "steps_grass_to_stairs"],
    "gravel": ["steps_gravel", "steps_gravel_2", "steps_forest_road"],
    "soil": ["steps_soil", "steps_dirt"],
    "horse": ["horse_neigh", "horse_neigh_2", "horse_walk", "horse_walk_3", "horse_gallop", "horse_snort"],
    "fire": ["fire_crackle_1", "fireplace", "crackle_1", "crackle_2", "fire_whoosh"],
    "vinyl": ["vinyl_crackle", "vinyl_loop"],
    "hooves": ["horse_hooves"],
    "mud": ["steps_muddy_road", "steps_puddle"],
    "shoe": ["steps_shoe"],
    "grass": ["steps_frozen_grass", "steps_grass_to_stairs"],
    "village": ["village_ambience"],
    "thunder": ["thunderstorm"],
    "birds": ["bird_chirps_4", "birds_forest_1", "birds_forest_2", "birds_chirp_1", "birds_chirp_2", "bird_chirp_3", "birds_forest_chirp", "birds_in_rain"],
    "water": ["water_relax", "pour_glass", "kettle_pour", "boiling"],
    "chai": ["chai_1", "stirring_tea", "tea_boil", "kettle_cup", "boiling"],
    "cooker": ["cooker_whistle", "cooker_1", "cooker_2", "cooker_release", "cooker_low"],
    "boil": ["boil_2", "boil_3", "boil_long", "boiling"],
    "bubbles": ["bubbles"],
    "underwater": ["underwater"],
    "lava": ["lava_loop"],
}

INDOOR_WORDS = ["घर", "कमरा", "हवेली", "अंदर", "सीढ़ी", "छत", "room", "indoor", "hall", "floor"]
OUTDOOR_WORDS = ["सड़क", "बाहर", "मिट्टी", "खेत", "बाज़ार", "गली", "road", "street", "outdoor", "concrete"]
FAST_WORDS = ["दौड़", "भाग", "तेज़", "तेज", "जल्दी", "fast", "run", "daud"]
SLOW_WORDS = ["धीरे", "आहिस्ता", "dheere", "slow"]
SCARY_WORDS = ["डरावन", "डर", "आहट", "scary", "horror", "धीमी"]

_ROT = {}


def _index():
    if os.path.exists(INDEX):
        try:
            data = json.load(open(INDEX, encoding="utf-8"))
            if data:
                return data
        except Exception:
            pass
    return DEFAULT_INDEX


def entries():
    return _index()


def info(name):
    key = find(name)
    if not key:
        return None
    m = dict(_index()[key])
    m["key"] = key
    return m


def _ff():
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def pick_footsteps(text=""):
    t = str(text or "")
    if any(w in t for w in INDOOR_WORDS):
        return "footsteps_hallway" if ("सीढ़ी" in t or "हवेली" in t) else "footsteps_parquet"
    if any(w in t for w in OUTDOOR_WORDS):
        return "footsteps_concrete"
    return "footsteps_parquet"


def speed_for(name, context=""):
    t = str(context or "")
    if any(w in t for w in FAST_WORDS):
        return 1.25
    if any(w in t for w in SCARY_WORDS):
        return 0.82
    if any(w in t for w in SLOW_WORDS):
        return 0.88
    return 1.0


def find(name, context=""):
    """Naam/tag se best key — exact pehle, phir poora shabd (rain ko brain me na pakde)."""
    low = str(name or "").lower().strip()
    if not low:
        return None
    if low in ("footsteps", "kadam", "कदम", "steps", "walking", "chalna", "चलना"):
        return pick_footsteps(context)
    idx = _index()
    if low in idx:
        return low
    alias = ALIAS.get(low)
    if alias and alias in idx:
        return alias
    for key, meta in idx.items():
        tags = [t.lower() for t in meta.get("tags", [])]
        if low in tags:
            return key
    pat = re.compile(r"(^|[^a-z])" + re.escape(low) + r"([^a-z]|$)")
    for key, meta in idx.items():
        if pat.search(key.lower()):
            return key
        if any(pat.search(t.lower()) for t in meta.get("tags", [])):
            return key
    return None


def _variant(name, context=""):
    if name in ("footsteps", "kadam", "कदम", "steps", "walking", "chalna", "चलना"):
        return pick_footsteps(context)
    if name in VARIANTS:
        lst = VARIANTS[name]
        i = _ROT.get(name, 0) % len(lst)
        _ROT[name] = i + 1
        return lst[i]
    return find(name, context)


# har library sound par safai: hiss/noise hatao, awaaz saaf karo
CLEAN_AF = ("afftdn=nr=12:nf=-45:tn=1,highpass=f=70,"
            "agate=threshold=0.02:ratio=3:range=0.10:attack=5:release=150,"
            "loudnorm=I=-19:TP=-2:LRA=9")


def fetch(name, context=""):
    """Asli library file ka wav (44.1k mono) — na mile to None."""
    key = _variant(name, context)
    if not key:
        return None
    meta = _index().get(key)
    if not meta:
        return None
    src = os.path.join(LIB, meta["file"])
    if not os.path.exists(src):
        return None
    sp = speed_for(name, context)
    out = os.path.join(CACHE, f"{key}_{sp:.2f}.wav")
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        return out
    cmd = [_ff(), "-loglevel", "error", "-y", "-i", src, "-ac", "1", "-ar", "44100"]
    if abs(sp - 1.0) > 0.02:
        cmd += ["-filter:a", f"atempo={sp:.3f}"]
    cmd += [out]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 5000:
        print("LIB_OK", key, "speed", sp, meta.get("license", ""), flush=True)
        return out
    print("LIB_FAIL", key, (r.stderr or b"")[-80:], flush=True)
    return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("library me:", len(_index()), "sounds")
        for k, v in list(_index().items())[:100]:
            print(f"  {k:20s} {v['file']}")
        sys.exit(0)
    for n in sys.argv[1:]:
        print(n, "->", fetch(n))
