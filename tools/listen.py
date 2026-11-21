#!/usr/bin/env python3
"""Listen — Swag ka bheja audio padho, note banao, aur yaad rakho.

Har audio par:
  1) audio_read6 se poori padhaai (sur, bhaav, kirdaar, background, rishta)
  2) voice_guru QA (4 jaanch)
  3) `knowledge/audio-notes/<file>.md` me note
  4) `knowledge/audio-lessons.jsonl` me ek line ka sabak

CLI: python tools/listen.py --audio x.mp3 [--name "chhota naam"]
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
NOTES = ROOT / "knowledge" / "audio-notes"
LESSONS = ROOT / "knowledge" / "audio-lessons.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--name", default="")
    a = ap.parse_args()
    p = Path(a.audio)
    name = a.name or p.stem[:40]
    NOTES.mkdir(parents=True, exist_ok=True)

    from tools import audio_read6 as ar
    rep = ar.read(str(p), learn=True)
    if not rep.get("ok"):
        print(json.dumps({"ok": False, "why": rep.get("why")})); return 1

    # QA
    qa = {}
    try:
        out = subprocess.run([sys.executable, str(ROOT / "tools" / "voice_guru.py"),
                              "--qa", str(p)], capture_output=True, text=True)
        qa = json.loads(out.stdout) if out.stdout.strip().startswith("{") else {}
    except Exception as e:
        qa = {"error": str(e)[:80]}

    labels = Counter(e["label"] for e in rep.get("events", []))
    moods = Counter(t["emotion"] for t in rep.get("turns", []))
    lines = [
        f"# {name}",
        "",
        f"- **Lambai:** {rep['dur']/60:.1f} min ({rep['dur']:.0f} s)",
        f"- **Awaaz / mahaul:** {rep['levels']['awaaz_dbfs']} dBFS / {rep['levels']['mahaul_dbfs']} dBFS "
        f"(farq {rep['levels']['farq_db']} dB) — {rep['fit']}",
        f"- **Turns:** {len(rep.get('turns', []))} | bolne ka hissa {rep['rishta']['bolne_ka_hissa']}% "
        f"| pause औसत {rep['rishta']['gap_mean_s']} s | tez jawab {rep['rishta']['tez_jawab']} | "
        f"der se {rep['rishta']['der_se_jawab']}",
        f"- **Sur milaap:** {rep['rishta']['sur_milaap_hz']} Hz",
        "",
        "## Bhaav",
        ", ".join(f"{k} ({v})" for k, v in moods.most_common(6)) or "—",
        "",
        "## Background me kya tha",
        ", ".join(f"{k} ({v})" for k, v in labels.most_common(10)) or "—",
        "",
        f"## Beds: {rep.get('bed_count', 0)}",
    ]
    for b in rep.get("beds", [])[:8]:
        lines.append(f"- {b['from']:.0f}-{b['to']:.0f}s {b['label']} (conf {b['confidence']})")
    lines += ["", "## QA (voice_guru)"]
    if qa.get("checks"):
        for k, v in qa["checks"].items():
            lines.append(f"- {k}: {'✅' if v.get('ok') else '❌'} — {json.dumps({kk: vv for kk, vv in v.items() if kk != 'ok'}, ensure_ascii=False)}")
    else:
        lines.append("- QA nahi chala")

    note = NOTES / f"{name}.md"
    note.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LESSONS.parent.mkdir(parents=True, exist_ok=True)
    with LESSONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "audio": p.name, "dur_s": rep["dur"],
                            "farq_db": rep["levels"]["farq_db"],
                            "turns": len(rep.get("turns", [])),
                            "pause_mean_s": rep["rishta"]["gap_mean_s"],
                            "moods": moods.most_common(3),
                            "sounds": labels.most_common(5),
                            "note": str(note)}, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": True, "note": str(note), "dur": rep["dur"],
                      "turns": len(rep.get("turns", [])), "qa": qa.get("passed", "—")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
