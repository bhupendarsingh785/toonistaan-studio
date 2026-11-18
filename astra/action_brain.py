#!/usr/bin/env python3
"""
ASTRA — Action Brain (v0.16 ka action foley, hamare library se juda).

Kaam: kahani ki lines me **physical action** dhoondhta hai (rassi khuli, gaandh kasi,
taala khula, khidki se kooda, paani me utra, seedhi chadhi...) aur usko
hamare library ke asli sound se jodta hai.

Niyam:
  - KABHI render nahi rokta (fail-open).
  - Sirf wahi sound deta hai jo library me asli me hai.
  - Jo action ka sound nahi hai, usko "missing" list me likh deta hai
    (taaki pata rahe kya bhejna hai).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# unka action  ->  hamare library ke variant naam (pehla jo mile)
ACTION_MAP = {
    # ---- rassi (rope) ----
    "rope_uncoil": ["paper_flutter", "cloth_rustle"],
    "rope_uncoil_or_drag": ["paper_flutter", "cloth_rustle"],
    "rope_friction": ["paper_flutter", "metalscrape_2"],
    "rope_release_friction": ["paper_flutter"],
    "rope_tension": ["paper_flutter"],
    "rope_grip_and_tension": ["paper_flutter"],
    "rope_load_tension": ["paper_flutter"],
    "rope_bear_weight": ["paper_flutter"],
    "rope_tension_test": ["paper_flutter"],
    "rope_wrap_anchor": ["paper_flutter"],
    "rope_anchor_contact": ["paper_flutter", "metal"],
    "rope_and_anchor": ["paper_flutter"],
    "rope_descend": ["paper_flutter", "footsteps"],
    "rope_descent": ["paper_flutter", "footsteps"],
    "rope_climb": ["paper_flutter", "footsteps"],
    "rope_release": ["paper_flutter"],
    "rope_slide_and_wall_contact": ["paper_flutter", "footsteps"],
    "knot_tighten": ["paper_flutter"],
    # ---- khidki / deewar ----
    "window_open": ["door_open_a", "gate_open"],
    "window_open_creak": ["door_iron_creak_old", "door_open_a"],
    "window_mechanism": ["door_lock_open"],
    "window_exit": ["door_open_a"],
    "window_sill_exit": ["footsteps"],
    "window_entry_jump": ["fall_impact"],
    "jump_window_in": ["fall_impact"],
    "jump_down": ["fall_impact"],
    "landing": ["fall_impact"],
    "wall_foot_contact": ["footsteps"],
    # ---- seedhi / darwaza ----
    "ladder_climb": ["steps_stairs_up", "footsteps"],
    "ladder_rung_and_hand_contact": ["steps_stairs_up"],
    "door_handle": ["door_lock_open", "door_open_a"],
    "door_handle_latch": ["door_lock_open"],
    "key_lock": ["door_lock_open"],
    "key_lock_mechanism": ["door_lock_open"],
    "door_open": ["gate_open"],
    "door_close": ["gate_close"],
    # ---- paani / zameen ----
    "water_entry": ["water"],
    "water_entry_splash": ["water"],
    "water_impact_and_submersion": ["water"],
    "footsteps_leaves": ["footsteps", "leaves"],
    "bush_push": ["leaves"],
}


def _resolves(name):
    """Library me asli file hai ya nahi."""
    try:
        sys.path.insert(0, HERE)
        import library as L
        return bool(L._variant(name, ""))
    except Exception:
        return False


def suggest_lines(ep, verbose=False):
    """{line_text: [sound names]} — action ke hisaab se. Fail par {}."""
    out = {}
    missing = set()
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from astra_audio.action_foley import analyze_action_chains

        lines, index = [], []
        for sc in ep.get("scenes", []):
            for ln in sc.get("lines", []):
                if isinstance(ln, (list, tuple)) and len(ln) > 1:
                    txt = str(ln[1])
                else:
                    txt = str(ln)
                lines.append(txt)
                index.append(txt)
        if not lines:
            return {}

        plan = analyze_action_chains("\n".join(lines))
        for chain in plan.get("action_chains", []):
            ln_no = chain.get("source_line")
            if not isinstance(ln_no, int) or ln_no < 1 or ln_no > len(index):
                continue
            txt = index[ln_no - 1]
            for ev in chain.get("events", []):
                act = ev.get("action")
                cands = ACTION_MAP.get(act) or []
                picked = None
                for c in cands:
                    if _resolves(c):
                        picked = c
                        break
                if picked:
                    out.setdefault(txt, [])
                    if picked not in out[txt]:
                        out[txt].append(picked)
                else:
                    missing.add(act)
        if verbose:
            print("ACTION_BRAIN cues:", len(out), "| missing sounds:", sorted(missing)[:8], flush=True)
    except Exception as e:
        if verbose:
            print("ACTION_BRAIN_SKIP", str(e)[:80], flush=True)
        return {}
    return out


def missing_actions(ep):
    """Kaunse action ke liye hamare paas sound nahi hai (report ke liye)."""
    miss = set()
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from astra_audio.action_foley import analyze_action_chains
        txt = "\n".join(
            (str(ln[1]) if isinstance(ln, (list, tuple)) and len(ln) > 1 else str(ln))
            for sc in ep.get("scenes", []) for ln in sc.get("lines", []))
        plan = analyze_action_chains(txt)
        for chain in plan.get("action_chains", []):
            for ev in chain.get("events", []):
                act = ev.get("action")
                cands = ACTION_MAP.get(act) or []
                if not any(_resolves(c) for c in cands):
                    miss.add(act)
    except Exception:
        pass
    return sorted(miss)
