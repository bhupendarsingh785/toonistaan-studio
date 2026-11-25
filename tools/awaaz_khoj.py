#!/usr/bin/env python3
"""awaaz_khoj.py — jo awaaz library me nahi, use KHUD dhoondho, parkho, chuno — aur aapki raay se SEEKHO.

  python tools/awaaz_khoj.py khoj मोर                 Hindi shabd -> khud samjho -> web (Freesound, sirf ijazat wali) ->
                                                       15 tak laao -> saaf_jaanch -> sabse achhi 4 rakho -> baaki hatao
  python tools/awaaz_khoj.py khoj footsteps_stairs     ya seedha khaane ka naam
  python tools/awaaz_khoj.py bharo                     library ke saare khaali khaane bharo
  python tools/awaaz_khoj.py raay library_awaaz/owl/123_x.mp3 galat    sunkar batao: sahi / galat
  python tools/awaaz_khoj.py sikhao मधुमक्खी "bee buzz"                 naya shabd sikhao (ek baar)
  python tools/awaaz_khoj.py dikhao                    kya seekha

Seekhna (knowledge/khoj_yaad.json): har file ki raay, har uploader par bharosa, kaun sa search shabd kaam aaya,
kaun si file kyun hatayi. 'galat' bolte hi wo file hat jaati hai aur us khaane ke liye nayi dhoondhi jaati hai.
Sirf Creative Commons 0 aur Attribution (CC-BY) — NonCommercial kabhi nahi (aapka channel commercial hai).
"""
from __future__ import annotations
import argparse, json, os, re, shutil, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import kahani_dimaag as KD          # noqa: E402
import saaf_jaanch as SJ            # noqa: E402

YAAD = ROOT / "knowledge" / "khoj_yaad.json"
ANJAAN = ROOT / "knowledge" / "khoj_anjaan.json"
STAGE = KD.LIB / "_jaanch"
LICENSES = '("Creative Commons 0" OR "Attribution")'

# Hindi -> Freesound search (shuruaati shabd-kosh; baaki 'sikhao' se ya apne aap seekhe hue)
KOSH = {
    "मोर": "peacock", "कोयल": "koel cuckoo", "तोता": "parrot", "कौआ": "crow", "कबूतर": "pigeon coo", "चील": "eagle",
    "गौरैया": "sparrow", "मुर्गी": "hen chicken", "बत्तख": "duck", "उल्लू": "owl", "चिड़िया": "bird chirp",
    "शेर": "lion roar", "बाघ": "tiger growl", "हाथी": "elephant trumpet", "बंदर": "monkey", "भालू": "bear growl",
    "घोड़ा": "horse neigh", "गाय": "cow moo", "भैंस": "buffalo", "बकरी": "goat bleat", "भेड़": "sheep", "ऊंट": "camel",
    "कुत्ता": "dog bark", "बिल्ली": "cat meow", "चूहा": "mouse squeak", "सांप": "snake hiss", "मेंढक": "frog",
    "मधुमक्खी": "bee buzz", "मच्छर": "mosquito", "मक्खी": "fly buzz", "झींगुर": "cricket", "भेड़िया": "wolf howl",
    "सियार": "jackal howl", "हिरण": "deer", "चिड़ियाघर": "zoo ambience",
    "पेड़": "tree wind", "पत्ते": "leaves rustle", "झाड़ी": "bush rustle", "जंगल": "forest ambience", "नदी": "river",
    "झरना": "waterfall", "समुद्र": "ocean waves", "लहर": "waves", "बारिश": "rain", "आंधी": "storm wind", "हवा": "wind",
    "बिजली": "thunder", "आग": "fire crackling", "चूल्हा": "fire crackle cooking", "कुआं": "well bucket water",
    "सीढ़ी": "footsteps stairs", "कदम": "footsteps", "दरवाज़ा": "door", "खिड़की": "window open", "ताला": "lock key",
    "घंटी": "bell", "मंदिर": "temple bell", "शंख": "conch shell", "ढोल": "dhol drum", "बांसुरी": "flute",
    "गाड़ी": "car", "बस": "bus", "ट्रेन": "train", "बैलगाड़ी": "ox cart wooden wheels", "साइकिल": "bicycle",
    "ट्रैक्टर": "tractor", "हॉर्न": "car horn", "बाज़ार": "market crowd", "मेला": "fair crowd festival",
    "बर्तन": "dishes kitchen", "पानी": "water pour", "छपाक": "splash", "कांच": "glass break", "तलवार": "sword",
    "हंसी": "laughter", "हंसना": "laughing", "रोना": "crying", "बच्चा रोया": "baby crying", "ताली": "applause clapping",
    "बच्चे खेल": "children playing", "भीड़": "crowd", "खांसी": "cough", "छींक": "sneeze", "खर्राटे": "snoring",
    "सन्नाटा": "night quiet ambience", "रात": "night ambience", "सुबह": "morning birds",
}
HUMAN = {"laughter", "laughing", "crying", "baby_crying", "applause_clapping", "children_playing", "crowd", "cough",
         "sneeze", "snoring", "market_crowd", "fair_crowd_festival"}


# ============================================================================ yaad
def yaad():
    import astra_paths as _AP
    d = _AP.read_json(YAAD)
    for k in ("files", "uploaders", "terms", "hataya"):
        d.setdefault(k, {})
    return d


def save_yaad(d):
    YAAD.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def rules():
    import astra_paths as _AP
    return _AP.read_json(KD.RULES, apni=True)


def save_rules(r):
    KD.RULES.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


# ============================================================================ shabd samajhna
def samjho(shabd, r=None):
    """Hindi shabd / khaana -> (tag, search shabd, kism). Naya ho to rules me khud jod deta hai (seekhna)."""
    r = r or rules()
    s = shabd.strip()
    if s in r["library_find"] or s in r["sfx"]:
        return s, r["library_find"].get(s, [s.replace("_", " ")]), _kism(s, r)
    tag = KD.best_match(s, r["sfx"])
    if tag:
        return tag, r["library_find"].get(tag, [tag.replace("_", " ")]), _kism(tag, r)
    toks = KD.tokens(s)
    eng = None
    for k in sorted(KOSH, key=len, reverse=True):
        if KD.has_word(toks, k):
            eng = KOSH[k]; break
    if eng is None and re.fullmatch(r"[a-zA-Z _-]+", s):
        eng = s.replace("_", " ")
    if eng is None:
        a = json.loads(ANJAAN.read_text(encoding="utf-8")) if ANJAAN.exists() else {}
        a[s] = time.strftime("%Y-%m-%d"); ANJAAN.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
        return None, [], None
    tag = re.sub(r"[^a-z0-9]+", "_", eng.lower()).strip("_")
    r["sfx"].setdefault(tag, {"words": [], "gain": -9})
    if s not in r["sfx"][tag]["words"] and not re.fullmatch(r"[a-zA-Z _-]+", s):
        r["sfx"][tag]["words"].append(s)
    r["library_find"].setdefault(tag, [eng])
    save_rules(r)
    return tag, r["library_find"][tag], "sfx"


def _kism(tag, r):
    beds = {b for sc in r["scenes"].values() for b in sc["beds"]}
    return "bed" if tag in beds else "sfx"


def sikhao(shabd, eng):
    r = rules()
    tag = re.sub(r"[^a-z0-9]+", "_", eng.lower()).strip("_")
    r["sfx"].setdefault(tag, {"words": [], "gain": -9})
    if shabd not in r["sfx"][tag]["words"]: r["sfx"][tag]["words"].append(shabd)
    r["library_find"].setdefault(tag, [])
    if eng not in r["library_find"][tag]: r["library_find"][tag].insert(0, eng)
    save_rules(r)
    if ANJAAN.exists():
        a = json.loads(ANJAAN.read_text(encoding="utf-8")); a.pop(shabd, None)
        ANJAAN.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Seekh liya: {shabd} -> {tag} ('{eng}')")
    return tag


# ============================================================================ web se laana
def _key():
    kf = ROOT / "freesound_key.txt"
    k = os.environ.get("FREESOUND_API_KEY") or (kf.read_text().strip() if kf.exists() else "")
    if not k:
        raise SystemExit("Freesound key chahiye (free): freesound.org/apiv2/apply -> key ko freesound_key.txt me daalo.")
    return k


def _search(term, kism, key, page_size=15, page=1):
    import urllib.request, urllib.parse, urllib.error
    dur = "[20 TO 600]" if kism == "bed" else "[0.4 TO 15]"
    q = {"query": term, "filter": f"license:{LICENSES} duration:{dur}", "page_size": str(page_size),
         "fields": "id,name,previews,license,username,duration,tags,avg_rating,num_downloads",
         "sort": "score", "token": key, "page": str(page)}
    for ep in ("search/", "search/text/"):
        try:
            with urllib.request.urlopen(f"https://freesound.org/apiv2/{ep}?" + urllib.parse.urlencode(q), timeout=30) as r:
                return json.loads(r.read()).get("results", [])
        except urllib.error.HTTPError as e:
            if e.code in (401, 403): raise SystemExit("Freesound key galat hai.")
        except Exception:
            continue
    return []


def _download(url, dest):
    import urllib.request
    urllib.request.urlretrieve(url, dest)
    return dest


def _lib_fps(yd, tag=None):
    return [v["fp"] for k, v in yd["files"].items() if v.get("fp") and (tag is None or v.get("tag") == tag)]


def khoj(shabd, rakho=4, laao=15, quiet=False, fetch=None):
    """Poora kram: samjho -> dhoondho -> laao -> parkho -> chuno -> rakho -> yaad. fetch = test ke liye nakli web."""
    r = rules()
    tag, terms, kism = samjho(shabd, r)
    if not tag:
        print(f"'{shabd}' ka matlab nahi pata. Ek baar sikhao:  python tools/awaaz_khoj.py sikhao {shabd} \"english shabd\"")
        return None
    yd = yaad()
    folder = KD.LIB / tag; folder.mkdir(parents=True, exist_ok=True)
    have = [p for p in folder.iterdir() if p.suffix.lower() in KD.AUDIO_EXT and yd["files"].get(_rel(p), {}).get("raay", 0) >= 0]
    need = rakho - len(have)
    if need <= 0:
        if not quiet: print(f"{tag}: pehle se {len(have)} achhi file"); return tag
        return tag
    stage = STAGE / tag; shutil.rmtree(stage, ignore_errors=True); stage.mkdir(parents=True)
    # search shabd seekhe hue kram me (jo pehle kaam aaye wo pehle)
    tw = yd["terms"].get(tag, {})
    terms = sorted(terms, key=lambda t: -tw.get(t, 0))
    seen = {str(v.get("id")) for v in yd["files"].values() if v.get("tag") == tag} | set(yd["hataya"].get(tag, []))
    cands = []
    key = None if fetch else _key()
    for term in terms:
        if len(cands) >= laao: break
        res = []
        for page in (1, 2, 3):                              # pehle page par saaf na mile to aage
            got = fetch(term, kism) if fetch else _search(term, kism, key, page=page)
            res += got
            if fetch or len(got) < 15 or len([x for x in res if str(x["id"]) not in seen]) >= laao: break
        for s in res:
            sid = str(s["id"])
            if sid in seen or len(cands) >= laao: continue
            if "noncommercial" in s.get("license", "").lower().replace(" ", ""): continue
            url = s.get("previews", {}).get("preview-hq-mp3") or s.get("previews", {}).get("preview-hq-ogg")
            if not url: continue
            dest = stage / f"{sid}_{re.sub(r'[^A-Za-z0-9-]+', '_', s['name'])[:36]}{Path(url).suffix or '.mp3'}"
            try:
                (fetch.download if fetch else _download)(url, dest)
            except Exception:
                continue
            seen.add(sid); cands.append((dest, s, term))
    if not cands:
        print(f"{tag}: web par kuch nahi mila (search: {', '.join(terms)})"); return tag
    fps = _lib_fps(yd)
    rows = []
    allow = tag in HUMAN
    for dest, s, term in cands:
        j = SJ.jaanch(dest, kism, allow_voice=allow, library_fps=fps)
        trust = yd["uploaders"].get(s.get("username", ""), 0)
        bonus = 4 * trust + min(6, (s.get("avg_rating") or 0)) + min(4, (s.get("num_downloads") or 0) / 500)
        final = j["score"] + bonus if j["theek"] else j["score"] - 100
        rows.append({"file": dest, "s": s, "term": term, "j": j, "final": round(final, 1)})
        fps.append(j["fingerprint"])
    rows.sort(key=lambda x: -x["final"])
    kept = [x for x in rows if x["j"]["theek"]][:need]
    for x in rows:
        sid = str(x["s"]["id"])
        if x in kept:
            to = folder / x["file"].name; shutil.move(str(x["file"]), to)
            yd["files"][_rel(to)] = {"id": sid, "tag": tag, "user": x["s"].get("username"), "license": x["s"].get("license"),
                                     "url": f"https://freesound.org/s/{sid}/", "score": x["j"]["score"], "raay": 0,
                                     "term": x["term"], "fp": x["j"]["fingerprint"], "aaya": time.strftime("%Y-%m-%d")}
            yd["terms"].setdefault(tag, {}); yd["terms"][tag][x["term"]] = yd["terms"][tag].get(x["term"], 0) + 1
            with open(KD.LIB / "CREDITS.txt", "a", encoding="utf-8") as cr:
                cr.write(f"{tag}\t{to.name}\t{x['s'].get('username')}\t{x['s'].get('license')}\thttps://freesound.org/s/{sid}/\n")
        else:
            yd["hataya"].setdefault(tag, []).append(sid)
    shutil.rmtree(stage, ignore_errors=True)
    save_yaad(yd)
    _report(tag, rows, kept, folder)
    if not quiet:
        print(f"\n{tag}: {len(rows)} laaye, {len(kept)} rakhe  (poora farq: {folder / 'KHOJ.md'})")
        for x in rows[:10]:
            mark = "RAKHA " if x in kept else ("saaf  " if x["j"]["theek"] else "HATAYA")
            why = "; ".join(m for _, m in x["j"]["kami"]) or "saaf"
            print(f"  {mark} {x['final']:>6}  {x['file'].name[:34]:<34} {why[:70]}")
    KD.scan(rules(), verbose=False)
    return tag


def _rel(p):
    return str(Path(p).resolve().relative_to(ROOT))


def _report(tag, rows, kept, folder):
    L = [f"# {tag} — khoj ki report ({time.strftime('%Y-%m-%d %H:%M')})", "",
         "| | score | file | uploader | license | kya mila |", "|---|---|---|---|---|---|"]
    for x in rows:
        mark = "✅ rakha" if x in kept else ("➖ saaf par zaroorat nahi" if x["j"]["theek"] else "❌ hataya")
        why = "<br>".join(f"{lvl}: {m}" for lvl, m in x["j"]["kami"]) or "saaf"
        L.append(f"| {mark} | {x['final']} | {x['file'].name} | {x['s'].get('username')} | {x['s'].get('license')} | {why} |")
    L += ["", "**Saaf vs kharab ka farq:** saaf = na phati, na beep/watermark, na koi bolta hua naam, na bhinbhin, "
          "na beech me gayab, na duplicate. 'dhyaan' wali cheezein (jaise kati shuruaat) chalti hain — fade lag jaata hai."]
    (folder / "KHOJ.md").write_text("\n".join(L), encoding="utf-8")


# ============================================================================ raay se seekhna
def raay(path, kya):
    yd = yaad(); rel = _rel(path)
    ent = yd["files"].get(rel)
    if not ent:
        raise SystemExit("Ye file khoj se nahi aayi (yaad me nahi).")
    good = kya in ("sahi", "achhi", "haan", "+")
    ent["raay"] = ent.get("raay", 0) + (1 if good else -1)
    u = ent.get("user") or ""
    yd["uploaders"][u] = round(max(-3, min(3, yd["uploaders"].get(u, 0) + (0.5 if good else -1))), 2)
    t = yd["terms"].setdefault(ent["tag"], {}); t[ent.get("term", "")] = t.get(ent.get("term", ""), 0) + (1 if good else -2)
    msg = "Yaad rakha: achhi."
    if not good:
        bad = KD.LIB / "_galat" / ent["tag"]; bad.mkdir(parents=True, exist_ok=True)
        if (ROOT / rel).exists(): shutil.move(str(ROOT / rel), bad / Path(rel).name)
        yd["hataya"].setdefault(ent["tag"], []).append(ent["id"])
        msg = f"Hata di, '{u}' par bharosa kam, search '{ent.get('term')}' ka wazan kam."
    save_yaad(yd); print(msg)
    if not good:
        try:
            khoj(ent["tag"], quiet=False)
        except SystemExit as e:
            print(e)


def weight(rel):
    """kahani_dimaag ke liye: kis file ko kitni baar chuna jaaye (galat = 0)."""
    v = yaad()["files"].get(rel)
    if not v: return 1.0
    return 0.0 if v.get("raay", 0) < 0 else 1.0 + v.get("raay", 0)


def bharo(rakho=4):
    r = rules()
    for t in sorted(KD.all_tags(r)):
        try:
            khoj(t, rakho, quiet=True)
            print(f"  {t:<20} ok")
        except SystemExit as e:
            print(e); return


def dikhao():
    yd = yaad()
    by = {}
    for v in yd["files"].values(): by.setdefault(v["tag"], []).append(v)
    for t, vs in sorted(by.items()):
        print(f"{t:<20} {len(vs)} file, raay {sum(v.get('raay', 0) for v in vs):+d}, search: "
              + ", ".join(f"{k}({n:+d})" for k, n in sorted(yd['terms'].get(t, {}).items(), key=lambda x: -x[1])[:3]))
    tr = sorted(yd["uploaders"].items(), key=lambda x: -x[1])
    if tr: print("bharosa:", ", ".join(f"{u} {s:+.1f}" for u, s in tr[:8]))
    if ANJAAN.exists(): print("in shabdon ka matlab nahi pata:", ", ".join(json.loads(ANJAAN.read_text(encoding="utf-8"))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["khoj", "bharo", "raay", "sikhao", "dikhao"])
    ap.add_argument("args", nargs="*"); ap.add_argument("--rakho", type=int, default=4)
    a = ap.parse_args()
    if a.cmd == "khoj": khoj(" ".join(a.args), a.rakho)
    elif a.cmd == "bharo": bharo(a.rakho)
    elif a.cmd == "raay": raay(a.args[0], a.args[1])
    elif a.cmd == "sikhao": sikhao(a.args[0], " ".join(a.args[1:]))
    else: dikhao()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
