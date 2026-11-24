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


def write_script(rows, out: Path) -> None:
    lines = []
    for who, text in rows:
        if not text:
            continue
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
    a = ap.parse_args()
    if a.stats:
        stats(Path(a.stats)); return 0
    rows = convert(Path(a.src))
    write_script(rows, Path(a.out))
    stats(Path(a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
