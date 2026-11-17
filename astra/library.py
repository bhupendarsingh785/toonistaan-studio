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
 "spirit_gain_2": {
  "file": "voices/spirit_gain_2.mp3",
  "tags": [
   "spirit",
   "aatma",
   "आत्मा",
   "gain"
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
 }
}

# hamare SFX naam -> library naam
ALIAS = {
    "scream": "scream_woman", "man_scream": "man_scream", "laugh": "man_laugh",
    "angry": "man_angry", "yell": "man_yell", "fall": "man_fall", "grunt": "man_grunt",
    "talk": "talk_crowd_1", "braam": "braam_dark", "monster": "monster_lurk",
    "panic": "crowd_panic", "sting": "scary_sting", "hit": "horror_hit",
    "horror": "horror_ambience", "rain": "rain", "wind": "wind",
}

# ek hi tarah ki kai awaazein — baari-baari
VARIANTS = {
    "gate_open": ["door_open_a", "door_open_b", "door_open_c"],
    "door": ["door_open_a", "door_open_b", "door_open_c"],
    "gate_close": ["door_close_a", "door_close_b", "door_close_c"],
    "talk": ["talk_crowd_1", "talk_crowd_2"],
    "scream": ["scream_woman", "man_scream", "man_scream_2", "man_death_scream"],
    "cry": ["man_cry", "man_sniffle"],
    "vampire": ["vampire_hiss", "vampire_hiss_2", "vampire_growl", "vampire_laugh", "vampire_laugh_2", "vampire_shriek"],
    "vampire_line": ["vampire_line_hunger", "vampire_line_humans", "vampire_line_soul", "vampire_line"],
    "screech": ["screech"],
    "transition": ["transition_swoosh"],
    "temple": ["temple_ambient", "temple_bell", "aarti_ganga", "monk_om", "sacral_pad", "tanpura", "sacral_chant"],
    "magic": ["holy_aura", "christmas_magic", "angel_choir", "light_magic", "incant", "heal_spell", "sound_of_god"],
    "church": ["church_ambience", "cathedral_organ", "psalm23"],
    "choir": ["holy_chorus", "choir_short", "angel_choir"],
    "ghost": ["ghost", "ghosts_past", "ghost_past_2"],
    "bell": ["temple_bell", "shofar"],
    "jungle": ["jungle_nature"],
    "train": ["train_pass_1", "train_pass_2", "train_pass_3", "train_running", "train_approaching", "train_crossing", "train_horn_1", "train_horn_2", "train_horn_3", "train_horn_4", "train_horn_distant", "train_horn_lofi", "train_horn_comical", "train_departure", "train_passing_cars", "train_loud", "train_rural_india", "train_distant_birds", "steam_train", "steam_train_2", "train_horn_5", "train_horn_6", "train_horn_pass_distant", "train_horn_passing", "train_horn_asia", "train_horn_lofi_2", "train_horn_blast", "train_musical", "diesel_horn", "train_horn_7", "train_horn_8", "train_horn_fade", "train_horn_horror", "station_ambience"],
    "machine": ["grinder_axe", "grinder_start", "mixer_beater", "coffee_grinder", "food_mixer", "mixer_2", "coffee_machine", "coffee_grinder_2", "concrete_mixer", "metal_scrape"],
    "vinyl": ["vinyl_scratch", "vinyl_crackle", "vinyl_loop"],
    "blender": ["blender_1", "blender_2", "blender_3", "blender_4"],
    "dragon": ["dragon_roar", "dragon_growl", "dinosaur_roar"],
    "alien": ["alien_roar"],
    "coffee": ["coffee_machine", "coffee_grinder_2", "coffee_grinder_3", "coffee_stir"],
    "horn": ["horn_1"],
    "sehnai": ["drum_sehnai"],
    "dhol": ["dhol_1", "dhol_2", "dhol_shadi", "dhol_wedding", "dhol_bass", "dhol_beats"],
    "knock": ["knock_1", "knock_2", "knock_3", "knock_4", "knock_5", "knock_6", "knock_7", "knock_8", "knock_9", "door_pounding"],
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
    "birds": ["birds_in_rain"],
    "water": ["water_relax", "pour_glass", "kettle_pour", "boiling"],
    "chai": ["tea_boil", "kettle_cup", "boiling"],
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
