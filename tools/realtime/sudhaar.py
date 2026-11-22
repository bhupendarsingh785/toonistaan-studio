"""
Sudhaar — galti pakdi gayi to turant theek karna, aur jo tareeka kaam aaya use yaad rakhna.

Shabdkosh (knowledge/hindi-lexicon.json): engine/awaaz ke hisaab se "yeh shabd aise likh kar bulwao".
  Line render hone SE PEHLE lag jaata hai -> jo galti ek baar theek hui, woh dobara nahi hoti.

Kism -> ummeedwar (candidates), har ek ko dobara render + sun kar jaancha jaata hai:
  mahapraan  ख→क्ह, घ→ग्ह, थ→त्ह, ध→द्ह, फ→प्ह, भ→ब्ह ... (G2P ko 'h' saaf dikhe)
  nukta      ज़ ka doosra Unicode roop (precomposed ↔ base+nukta) — bahut se G2P ek roop nahi padhte
  matra-lambai ि↔ी, ु↔ू (lambi likho to lambi bolega)
  anunasik   ँ ↔ ं ↔ न्/म्
  schwa      'अ' gaya: ZWNJ se tod do; 'अ' zyada: halant (्) lagao
  sanyukt    क्ष→क्श, ज्ञ→ग्य (Hindi uchcharan), ्र ...
  murdhanya/ushm/ghosh/vyanjan/chhoota: shabd se pehle halka viraam (",") + line dheemi (rate 0.9)
  aakhri upaay: doosra engine (engine_bus)
Kram seekha hua: bahi.best_methods() — jo tareeka is kism par pehle jeeta, woh pehle.
"""
from __future__ import annotations
import json, re, time, unicodedata
from pathlib import Path
import akshar as A

ASP = {"ख": "क", "घ": "ग", "छ": "च", "झ": "ज", "ठ": "ट", "ढ": "ड", "थ": "त", "ध": "द", "फ": "प", "भ": "ब"}
DECOMP = {"क़": "क़", "ख़": "ख़", "ग़": "ग़", "ज़": "ज़", "ड़": "ड़", "ढ़": "ढ़", "फ़": "फ़"}
RECOMP = {v: k for k, v in DECOMP.items()}
SANYUKT_ALT = {"क्ष": ["क्श", "क्छ"], "ज्ञ": ["ग्य", "ग्यँ"], "श्र": ["श्र"], "त्र": ["त्र"]}

class Lexicon:
    def __init__(self, path):
        self.path = Path(path)
        self.d = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
    def apply(self, text, ev):
        """Render se pehle: seekhi hui likhai lagao. Returns (naya_text, [lage hue shabd])."""
        L = self.d.get(ev, {}); G_ = self.d.get(ev.split("/")[0] + "/*", {}); used = []
        def rep(m):                       # pehle is kirdaar ki seekh, phir poore engine ki (G2P sab awaazon me same hota hai)
            w = m.group(0)
            for D in (L, G_):
                if w in D: used.append(w); D[w]["uses"] = D[w].get("uses", 0) + 1; return D[w]["say"]
            return w
        out = re.sub(r"[ऀ-ॣ०-ॿ‌‍]+", rep, text)   # raw roop — NFC khud likhai badal deta (precomposed nukta)
        return out, used
    def learn(self, ev, word, say, kind, gain, method):
        e = {"say": say, "kind": kind, "gain": round(gain, 3), "method": method, "uses": 0, "learned": time.strftime("%Y-%m-%d")}
        self.d.setdefault(ev, {})[word] = e
        self.d.setdefault(ev.split("/")[0] + "/*", {}).setdefault(word, dict(e, from_voice=ev.split("/", 1)[1]))
    def save(self):
        self.path.write_text(json.dumps(self.d, ensure_ascii=False, indent=1), encoding="utf-8")

def _replace_first_akshar(word, exp_ak, new_ak):
    i = word.find(exp_ak)
    return word if i < 0 else word[:i] + new_ak + word[i + len(exp_ak):]

def candidates(word, err):
    """(method, naya_shabd ya None, line-params) ummeedwar list."""
    k, e = err["kind"], err["expected"] or ""
    nw = word; out = []
    if k in ("mahapraan",) and e:
        for asp, base in ASP.items():
            if asp in e: out.append(("h-spell", _replace_first_akshar(nw, e, e.replace(asp, base + "्ह", 1)), {}))
    if k in ("nukta", "nukta-flap"):
        alt = "".join(DECOMP.get(c, c) for c in nw)
        if alt != nw: out.append(("nukta-decomp", alt, {}))
        alt2 = nw
        for dcp, pre in RECOMP.items(): alt2 = alt2.replace(dcp, pre)
        if alt2 != nw: out.append(("nukta-precomp", alt2, {}))
    if k == "matra-lambai" and e:
        for a, b in (("ि", "ी"), ("ी", "ि"), ("ु", "ू"), ("ू", "ु")):
            if a in e: out.append(("matra-swap", _replace_first_akshar(nw, e, e.replace(a, b)), {})); break
    if k == "anunasik" and e:
        if "ं" in e: out.append(("chandra", _replace_first_akshar(nw, e, e.replace("ं", "ँ")), {}))
        if "ँ" in e: out.append(("anusvar", _replace_first_akshar(nw, e, e.replace("ँ", "ं")), {}))
    if k == "schwa" and e:
        if err.get("heard", "").endswith("्"): out.append(("zwnj-break", _replace_first_akshar(nw, e, e + "‌"), {}))
        else: out.append(("halant", _replace_first_akshar(nw, e, e + "्"), {}))
    if k == "sanyukt":
        for s, alts in SANYUKT_ALT.items():
            if s in nw:
                for a in alts: out.append(("sanyukt-alt", nw.replace(s, a), {}))
    # sab kismon ke liye aam upaay
    out.append(("viraam", ", " + nw, {}))
    out.append(("dheema", None, {"rate": 0.9}))
    out.append(("viraam+dheema", ", " + nw, {"rate": 0.9}))
    return out

def order_by_learning(cands, best):
    rank = {m: i for i, m in enumerate(best)}
    return sorted(cands, key=lambda c: rank.get(c[0], len(rank) + 1))

def apply_word(text, word, new_word):
    """Line me shabd ko (poore shabd par) badlo."""
    return re.sub(rf"(?<![ऀ-ॣ०-ॿ]){re.escape(word)}(?![ऀ-ॣ०-ॿ])", lambda m: new_word, text, count=1)

SOFT_METHODS = {"nukta-decomp", "nukta-precomp", "matra-swap", "chandra", "anusvar"}   # shak ke liye raftaar nahi badalte (nirantarta bachao)
