#!/usr/bin/env python3
"""Engine Sync — ek hi bundle se charon engines ke folder banao (samajhne layak).

Har engine ke liye:
  voice/engines/<engine>/config.json      → us engine ki settings
  voice/engines/<engine>/README-hindi.md  → saaf Hindi me samjhauti
  voice/engines/<engine>/targets.json     → sur/bhaav/beat ka poora data

CLI: python tools/engine_sync.py [--out voice/engines]
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "knowledge" / "engine-bundle.json"

ENGINES = {
    "edge": {"note": "Microsoft Edge TTS — free, online, tez",
             "params": lambda c: {"pitch": f"{c['f0'] - 120:+d}Hz",
                                  "rate": f"{int((c['pace']/4.0 - 1)*100):+d}%"},
             "rules": ["pitch +30Hz se upar kabhi nahi", "har vakya alag render karo"]},
    "espeak": {"note": "espeak-ng — sabse halka, offline, robotic",
               "params": lambda c: {"pitch": int(max(0, min(99, 50 * c["f0"] / 120))),
                                    "speed": int(c["pace"] * 40),
                                    "gap_ms": int(c["pause_s"] * 1000)},
               "rules": ["akela mat chhodo — highpass/compressor/treble lagao"]},
    "piper": {"note": "Piper — offline neural, dheema par apna",
              "params": lambda c: {"length_scale": round(4.0 / c["pace"], 2),
                                   "sentence_silence": round(c["pause_s"] * 0.4, 2)},
              "rules": ["thread-safe nahi — ek baar me ek render", "200 akshar par todo"]},
    "elevenlabs": {"note": "ElevenLabs — sabse natural (paid), private key",
                   "params": lambda c: {"stability": 0.40, "similarity_boost": 0.75,
                                        "style": 0.38, "speaker_boost": True},
                   "rules": ["stability 0.30 se neeche nahi", "clone ke liye 30s+ sample"]},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "voice" / "engines"))
    a = ap.parse_args()
    b = json.loads(BUNDLE.read_text(encoding="utf-8"))
    out = Path(a.out)
    for name, meta in ENGINES.items():
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        cfg = {c: meta["params"](v) for c, v in b["awaaz"]["characters"].items()}
        cfg["_emotion_map"] = b["awaaz"]["emotion_map"]
        cfg["_qa"] = b["awaaz"]["qa"]
        (d / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "targets.json").write_text(json.dumps(
            {"awaaz": b["awaaz"], "bhaav_ke_signal": b["bhaav_ke_signal"],
             "beats": b["beats"], "blueprints": b["audio_blueprints"]},
            ensure_ascii=False, indent=1), encoding="utf-8")
        lines = [f"# {name.upper()} — kya karna hai (saaf Hindi)", "",
                 f"**Kya hai:** {meta['note']}", "",
                 "## 1. Awaaz ki setting (per kirdaar)", "",
                 "| Kirdaar | Setting |", "|---|---|"]
        for c, v in cfg.items():
            if c.startswith("_"):
                continue
            lines.append(f"| {c} | `{json.dumps(v, ensure_ascii=False)}` |")
        lines += ["", "## 2. Bhaav ka naksha (sur ×, raftaar ×, thahraav ×)", ""]
        for e, v in b["awaaz"]["emotion_map"].items():
            lines.append(f"- **{e}**: sur {v['pitch_mul']} · raftaar {v['rate_mul']} · thahraav {v['pause_mul']}")
        lines += ["", "## 3. Beats (16 step — `X` = bajta hai)", ""]
        for pn, pv in b["beats"]["patterns_16step"].items():
            lines += [f"**{pn}** ({pv['bpm']} BPM)", "```",
                      f"kick  {pv['kick']}", f"snare {pv['snare']}", f"hat   {pv['hat']}", "```"]
        lines += ["", "## 4. Bhaav ke asli signal (naap se)", ""]
        for k, v in b["bhaav_ke_signal"].items():
            if k == "source":
                continue
            lines.append(f"- **{k}**: `{json.dumps(v, ensure_ascii=False)}`")
        lines += ["", "## 5. Audio ke blueprint", ""]
        for k, v in b["audio_blueprints"].items():
            lines.append(f"- **{k}**: {json.dumps(v, ensure_ascii=False)}")
        lines += ["", "## 6. Is engine ke niyam", ""] + [f"- {r}" for r in meta["rules"]]
        lines += ["", "## 7. QA (bina iske deliver nahi)", "",
                  "- sur band me (dada 88–125, dadi 140–185, mahila 165–205, ladki 190–240, bachcha 240–330)",
                  "- sur ka kaanpna (std) 12+", "- raftaar 3.0–4.5 akshar/s",
                  "- background 8–16 dB neeche", "- clipping 0%, peak < 0.95", ""]
        (d / "README-hindi.md").write_text("\n".join(lines), encoding="utf-8")
        print("bana:", d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
