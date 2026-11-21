#!/usr/bin/env python3
"""Story Audio — kahani + background + bhaav, ek hi file me (cinematic).

Kaam:
  1) Har line ek kirdaar + bhaav ke saath render (edge → piper → espeak chain)
  2) Background library se: bed (laga rahe) + foley (kadam/patte/barish)
  3) Dialogue ke waqt bed **duck** (9 dB neeche) — bolne wala saaf
  4) Foley ko line ke shuru me rakhta hai (kadam, darwaza, barish)
  5) Aakhir me loudnorm (-18 LUFS) + halka reverb (jagah ka ehsaas)

CLI:
  python tools/story_audio.py --out output/kahani.mp3
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
LIB = ROOT / "astra" / "library"
from tools import worktmp as wt

# ---------------- kahani (chhoti, garma-garam) ----------------
STORY = [
    {"who": "dadi",  "bhaav": "pyaar",  "text": "बेटा, आ जा पास। आज मैं तुम्हें एक कहानी सुनाती हूँ।"},
    {"who": "bachcha", "bhaav": "khushi", "text": "दादी, कहानी सुनाओ ना! आज कौन सी?"},
    {"who": "dadi",  "bhaav": "neutral", "text": "उस जंगल में एक छोटी नदी बहती थी, और उसके किनारे एक बूढ़ा पेड़ था।"},
    {"who": "dadi",  "bhaav": "dar",     "text": "एक रात बारिश इतनी तेज़ हुई कि पूरा जंगल काँपने लगा।"},
    {"who": "bachcha", "bhaav": "dar",   "text": "फिर क्या हुआ दादी? डर नहीं लगा?"},
    {"who": "dadi",  "bhaav": "khushi",  "text": "डर तो लगा, पर पेड़ ने अपनी जड़ों से नदी को रोक लिया।"},
    {"who": "dadi",  "bhaav": "pyaar",   "text": "सुबह जब धूप निकली, तो गाँव बच गया। और वह पेड़ आज भी खड़ा है।"},
    {"who": "bachcha", "bhaav": "khushi", "text": "वाह दादी! कल मैं उस पेड़ को देखने जाऊँगा।"},
]

# background plan: (kitne second se, asset, gain_db, loop?)
BED = [("ambience/bvk_forest_1.mp3", -16, True),
       ("ambience/rain_gentle_1.mp3", -21, True)]
EVENTS = [
    (0.2,  "footsteps/steps_soil.mp3", -12),
    (13.0, "ambience/weather_rain_thunder_storm.mp3", -20),
    (21.0, "footsteps/steps_soil.mp3", -13),
    (26.0, "birds/birds_chirp_1.mp3", -22) if (LIB / "birds/birds_chirp_1.mp3").exists() else (26.0, "ambience/birds_forest_1.mp3", -22),
]


def _ff() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()


def _dur(p: Path) -> float:
    import numpy as np
    raw = subprocess.run([_ff(), "-v", "quiet", "-i", str(p), "-f", "s16le",
                          "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    return round(len(np.frombuffer(raw, dtype=np.int16)) / 16000, 2)


def merge_lines(story: list[dict]) -> list[dict]:
    """Ek hi kirdaar ki lagataar lines ko jodo — TTS ke beech ke "ruko" kam ho."""
    merged: list[dict] = []
    for line in story:
        if merged and merged[-1]["who"] == line["who"]:
            merged[-1]["text"] = merged[-1]["text"].rstrip() + " " + line["text"].lstrip()
        else:
            merged.append(dict(line))
    return merged


def _trim_silence(src: Path, dest: Path) -> bool:
    """Line ke shuru/aakhir ki chupai hatao (warna beech me 'khaali' sunai deta hai)."""
    r = subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", str(src),
                        "-af", "silenceremove=start_periods=1:start_threshold=-45dB:"
                               "start_silence=0.12,areverse,"
                               "silenceremove=start_periods=1:start_threshold=-45dB:"
                               "start_silence=0.05,areverse",
                        "-c:a", "libmp3lame", "-b:a", "160k", str(dest)], capture_output=True)
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 2000


ENGINE = os.environ.get("STORY_ENGINE", "sarvam")
# A/B naap se: ishita (F0 std 67) sabse expressive, suhani tez+saaf
CAST = {"dadi": "ishita", "bachcha": "tanya", "maa": "priya", "narrator": "suhani"}
# bhaav -> temperature (Sarvam: zyada = zyada expressive; dukh/gussa me thoda alag)
TEMP = {"neutral": 0.70, "dukh": 0.72, "gussa": 0.85, "khushi": 0.85,
        "dar": 0.80, "pyaar": 0.78}


def render_single(tmp: Path) -> list[dict]:
    """Poori kahani ek hi awaaz (dadi) me — sabse smooth, koi beech ka break nahi."""
    from tools import engine_router as er
    text = " ".join(l["text"] for l in STORY)
    f = tmp / "story_single.mp3"
    ok, _ = er.render_line(text, "dadi", f, engine=ENGINE, bhaav="pyaar")
    if not ok:
        ok, _ = er.render_line(text, "dadi", f, engine="edge", bhaav="pyaar")
    trimmed = f.with_name("story_single_trim.mp3")
    if ok and _trim_silence(f, trimmed):
        f = trimmed
    d = _dur(f) if f.exists() else 0
    return [{"who": "dadi", "bhaav": "pyaar", "text": text, "file": str(f),
             "start": 0.25, "dur": d, "ok": ok}]


def render_lines(tmp: Path) -> list[dict]:
    from tools import engine_router as er
    out = []
    t = 0.25
    for i, line in enumerate(merge_lines(STORY)):
        f = tmp / f"line_{i:02d}.mp3"
        os.environ["SARVAM_SPEAKER_" + line["who"].upper()] = CAST.get(line["who"], "ishita")
        os.environ["SARVAM_TEMP"] = str(TEMP.get(line["bhaav"], 0.75))
        ok, log = er.render_line(line["text"], line["who"], f, engine=ENGINE, bhaav=line["bhaav"])
        if not ok:
            ok, log = er.render_line(line["text"], line["who"], f, engine="piper", bhaav=line["bhaav"])
        if not ok:
            ok, log = er.render_line(line["text"], line["who"], f, engine="free", bhaav=line["bhaav"])
        if ok:
            trimmed = f.with_name(f.stem + "_trim.mp3")
            if _trim_silence(f, trimmed):
                f = trimmed
        d = _dur(f) if f.exists() else 0
        out.append({**line, "file": str(f), "start": round(t, 2), "dur": d, "ok": ok})
        t += d + 0.15                      # chhota saans (0.45s "ruka-ruka" lagta tha)
    return out


def build(out: Path, lines: list[dict]) -> dict:
    total = max(l["start"] + l["dur"] for l in lines) + 1.2
    cmd = [_ff(), "-loglevel", "error", "-y"]
    filt, mix = [], []

    # 1) bed (loop)
    for asset, gain, loop in BED:
        p = LIB / asset
        if not p.exists():
            continue
        cmd += ["-stream_loop", "-1", "-i", str(p)]
        idx = (len(cmd) - 1) - sum(1 for a in cmd if a == "-i") + 1
        filt.append(f"[{sum(1 for a in cmd if a=='-i')-1}:a]aresample=44100,atrim=0:{total:.2f},"
                    f"volume={gain}dB[bed{len(mix)}]")
        mix.append(f"[bed{len(mix)}]")

    # 2) dialogue (duck bed) — har line ko halka warm + saaf karo
    for l in lines:
        if not l["ok"] or not Path(l["file"]).exists():
            continue
        cmd += ["-i", str(l["file"])]
        i = sum(1 for a in cmd if a == "-i") - 1
        filt.append(
            f"[{i}:a]aresample=44100,"
            "highpass=f=75,"
            "acompressor=threshold=-18dB:ratio=2.5:attack=8:release=180:makeup=2,"
            "treble=g=1.5:f=5500,"
            f"adelay={int(l['start']*1000)}|{int(l['start']*1000)},volume=-2dB[dl{len(mix)}]")
        mix.append(f"[dl{len(mix)}]")

    # 3) foley events
    for start, asset, gain in EVENTS:
        p = LIB / asset
        if not p.exists():
            continue
        cmd += ["-i", str(p)]
        i = sum(1 for a in cmd if a == "-i") - 1
        filt.append(f"[{i}:a]aresample=44100,adelay={int(start*1000)}|{int(start*1000)},"
                    f"volume={gain}dB[fx{len(mix)}]")
        mix.append(f"[fx{len(mix)}]")

    if not mix:
        return {"ok": False, "why": "koi audio nahi bana"}

    # bed ko dialogue ke waqt dheema karo (ducking) — sidechain compression
    voice_labels = [m for m in mix if m.startswith("[dl")]
    bed_labels = [m for m in mix if m.startswith("[bed")]
    fx_labels = [m for m in mix if m.startswith("[fx")]
    if voice_labels:
        filt.append("".join(voice_labels) +
                    f"amix=inputs={len(voice_labels)}:normalize=0[voice]")
        if bed_labels:
            filt.append("[voice]asplit=2[voiceA][voiceB]")
            filt.append(f"{bed_labels[0]}[voiceB]sidechaincompress="
                        "threshold=0.03:ratio=6:attack=20:release=350[bedduck]")
            tails = [bed_labels[0].replace("[bed0]", "[bedduck]")] + bed_labels[1:] + fx_labels
            filt.append("".join(tails) + f"amix=inputs={len(tails)}:normalize=0[bedmix]")
            filt.append("[bedmix][voiceA]" +
                        f"amix=inputs=2:normalize=0[mixed]")
        else:
            filt.append("[voice]" + "".join(fx_labels) +
                        f"amix=inputs={1 + len(fx_labels)}:normalize=0[mixed]")
    else:
        filt.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0[mixed]")

    filt.append("[mixed]loudnorm=I=-18:TP=-2:LRA=11,alimiter=limit=0.95[out]")
    cmd += ["-filter_complex", ";".join(filt), "-map", "[out]", "-t", f"{total:.2f}",
            "-c:a", "libmp3lame", "-b:a", "160k", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    cues = {"lines": lines, "total": round(total, 2), "bed": [b[0] for b in BED],
            "events": [{"at": e[0], "asset": e[1]} for e in EVENTS]}
    out.with_suffix(".cues.json").write_text(json.dumps(cues, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": r.returncode == 0 and out.exists(), "error": r.stderr[-300:] if r.returncode else "",
            "dur": _dur(out) if out.exists() else 0, "kb": out.stat().st_size // 1024 if out.exists() else 0}


def main() -> int:
    ap = argparse.ArgumentParser(description="kahani + background audio")
    ap.add_argument("--out", default=str(ROOT / "output" / "kahani.mp3"))
    ap.add_argument("--single", action="store_true", help="poori kahani ek hi awaaz me")
    ap.add_argument("--script", default="", help="JSON kahani file (lines/bed/events)")
    a = ap.parse_args()
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    tmp = wt.work_tmp("story")
    t0 = time.time()
    global STORY, BED, EVENTS
    if a.script:
        data = json.loads(Path(a.script).read_text(encoding="utf-8"))
        STORY = data["lines"]
        BED = [(b["file"], b["gain"]) for b in data.get("bed", [])]
        EVENTS = [(e["at"], e["file"], e["gain"]) for e in data.get("events", [])]
    lines = render_single(tmp) if a.single else render_lines(tmp)
    ok_lines = sum(1 for l in lines if l["ok"])
    rep = build(out, lines)
    rep.update({"lines_ok": ok_lines, "lines_total": len(lines), "seconds": round(time.time() - t0, 1)})
    print(json.dumps(rep, ensure_ascii=False))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
