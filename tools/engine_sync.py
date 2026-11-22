#!/usr/bin/env python3
"""Engine Sync v2 — ek brain se charon engines ke folder (samajhne layak Hindi)."""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "knowledge" / "local-brain.json"

ENGINES = {
 "edge": {"note": "Microsoft Edge TTS — free, online, tez", "rules": ["pitch +30Hz se upar nahi", "har vakya alag render"]},
 "espeak": {"note": "espeak-ng — offline, halka, robotic", "rules": ["akela mat chhodo — highpass + compressor + treble"]},
 "piper": {"note": "Piper — offline neural (yahi local me chalta hai)", "rules": [
     "har line: trim → andar ki gap 65 ms → 20 ms fade-in",
     "lines ke beech pause 0.35–0.6 s", "length_scale 0.9–1.2", "reverb/comb band rakho"]},
 "elevenlabs": {"note": "ElevenLabs — sabse natural (paid, private key)", "rules": ["stability 0.35–0.5", "clone ke liye 30s+ sample"]},
}

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(ROOT / "voice" / "engines"))
    a = ap.parse_args()
    b = json.loads(BUNDLE.read_text(encoding="utf-8"))
    out = Path(a.out)
    for name, meta in ENGINES.items():
        d = out / name; d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps({
            "targets": b["awaaz"]["targets"], "measured": b["awaaz"]["measured_cast"],
            "emotion_map": b["awaaz"]["emotion_map"], "smoothness": b["awaaz"]["smoothness_rules"],
            "qa": b["qa"]["checks"]}, ensure_ascii=False, indent=1), encoding="utf-8")
        lines = [f"# {name.upper()} — kya karna hai (Hindi)", "", f"**Kya hai:** {meta['note']}", "",
                 "## 1. Sur ka target (naap kar)", "", "| Kirdaar | F0 (Hz) |", "|---|---|"]
        for k, v in b["awaaz"]["targets"].items():
            lines.append(f"| {k} | {v[0]}–{v[1]} |")
        lines += ["", "## 2. Robot lagne ke 5 karan (inse bacho)", ""] + [f"- {x}" for x in b["awaaz"]["robotic_ke_5_karan"]]
        lines += ["", "## 3. Smoothness ke niyam (ruk-ruk kar bolna band)", ""] + [f"- {x}" for x in b["awaaz"]["smoothness_rules"]]
        lines += ["", "## 4. Bhaav ke signal", ""] + [f"- **{k}**: `{json.dumps(v, ensure_ascii=False)}`"
                                                      for k, v in b["bhaav_ke_signal"].items() if k != "note"]
        lines += ["", "## 5. Shabd galat (piper G2P)", "", b["shabd_galat"]["problem"], "",
                  "| Script | Bola jaata |", "|---|---|"] + [f"| {k} | {v} |" for k, v in b["shabd_galat"]["examples"].items()]
        lines += ["", f"**Hal:** {b['shabd_galat']['hal']}", "", "## 6. Beats (16 step)", ""]
        for pn, pv in b["beats"]["patterns_16"].items():
            lines += [f"**{pn}** ({pv['bpm']} BPM)", "```", f"kick  {pv['kick']}", f"snare {pv['snare']}", f"hat   {pv['hat']}", "```"]
        lines += ["", "## 7. QA (bina iske deliver nahi)", ""] + [f"- {k}: {v}" for k, v in b["qa"]["checks"].items()]
        lines += ["", "## 8. Is engine ke niyam", ""] + [f"- {r}" for r in meta["rules"]]
        (d / "README-hindi.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("bana:", d)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
