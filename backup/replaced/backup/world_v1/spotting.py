#!/usr/bin/env python3
"""
Spotting — kahani padh kar "cue sheet" banana: kaun si awaaz, kis pal, kahan, kab tak.
(Film me sound designer yahi karta hai: har line par baith kar awaazein 'spot' karta hai.)

Do dimaag, dono local:
  1. Niyam (rules)  : knowledge/sound-events.json + harkat.py — hamesha chalta hai, tez, pakka.
  2. Local LLM      : Ollama (localhost) — optional. Woh chhupi/indirect awaazein pakadta hai
                      ("usne gilaas mez par rakha" -> glass_set). Uske naye sujhaav missing-sounds.json me.
Dono ko jod kar ek cue sheet. Jo awaaz system ke paas nahi, woh knowledge/missing-sounds.json me
likhi jaati hai — agle round me agent/insaan use jod deta hai (self-evolving).

python tools/world/spotting.py --marks story_local.json --out cues.json [--llm qwen2.5:7b]
"""
from __future__ import annotations
import argparse, json, re, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import harkat as H

EVENTS_PATH = ROOT / "knowledge" / "sound-events.json"
MISSING_PATH = ROOT / "knowledge" / "missing-sounds.json"

def load_events(p=EVENTS_PATH):
    return json.load(open(p, encoding="utf-8"))

_L = "\u0900-\u0963\u0966-\u097Fa-zA-Z0-9"   # \u0964/\u0965 = । ॥ (viraam) shabd ka hissa nahi     # Devanagari + Latin (matra bhi shabd ka hissa)
def _rx(w):
    """Poora shabd: 'आग' 'आगे' me nahi milega. Shabd ke ant me '*' = jad (stem), jaise 'बैठ*'."""
    stem = w.endswith("*"); w = w.rstrip("*")
    return re.compile(f"(?<![{_L}]){re.escape(w.lower())}" + ("" if stem else f"(?![{_L}])"))
_RXC = {}
def _pos(text, w):
    if w not in _RXC: _RXC[w] = _rx(w)
    m = _RXC[w].search(text.lower()); return m.start() if m else -1

def has(text, words):
    return any(w and _pos(text, w) >= 0 for w in words)

def first_pos(text, words):
    ps = [_pos(text, w) for w in words if w]; ps = [p for p in ps if p >= 0]
    return min(ps) if ps else -1

def t_at(line, pos):
    """Akshar ki jagah -> samay (ASR word timestamps ho to unse)."""
    if pos < 0: return line["start"]
    if line.get("words"):
        acc = 0
        for w in line["words"]:
            acc += len(w.get("w", "")) + 1
            if acc > pos: return w["start"]
    return line["start"] + (line["end"] - line["start"]) * (pos + 1) / max(1, len(line["text"]))

def find_stop(lines, i, t_from, stop_words, total, max_s):
    """State kab khatm: is line me start ke baad, ya agli lines me pehla stop-shabd."""
    for j in range(i, len(lines)):
        ln = lines[j]; txt = ln["text"]
        p = first_pos(txt, stop_words)
        if p >= 0:
            t = t_at(ln, p)
            if t > t_from + 0.3: return min(t, t_from + max_s), j
    return min(total, t_from + max_s), None


# ---------------------------------------------------------------- niyam (rules)
def spot_rules(lines, total, kb, wmap):
    ev = kb["events"]; cues = []; missing = []
    # 1) events (+ states)
    for i, ln in enumerate(lines):
        txt = ln["text"]; hit_any = False
        for name, e in ev.items():
            if not e.get("kw") or not has(txt, e["kw"]): continue
            hit_any = True
            p = first_pos(txt, e["kw"])
            t = ln["start"] + 0.1 if e.get("at") == "line" else t_at(ln, p)
            c = dict(event=name, t=round(t, 3), pan=e.get("pan", 0.0), dist=e.get("dist", 1.5), level=e.get("level", -16),
                     line=i, source="rule", _pos=p, _learned=bool(e.get("learned")))
            st = e.get("state")
            if st and st.get("loop"):
                t1, j = find_stop(lines, i, t, st.get("stop", []), total, st.get("max_s", 30))
                c["t_end"] = round(t1, 3)
                if e.get("then"): cues.append(dict(event=e["then"], t=round(t1, 3), pan=ev[e["then"]].get("pan", 0),
                                                   dist=ev[e["then"]].get("dist", 1), level=ev[e["then"]].get("level", -16), line=j if j is not None else i, source="rule"))
            elif e.get("at") == "line":
                nxt = lines[i + 1]["start"] if i + 1 < len(lines) else total
                c["t_end"] = round(min(total, nxt + 1.0), 3)
            if e.get("repeat"): c["repeat"] = e["repeat"]
            cues.append(c)
        # ek hi shabd par seekhi hui (asli) awaaz ho to synth wali hatao; "prefer" = yeh ho to main nahi
        mine = [c for c in cues if c.get("line") == i and "_pos" in c]
        names = {c["event"] for c in mine}
        for c in list(mine):
            if set(ev[c["event"]].get("prefer", [])) & names: cues.remove(c); mine.remove(c)
        for c in mine:
            if not c["_learned"] and any(o["_learned"] and abs(o["_pos"] - c["_pos"]) <= 3 for o in mine if o is not c):
                cues.remove(c)
        # 2) awaaz wala shabd hai par event nahi -> missing (seekhne ke liye)
        if not hit_any and has(txt, kb["sound_verbs"]["words"]):
            acts = [k for k, w in H.ACTIONS.items() if has(txt, w)]
            if not acts: missing.append({"text": txt, "line": i})
    # 3) aawa-jaahi (motion) -> kadam + darwaza
    mo = kb["motion"]; motion = []
    for i, ln in enumerate(lines):
        txt = ln["text"]; pan = ln.get("pan", 0.0)
        nxt = lines[i + 1]["start"] if i + 1 < len(lines) else total
        def tw(words): return t_at(ln, first_pos(txt, words))
        moving = H.has(txt, H.ACTIONS["run"]) or H.has(txt, H.ACTIONS["walk"])
        door_cued = any(c["line"] == i and c["event"].startswith("door") for c in cues)
        if has(txt, mo["enter"]):
            t = tw(mo["enter"])
            if not door_cued: motion.append(dict(kind="door", t=t - 1.2))
            if not moving: motion.append(dict(kind="approach", t0=t - 0.6, t1=t + 2.4, pan0=-0.6, pan1=pan))
        elif has(txt, mo["approach"]) and not moving:
            t = tw(mo["approach"]); motion.append(dict(kind="approach", t0=max(0, t - 2.5), t1=t + 0.4, pan0=-0.7, pan1=pan))
        if has(txt, mo["exit"]):
            t = tw(mo["exit"])
            if not moving: motion.append(dict(kind="leave", t0=t, t1=t + 2.8, pan0=pan, pan1=0.7))
            motion.append(dict(kind="door_close", t=t + (3.0 if not moving else 1.2)))
        elif has(txt, mo["leave"]) and not moving:
            t = tw(mo["leave"]); motion.append(dict(kind="leave", t0=t, t1=t + 3.2, pan0=pan, pan1=0.75))
        if has(txt, mo["sit"]): motion.append(dict(kind="sit", t=tw(mo["sit"]), pan=pan))
        elif has(txt, mo["stand"]) and not has(txt, ["उठाया", "उठा लिया", "uthaya"]): motion.append(dict(kind="stand", t=tw(mo["stand"]), pan=pan))
    return cues, motion, missing

def place_timeline(lines, total, kb):
    """Andar/bahar: shabd se badalta hai, warna pichhla jaari."""
    P = kb["places"]; cur = None; spans = []; t0 = 0.0
    for ln in lines:
        txt = ln["text"]; new = None
        pi, po = first_pos(txt, P["indoor"]), first_pos(txt, P["outdoor"])
        if pi >= 0 and (po < 0 or pi > po): new = "indoor"
        elif po >= 0: new = "outdoor"
        if ln.get("place"): new = ln["place"]
        if new and new != cur:
            if cur: spans.append((t0, ln["start"], cur))
            cur, t0 = new, ln["start"]
    spans.append((t0, total, cur or "outdoor"))
    return [dict(t0=round(a, 3), t1=round(b, 3), place=p) for a, b, p in spans]

def weather_timeline(lines, total, kb):
    W = kb["weather"]["states"]; active = {}; spans = []
    for ln in lines:
        txt = ln["text"]
        for s, d in W.items():
            if "start" not in d: continue
            if s not in active and has(txt, d["start"]) and not has(txt, d.get("stop", [])):
                active[s] = t_at(ln, first_pos(txt, d["start"]))
            elif s in active and has(txt, d.get("stop", [])):
                t1 = t_at(ln, first_pos(txt, d["stop"]))
                spans.append(dict(state=s, t0=round(active.pop(s), 3), t1=round(t1, 3)))
                if d.get("after"):
                    spans.append(dict(state=d["after"], t0=round(t1, 3), t1=round(min(total, t1 + W[d["after"]].get("dur_s", 10)), 3)))
        # subah aayi to raat khatm (aur ulta)
        if "night" in active and has(txt, W["morning"]["start"]):
            spans.append(dict(state="night", t0=round(active.pop("night"), 3), t1=ln["start"]))
        if "morning" in active and has(txt, W["night"]["start"]):
            spans.append(dict(state="morning", t0=round(active.pop("morning"), 3), t1=ln["start"]))
    for s, t0 in active.items():
        mx = W[s].get("max_s")
        spans.append(dict(state=s, t0=round(t0, 3), t1=round(min(total, t0 + mx) if mx else total, 3)))
    return spans


# ---------------------------------------------------------------- local LLM (optional)
LLM_PROMPT = """Tum ek film sound designer ho. Neeche Hindi kahani ki lines hain (number: text).
Har line ke liye batao kaun si awaazein background ya kirdaar ke saath aani chahiye — jo likhi hain AUR jo
dikhai nahi deti par asli duniya me hoti (jaise 'chai di' -> cup rakhne ki khanak).
Sirf is list ke naam use karo: {allowed}
Agar zaroori awaaz list me nahi hai to use "new:<chhota_english_naam>" likho.
Sirf JSON do, aur kuch nahi: {{"cues":[{{"line":<number>,"event":"<naam>","when":"start|word|end","word":"<line ka shabd>","pan":-1..1,"dist":0.5..8}}]}}

{lines}"""

def spot_llm(lines, kb, model, host="http://127.0.0.1:11434", timeout=120):
    allowed = sorted(set(kb["events"].keys()) | {"walk", "run", "stop", "fall", "jump", "twig", "splash", "howl", "growl", "thunder"})
    body = "\n".join(f"{i}: {l['text']}" for i, l in enumerate(lines))
    prompt = LLM_PROMPT.format(allowed=", ".join(allowed), lines=body)
    req = urllib.request.Request(host + "/api/generate", data=json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json",
                                 "options": {"temperature": 0.2}}).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = json.loads(r.read())["response"]
    except Exception as ex:
        return [], [], f"LLM band/nahi mila ({ex.__class__.__name__}) — sirf niyam chale"
    return parse_llm(txt, lines, kb) + (None,)

def parse_llm(txt, lines, kb):
    try:
        data = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
    except Exception:
        return [], []
    cues, new = [], []
    for c in data.get("cues", []):
        try:
            i = int(c["line"]); ln = lines[i]; name = str(c["event"]).strip()
        except Exception:
            continue
        when = c.get("when", "word")
        if when == "start": t = ln["start"] + 0.1
        elif when == "end": t = ln["end"] + 0.05
        else: t = t_at(ln, first_pos(ln["text"], [c.get("word", "")]))
        if name.startswith("new:") or (name not in kb["events"] and name not in H.ACTIONS and name not in ("howl", "growl")):
            new.append({"text": ln["text"], "line": i, "suggest": name.replace("new:", "")}); continue
        e = kb["events"].get(name, {})
        cues.append(dict(event=name, t=round(t, 3), pan=float(c.get("pan", e.get("pan", 0))), dist=float(c.get("dist", e.get("dist", 1.5))),
                         level=e.get("level", -16), line=i, source="llm"))
    return cues, new

def merge(rule_cues, llm_cues):
    out = list(rule_cues)
    for c in llm_cues:
        if not any(r["event"] == c["event"] and abs(r["t"] - c["t"]) < 1.5 for r in out): out.append(c)
    return sorted(out, key=lambda c: c["t"])

def log_missing(items, story="?"):
    """Jo awaaz system ke paas nahi — yahan jama hoti hai. Agent/insaan isse sound-events.json badhata hai."""
    if not items: return
    db = json.load(open(MISSING_PATH, encoding="utf-8")) if MISSING_PATH.exists() else {"_note": "Kahaniyon me aayi awaazein jo system ke paas nahi thi. Inhe sound-events.json + awaazein.py me jodo.", "items": []}
    for it in items:
        key = it.get("suggest") or it["text"][:60]
        old = next((x for x in db["items"] if x["key"] == key), None)
        if old: old["count"] += 1; old["last_story"] = story
        else: db["items"].append({"key": key, "example": it["text"], "suggest": it.get("suggest"), "count": 1, "last_story": story, "added": time.strftime("%Y-%m-%d")})
    MISSING_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- poora spot
def spot(lines, total, kb, wmap, llm=None, story="?"):
    cues, motion, missing = spot_rules(lines, total, kb, wmap)
    note = None
    if llm:
        lc, new, note = spot_llm(lines, kb, llm)
        cues = merge(cues, lc); missing += new
    actions, emo = H.plan_actions(lines, total, wmap)
    for c in cues: c.pop("_pos", None); c.pop("_learned", None)
    sheet = {
        "cues": sorted(cues, key=lambda c: c["t"]), "motion": motion, "actions": actions,
        "emotions": [dict(t0=a, t1=b, e=e) for a, b, e in emo],
        "places": place_timeline(lines, total, kb), "weather": weather_timeline(lines, total, kb),
        "phone_lines": [i for i, l in enumerate(lines) if l.get("phone") or "(फ़ोन)" in l.get("who", "") or "(phone)" in l.get("who", "")],
        "missing": missing, "llm": note or (llm and "ok") or "off",
    }
    log_missing(missing, story)
    return sheet

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--marks", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--llm", default=None, help="Ollama model, jaise qwen2.5:7b (optional)")
    a = ap.parse_args()
    mk = json.load(open(a.marks, encoding="utf-8")); lines = mk.get("lines", mk) if isinstance(mk, dict) else mk
    total = max(l["end"] for l in lines) + 2
    sys.path.insert(0, str(HERE)); import duniya as D
    sheet = spot(lines, total, load_events(), D.load_map(), a.llm, Path(a.marks).stem)
    Path(a.out).write_text(json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cues {len(sheet['cues'])} · motion {len(sheet['motion'])} · actions {len(sheet['actions'])} · missing {len(sheet['missing'])} · llm {sheet['llm']}")
