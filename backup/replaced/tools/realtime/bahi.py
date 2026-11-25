"""
Bahi (galti ka khaata) — system ko yaad rahe ki KIS ENGINE/AWAAZ ko KIS AKSHAR me galti hoti hai.

knowledge/hindi-galti-bahi.json:
  engines["piper/narrator"] = {
     "lines", "akshar_total",
     "seen":   {akshar: kitni baar bola},                  -> galti-dar (rate) nikaalne ke liye
     "pairs":  {"खा→का": {count, kind, words{}, fixed{respelling: count}}},
     "kinds":  {mahapraan: n, nukta: n, ...},
     "fixes":  {kind: {tareeka: [jeet, koshish]}}           -> kaunsa sudhaar kis kism par kaam karta hai
  }
  history = [{date, story, engine, lines, cer, hard, soft, fixed}]
report() -> "sabse kamzor 10 akshar", kism-war ginti, kaunse sudhaar kaam aaye, aur pichhli kahaniyon se tulna.
"""
from __future__ import annotations
import json, time
from pathlib import Path

class Bahi:
    def __init__(self, path):
        self.path = Path(path)
        self.d = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"engines": {}, "history": []}

    def _e(self, ev):
        return self.d["engines"].setdefault(ev, {"lines": 0, "akshar_total": 0, "seen": {}, "pairs": {}, "kinds": {}, "fixes": {}})

    def record_line(self, ev, expected_tokens, cmp):
        E = self._e(ev); E["lines"] += 1; E["akshar_total"] += len(expected_tokens)
        for a in expected_tokens: E["seen"][a] = E["seen"].get(a, 0) + 1
        for er in cmp["errors"]:
            key = f"{er['expected'] or '∅'}→{er['heard'] or '∅'}"
            P = E["pairs"].setdefault(key, {"count": 0, "kind": er["kind"], "severity": er["severity"], "words": {}, "fixed": {}})
            P["count"] += 1; P["words"][er["word"]] = P["words"].get(er["word"], 0) + 1
            E["kinds"][er["kind"]] = E["kinds"].get(er["kind"], 0) + 1

    def record_fix(self, ev, kind, method, won, pair=None, respell=None):
        E = self._e(ev); f = E["fixes"].setdefault(kind, {}).setdefault(method, [0, 0])
        f[1] += 1; f[0] += int(won)
        if won and pair and pair in E["pairs"] and respell:
            E["pairs"][pair]["fixed"][respell] = E["pairs"][pair]["fixed"].get(respell, 0) + 1

    def best_methods(self, ev, kind):
        """Is kism par pehle kya kaam aaya — usi ko pehle aazmao (seekha hua kram)."""
        f = self._e(ev)["fixes"].get(kind, {})
        return [m for m, (w, t) in sorted(f.items(), key=lambda kv: -(kv[1][0] + 1) / (kv[1][1] + 2))]

    def hopeless(self, ev, kind, min_tries=3):
        """Is engine par yeh kism kabhi theek nahi hui? (>= min_tries koshish, 0 jeet) -> koshish ginti, warna 0."""
        f = self._e(ev)["fixes"].get(kind, {})
        tries = sum(t for w, t in f.values()); wins = sum(w for w, t in f.values())
        return tries if tries >= min_tries and wins == 0 else 0

    def weakest(self, ev, top=10):
        E = self._e(ev); rows = []
        per = {}
        for key, P in E["pairs"].items():
            exp = key.split("→")[0]
            if P["severity"] != "hard": continue
            per.setdefault(exp, {"err": 0, "pairs": []}); per[exp]["err"] += P["count"]; per[exp]["pairs"].append((key, P))
        for exp, v in per.items():
            seen = E["seen"].get(exp, max(1, v["err"]))
            rows.append({"akshar": exp, "galti": v["err"], "bola": seen, "dar": round(v["err"] / max(seen, 1), 3),
                         "kism": max(v["pairs"], key=lambda kp: kp[1]["count"])[1]["kind"],
                         "ban_jata": [k.split("→")[1] for k, _ in sorted(v["pairs"], key=lambda kp: -kp[1]["count"])][:3],
                         "shabd": sorted({w for _, P in v["pairs"] for w in P["words"]})[:4]})
        return sorted(rows, key=lambda r: (-r["dar"], -r["galti"]))[:top]

    def add_history(self, row):
        row["date"] = time.strftime("%Y-%m-%d %H:%M"); self.d["history"].append(row); self.d["history"] = self.d["history"][-200:]

    def save(self):
        self.path.write_text(json.dumps(self.d, ensure_ascii=False, indent=1), encoding="utf-8")

    def report_md(self, ev, kind_names):
        E = self._e(ev); L = [f"### {ev}", "", f"Lines: {E['lines']} · akshar bole: {E['akshar_total']}", ""]
        w = self.weakest(ev)
        if w:
            L += ["**Sabse kamzor akshar (pakki galti):**", "", "| Akshar | Ban jaata hai | Kism | Galti / bola | Shabd |", "|---|---|---|---|---|"]
            for r in w: L.append(f"| {r['akshar']} | {', '.join(x for x in r['ban_jata'])} | {kind_names.get(r['kism'], r['kism'])} | {r['galti']}/{r['bola']} | {', '.join(r['shabd'])} |")
        if E["kinds"]:
            L += ["", "**Kism-war:** " + " · ".join(f"{kind_names.get(k, k).split(' (')[0]} {v}" for k, v in sorted(E["kinds"].items(), key=lambda kv: -kv[1]))]
        if E["fixes"]:
            L += ["", "**Kaunsa sudhaar kaam aaya:**", ""]
            for k, f in E["fixes"].items():
                L.append(f"- {kind_names.get(k, k).split(' (')[0]}: " + ", ".join(f"{m} {w}/{t}" for m, (w, t) in f.items()))
        hist = [h for h in self.d["history"] if h.get("engine") == ev][-5:]
        if len(hist) > 1:
            L += ["", "**Pichhli kahaniyan (CER, pakki galti):** " + " → ".join(f"{h['cer']:.3f}/{h['hard']}" for h in hist)]
        return "\n".join(L)
