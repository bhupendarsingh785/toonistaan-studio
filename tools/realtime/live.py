#!/usr/bin/env python3
"""
Live — banate waqt hi poori jaanch aur turant sudhaar (real-time checker + auto-fix), 100% local.

Har line ke liye (line render hote hi, agli line ke render ke saath-saath, alag worker me):
  1. Pehle-se-sudhaar : shabdkosh (seekhi likhai) render se PEHLE laga do
  2. Gates (<50 ms)    : clipping, echo (F0-safe), brightness, gap, ant-kata, khaali
  3. Kaan (ASR)        : line suno -> akshar-akshar milaan -> kaun sa akshar, kya bana, kis kism ki galti
  4. Nirantarta        : kirdaar ka sur/raftaar/zor/chamak/rang profile se mila
  5. Sudhaar (max 3)   : line par hi (gain/EQ/gap) ya dobara render (respelling, dheema, pitch, no_fx) -> phir jaancho
  6. Yaad              : galti-bahi (kaun sa akshar kamzor), shabdkosh (kaunsi likhai kaam aayi), voice-profiles
Output: live log + manifest JSON (har line ka qa) + galti report (markdown).

Story pipeline se jodna:
    chk = LiveChecker(tts, ear, engine="piper")
    fut = chk.submit(line, wav, sr)            # story_local.py me har line render ke turant baad
    final_wav, report = fut.result()            # jodne se pehle
"""
from __future__ import annotations
import argparse, json, math, subprocess, sys, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import akshar as A, gates as G, kaan as K, nirantarta as N, bahi as B, sudhaar as S, bhaav as BH

KN = ROOT / "knowledge"
RULES = {"max_attempts": 3, "max_candidates": 4, "doubt_p": 0.45, "workers": 2}
_print_lock = threading.Lock()

def log(msg):
    with _print_lock: print(time.strftime("%H:%M:%S"), msg, flush=True)

# ---------------------------------------------------------------- TTS adapters
class EspeakTTS:
    """Test/draft engine. voices: {who: (voice, speed, pitch)}"""
    name = "espeak"
    def __init__(self, voices, sr=22050): self.v = voices; self.sr = sr
    def render(self, text, who, params=None):
        p = params or {}; voice, speed, pitch = self.v.get(who, self.v["narrator"])
        speed = int(p.get("speed_override", speed) * p.get("rate", 1.0))
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            subprocess.run(["espeak-ng", "-v", voice, "-s", str(speed), "-p", str(pitch), "-w", f.name, text], check=True, capture_output=True)
            r = subprocess.run(["ffmpeg", "-v", "error", "-i", f.name, "-f", "f32le", "-ac", "1", "-ar", str(self.sr), "-"], capture_output=True, check=True)
        y = np.frombuffer(r.stdout, np.float32).astype(np.float64)
        nz = np.flatnonzero(np.abs(y) > 0.005)
        if len(nz):                                    # aage 10 ms, peeche 60 ms poonchh rakho (kaato mat)
            y = y[max(0, nz[0] - int(0.01 * self.sr)): nz[-1] + int(0.06 * self.sr)].copy()
            k = int(0.015 * self.sr); y[-k:] *= np.linspace(1, 0, k)
        y = y * 0.5                                      # −6 dB headroom: bhaav ka zor badhe to clip na ho
        return post(y, self.sr, p), self.sr

class PiperTTS:
    """Asli engine. models: {who: model.onnx}. rate -> length_scale (dheema = bada length_scale)."""
    name = "piper"
    def __init__(self, models, length_scale=1.0, sr=22050, exe="piper"):
        self.m, self.ls, self.sr, self.exe = models, length_scale, sr, exe
    def render(self, text, who, params=None):
        p = params or {}
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            subprocess.run([self.exe, "--model", self.m.get(who, self.m["narrator"]), "--length_scale", str(self.ls / p.get("rate", 1.0)),
                            "--output_file", f.name], input=text.encode(), check=True, capture_output=True)
            r = subprocess.run(["ffmpeg", "-v", "error", "-i", f.name, "-f", "f32le", "-ac", "1", "-ar", str(self.sr), "-"], capture_output=True, check=True)
        return post(np.frombuffer(r.stdout, np.float32).astype(np.float64), self.sr, p), self.sr

def post(y, sr, p):
    """Render ke baad ke param: pitch_st (sur), gain_db, presence_db."""
    if abs(p.get("pitch_st", 0)) > 0.05:
        import librosa
        r0 = np.sqrt(np.mean(y ** 2)) + 1e-12
        y = librosa.effects.pitch_shift(y.astype(np.float32), sr=sr, n_steps=p["pitch_st"]).astype(np.float64)
        y *= r0 / (np.sqrt(np.mean(y ** 2)) + 1e-12)          # pitch_shift level gira deta hai (~4 dB) — wapas
    if p.get("gain_db"): y = y * 10 ** (p["gain_db"] / 20)
    if p.get("presence_db"): y = G.presence(y, sr, p["presence_db"])
    return y

# ---------------------------------------------------------------- checker
def _bh_slim(b):
    if not b: return None
    out = {"target": b["target"], "ready": b.get("ready", False), "desc": BH.describe(b)}
    if b.get("ready"):
        out.update({"found": b["est"]["top"], "found_frac": b["est"]["top_frac"], "frac": b["frac"], "ok": b["ok"], "dev": b["dev"],
                    "words": [{"word": w["word"], "why": w["why"], "need": {k: w["need"][k] for k in ("len", "f0", "energy", "pause_ms")},
                               "got": {k: w["got"][k] for k in ("len", "f0", "energy", "gap_before_ms")}, "ok": w["ok"]} for w in b["word_judge"]]})
    return out

class LiveChecker:
    def __init__(self, tts, ear, engine=None, voice_rules=None, knowledge=KN, rules=None):
        self.tts, self.ear = tts, ear
        self.engine = engine or tts.name
        self.R = dict(RULES, **(rules or {}))
        self.VR = voice_rules or {}
        self.lex = S.Lexicon(knowledge / "hindi-lexicon.json")
        self.bahi = B.Bahi(knowledge / "hindi-galti-bahi.json")
        self.prof = N.Profiles(knowledge / "voice-profiles.json")
        self.yaad = BH.BhaavYaad(knowledge / "bhaav-yaad.json")
        self.pool = ThreadPoolExecutor(self.R["workers"])
        self.lock = threading.Lock()
        self.reports = []

    def ev(self, who): return f"{self.engine}/{who}"

    # ---- ek line ki poori jaanch
    def inspect(self, line, said, y, sr, params):
        t0 = time.time()
        g = G.check(y, sr, self.VR.get(line.get("who"), {}), line["text"])
        heard = self.ear.hear(y, sr, hint=said)
        cmp = A.compare(line["text"], heard["text"])
        doubt = [w["w"] for w in heard.get("words", []) if w.get("p", 1) < self.R["doubt_p"]]
        feat = N.features(y, sr, A.matra_units(line["text"]))
        ev = self.ev(line.get("who", "narrator"))
        with self.lock:
            base = self.yaad.neutral(ev); base = base if base and base.get("n", 0) >= 3 else None
            noise, calib = self.yaad.noise(ev), self.yaad.calib(ev)
        words = heard.get("words") if all(w.get("end", 0) > 0 for w in heard.get("words", [])) else None
        bh = BH.analyse(y, sr, line, base, calib, words, noise)
        emotional = bh["target"]["emotion"] != "neutral"
        with self.lock:
            cons = self.prof.check(line.get("who", "narrator"), self.engine, feat, line.get("emotion", "neutral"))
        if emotional:      # bhaav wali line: sur/raftaar/zor bhaav engine ke haath; nirantarta sirf rang (halka)
            cons = dict(cons, drift=[d for d in cons.get("drift", []) if d["what"] == "rang"], ok=True)
        bh_ok = (not bh.get("ready")) or bh["ok"]
        ok = all(x["ok"] for x in g) and cmp["hard"] == 0 and cons["ok"] and bh_ok
        return {"ok": ok, "gates": g, "heard": heard["text"], "ear_ms": heard["ms"], "cmp": cmp, "doubt": doubt,
                "consistency": cons, "feat": feat, "bhaav": bh, "ms": int((time.time() - t0) * 1000)}

    def shape(self, y, sr, line, params):
        """Bhaav ka shabd-tarashna: zor wale shabdon ko lakshya tak (lamba/ooncha/tez/ruka) + aakhri sur."""
        ev = self.ev(line.get("who", "narrator"))
        with self.lock:
            base = self.yaad.neutral(ev)
        if not base: return y
        b = BH.analyse(y, sr, line, base, self.yaad.calib(ev), None, self.yaad.noise(ev))
        plan = []
        for wj in b.get("word_judge", []):
            if wj["ok"]: continue
            n, g = wj["need"], wj["got"]
            sp = next(((s0, e0) for w, s0, e0 in b["spans"] if w == wj["word"]), None)
            if not sp: continue
            lx = float(np.clip(n["len"] / max(g["len"], 0.3), 0.85, 1.5))
            st = float(np.clip(n["f0"] - g["f0"] + 0.3 * params.get("range_boost", 0), -4, 4))
            gd = float(np.clip(n["energy"] - g["energy"], -4, 5))
            pz = max(0, n.get("pause_ms", 0) - g.get("gap_before_ms", 0))
            plan.append((sp[0], sp[1], lx, st, gd, pz))
        if plan:
            y = BH.sculpt(y, sr, b["spans"], plan)
            log(f"      ✎ shabd tarashe: " + ", ".join(f"{w} (lamba×{lx:.2f}, sur{st:+.1f}, zor{gd:+.1f}{', ruka ' + str(pz) + 'ms' if pz else ''})"
                                                    for (s0, e0, lx, st, gd, pz), w in zip(plan, [wj['word'] for wj in b['word_judge'] if not wj['ok']])))
        if abs(params.get("end_st", 0)) > 0.2 and b.get("spans"):
            b2 = BH.analyse(y, sr, line, base, None, None, self.yaad.noise(ev)) if plan else b
            y = BH.end_contour(y, sr, b2["spans"], params["end_st"])
        return y

    def _orig_word(self, text, norm_word):
        for w in text.split():
            if A.normalize(w) == norm_word: return w.strip("।,.!?\"'")
        return norm_word

    # ---- sudhaar loop
    def _try(self, i, line, ev, who, said, params, rep, er, word, cands, tried, blocking=True):
        for method, new_word, pp in cands:
            key = (er["expected"], er["word_i"], method, new_word, tuple(sorted(pp.items())))
            if key in tried: continue
            tried.add(key)
            s2 = S.apply_word(said, word, new_word) if new_word else said
            p2 = dict(params, **pp)
            y2, sr2 = self.tts.render(s2, who, p2)
            h2 = self.ear.hear(y2, sr2, hint=s2); c2 = A.compare(line["text"], h2["text"])
            still = any(e["word_i"] == er["word_i"] and e["expected"] == er["expected"] for e in c2["errors"])
            won = (not still) and c2["hard"] <= rep["cmp"]["hard"] - (1 if blocking else 0)
            with self.lock: self.bahi.record_fix(ev, er["kind"], method, won, f"{er['expected']}→{er['heard']}", new_word)
            log(f"   ↻ line {i + 1}: '{word}' [{A.KIND_HINDI[er['kind']].split(' (')[0]}{'' if blocking else ', shak'}] aazmaya '{method}'"
                + (f" → '{new_word.strip(', ')}'" if new_word and new_word.strip(', ') != word else "") + (f" rate {p2.get('rate', 1):.2f}" if 'rate' in pp else "")
                + f" → {'✓ theek' if won else '✗'}")
            if won: return (method, new_word, s2, p2, y2, sr2)
        return None

    def fix_line(self, i, line, said, y, sr, params, rep):
        who = line.get("who", "narrator"); ev = self.ev(who); applied = []
        tried, unresolved, soft_done = set(), set(), set()
        def score(r):                      # chhota = behtar: pass > kam pakki galti > bhaav lakshya ke paas
            b = r.get("bhaav", {}); bs = abs(math.log(max(b["frac"], 0.05))) if b.get("ready") and b["target"]["emotion"] != "neutral" else 0.0
            return (0 if r["ok"] else 1, r["cmp"]["hard"], round(bs, 3))
        best = (score(rep), said, y, sr, dict(params), rep)
        for attempt in range(1, self.R["max_attempts"] + 1):
            # (a) awaaz ke gate: line par hi
            changed = False
            for gr in rep["gates"]:
                if gr["ok"]: continue
                if gr["fix"] in ("gain-2", "presence+0.8", "presence-0.8", "gap0.20"):
                    y, ok = G.apply_fix(y, sr, gr["fix"], gr, line["text"]); changed |= ok; applied.append(f"{gr['gate']}:{gr['fix']}")
                elif gr["fix"] in ("rerender", "rerender_no_fx"):
                    params = dict(params, no_fx=True) if gr["fix"].endswith("no_fx") else params
                    y, sr = self.tts.render(said, who, params); changed = True; applied.append(f"{gr['gate']}:{gr['fix']}")
            # (b) nirantarta: zor/chamak line par; sur/raftaar dobara render
            for d in rep["consistency"].get("drift", []):
                fx = d["fix"]
                if d.get("severity") == "soft":
                    if attempt > 1 or "rerender" in fx: continue          # chamak: sirf ek baar halka EQ; rang: sirf darj
                if "gain_db" in fx: y = y * 10 ** (fx["gain_db"] / 20); applied.append(f"zor:{fx['gain_db']:+.1f}dB"); changed = True
                if "presence_db" in fx: y = G.presence(y, sr, fx["presence_db"]); applied.append(f"chamak:{fx['presence_db']:+.1f}dB"); changed = True
                if "rate" in fx or "pitch_st" in fx:
                    if "rate" in fx: params = dict(params, rate=params.get("rate", 1.0) / fx["rate"])
                    if "pitch_st" in fx: params = dict(params, pitch_st=params.get("pitch_st", 0) + fx["pitch_st"])
                    y, sr = self.tts.render(said, who, params); changed = True
                    applied.append(f"{d['what']}:{'rate ' + format(params.get('rate', 1), '.2f') if 'rate' in fx else 'sur ' + format(params.get('pitch_st', 0), '+.2f') + 'st'}")
            # (c) uchcharan: pakki galti — har ek ke liye ummeedwar (jo pehle aazma chuke, dobara nahi)
            hard = [e for e in rep["cmp"]["errors"] if e["severity"] == "hard" and (e["expected"], e["word_i"]) not in unresolved]
            if hard:
                er = hard[0]; word = self._orig_word(line["text"], er["word"])
                hopeless = self.bahi.hopeless(ev, er["kind"])
                if hopeless:
                    log(f"   ⓘ line {i + 1}: '{word}' [{A.KIND_HINDI[er['kind']].split(' (')[0]}] — seekha hua: is engine par yeh kism kabhi theek nahi hui ({hopeless} koshish) → seedha 'engine badlo'")
                cands = [] if hopeless else S.order_by_learning(S.candidates(word, er), self.bahi.best_methods(ev, er["kind"]))[: self.R["max_candidates"]]
                best = self._try(i, line, ev, who, said, params, rep, er, word, cands, tried, True) if cands else None
                if best:
                    method, new_word, said, params, y, sr = best; changed = True
                    applied.append(f"uchcharan:{er['expected']}→{method}")
                    if new_word and new_word.strip(", ") != word:
                        with self.lock: self.lex.learn(ev, word, new_word.strip(", "), er["kind"], 1, method)
                else:
                    unresolved.add((er["expected"], er["word_i"])); changed = True
                    applied.append(f"uchcharan:{er['expected']} ANSULJHA (engine kamzor — doosra engine aazmao)")
            # (d) shak: ek-do khaas tareeke (line nahi rukti)
            elif self.R.get("fix_soft", True):
                for er in [e for e in rep["cmp"]["errors"] if e["severity"] == "soft" and (e["expected"], e["word_i"]) not in soft_done][:2]:
                    soft_done.add((er["expected"], er["word_i"])); word = self._orig_word(line["text"], er["word"])
                    if self.bahi.hopeless(ev, er["kind"]): continue               # seekha: is kism ki shak yahan theek nahi hoti
                    cands = [c for c in S.candidates(word, er) if c[0] in S.SOFT_METHODS][:2]
                    best = self._try(i, line, ev, who, said, params, rep, er, word, cands, tried, False)
                    if best:
                        method, new_word, said, params, y, sr = best; changed = True
                        applied.append(f"shak:{er['expected']}→{method}")
                        if new_word and new_word.strip(", ") != word:
                            with self.lock: self.lex.learn(ev, word, new_word.strip(", "), er["kind"], 0, method)
            # (e) bhaav: line par (sur/raftaar/zor/chamak) + shabd tarashna (zor wale shabd) + aakhri sur
            bh = rep.get("bhaav", {})
            if bh.get("ready") and not bh["ok"] and attempt <= self.R["max_attempts"]:
                corr, miss = BH.correction(bh["target"], bh["est"], bh["dev"], damp=0.8 if attempt == 1 else 0.5)
                params = dict(params, pitch_st=round(params.get("pitch_st", 0) + corr["pitch_st"], 2),
                              rate=round(float(np.clip(params.get("rate", 1.0) * corr["rate"], 0.7, 1.35)), 3),
                              gain_db=round(float(np.clip(params.get("gain_db", 0) + corr["gain_db"], -8, 8)), 2),
                              presence_db=round(float(np.clip(params.get("presence_db", 0) + corr["presence_db"], -4, 4)), 2),
                              end_st=round(float(np.clip(params.get("end_st", 0) + corr["end_st"], -4, 4)), 2),
                              range_boost=round(float(np.clip(params.get("range_boost", 0) + corr["range_boost"], -3, 4)), 2))
                y, sr = self.tts.render(said, who, params)
                y = self.shape(y, sr, line, params)
                changed = True
                applied.append(f"bhaav:{bh['target']['emotion']} sur{corr['pitch_st']:+.1f} raftaar×{corr['rate']:.2f} zor{corr['gain_db']:+.1f}")
                log(f"   ♥ line {i + 1}: {BH.describe(bh)} → sudhaar: sur {corr['pitch_st']:+.1f}st · raftaar ×{corr['rate']:.2f} · zor {corr['gain_db']:+.1f}dB · chamak {corr['presence_db']:+.1f}dB · aakhri sur {corr['end_st']:+.1f}st")
            rep = self.inspect(line, said, y, sr, params)
            if score(rep) < best[0]: best = (score(rep), said, y, sr, dict(params), rep)
            left_hard = [e for e in rep["cmp"]["errors"] if e["severity"] == "hard" and (e["expected"], e["word_i"]) not in unresolved]
            left_soft = [e for e in rep["cmp"]["errors"] if e["severity"] == "soft" and (e["expected"], e["word_i"]) not in soft_done]
            if rep.get("bhaav", {}).get("ready") and not rep["bhaav"]["ok"]: changed = changed or attempt < self.R["max_attempts"]
            bh_ok = (not rep.get("bhaav", {}).get("ready")) or rep["bhaav"]["ok"]
            if not changed or (rep["ok"] and not left_soft) or (not rep["ok"] and not left_hard and all(g["ok"] for g in rep["gates"]) and rep["consistency"]["ok"] and bh_ok): break
        if best[0] < score(rep):           # aakhri koshish pichhli se buri? sabse achhi wali rakho
            _, said, y, sr, params, rep = best; applied.append("sabse-achhi-koshish-rakhi")
        return said, y, sr, params, rep, applied, attempt

    # ---- ek line: render + jaanch + sudhaar
    def process(self, i, line, y=None, sr=None):
        t0 = time.time(); who = line.get("who", "narrator"); ev = self.ev(who)
        with self.lock: said, used = self.lex.apply(line["text"], ev)
        params = dict(line.get("_params", {}))
        tgt = BH.target(line)
        if tgt["emotion"] != "neutral":
            with self.lock: sp = self.yaad.start_params(ev, tgt["emotion"], tgt["intensity"])
            if sp:
                params.update(sp); log(f"   ★ line {i + 1}: pehle-se-bhaav (seekha hua {BH.rules()['names'][tgt['emotion']]}): sur {sp['pitch_st']:+.1f} · raftaar ×{sp['rate']:.2f} · zor {sp['gain_db']:+.1f}")
        if y is None:
            y, sr = self.tts.render(said, who, params)
            if tgt["emotion"] != "neutral" and any(params.get(k) for k in ("end_st", "range_boost")): y = self.shape(y, sr, line, params)
        t_r = time.time()
        if used: log(f"   ★ line {i + 1}: pehle-se-sudhaar (seekha hua): {', '.join(used)}")
        rep = self.inspect(line, said, y, sr, params)
        applied, attempts = [], 0
        first = rep
        if not rep["ok"] or any(e["severity"] == "soft" for e in rep["cmp"]["errors"]):
            self._log_problems(i, line, rep)
            said, y, sr, params, rep, applied, attempts = self.fix_line(i, line, said, y, sr, params, rep)
        with self.lock:
            self.bahi.record_line(ev, [a for a, _ in A.tokens(line["text"])], first["cmp"])
            # profile pehli (bina-badli) render se seekho — agar woh kirdaar se bhatki nahi thi aur param default the
            p0 = line.get("_params", {})
            if not any(k in p0 for k in ("rate", "pitch_st", "speed_override")) and first["consistency"]["ok"] and all(g["ok"] for g in first["gates"]):
                if tgt["emotion"] == "neutral": self.prof.update(who, self.engine, first["feat"], line.get("emotion", "neutral"))
            # bhaav ki yaad
            fb = rep.get("bhaav", {})
            if tgt["emotion"] == "neutral" and not p0 and first["bhaav"]["pros"] and (not first["bhaav"].get("ready") or first["bhaav"]["ok"]):
                self.yaad.update_neutral(ev, first["bhaav"]["pros"], A.matra_units(line["text"]))
            elif tgt["emotion"] != "neutral" and fb.get("ready"):
                if fb["ok"]: self.yaad.learn(ev, tgt["emotion"], tgt["intensity"], params, fb["frac"])
                else: self.yaad.note_short(ev, tgt["emotion"])
        total = int((time.time() - t0) * 1000)
        status = "✓ PASS" if rep["ok"] else "✗ FAIL (bacha hua)"
        bdesc = BH.describe(rep["bhaav"]) if rep.get("bhaav") else ""
        soft = [f"{e['expected']}→{e['heard']}" for e in rep["cmp"]["errors"] if e["severity"] == "soft"]
        log(f"{status}  line {i + 1} [{who}] render {int((t_r - t0) * 1000)} ms · jaanch {rep['ms']} ms · kul {total} ms"
            + (f" · sudhaar: {', '.join(applied)}" if applied else "") + (f" · shak: {', '.join(soft)}" if soft else "")
            + (f"\n         bhaav: {bdesc}" if rep.get("bhaav") and (rep["bhaav"]["target"]["emotion"] != "neutral" or (rep["bhaav"].get("ready") and not rep["bhaav"]["ok"])) else ""))
        R = {"i": i, "who": who, "text": line["text"], "said": said, "params": params, "ok": rep["ok"], "attempts": attempts,
             "heard": rep["heard"], "cer": rep["cmp"]["cer"], "errors_first": first["cmp"]["errors"], "errors_final": rep["cmp"]["errors"],
             "doubt": rep["doubt"], "gates": {g["gate"]: (g["ok"], g["value"]) for g in rep["gates"]},
             "drift_first": first["consistency"].get("drift", []), "drift_final": rep["consistency"].get("drift", []),
             "fixes": applied, "ms": total, "audio_s": round(len(y) / sr, 2),
             "bhaav_first": _bh_slim(first.get("bhaav")), "bhaav_final": _bh_slim(rep.get("bhaav"))}
        with self.lock: self.reports.append(R)
        return y, sr, R

    def _log_problems(self, i, line, rep):
        for g in rep["gates"]:
            if not g["ok"]: log(f"   ⚠ line {i + 1}: gate '{g['gate']}' = {g['value']}")
        for e in rep["cmp"]["errors"]:
            if e["severity"] == "hard":
                log(f"   ✗ line {i + 1}: shabd '{e['word']}' — akshar '{e['expected'] or '∅'}' → '{e['heard'] or '∅'}'  [{A.KIND_HINDI[e['kind']]}]")
        b = rep.get("bhaav", {})
        if b.get("ready") and not b["ok"]:
            log(f"   ♡ line {i + 1}: bhaav kam/galat — {BH.describe(b)}")
            for wj in b["word_judge"]:
                if not wj["ok"]:
                    n, g = wj["need"], wj["got"]
                    log(f"      · '{wj['word']}' ({wj['why']}): chahiye lamba×{n['len']}, sur {n['f0']:+.1f}st, zor {n['energy']:+.1f}dB{', pehle ruka ' + str(n['pause_ms']) + 'ms' if n['pause_ms'] else ''}"
                        f" · mila ×{g['len']}, {g['f0']:+.1f}st, {g['energy']:+.1f}dB")
        for d in rep["consistency"].get("drift", []):
            log(f"   ⚠ line {i + 1}: {line.get('who')} ki awaaz bhatki — {d['what']} {d['got']} (chahiye {d['want']}){'' if d.get('severity') == 'hard' else ' [halka]'}")

    def submit(self, i, line, y=None, sr=None):
        return self.pool.submit(self.process, i, line, y, sr)

    def run(self, lines):
        futs = [self.submit(i, l) for i, l in enumerate(lines)]
        out = [f.result() for f in futs]
        self.save()
        return out

    def save(self):
        with self.lock: self.lex.save(); self.bahi.save(); self.prof.save(); self.yaad.save()

    def summary(self, story="story"):
        R = sorted(self.reports, key=lambda r: r["i"])
        tot_ak = sum(len(A.tokens(r["text"])) for r in R)
        first_hard = sum(sum(e["severity"] == "hard" for e in r["errors_first"]) for r in R)
        final_hard = sum(sum(e["severity"] == "hard" for e in r["errors_final"]) for r in R)
        s = {"story": story, "engine": self.engine, "lines": len(R), "pass": sum(r["ok"] for r in R),
             "akshar": tot_ak, "hard_first": first_hard, "hard_final": final_hard,
             "cer_first": round(first_hard / max(1, tot_ak), 4), "cer_final": round(final_hard / max(1, tot_ak), 4),
             "fixed_lines": sum(bool(r["fixes"]) for r in R), "ms_total": sum(r["ms"] for r in R),
             "audio_s": round(sum(r["audio_s"] for r in R), 1)}
        for who in sorted({r["who"] for r in R}):
            self.bahi.add_history({"story": story, "engine": self.ev(who), "lines": sum(r["who"] == who for r in R),
                                   "cer": round(sum(sum(e['severity'] == 'hard' for e in r['errors_first']) for r in R if r['who'] == who) / max(1, sum(len(A.tokens(r['text'])) for r in R if r['who'] == who)), 4),
                                   "hard": sum(sum(e['severity'] == 'hard' for e in r['errors_first']) for r in R if r['who'] == who),
                                   "soft": sum(sum(e['severity'] == 'soft' for e in r['errors_first']) for r in R if r['who'] == who),
                                   "fixed": sum(bool(r['fixes']) for r in R if r['who'] == who)})
        self.save()
        return s

    def report_md(self, s):
        R = sorted(self.reports, key=lambda r: r["i"])
        L = [f"# Galti report — {s['story']}", "",
             f"Engine **{s['engine']}** · {s['lines']} line · {s['akshar']} akshar · PASS {s['pass']}/{s['lines']}",
             f"Pakki galti: pehle {s['hard_first']} (CER {s['cer_first']:.3f}) → sudhaar ke baad **{s['hard_final']}** (CER {s['cer_final']:.3f})",
             f"Sudhri lines: {s['fixed_lines']} · samay {s['ms_total'] / 1000:.1f} s (audio {s['audio_s']} s)", "", "## Line-war", "",
             "| # | Kaun | Galti (pehle) | Sudhaar | Nateeja |", "|---|---|---|---|---|"]
        for r in R:
            errs = "; ".join(f"{e['word']}: {e['expected'] or '∅'}→{e['heard'] or '∅'} ({e['kind']}{'' if e['severity'] == 'hard' else ', shak'})" for e in r["errors_first"]) or "—"
            drift = "; ".join(f"{d['what']} {d['got']}≠{d['want']}" for d in r["drift_first"])
            L.append(f"| {r['i'] + 1} | {r['who']} | {errs}{(' · ' + drift) if drift else ''} | {', '.join(r['fixes']) or '—'} | {'✓' if r['ok'] else '✗ ' + '; '.join(e['expected'] or '' for e in r['errors_final'] if e['severity'] == 'hard')} |")
        N_ = BH.rules()["names"]
        L += ["", "## Bhaav (bhavna) — chahiye vs mila", "",
              "| # | Kaun | Chahiye | Pehle mila | Sudhaar ke baad | Zor wale shabd (chahiye → mila) |", "|---|---|---|---|---|---|"]
        for r in R:
            b0, b1 = r.get("bhaav_first"), r.get("bhaav_final")
            if not b0: continue
            t = b0["target"]
            def fm(b): return "seekh raha" if not b.get("ready") else f"{N_.get(b['found'])} {int(b['found_frac'] * 100)}%" + ("" if t["emotion"] == "neutral" else f" (lakshya ka {int(b['frac'] * 100)}%)") + (" ✓" if b["ok"] else " ✗")
            ws = "; ".join(f"{w['word']}: ×{w['need']['len']}/{w['need']['f0']:+.0f}st/{w['need']['energy']:+.0f}dB → ×{w['got']['len']}/{w['got']['f0']:+.0f}st/{w['got']['energy']:+.0f}dB{' ✓' if w['ok'] else ' ✗'}"
                           for w in (b1 or b0).get("words", [])) or "—"
            if t["emotion"] == "neutral" and b0.get("ready") and b0.get("ok") and not ws.strip("—"): continue
            L.append(f"| {r['i'] + 1} | {r['who']} | {N_.get(t['emotion'])} {int(t['intensity'] * 100)}% | {fm(b0)} | {fm(b1) if b1 else '—'} | {ws} |")
        Y = self.yaad.d["voices"]
        if any(Y.values()):
            L += ["", "**Bhaav ki yaad (agli baar render se pehle yahi param):**", ""]
            for ev, emos in Y.items():
                for e, m in emos.items():
                    ach = m.get("achieved", [])
                    L.append(f"- `{ev}` {N_.get(e, e)}: sur {m['pitch_st']:+.1f}st · raftaar ×{m['rate']:.2f} · zor {m['gain_db']:+.1f}dB · chamak {m['presence_db']:+.1f}dB"
                             f" · aakhri sur {m.get('end_st', 0):+.1f}st (seekha {m['n']} line se, {int(m['inten'] * 100)}% bhaav par"
                             + (f"; lakshya ka ausat {int(100 * sum(ach) / len(ach))}%" if ach else "") + (f"; {m['short']} baar kam pada" if m.get("short") else "") + ")")
        L += ["", "## Galti-bahi (yaad: kaun sa akshar kamzor)", ""]
        for ev in sorted({self.ev(r["who"]) for r in R}): L += [self.bahi.report_md(ev, A.KIND_HINDI), ""]
        lexd = self.lex.d
        if any(lexd.values()):
            L += ["## Shabdkosh (seekhi likhai — agli baar render se pehle lagegi)", ""]
            for ev, ws in lexd.items():
                for w, v in ws.items(): L.append(f"- `{ev}`: **{w}** → bulwao **{v['say']}** ({v['kind']}, tareeka {v['method']})")
        return "\n".join(L)


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="Real-time Hindi checker + auto-fix")
    ap.add_argument("--lines", required=True, help="JSON: [{who,text,emotion?}]")
    ap.add_argument("--engine", default="espeak", choices=["espeak", "piper"])
    ap.add_argument("--piper-models", help='JSON {"narrator":"hi_IN-...onnx",...}')
    ap.add_argument("--ear", default="faster-whisper", help="faster-whisper | simulated:<profile.json>")
    ap.add_argument("--whisper-model", default="small")
    ap.add_argument("--knowledge", default=str(KN))
    ap.add_argument("--out", required=True, help="out prefix (wav + json + md)")
    ap.add_argument("--story", default=None)
    ap.add_argument("--strict", action="store_true", help="CI: koi pakki galti bachi to exit 1")
    a = ap.parse_args()
    lines = json.load(open(a.lines, encoding="utf-8")); lines = lines.get("lines", lines) if isinstance(lines, dict) else lines
    if a.engine == "espeak":
        tts = EspeakTTS({"narrator": ("hi", 150, 50), "raju": ("hi+m3", 165, 65), "sonu": ("hi+f3", 170, 80), "dadi": ("hi+f2", 140, 60)})
    else:
        tts = PiperTTS(json.load(open(a.piper_models)))
    rate_box = {"rate": 1.0}
    if a.ear.startswith("simulated:"):
        prof = json.load(open(a.ear.split(":", 1)[1], encoding="utf-8"))
        ear = K.SimulatedEar(prof, rate_of=lambda: rate_box["rate"])
        _orig = tts.render
        def render_track(text, who, params=None):     # simulated kaan ko raftaar batani hoti hai
            rate_box["rate"] = (params or {}).get("rate", 1.0); return _orig(text, who, params)
        tts.render = render_track
        log("⚠ SIMULATED kaan (sirf test) — asli kaam me faster-whisper lagao")
        RULES["workers"] = 1                            # simulated kaan ki raftaar-state ke liye
    else:
        ear = K.CacheEar(K.FasterWhisperEar(a.whisper_model), Path(a.knowledge) / "asr_cache")
    chk = LiveChecker(tts, ear, engine=a.engine, knowledge=Path(a.knowledge))
    log(f"▶ {len(lines)} line · engine {a.engine} · kaan {ear.name}")
    out = chk.run(lines)
    sr = out[0][1]; gap = np.zeros(int(0.45 * sr))
    y = np.concatenate([np.concatenate([o[0], gap]) for o in out]); y = y / (np.abs(y).max() + 1e-9) * 0.9
    import soundfile as sf
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    sf.write(a.out + ".wav", y.astype(np.float32), sr)
    s = chk.summary(a.story or Path(a.lines).stem)
    Path(a.out + ".json").write_text(json.dumps({"summary": s, "lines": sorted(chk.reports, key=lambda r: r["i"])}, ensure_ascii=False, indent=1,
                                                     default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")
    Path(a.out + ".md").write_text(chk.report_md(s), encoding="utf-8")
    log(f"■ PASS {s['pass']}/{s['lines']} · pakki galti {s['hard_first']} → {s['hard_final']} · CER {s['cer_first']:.3f} → {s['cer_final']:.3f} · {s['ms_total'] / 1000:.1f} s")
    if a.strict and (s["hard_final"] > 0 or s["pass"] < s["lines"]): sys.exit(1)

if __name__ == "__main__":
    main()
