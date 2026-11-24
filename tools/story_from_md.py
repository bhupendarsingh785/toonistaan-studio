#!/usr/bin/env python3
"""story_from_md.py — markdown kahani ko hamare script format me badlo (kirdaar pehchan ke).

Kaam:
  • images/links/headings hatao, sirf bolne wala text rakho
  • dialogue ("...") se kirdaar pehchano: naam paas me ho to wahi, warna baari-baari
  • har line par bhaav (bhaav_v2) — shabdon ke cues se
  • vachak ki line alag

  python tools/story_from_md.py /scratch/input/paste-1-13.md --out /scratch/work/chandravan.txt
  python tools/story_from_md.py --stats /scratch/work/chandravan.txt
"""
from __future__ import annotations
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

NAMES = ["गौरी", "कमला", "मोहन", "हरिदास", "अर्जुन", "वीरभद्र", "रघु", "ऋषि", "माई", "सरपंच", "भेड़िया"]
FEMALE = {"गौरी", "कमला", "माई"}
CHILD = {"मोहन"}
OLD = {"हरिदास", "ऋषि", "माई", "सरपंच"}


def clean(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)          # image
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)      # link -> text
    text = re.sub(r"[*_`>#]+", "", text)                      # markdown marks
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sentences(par: str):
    return [s.strip() for s in re.split(r"(?<=[।!?])\s+", par) if s.strip()]


ADDRESS_ELDER = ("बेटा", "बेटी", "बच्चे", "अरे बच्चे")
ADDRESS_MOTHER = ("माँ", "मां", "अम्मा")


def speaker_for(quote: str, prev_speaker, nearby: str, history: list) -> str:
    """Kirdaar pehchano — naam, sambodhan (बेटा/माँ), aur baari ke hisaab se."""
    # 1) paas ki narration me naam
    for n in NAMES:
        if n in nearby:
            return n
    # 2) sambodhan se
    if any(w in quote for w in ADDRESS_ELDER):
        # bachche ko bol raha/rahi hai -> maa/pita/buzurg
        for cand in ("कमला", "हरिदास", "माई"):
            if cand in NAMES:
                return cand
    if any(w in quote for w in ADDRESS_MOTHER):
        return "मोहन" if "मोहन" in NAMES else "गौरी"
    # 3) baari: pichhle do se alag
    recent = [h for h in history[-2:] if h != "वाचक"]
    if len(recent) >= 2 and recent[-1] != recent[-2]:
        for cand in ("गौरी", "कमला", "मोहन", "हरिदास", "भेड़िया"):
            if cand != recent[-1]:
                return cand
    if recent:
        for cand in ("गौरी", "कमला", "मोहन", "हरिदास", "भेड़िया"):
            if cand != recent[-1]:
                return cand
    return "गौरी"


def convert(md_path: Path) -> list[tuple[str, str]]:
    raw = md_path.read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    last_speaker = None
    history: list[str] = []
    for block in raw.split("\n\n"):
        b = block.strip()
        if not b or b.startswith("![") or b.startswith("#"):
            if b.startswith("#"):
                title = clean(b)
                if title:
                    out.append(("वाचक", title + "।"))
            continue
        b = clean(b)
        if not b:
            continue
        # paragraph ko quote / non-quote me todo
        parts = re.split(r"(“[^”]*”)", b)
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if p.startswith("“"):
                q = p.strip("“”").strip()
                sp = speaker_for(q, last_speaker, b, history)
                out.append((sp, q))
                history.append(sp)
                last_speaker = sp
            else:
                out.append(("वाचक", p))
                history.append("वाचक")
                last_speaker = "वाचक"
    return out


def intro_only(rows, seconds: float = 10.0):
    """Vachak sirf shuruaat me (5-10s) — baaki narration scene ke kirdaar bolte hain."""
    out, used = [], 0.0
    for who, text in rows:
        d = max(1.0, len(text) / 12.0)
        if who == "वाचक" and used < seconds:
            out.append((who, text)); used += d
            continue
        if who == "वाचक":
            # scene ka kirdaar: paas ke shabdon me naam, warna गौरी
            pick = "गौरी"
            for n in ("भेड़िया", "हरिदास", "कमला", "मोहन", "ऋषि", "माई"):
                if n in text:
                    pick = n; break
            out.append((pick, text))
        else:
            out.append((who, text))
    return out


def no_narrator(rows):
    """Vachak bilkul nahi — narration scene ke kirdaar ke muh se.

    Sunne wale ko lagta hai ki kirdaar khud apna kaam-kaj bata raha hai
    ("main nadi kinare gayi"), bahar ka reader nahi.
    """
    out = []
    for who, text in rows:
        if who != "वाचक":
            out.append((who, text)); continue
        pick = "गौरी"
        if len(text) > 40:                     # title/chhoti line par naam-match nahi
            txt2 = text.replace("ऋषि-मुनि", "").replace("ऋषियों", "")
            for n in ("हरिदास", "कमला", "मोहन", "ऋषि", "माई"):
                if n in txt2:
                    pick = n; break
        out.append((pick, text))
    return out


def merge_same(rows, max_len: int = 150):
    """Ek hi kirdaar ki lagataar lines jodo — beech me rukna kam (smooth)."""
    out = []
    for who, text in rows:
        if out and out[-1][0] == who and len(out[-1][1]) + len(text) + 1 <= max_len:
            prev = out[-1][1].rstrip("।, ")
            out[-1] = (who, prev + "। " + text.lstrip())
        else:
            out.append((who, text))
    return out


def split_commas(rows, max_len: int = 110):
    """Lambi line ko vakya me todo; phir bhi lambi ho to aakhri comma par.

    Chhote tukde ("जंगल, ऋषि-मुनि") nahi banate — sirf jahan saans lena natural ho.
    """
    import re as _re
    out = []
    for who, text in rows:
        text = text.strip()
        if len(text) <= max_len:
            out.append((who, text)); continue
        sents = [x.strip() for x in _re.split(r"(?<=[।!?])\s*", text) if x.strip()]
        buf = ""
        for s_ in sents:
            while len(s_) > max_len:
                cut = s_.rfind(",", 0, max_len)
                cut = cut if cut > 40 else max_len
                head, s_ = s_[:cut + 1].strip(), s_[cut + 1:].strip()
                if buf:
                    out.append((who, buf)); buf = ""
                out.append((who, head))
            if len(buf) + len(s_) + 1 <= max_len:
                buf = (buf + " " + s_).strip()
            else:
                if buf:
                    out.append((who, buf))
                buf = s_
        if buf:
            out.append((who, buf))
    return out


def apply_pov(rows, pov: str):
    """Vachak ki narration POV kirdaar ke muh se — bahar ka reader nahi.

    Sunne wale ko lagta hai ki kahani usi kirdaar ne sunai hai (pehla purush),
    isliye "screen ke upar wala aadmi" jaisa ehsaas nahi hota.
    """
    if not pov:
        return rows
    return [(pov if who == "वाचक" else who, text) for who, text in rows]


def write_script(rows, out: Path) -> None:
    lines = []
    try:
        import hindi_text as HT
    except Exception:
        HT = None
    for who, text in rows:
        if not text:
            continue
        if HT:
            text = HT.normalize(text)
        lines.append(f"{who}: {text}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def stats(path: Path) -> None:
    rows = [l.split(":", 1) for l in path.read_text(encoding="utf-8").splitlines() if ":" in l]
    c = Counter(r[0].strip() for r in rows)
    words = sum(len(re.findall(r"[\u0900-\u097F]+", r[1])) for r in rows)
    print(f"lines: {len(rows)} | shabd: {words} | andaaza: {words/2.2/60:.1f} min")
    print("kirdaar:", dict(c))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default="")
    ap.add_argument("--out", default="/scratch/work/story-script.txt")
    ap.add_argument("--stats", default="")
    ap.add_argument("--pov", default="", help="narration kis kirdaar ke muh se (jaise गौरी)")
    ap.add_argument("--intro-only", action="store_true", help="vachak sirf 10s, phir kirdaar bolte hain")
    ap.add_argument("--no-narrator", action="store_true", help="vachak bilkul nahi — kirdaar khud bolte hain")
    ap.add_argument("--merge-same", action="store_true", help="ek kirdaar ki lines jodo (smooth)")
    ap.add_argument("--split-commas", action="store_true", help="lambi line comma par todo (saans)")
    a = ap.parse_args()
    if a.stats:
        stats(Path(a.stats)); return 0
    rows = convert(Path(a.src))
    if a.no_narrator:
        rows = no_narrator(rows)
    if a.intro_only:
        rows = intro_only(rows, 10.0)
    if a.pov:
        rows = apply_pov(rows, a.pov)
    if a.split_commas:
        rows = split_commas(rows)
    if a.merge_same:
        rows = merge_same(rows)
    write_script(rows, Path(a.out))
    stats(Path(a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
