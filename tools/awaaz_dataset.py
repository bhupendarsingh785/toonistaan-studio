#!/usr/bin/env python3
"""awaaz_dataset.py — IJAZAT wale khule dataset se alag-alag insaanon ki SAAF awaaz chuno (awaaz bank ke liye).

Kaun se dataset (inme logon ne khud apni awaaz daan ki hai):
  • Mozilla Common Voice — Hindi (CC0)        commonvoice.mozilla.org se 'hi' download karo, khol do
  • AI4Bharat IndicVoices-R — Hindi           shartein maan kar download (umar + ling ke saath)

  python tools/awaaz_dataset.py chuno D:/cv-corpus/hi --kitne 30
  python tools/awaaz_dataset.py chuno D:/IndicVoices-R/hindi --kitne 30 --license "IndicVoices-R (unki shartein)"
  python tools/awaaz_dataset.py report

Kya karta hai:
  1. manifest (validated.tsv / .jsonl / .csv) padh kar har clip ka: bolne wala, ling, umar, likha text, votes
  2. har bolne wale ki 5–14 second wali clips -> saaf_jaanch (kism 'awaaz'): shor, goonj, phatna, beep, bhinbhin,
     dabbi, beech me gayab, aur whisper ho to 'bola hua = likha hua?' (extra shabd / ad / galat text pakadta hai)
  3. har insaan ki sabse saaf ek clip
  4. ling x umar ke khaane me baant kar, har khaane me SUR ka phailaav (bhaari se halki) — taaki sab alag lagen
  5. voices/bank/ me 'ds-stri-jawan-03' jaise naam se, license + srot ke record ke saath
  6. report: kaun chuna, kaun kyun hata (saaf vs kharab ka farq)

Sach: datasets me zyaadatar SAADHARAN bolna hota hai — hansna/rona/gussa wali recording inme nahi milti, aur
12 saal se chhote bachchon ki awaaz lagbhag nahi hoti. Unke liye apni recording (awaaz_bank ui, ijazat ke saath).
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, sys, time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import saaf_jaanch as SJ        # noqa: E402
import awaaz_bank as AB         # noqa: E402

REPORT = ROOT / "knowledge" / "dataset_report.md"
COLS = {
    "path": ["path", "filepath", "audio_filepath", "file", "audio", "filename", "wav"],
    "text": ["sentence", "normalized", "text", "verbatim", "transcript", "transcription"],
    "spk": ["client_id", "speaker_id", "speaker", "spk_id"],
    "gender": ["gender", "sex"],
    "age": ["age", "age_group", "agegroup"],
    "up": ["up_votes"], "down": ["down_votes"],
}
CV_AGE = {"teens": 16, "twenties": 25, "thirties": 35, "fourties": 45, "forties": 45, "fifties": 55,
          "sixties": 65, "seventies": 75, "eighties": 85, "nineties": 95}


def _pick(row, kind):
    for c in COLS[kind]:
        for k in row:
            if k.lower().strip() == c and str(row[k]).strip() not in ("", "nan", "None"):
                return str(row[k]).strip()
    return ""


def _rows(folder: Path):
    """Har manifest padho (tsv/csv/jsonl/json)."""
    files = [p for p in folder.rglob("*") if p.suffix.lower() in (".tsv", ".csv", ".jsonl", ".json") and p.is_file()]
    if (folder / "validated.tsv").exists():                       # Common Voice: sirf jaanchi hui clips
        files = [folder / "validated.tsv"]
    for f in files:
        try:
            if f.suffix.lower() in (".tsv", ".csv"):
                with open(f, encoding="utf-8", newline="") as fh:
                    for r in csv.DictReader(fh, delimiter="\t" if f.suffix.lower() == ".tsv" else ","):
                        yield f, r
            elif f.suffix.lower() == ".jsonl":
                for line in open(f, encoding="utf-8"):
                    if line.strip(): yield f, json.loads(line)
            else:
                d = json.loads(f.read_text(encoding="utf-8"))
                for r in (d if isinstance(d, list) else d.get("data", [])):
                    if isinstance(r, dict): yield f, r
        except Exception:
            continue


def _find_audio(folder, manifest, p):
    for c in (Path(p), manifest.parent / p, folder / p, folder / "clips" / p, manifest.parent / "clips" / p,
              manifest.parent / "wavs" / p):
        if c.is_file(): return c
    return None


def ling_umar(gender, age):
    g = gender.lower()
    stri = g.startswith(("f", "female", "स्त्री", "महिला")) or "fem" in g
    purush = g.startswith(("m", "male", "पुरुष")) and not stri
    if not (stri or purush): return None, None
    a = CV_AGE.get(age.lower())
    if a is None:
        m = re.search(r"\d+", age); a = int(m.group()) if m else None
    if a is None: umar = "?"
    elif a < 13: umar = AB.UMAR[0]
    elif a < 20: umar = AB.UMAR[1]
    elif a < 40: umar = AB.UMAR[2]
    elif a < 60: umar = AB.UMAR[3]
    else: umar = AB.UMAR[4]
    if a is not None and a < 13: ling = "bachcha"
    elif a is not None and a >= 60: ling = "budhi" if stri else "budha"
    else: ling = "stri" if stri else "purush"
    return ling, umar


def chuno(folder, kitne=30, license_=None, max_jaanch=3000, per_spk=3, seed=7):
    folder = Path(folder)
    if not folder.exists(): raise SystemExit(f"Folder nahi mila: {folder}")
    if license_ is None:
        if (folder / "validated.tsv").exists(): license_ = "CC0-1.0 (Mozilla Common Voice)"
        else: raise SystemExit("Is dataset ka license batao: --license \"...\" (record ke liye zaroori)")
    by_spk = defaultdict(list); reasons = Counter(); meta_miss = 0
    for mf, r in _rows(folder):
        p, txt, spk = _pick(r, "path"), _pick(r, "text"), _pick(r, "spk")
        ling, umar = ling_umar(_pick(r, "gender"), _pick(r, "age"))
        if not p or not txt:
            continue
        if not ling:
            meta_miss += 1; continue
        up, down = _pick(r, "up"), _pick(r, "down")
        if down and down.isdigit() and int(down) > 0:
            reasons["dataset me kisi ne galat bataya (down vote)"] += 1; continue
        by_spk[spk or p].append((mf, p, txt, ling, umar, int(up) if up.isdigit() else 0))
    if not by_spk:
        raise SystemExit("Koi kaam ki clip nahi mili (ling/umar wali). Manifest ke column naam dekho.")
    rng = np.random.default_rng(seed)
    best = {}; checked = 0
    spks = list(by_spk); rng.shuffle(spks)
    for spk in spks:
        if checked >= max_jaanch: break
        clips = sorted(by_spk[spk], key=lambda x: -x[5])[:per_spk]
        for mf, p, txt, ling, umar, up in clips:
            a = _find_audio(folder, mf, p)
            if not a:
                reasons["audio file nahi mili"] += 1; continue
            checked += 1
            j = SJ.jaanch(a, "awaaz", text=txt)
            if not j["theek"]:
                for lvl, m in j["kami"]:
                    if lvl == SJ.BAD: reasons[m.split("(")[0].split("—")[0].strip()] += 1
                continue
            if not (5 <= j["naap"].get("lambai_s", 0) <= 14):
                reasons["lambai 5–14s nahi"] += 1; continue
            cand = {"spk": spk, "file": a, "text": txt, "ling": ling, "umar": umar, "score": j["score"],
                    "sur": j["naap"].get("sur_hz", 0), "naap": j["naap"]}
            if spk not in best or cand["score"] > best[spk]["score"]:
                best[spk] = cand
    groups = defaultdict(list)
    for c in best.values(): groups[(c["ling"], c["umar"])].append(c)
    # khaano me barabar hissa, phir har khaane me sur ka phailaav (bhaari -> halki)
    chosen, left = [], kitne
    order = sorted(groups, key=lambda g: len(groups[g]))
    for i, g in enumerate(order):
        share = max(1, left // (len(order) - i))
        cs = sorted(groups[g], key=lambda c: c["sur"])
        k = min(share, len(cs))
        idx = np.unique(np.linspace(0, len(cs) - 1, k).round().astype(int)) if k else []
        chosen += [cs[t] for t in idx]; left -= len(idx)
    saved = []
    count = Counter()
    for c in sorted(chosen, key=lambda c: (c["ling"], c["umar"], c["sur"])):
        u = c["umar"].split(" ")[0]
        count[(c["ling"], u)] += 1
        part = c["ling"] if c["ling"] in ("budha", "budhi", "bachcha") else f"{c['ling']}-{u}"
        naam = f"ds-{part}-{count[(c['ling'], u)]:02d}"
        r = AB.jodo(naam, "saadharan", c["file"], c["text"], c["ling"], c["umar"], ijazat=True, force=True)
        if r["saved"]:
            ix = AB._index()
            ix[naam].update({"srot": str(folder.name), "license": license_,
                             "speaker": hashlib.sha1(str(c["spk"]).encode()).hexdigest()[:10],
                             "ijazat": f"dataset: {license_}"})
            AB._save_index(ix)
            saved.append((naam, c))
    _write_report(folder, license_, saved, reasons, checked, len(by_spk), meta_miss)
    print(f"{len(by_spk)} bolne wale, {checked} clip jaanchi, {len(best)} saaf mile -> {len(saved)} bank me")
    for naam, c in saved:
        print(f"  {naam:<24} sur {c['sur']:>4} Hz  {AB.group(c['ling'], c['sur']):<6} score {c['score']}")
    print(f"Report: {REPORT}")
    return saved


def _write_report(folder, lic, saved, reasons, checked, nspk, meta_miss):
    L = [f"# Dataset se chuni awaazein — {folder.name} ({time.strftime('%Y-%m-%d')})", "",
         f"License: **{lic}** · bolne wale: {nspk} · jaanchi clips: {checked} · ling/umar nahi likha (chhodi): {meta_miss}", "",
         "## Chuni gayi", "| naam | ling | umar | sur | rang | score |", "|---|---|---|---|---|---|"]
    for n, c in saved:
        L.append(f"| {n} | {c['ling']} | {c['umar']} | {c['sur']} Hz | {AB.group(c['ling'], c['sur'])} | {c['score']} |")
    L += ["", "## Kyun hatayi (saaf vs kharab ka farq)", "| kaaran | kitni |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in reasons.most_common()]
    L += ["", "Saaf = shor kam (SNR 25 dB+), goonj nahi, phati nahi, beep/watermark nahi, bhinbhin nahi, dabbi nahi, "
          "beech me gayab nahi, aur (whisper ho to) bola hua likhe text se mel khaata hai."]
    REPORT.write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["chuno", "report"]); ap.add_argument("folder", nargs="?")
    ap.add_argument("--kitne", type=int, default=30); ap.add_argument("--license", default=None)
    ap.add_argument("--max", type=int, default=3000)
    a = ap.parse_args()
    if a.cmd == "report":
        print(REPORT.read_text(encoding="utf-8") if REPORT.exists() else "Abhi report nahi"); return 0
    chuno(a.folder, a.kitne, a.license, a.max); return 0


if __name__ == "__main__":
    raise SystemExit(main())
