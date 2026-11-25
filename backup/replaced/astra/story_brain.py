#!/usr/bin/env python3
"""
ASTRA — Story Brain (v0.11 ka story intelligence, safe wrapper).

Kaam: kahani ki lines padh kar batata hai ki kis line me kaunsi awaaz honi chahiye —
unke `astra_audio.story_intelligence` se, par hum apne library ke naam me badal kar.

Niyam:
  - KABHI render nahi rokta (fail-open). Kuch na mile to khali list.
  - Sirf wahi sound deta hai jo hamare mahaul (env) me allowed hai.
  - Koi network nahi, koi naya paisa nahi.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# unka event naam  ->  hamare library ke naam (pehla jo mile wahi)
EVENT_MAP = {
    "footsteps": ["footsteps"],
    "door": ["gate_open", "door"],
    "rain": ["rain"],
    "wind": ["wind_blowing", "wind"],
    "vehicle": ["car", "train"],
    "crowd": ["crowd"],
    "animal_bird": ["birds", "peacock", "dog"],
    "fire": ["fire"],
    "water": ["water"],
    "breathing": ["breath", "heartbeat"],
    "clothing_jewellery": ["cloth_rustle", "paper_1"],
    "foliage": ["leaves"],
    "bell_chime": ["temple_bell", "bell"],
    "conch": ["shankh"],
    "crying_sobbing": ["cry_1", "plors_sob"],
    "laughter": ["laugh", "baby_laughs_2"],
    "metal_glass": ["glass_break", "metal"],
    "impact": ["fall_impact", "thud"],
}

# mahaul ke hisaab se allowed (sfx_extra ki hi list — do jagah niyam nahi)
def _allowed(env):
    try:
        import sfx_extra
        return sfx_extra.ENV_ALLOW.get(env, set())
    except Exception:
        return set()


def _ok_in_env(name, env):
    al = _allowed(env)
    if not al:
        return True
    return any(name.startswith(a) or a.startswith(name) for a in al)


def suggest_lines(ep, verbose=False):
    """{line_text: [sound names]} — har line ke liye sujhav. Fail par {}."""
    out = {}
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from astra_audio.story_intelligence import analyze_script_text

        # kahani ko script jaisa likho (speaker: text), taaki unka analyzer line-wise cue de
        script_lines, index = [], []
        for sc in ep.get("scenes", []):
            env = sc.get("env", "neutral")
            for ln in sc.get("lines", []):
                if isinstance(ln, (list, tuple)):
                    spk = str(ln[0]) if ln else "madhur"
                    txt = str(ln[1]) if len(ln) > 1 else ""
                else:
                    spk, txt = "madhur", str(ln)
                script_lines.append(f"{spk}: {txt}")
                index.append((txt, env))
        if not script_lines:
            return {}

        rep = analyze_script_text("\n".join(script_lines))
        # source_line = script_lines me 1-based number
        for sc in rep.get("scenes", []):
            for cue in sc.get("sound_cues", []):
                if cue.get("cue_type") != "sound_event":
                    continue
                ev = cue.get("event")
                ln_no = cue.get("source_line")
                if not ev or not isinstance(ln_no, int) or ln_no < 1 or ln_no > len(index):
                    continue
                txt, env = index[ln_no - 1]
                for cand in EVENT_MAP.get(ev, []):
                    if _ok_in_env(cand, env):
                        out.setdefault(txt, [])
                        if cand not in out[txt]:
                            out[txt].append(cand)
                        break
        if verbose:
            print("STORY_BRAIN cues:", len(out), flush=True)
    except Exception as e:
        if verbose:
            print("STORY_BRAIN_SKIP", str(e)[:80], flush=True)
        return {}
    return out


def mood_of(ep):
    """Poori kahani ka mood (unke analyzer se) — sirf report ke liye."""
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from astra_audio.story_intelligence import analyze_script_text
        txt = "\n".join(
            f"{ln[0]}: {ln[1]}" if isinstance(ln, (list, tuple)) and len(ln) > 1 else str(ln)
            for sc in ep.get("scenes", []) for ln in sc.get("lines", []))
        rep = analyze_script_text(txt)
        moods = [s.get("lexical_mood") for s in rep.get("scenes", []) if s.get("lexical_mood")]
        return moods
    except Exception:
        return []
