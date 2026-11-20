#!/usr/bin/env python3
"""World Scape — kahani se asli duniya ki awaaz (aankh band karke mehsoos ho).

Kaam:
  1) Text padh kar jagah (gaon/ jungle/ nadi/ sadak), mausam (barish/ toofan), zameen
     (ghaas/ keechad/ patthar/ sookhe patte) aur cheezein (tractor/ gaadi/ ghanti) pehchano
  2) Teen parat banao: BED (laga rahe), MID (barish/ bijli), CLOSE (kadam/ patte)
  3) Dialogue ke neeche bed ko dheema karo (ducking), doori se awaaz dheemi + reverb
  4) Sab kuch ek file me — cues.json ke saath (kab, kya, kitna zor, kis taraf)

CLI:
  python tools/world_scape.py plan --text "वह जंगल से गुजरा, पास में नदी बह रही थी।"
  python tools/world_scape.py build --script scene.txt --out output/world --seconds 24
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "astra" / "library"
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------- pehchan
PLACES = {
    "gaon":      ["गाँव", "गांव", "गली", "चाय", "दुकान", "आँगन", "आंगन", "village"],
    "jungle":    ["जंगल", "झाड़ी", "झाड़ियों", "पेड़", "पत्ते", "forest", "bush"],
    "nadi":      ["नदी", "पानी", "घाट", "बहती", "river", "stream"],
    "sadak":     ["सड़क", "रास्ता", "ट्रैक्टर", "गाड़ी", "road", "tractor"],
    "station":   ["स्टेशन", "रेल", "ट्रेन", "प्लेटफ़ॉर्म", "platform"],
    "ghar":      ["कमरा", "घर", "दरवाज़ा", "दरवाजा", "room", "door"],
    "mandir":    ["मंदिर", "घंटी", "आरती", "temple"],
}
WEATHER = {
    "barish":  ["बारिश", "बरसात", "rain"],
    "toofan":  ["तूफ़ान", "तूफान", "आंधी", "storm", "हवा"],
    "bijli":   ["बिजली", "बादल", "गरज", "thunder", "cloud"],
}
GROUND = {
    "ghaas":   ["घास", "मैदान", "grass"],
    "keechad": ["कीचड़", "कीच", "mud"],
    "patthar": ["पत्थर", "कंकड़", "gravel"],
    "patte":   ["पत्ते", "सूखे", "leaves"],
    "lakdi":   ["लकड़ी", "फर्श", "wood"],
    "sadak":   ["सड़क", "road"],
}
PROPS = {
    "tractor": ["ट्रैक्टर", "tractor"],
    "gaadi":   ["गाड़ी", "कार", "bus", "car"],
    "ghanti":  ["घंटी", "bell"],
    "train":   ["ट्रेन", "रेलगाड़ी", "train"],
}

# library me asset (na ho to None — saaf batayenge)
ASSETS = {
    "bed": {
        "gaon":    "ambience/ambience_general.mp3",
        "jungle":  "ambience/bvk_forest_1.mp3",
        "nadi":    "ambience/forest_river_bed.mp3",
        "sadak":   "ambience/indian_city_road_ambience.mp3",
        "station": "transport/railway_station_3.mp3",
        "ghar":    "ambience/ambience_general.mp3",
        "mandir":  "ambience/aarti_ganga_small.mp3",
        "bazaar":  "crowd/kolkata_fish_market_1.mp3",
    },
    "nadi":   "ambience/forest_river_bed.mp3",
    "barish": "ambience/rain_gentle_1.mp3",
    "toofan": "ambience/desert_wind.mp3",
    "bijli":  "ambience/weather_rain_thunder_storm.mp3",
    "ground": {
        "ghaas":   "footsteps/steps_frozen_grass.mp3",
        "keechad": "footsteps/steps_muddy_road.mp3",
        "patthar": "footsteps/stone_pebbles_walk.mp3",
        "patte":   "footsteps/feet_leaves.mp3",
        "lakdi":   "footsteps/footsteps_parquet.mp3",
        "sadak":   "footsteps/footsteps_walk.mp3",
    },
    "props": {
        "tractor": "machines/tractor.mp3",       # library me na ho to None
        "gaadi":   "car/car_pass_1.mp3",
        "ghanti":  "bells/bell_1.mp3",
        "train":   "ambience/train_pass_1.mp3",
    },
}


def _hits(text: str, table: dict) -> list[str]:
    t = (text or "").lower()
    out = []
    for name, words in table.items():
        if any(w.lower() in t for w in words):
            out.append(name)
    return out


def plan_scene(text: str) -> dict:
    """Text se duniya ka plan — kya sunai dena chahiye."""
    places = _hits(text, PLACES) or ["gaon"]
    weather = _hits(text, WEATHER)
    ground = (_hits(text, GROUND) or ["ghaas"])[0]
    props = _hits(text, PROPS)
    layers = [{"kind": "bed", "asset": ASSETS["bed"].get(places[0]), "gain_db": -26, "loop": True}]
    if "nadi" in places:
        layers.append({"kind": "bed", "asset": ASSETS["nadi"], "gain_db": -28, "loop": True})
    for w in weather:
        layers.append({"kind": "mid", "asset": ASSETS.get(w), "gain_db": -20, "loop": w == "barish"})
    layers.append({"kind": "close", "asset": ASSETS["ground"].get(ground), "gain_db": -16, "loop": False})
    for p in props:
        layers.append({"kind": "event", "asset": ASSETS["props"].get(p), "gain_db": -14, "loop": False})
    missing = [l for l in layers if not l.get("asset") or not (LIB / l["asset"]).exists()]
    return {"places": places, "weather": weather, "ground": ground, "props": props,
            "layers": layers, "missing": missing,
            "note": "jo asset nahi mila, use 'missing' me likha hai — chhupaya nahi"}


def duck_curve(dialogue: list[tuple[float, float]], base_db: float, duck_db: float = 9.0) -> str:
    """Dialogue ke waqt bed dheema — ffmpeg volume expression."""
    if not dialogue:
        return f"volume={base_db}dB"
    parts = []
    for st, en in dialogue:
        parts.append(f"between(t,{st:.2f},{en:.2f})")
    cond = "+".join(parts)
    return f"volume='{base_db} - {duck_db}*({cond})':eval=frame"


def build(text: str, out_dir: str, seconds: float = 24.0, dialogue: list[dict] | None = None) -> dict:
    """Duniya banao — bed + mid + close + events, dialogue ke neeche ducking."""
    from imageio_ffmpeg import get_ffmpeg_exe
    ff = get_ffmpeg_exe()
    od = Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    plan = plan_scene(text)
    dialogue = dialogue or []
    spans = [(d["start"], d["start"] + d["dur"]) for d in dialogue]
    inputs, filt, mix = [], [], []
    n_inputs = 0
    for layer in plan["layers"]:
        asset = layer.get("asset")
        if not asset or not (LIB / asset).exists():
            continue
        if layer["loop"]:
            inputs += ["-stream_loop", "-1", "-i", str(LIB / asset)]
        else:
            inputs += ["-i", str(LIB / asset)]
        idx = n_inputs          # ffmpeg input index 0 se shuru hota hai
        n_inputs += 1
        g = layer["gain_db"]
        if layer["kind"] == "bed":
            vol = duck_curve(spans, g)
        else:
            vol = f"volume={g}dB"
        filt.append(f"[{idx}:a]aresample=44100,atrim=0:{seconds},{vol}[l{idx}]")
        mix.append(f"[l{idx}]")
    if not mix:
        return {"ok": False, "reason": "koi asset nahi mila", "plan": plan}
    filt.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=longest[m]")
    filt.append("[m]aecho=0.8:0.85:22:0.16,loudnorm=I=-18:TP=-2:LRA=11,alimiter=limit=0.95[out]")
    out = od / "world.mp3"
    cmd = [ff, "-loglevel", "error", "-y"] + inputs + ["-filter_complex", ";".join(filt),
           "-map", "[out]", "-t", str(seconds), "-c:a", "libmp3lame", "-b:a", "160k", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    cues = {"plan": plan, "dialogue": dialogue, "seconds": seconds,
            "file": str(out) if r.returncode == 0 else None, "error": r.stderr[:200] if r.returncode else ""}
    (od / "world.cues.json").write_text(json.dumps(cues, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": r.returncode == 0, "file": str(out), "cues": str(od / "world.cues.json"),
            "layers_used": len(mix), "missing": len(plan["missing"]), "plan": plan}


def main() -> int:
    ap = argparse.ArgumentParser(description="kahani se duniya ki awaaz")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--text", required=True)
    b = sub.add_parser("build"); b.add_argument("--script", required=True)
    b.add_argument("--out", required=True); b.add_argument("--seconds", type=float, default=24.0)
    a = ap.parse_args()
    if a.cmd == "plan":
        print(json.dumps(plan_scene(a.text), ensure_ascii=False, indent=2)); return 0
    text = Path(a.script).read_text(encoding="utf-8")
    rep = build(text, a.out, a.seconds)
    print(json.dumps({k: rep[k] for k in ("ok", "file", "layers_used", "missing") if k in rep},
                     ensure_ascii=False, indent=2))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
