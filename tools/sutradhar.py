#!/usr/bin/env python3
"""
sutradhar.py — Seetal/ASTRA ka EK hi raasta (master pipeline).

Samasya: system me 8+ alag "build" raaste hain (story_local.build, local_story/story_local.build,
horror_story.build, awaaz_studio.sunao, story_audio.build, world_scape.build, duniya.main,
engine_router.render_story). Har raasta kuch kaam karta hai, kuch bhool jata hai
(bed, ducking, nadi ka lagataar chalna, loudness...).

Hal: sirf YAHI file kahani banati hai. Har kaam ka ek hi maalik (module) hai, ek hi kram hai,
aur aakhir me "Pakki Jaanch" asli awaaz ko naapti hai. Koi bhi zaroori cheez chhooti
to file "PASS" nahi hogi — saaf bataayega kya chhoota aur kahan.

Rakhne ki jagah: tools/sutradhar.py  (wahi folder jisme world/, realtime/, local_story/ hain)

Chalana:
  python tools/sutradhar.py wire                  # har stage ka module/function/argument mil raha hai?
  python tools/sutradhar.py run kahani.txt out/   # poori kahani, sab stage, phir pakki jaanch
  python tools/sutradhar.py check out/            # bani hui kahani ki dobara jaanch (stems se)
"""
from __future__ import annotations

import importlib
import inspect
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

SR = 44100

# ---------------------------------------------------------------------------
# 1) KAAM KA NAKSHA — har kaam ka EK maalik. Duplicate files yahan nahi aate.
#    (module, function, zaroori arguments, zaroori?, kaam)
# ---------------------------------------------------------------------------
STAGES = [
    # --- shabd aur awaaz ---
    ("script",    "script_pipeline",     "prepare_script", ["text", "max_chars", "default_speaker"], True,  "Script ko lines + kirdaar + bhaav me todo"),
    ("shabd",     "local_story.respell", "respell",        ["text", "hspell", "safe"],              False, "Hindi shabd-mala theek (chandrabindu/nasal)"),
    ("bhaav",     "realtime.bhaav",      "target",         ["line", "context"],                     False, "Har line ka lakshya bhaav"),
    ("awaaz",     "engine_router",       "render_line",    ["text", "character", "out", "engine", "fallbacks", "bhaav"], True, "Line ki awaaz (engine chain + fallback)"),
    ("shabd_live","local_story.shabd_live", "best",        ["text", "voice"],                       False, "Shabd jaanch + sudhaar (aadhe shabd ka ilaaz; SEETAL_WORD_CHECK=1)"),
    ("gates",     "realtime.gates",      "check",          ["y", "sr", "profile", "text"],          False, "Line ki jaanch: echo, gap, presence"),
    ("gate_fix",  "realtime.gates",      "apply_fix",      ["y", "sr", "fix", "gate_res", "text"],  False, "Line par hi sudhaar"),
    ("ruke",      "world.duniya",        "pause_after",    ["text", "next_who", "who", "scene_break", "wmap", "rng"], True, "Lines ke beech insaan jaise ruke"),
    ("voice_eq",  "world.duniya",        "voice_chain",    ["v"],                                   True,  "Awaaz ka halka EQ"),
    # --- duniya (background) ---
    ("spot",      "world.spotting",      "spot",           ["lines", "total", "kb", "wmap", "llm", "story"], True, "Script se awaazein + kab shuru/kab band (nadi jaise STATE)"),
    ("jagah",     "world.spotting",      "place_timeline", ["lines", "total", "kb"],                True,  "Andar/bahar timeline"),
    ("mausam",    "world.spotting",      "weather_timeline", ["lines", "total", "kb"],              True,  "Barish/hawa timeline"),
    ("harkat",    "world.harkat",        "plan_actions",   ["lines", "total", "wmap"],              True,  "Kadam, daudna, girna — kab, kahan, kis bhaav me"),
    ("scene",     "world.duniya",        "plan_scene",     ["lines", "total", "wmap", "overrides"], True,  "Har layer ka gain-envelope (nadi, hawa, chidiya...)"),
    ("bhaav_env", "world.duniya",        "apply_emotion",  ["env", "emo", "total"],                 True,  "Dar -> chidiyan chup; khushi -> zyada"),
    ("mausam_env","world.duniya",        "apply_weather",  ["env", "spans", "kb", "total", "events", "cues", "rng"], True, "Mausam ko env me lagao"),
    ("world",     "world.duniya",        "render_world",   ["total", "env", "walks", "wmap", "lib", "rng", "tod", "river_pass"], True, "Lagataar background (bed) banao"),
    ("sheet",     "world.duniya",        "render_sheet",   ["total", "sheet", "kb", "lib", "rng", "ind", "lines"], True, "Spotted events ki awaaz"),
    ("fx",        "world.duniya",        "render_fx",      ["total", "events", "emo", "rng"],       True,  "Harkat ki awaazein"),
    ("andar",     "world.duniya",        "place_env",      ["places", "total"],                     True,  "Andar=1 / bahar=0 curve"),
    ("deewar",    "world.duniya",        "indoor_muffle",  ["world", "ind"],                        True,  "Andar ho to bahar ki duniya dabi hui"),
    # --- mix aur master ---
    ("mix",       "world.duniya",        "mix",            ["voice", "world", "wmap", "voice_pan", "lines", "fx", "ind", "phone_lines"], True, "Awaaz + duniya + ducking"),
    ("master",    "world.duniya",        "master",         ["st", "out_path", "lufs", "tp"],        True,  "Loudness (LUFS) + true-peak"),
    # --- jaanch ---
    ("qa_world",  "world.world_qa",      "judge",          ["path"],                                True,  "Duniya ki QA"),
    ("self_improve","self_improve",         "deep",           ["path"],                               False, "Render ka gehra naap + shakha diagnosis + fix plan"),
    ("manifest",  "render_manifest",     "build",          ["script", "audio", "out", "settings"],  False, "Hisaab-kitaab (kya bana, kaise)"),
]

# Ye files purane/doosre raaste hain — sutradhar inhe KABHI import nahi karta.
PURANE_RAASTE = [
    "story_local.py (root)  == local_story/story_local.py ki copy — ek hatao",
    "awaaz_studio.sunao, story_audio.build, world_scape.build, local_story/horror_story.build",
    "audio_read.py .. audio_read5.py (audio_read6 sabse naya)",
    "sound_id.py, sound_id2.py (sound_id3 naya)",
    "music_make.py (music_make2 naya)",
]


# ---------------------------------------------------------------------------
# 2) HISAAB (ledger) — har stage ne kya kiya, likha jaata hai. Kuch chhoota to dikhega.
# ---------------------------------------------------------------------------
@dataclass
class Hisaab:
    rows: list = field(default_factory=list)

    def note(self, stage, ok, detail="", secs=0.0):
        self.rows.append({"stage": stage, "ok": bool(ok), "detail": str(detail)[:300], "secs": round(secs, 2)})

    def bad(self):
        return [r for r in self.rows if not r["ok"]]

    def print(self):
        for r in self.rows:
            print(f"  {'OK ' if r['ok'] else 'XX '} {r['stage']:<11} {r['secs']:>6}s  {r['detail']}")


def get_fn(module, fn):
    return getattr(importlib.import_module(module), fn)


# ---------------------------------------------------------------------------
# 3) WIRE — har stage ka module + function + argument naam sach me hain?
# ---------------------------------------------------------------------------
def wire() -> int:
    bad = 0
    print("Stage wiring (module.function — zaroori arguments):")
    for name, mod, fn, args, req, kaam in STAGES:
        try:
            f = get_fn(mod, fn)
            params = list(inspect.signature(f).parameters)
            missing = [a for a in args if a not in params]
            if missing:
                raise TypeError(f"argument nahi mile: {missing} (asli: {params})")
            left = [p for p in params if p not in args]
            print(f"  OK  {name:<11} {mod}.{fn}" + (f"   (default par chhode: {left} — dekh lo zaroori to nahi)" if left else ""))
        except Exception as e:  # noqa: BLE001
            bad += req
            print(f"  {'XX' if req else '--'}  {name:<11} {mod}.{fn}  ->  {e}")
    print("\nPurane raaste (sutradhar inhe use nahi karta):")
    for p in PURANE_RAASTE:
        print("  -", p)
    print(f"\n{'SAB JUDA HAI' if not bad else f'{bad} zaroori stage toote hain'}")
    return 1 if bad else 0


# ---------------------------------------------------------------------------
# 4) PAKKI JAANCH — modules ki baat par bharosa nahi; asli stems naapo.
# ---------------------------------------------------------------------------
def _db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-9) if len(x) else -120.0


def _mono(x):
    x = np.asarray(x, dtype=np.float32)
    return x.mean(axis=0) if x.ndim == 2 and x.shape[0] in (1, 2) else (x.mean(axis=1) if x.ndim == 2 else x)


def loop_score(w, sr, hop_s=0.05, lo=5, hi=60):
    """Background ke 'rang' (band energy) ka pattern kitna hubahu dohraata hai. 1 = bilkul loop."""
    hop = int(hop_s * sr); n = len(w) // hop
    if n < int(2 * lo / hop_s):
        return {"score": 0.0, "lag": 0}
    fr = w[: n * hop].reshape(n, hop)
    spec = np.abs(np.fft.rfft(fr * np.hanning(hop), axis=1))
    bands = np.array_split(spec, 8, axis=1)
    feat = np.log(np.stack([b.mean(axis=1) for b in bands], 1) + 1e-9)
    feat = (feat - feat.mean(0)) / (feat.std(0) + 1e-9)
    best, lag_b = 0.0, 0
    for lag in range(int(lo / hop_s), min(int(hi / hop_s), n // 2)):
        a, b = feat[:-lag].ravel(), feat[lag:].ravel()
        c = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        if c > best:
            best, lag_b = c, lag * hop_s
    return {"score": best, "lag": lag_b}


def _lufs_ffmpeg(path):
    """Asli integrated LUFS (ffmpeg ebur128) — approx se nahi."""
    import subprocess
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        import re
        m = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", out)
        return float(m[-1]) if m else None
    except Exception:
        return None


def lufs_target(channels):
    """Stereo -16 LUFS, mono -19 LUFS (Apple/Google podcast niyam). Master aur jaanch dono yahi use karein."""
    return -16.0 if channels >= 2 else -19.0


def _channels(x):
    x = np.asarray(x)
    return 1 if x.ndim == 1 else min(x.shape)


def _lufs_approx(x, sr):
    """Halka LUFS andaaza (K-weighting ke bina, gated). Asli naap world_qa.lufs se."""
    blk = int(0.4 * sr)
    vals = [_db(x[i:i + blk]) for i in range(0, max(1, len(x) - blk), blk // 4)]
    vals = [v for v in vals if v > -70]
    return float(np.mean(vals)) - 0.691 if vals else -120.0


def pakki_jaanch(voice, world, final, sr, lines, states, target_lufs=-16.0, final_path=None):
    """
    voice, world, final : numpy (mono ya stereo) — ALAG stems zaroori hain.
    lines  : [{start, end, text, who}]
    states : [{name, start, end}]  — jaise nadi jo script ke hisaab se lagataar bahni chahiye.
    Returns list of {jaanch, ok, value, fix}
    """
    v, w, f = _mono(voice), _mono(world), _mono(final)
    n = min(len(v), len(w), len(f))
    v, w, f = v[:n], w[:n], f[:n]
    out = []

    def add(j, ok, val, fix):
        out.append({"jaanch": j, "ok": bool(ok), "value": val, "fix": "" if ok else fix})

    # 1. Background hai bhi?
    wdb = _db(w)
    add("bed_hai", wdb > -45, f"{wdb:.1f} dBFS", "render_world chala hi nahi ya env khaali — 'scene' stage dekho")

    # 2. Background kabhi poora gayab to nahi (2s se lamba sannata)?
    blk = sr
    lv = np.array([_db(w[i:i + blk]) for i in range(0, n - blk + 1, blk)]) if n >= blk else np.array([wdb])
    run, longest = 0, 0
    for d in lv:
        run = run + 1 if d < -60 else 0
        longest = max(longest, run)
    add("bed_lagataar", longest < 2, f"sabse lamba khaali: {longest}s", "room_tone/bed ko poori lambai tak loop karo (loop_to)")

    # 3. Har STATE (nadi, barish...) apni poori span me chal rahi hai?
    for s in states:
        a, b = int(s["start"] * sr), int(min(s["end"], n / sr) * sr)
        seg = [_db(w[i:i + blk]) for i in range(a, max(a + 1, b - blk + 1), blk)] or [-120]
        dead = sum(1 for d in seg if d < -55)
        add(f"state:{s['name']}", dead == 0 and len(seg) > 0,
            f"{s['start']:.0f}-{s['end']:.0f}s, {dead}/{len(seg)} second chup",
            f"'{s['name']}' beech me band hua — spotting.find_stop ka stop-shabd ya env curve dekho")

    # 4. Ducking: bolte waqt bed neeche, chup me upar.
    speech = np.zeros(n, bool)
    for L in lines:
        speech[int(L["start"] * sr):int(L["end"] * sr)] = True
    if speech.any() and (~speech).any():
        # stems se naap (projection se nahi — wo misalign ho jaata tha, naap se mila)
        _sv = _sw = None
        if False:
            try:
                import soundfile as _sf
                _v = _mono(_sf.read(str(_sv))[0]); _w = _mono(_sf.read(str(_sw))[0])
                _n = min(len(_v), len(_w), len(f))
                _sp = np.zeros(_n, dtype=bool)
                for L in lines:
                    _sp[int(L["start"] * sr):min(_n, int(L["end"] * sr))] = True
                if _sp.any() and (~_sp).any():
                    _v, _w = _v[:_n], _w[:_n]
                    during_w, gaps_w = _db(_w[_sp]), _db(_w[~_sp])
                    diff = gaps_w - during_w
                    add("ducking", 1.5 <= diff <= 8.0, f"chup-me {gaps_w:.1f} / bolte {during_w:.1f} dB (fark {diff:.1f})",
                        "ducking 2-6 dB rakho")
                    snr = _db(_v[_sp]) - during_w
                    add("awaaz_saaf", snr >= 10, f"voice/bed {snr:.1f} dB (stems se)", "bed level kam karo")
                    _stems_done = True
            except Exception:
                _stems_done = False
        else:
            _stems_done = False
    if not _stems_done:
        # ducking mix() me lagti hai — isliye FINAL me se awaaz hata kar bachi duniya naapo
        # 1) awaaz/bed: stems se (voice stem vs world stem)
        _n2 = min(len(f), len(v), len(w))
        v2, w2 = v[:_n2], w[:_n2]
        speech = speech[:_n2]
        # 2) ducking: duniya ke asli (ducked) stem se — residual se nahi
        during, gaps = _db(w2[speech]), _db(w2[~speech])
        diff = gaps - during
        add("ducking", 1.5 <= diff <= 8.0, f"chup-me {gaps:.1f} / bolte {during:.1f} dB (fark {diff:.1f})",
            "ducking 2-6 dB rakho; zyada dabane se duniya saans leti lagti hai")
        # 5. Awaaz bed se upar saaf?
        snr = _db(v2[speech]) - during
        add("awaaz_saaf", snr >= 10, f"voice/bed {snr:.1f} dB (stems se)", "bed bahut tez — world level kam karo")
    else:
        add("ducking", False, "lines ka samay nahi mila", "lines me start/end bharo (repace ke baad)")

    # 5b. Loop pakda to nahi jaata? (background ka pattern 5-60 s baad hubahu dohraaya)
    lp = loop_score(w, sr)
    add("loop_nahi", lp["score"] < 0.92,
        (f"sabse milta dohraav {lp['score']:.2f} @ {lp['lag']:.0f}s" if lp["lag"] else "kahani 10s se chhoti — loop jaancha nahi"),
        "bed se khaas awaazein (chidiya, kutta) nikaal kar alag random events banao; loop_to ki jagah parten")

    # 6. Loudness + clipping  (stereo -16, mono -19 LUFS; true-peak -1 dB) — target caller deta hai
    L = _lufs_ffmpeg(final_path) if final_path else None
    if L is None:
        L = _lufs_approx(f, sr)
    add("loudness", abs(L - target_lufs) <= 1.0, f"~{L:.1f} LUFS (lakshya {target_lufs})", "master() nahi chala ya lufs galat")
    peak = float(np.max(np.abs(f))) if n else 0
    add("clip_nahi", peak < 0.999, f"peak {peak:.3f}", "master me true-peak limit (tp=-1)")

    # 7. Final me sach me duniya mili hai? (final - voice ≈ world)
    resid = _db(f[~speech]) if (~speech).any() else -120
    add("final_me_duniya", resid > -50, f"chup jagah par final {resid:.1f} dB", "mix() me world stem joda hi nahi gaya")
    return out


# ---------------------------------------------------------------------------
# 5) RUN — ek hi kram. Har stage hisaab me likha jaata hai.
# ---------------------------------------------------------------------------
TRACE = []          # har stage ka asli execution: input shapes, output shape, time


def _shape(x):
    """Kisi bhi value ka chhota sa chitra (trace ke liye)."""
    try:
        import numpy as _np
        if isinstance(x, _np.ndarray):
            return f"np{tuple(x.shape)}:{x.dtype}"
    except Exception as _e:
        print(f'[chhoti dikkat] {type(_e).__name__}: {_e}', file=__import__('sys').stderr)
    if isinstance(x, (list, tuple)):
        inner = _shape(x[0]) if len(x) else "khaali"
        return f"{type(x).__name__}[{len(x)}] of {inner}"
    if isinstance(x, dict):
        return f"dict({len(x)}): {sorted(list(x))[:6]}"
    if isinstance(x, str):
        return f"str[{len(x)}]"
    if x is None:
        return "None"
    if isinstance(x, (int, float, bool)):
        return f"{type(x).__name__}={x}"
    return type(x).__name__


def _stage(h: Hisaab, name, fn, *a, required=True, **kw):
    t = time.time()
    try:
        _t0 = time.time()
        r = fn(*a, **kw)
        _dt = time.time() - _t0
        h.note(name, True, "", time.time() - t)
        TRACE.append({"stage": name,
                      "fn": f"{getattr(fn, '__module__', '')}.{getattr(fn, '__name__', '?')}",
                      "in": [_shape(x) for x in a], "out": _shape(r),
                      "secs": round(_dt, 2), "kw": sorted(kw) if kw else []})
        return r
    except Exception as e:  # noqa: BLE001
        h.note(name, not required, f"{type(e).__name__}: {e}", time.time() - t)
        if required:
            raise StageFail(name, traceback.format_exc())
        return None


class StageFail(Exception):
    def __init__(self, stage, tb):
        super().__init__(stage)
        self.stage, self.tb = stage, tb


def space_voice(voice, ind, rng, wet_out=0.10, wet_in=0.16):
    """
    Awaaz ko usi jagah me rakho jahan duniya hai (film me 'worldizing').
    bahar: duniya.outdoor_reverb (khuli, halki); andar: pyroomacoustics ka kamra (ho to), warna chhota reverb.
    ind curve (0 bahar .. 1 andar) se dono mile. Wet kam rakha — awaaz saaf rahe.
    """
    v = _mono(voice).astype(np.float32)
    out_rev = get_fn("world.duniya", "outdoor_reverb")
    # BUG: outdoor_reverb stereo (2,n) maangta hai — mono dene par crash hota tha
    bahar = _mono(out_rev(np.vstack([v, v]).astype(np.float32), 1.2, 11))[: len(v)]
    try:
        import pyroomacoustics as pra
        room = pra.ShoeBox([4.0, 3.5, 2.8], fs=SR, materials=pra.Material(0.35), max_order=8)
        room.add_source([1.2, 1.5, 1.6]); room.add_microphone([2.6, 2.0, 1.6]); room.compute_rir()
        rir = np.asarray(room.rir[0][0], np.float32); rir /= np.max(np.abs(rir)) + 1e-9
        import scipy.signal as ss
        andar = ss.fftconvolve(v, rir)[: len(v)]
    except Exception:  # pyroomacoustics nahi — chhota reverb
        andar = _mono(out_rev(np.vstack([v, v]).astype(np.float32), 0.45, 12))[: len(v)]
    def _fit(x):
        x = np.asarray(x, np.float32); return np.pad(x, (0, max(0, len(v) - len(x))))[: len(v)]
    bahar, andar = _fit(bahar), _fit(andar)
    bahar *= (np.sqrt(np.mean(v**2)) / (np.sqrt(np.mean(bahar**2)) + 1e-9))
    andar *= (np.sqrt(np.mean(v**2)) / (np.sqrt(np.mean(andar**2)) + 1e-9))
    k = np.clip(np.interp(np.arange(len(v)), np.linspace(0, len(v) - 1, len(ind)), np.asarray(ind, float)), 0, 1) \
        if ind is not None and len(ind) else np.zeros(len(v))
    wet = (1 - k) * wet_out * bahar + k * wet_in * andar
    return v + wet.astype(np.float32)


RAAT = ("रात", "अँधेरा", "अंधेरा", "आधी रात", "चाँद", "तारे")
SUBAH = ("सुबह", "सवेरा", "भोर")
SHAAM = ("शाम", "सूरज ढल")
PHONE_WORDS = ("फ़ोन पर", "फोन पर", "फ़ोन से", "फोन से")


def time_of_day(lines):
    """Script se din/raat — render_world ko 'tod' dena zaroori hai, warna raat ka sannata nahi banta."""
    txt = " ".join(L["text"] for L in lines)
    pos = {k: max((txt.rfind(w) for w in ws), default=-1) for k, ws in
           (("raat", RAAT), ("subah", SUBAH), ("shaam", SHAAM))}
    k = max(pos, key=pos.get)
    return k if pos[k] >= 0 else "din"


def _wav(path):
    import soundfile as sf
    y, sr = sf.read(str(path), always_2d=False, dtype="float32")
    if sr != SR:
        import scipy.signal as ss
        y = ss.resample_poly(y, SR, sr, axis=0)
    return _mono(y)


def run(script_path: str, out_dir: str) -> int:
    import soundfile as sf
    out = Path(out_dir); (out / "lines").mkdir(parents=True, exist_ok=True)
    h, rng = Hisaab(), np.random.default_rng(7)
    text = Path(script_path).read_text(encoding="utf-8")
    F = {name: (mod, fn) for name, mod, fn, *_ in STAGES}
    g = lambda s: get_fn(*F[s])  # noqa: E731

    try:
        # --- 1. script ---
        items = _stage(h, "script", g("script"), text, 400, "vachak")
        lines = [{"who": it.get("speaker") or it.get("who", "vachak"),
                  "text": it.get("text", ""), "bhaav": it.get("emotion") or it.get("bhaav")} for it in items]

        # --- 2. har line: shabd -> bhaav -> awaaz -> gates ---
        wavs, lock = [], {}          # lock: kirdaar -> engine (poori kahani ek hi awaaz)
        for i, L in enumerate(lines):
            t2 = _stage(h, "shabd", g("shabd"), L["text"], True, True, required=False) or L["text"]
            if not L["bhaav"]:
                tg = _stage(h, "bhaav", g("bhaav"), L["text"], lines[max(0, i - 2):i], required=False)
                L["bhaav"] = (tg or {}).get("bhaav") if isinstance(tg, dict) else tg
            p = out / "lines" / f"{i:04d}.wav"
            eng = lock.get(L["who"])
            ok, tries = _stage(h, "awaaz", g("awaaz"), t2, L["who"], str(p), eng, [] if eng else None, L["bhaav"])
            if not ok and eng:
                # locked engine fail: doosra engine chala sakte hain, par ZOR se likho — awaaz badal jaayegi
                ok, tries = _stage(h, "awaaz", g("awaaz"), t2, L["who"], str(p), None, None, L["bhaav"])
                h.note("awaaz_lock", False, f"line {i}: '{L['who']}' ka engine {eng} fail, doosra laga — awaaz badli hogi")
            if not ok:
                raise StageFail("awaaz", f"line {i} kisi engine se nahi bani: {tries}")
            used = next((t.get("engine") for t in reversed(tries or []) if isinstance(t, dict) and t.get("ok")), None)
            if used and L["who"] not in lock:
                lock[L["who"]] = used
            import os as _os
            if _os.environ.get("SEETAL_WORD_CHECK") == "1":
                try:
                    _sl = get_fn("local_story.shabd_live", "best")
                    _r = _sl(t2, "rohan", keep=p)      # behtar roop mila to wahi line likh do
                    _b = (_r or {}).get("best") or {}
                    h.note("shabd_live", _b.get("cer", 1) < 0.15, f"line {i}: cer={_b.get('cer')} variant={_b.get('variant')}")
                except Exception as _e:
                    h.note("shabd_live", False, f"line {i}: {type(_e).__name__}")
            y = _wav(p)
            res = _stage(h, "gates", g("gates"), y, SR, None, L["text"], required=False) or []
            for gr in res:
                if not gr.get("ok", True) and gr.get("fix"):
                    r2 = _stage(h, "gate_fix", g("gate_fix"), y, SR, gr["fix"], gr, L["text"], required=False)
                    if r2:
                        y = r2[0]
            wavs.append(y)

        # --- 3. timeline (insaan jaise ruke) -> voice stem ---
        _wmp = HERE.parent / "knowledge" / "world-map.json"      # asli gyaan yahan hai (world_map.json nahi)
        if not _wmp.exists():
            _wmp = HERE / "world" / "world-map.json"
        wmap = get_fn("world.duniya", "load_map")(str(_wmp)) if _wmp.exists() else {}
        parts, t = [], 0.0
        for i, (L, y) in enumerate(zip(lines, wavs)):
            L["start"], L["end"] = t, t + len(y) / SR
            parts.append(y)
            nxt = lines[i + 1]["who"] if i + 1 < len(lines) else None
            gap = _stage(h, "ruke", g("ruke"), L["text"], nxt, L["who"],
                         get_fn("world.duniya", "is_scene_start")(lines[i + 1]["text"]) if nxt else False, wmap, rng)
            gap = float(gap or 0.4)
            parts.append(np.zeros(int(gap * SR), np.float32))
            t = L["end"] + gap
        voice = _stage(h, "voice_eq", g("voice_eq"), np.concatenate(parts))
        total = len(voice) / SR

        # --- 4. duniya: SAB stage, ek ke baad ek, koi skip nahi ---
        _kb = HERE.parent / "knowledge" / "sound-events.json"
        if not _kb.exists():
            _kb = HERE / "world" / "sound-events.json"
        kb = get_fn("world.spotting", "load_events")(str(_kb))
        cues = _stage(h, "spot", g("spot"), lines, total, kb, wmap, False, script_path)
        places = _stage(h, "jagah", g("jagah"), lines, total, kb)
        wspans = _stage(h, "mausam", g("mausam"), lines, total, kb)
        acts = _stage(h, "harkat", g("harkat"), lines, total, wmap)
        events, emo = (acts if isinstance(acts, tuple) else (acts, []))
        cues = list(events or [])      # BUG: cues pehle banaye hi nahi gaye the (mausam_env crash)
        scene = _stage(h, "scene", g("scene"), lines, total, wmap, None)
        # plan_scene -> (env, walks, river_pan, events_extra) — chaaron chahiye, ek bhi chhoota to awaaz kam
        if isinstance(scene, tuple):
            env, walks, river_pan, extra = (list(scene) + [None] * 4)[:4]
        else:
            env, walks = scene.get("env", scene), scene.get("walks", [])
            river_pan, extra = scene.get("river_pan"), scene.get("events_extra")
        if extra:
            events = list(events or []) + list(extra)
        tod = time_of_day(lines)
        env = _stage(h, "bhaav_env", g("bhaav_env"), env, emo, total)
        env = _stage(h, "mausam_env", g("mausam_env"), env, wspans, kb, total, events, cues, rng) or env
        _libroot = HERE.parent / "library"
        if not _libroot.exists():
            _libroot = Path("/scratch/input")          # Swag ki 2000+ recordings
        lib = get_fn("world.duniya", "Library")(str(_libroot))
        synth_chala = []
        _find = lib.find
        def _find_log(*a, **kw):                     # asli recording na mili to likho (chupchap synth nahi)
            r = _find(*a, **kw)
            if not r:
                synth_chala.append(a[0] if a else kw)
            return r
        lib.find = _find_log
        ind = _stage(h, "andar", g("andar"), places, total)
        world = _stage(h, "world", g("world"), total, env, walks, wmap, lib, rng, tod, river_pan)
        if isinstance(world, tuple):         # render_world (audio, used) deta hai
            world = world[0]
        # cue contract: render_sheet "event" maangta hai, harkat "kind" deta hai — normalize
        for _c in (cues or []):
            if isinstance(_c, dict) and "event" not in _c:
                _c["event"] = _c.get("kind") or _c.get("name") or _c.get("state") or "birds"
            if isinstance(_c, dict) and "t" not in _c and "t0" in _c:
                _c["t"] = _c["t0"]
        sheet_aud = _stage(h, "sheet", g("sheet"), total, {"cues": cues, "motion": walks or []}, kb, lib, rng, ind, lines)   # cues + motion dono chahiye
        if isinstance(sheet_aud, tuple):     # render_sheet (audio, log) deta hai
            sheet_aud = sheet_aud[0]
        fx = _stage(h, "fx", g("fx"), total, events, emo, rng)
        if isinstance(fx, tuple):            # render_fx (audio, log) deta hai
            fx = fx[0]
        if sheet_aud is not None:
            fx = fx + sheet_aud if fx is not None else sheet_aud
        world = _stage(h, "deewar", g("deewar"), world, ind)
        if synth_chala:
            h.note("asli_awaaz", False, f"library me nahi mili, synth chala: {sorted(set(map(str, synth_chala)))[:15]}")
        voice = _stage(h, "jagah_goonj", space_voice, voice, ind, rng)

        # stems hamesha alag save — jaanch inhi se hoti hai
        sf.write(out / "stem_voice.wav", _mono(voice), SR)
        sf.write(out / "stem_world.wav", _mono(world) + (_mono(fx) if fx is not None else 0), SR)

        # --- 5. mix + master ---
        phone_lines = [i for i, L in enumerate(lines) if any(w in L["text"] for w in PHONE_WORDS)]
        # bed ko awaaz ke neeche rakho (naap: pehle bed awaaz se 21 dB tez tha)
        world = world * (10 ** (-9 / 20.0))
        if fx is not None:
            fx = fx * (10 ** (-6 / 20.0))
        st = _stage(h, "mix", g("mix"), voice, world, wmap, 0.0, lines, fx, ind, phone_lines)
        try:
            _parts = get_fn("world.duniya", "LAST_PARTS") if False else None
        except Exception:
            _parts = None
        try:
            import world.duniya as _D
            if getattr(_D, "LAST_PARTS", None):
                import soundfile as _sf
                _sf.write(out / "stem_world_ducked.wav", _D.LAST_PARTS["world_ducked"].T if _D.LAST_PARTS["world_ducked"].ndim == 2 else _D.LAST_PARTS["world_ducked"], SR)
                _sf.write(out / "stem_voice_used.wav", _D.LAST_PARTS["voice"] if _D.LAST_PARTS["voice"].ndim == 1 else _D.LAST_PARTS["voice"].T, SR)
        except Exception as _e:
            print(f'[chhoti dikkat] {type(_e).__name__}: {_e}', file=__import__('sys').stderr)
        final_p = out / "kahani.wav"
        target_lufs = lufs_target(_channels(st))
        _stage(h, "master", g("master"), st, str(final_p), target_lufs, -1.0)
        _stage(h, "qa_world", g("qa_world"), str(final_p))
        _stage(h, "self_improve", g("self_improve"), str(final_p), required=False)
        _stage(h, "manifest", g("manifest"), script_path, str(final_p), str(out / "manifest.json"),
               {"lufs": target_lufs}, required=False)

        # states nikaalo (nadi jaise lagataar wale) — pakki jaanch ke liye
        states = [{"name": c.get("name") or c.get("kind"), "start": c["start"], "end": c["end"]}
                  for c in (cues or []) if isinstance(c, dict) and c.get("end") and c.get("state", c.get("kind") == "state")]
        json.dump({"lines": lines, "states": states}, open(out / "timeline.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1, default=str)
    except StageFail as e:
        print(f"\nRUKA: stage '{e.stage}' fail — aage nahi badha (aadhi kahani nahi banegi).\n")
        h.print()
        print("\n" + e.tb[-1500:])
        json.dump(h.rows, open(out / "hisaab.json", "w"), indent=1)
        return 2

    h.print()
    json.dump(h.rows, open(out / "hisaab.json", "w"), indent=1)
    json.dump(TRACE, open(out / "trace.json", "w"), ensure_ascii=False, indent=1)
    return check(out_dir)


def check(out_dir: str) -> int:
    import soundfile as sf
    out = Path(out_dir)
    target_lufs = lufs_target(sf.info(str(out / "kahani.wav")).channels)
    tl = json.load(open(out / "timeline.json", encoding="utf-8"))
    _wp = out / "stem_world_ducked.wav"
    _world = _wav(_wp) if _wp.exists() else _wav(out / "stem_world.wav")
    res = pakki_jaanch(_wav(out / "stem_voice.wav"), _world, _wav(out / "kahani.wav"),
                       SR, tl["lines"], tl["states"], target_lufs, final_path=str(out / "kahani.wav"))
    print("\nPakki jaanch (asli awaaz naap kar):")
    for r in res:
        print(f"  {'OK ' if r['ok'] else 'XX '} {r['jaanch']:<18} {r['value']}" + (f"\n        hal: {r['fix']}" if r["fix"] else ""))
    json.dump(res, open(out / "jaanch.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    bad = [r for r in res if not r["ok"]]
    print(f"\n{'PASS — kahani poori hai' if not bad else f'FAIL — {len(bad)} cheez chhooti, file ko final mat maano'}")
    return 1 if bad else 0


def selftest() -> int:
    """Pakki jaanch khud sahi pakadti hai? (nakli stems par)"""
    sr, n = SR, SR * 20
    rng = np.random.default_rng(0)
    voice = np.zeros(n, np.float32); lines = []
    for s in (1, 7, 13):
        voice[s * sr:(s + 4) * sr] = 0.3 * np.sin(2 * np.pi * 180 * np.arange(4 * sr) / sr)
        lines.append({"start": s, "end": s + 4})
    duck = np.ones(n, np.float32)
    for L in lines:
        duck[L["start"] * sr:L["end"] * sr] = 0.4
    river = 0.03 * rng.standard_normal(n).astype(np.float32)          # stem: bina ducking
    good = pakki_jaanch(voice, river, (voice + river * duck) * 1.6, sr, lines, [{"name": "nadi", "start": 0, "end": 20}], -16)
    broken = river.copy(); broken[9 * sr:15 * sr] = 0            # nadi beech me gayab
    bad = pakki_jaanch(voice, broken, voice + broken, sr, lines, [{"name": "nadi", "start": 0, "end": 20}], -16)
    g = {r["jaanch"]: r["ok"] for r in good}; b = {r["jaanch"]: r["ok"] for r in bad}
    piece = river[: 8 * sr] * np.linspace(0.5, 1.5, 8 * sr).astype(np.float32)   # 8 s tukda baar-baar
    looped = np.tile(piece, 3)[:n]
    lp_bad, lp_good = loop_score(looped, sr)["score"], loop_score(river, sr)["score"]
    print(f"  loop: asli {lp_good:.2f} (chahiye <0.92), loop wala {lp_bad:.2f} (chahiye >0.92)")
    ok = g["state:nadi"] and g["ducking"] and g["bed_lagataar"] and not b["state:nadi"] and not b["bed_lagataar"] \
        and not b["ducking"] \
        and lp_bad > 0.92 and lp_good < 0.92
    print("selftest:", "OK" if ok else "GADBAD", "\n  sahi:", g, "\n  toota:", b)
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "wire":
        sys.exit(wire())
    if a[0] == "run" and len(a) >= 3:
        sys.exit(run(a[1], a[2]))
    if a[0] == "check" and len(a) >= 2:
        sys.exit(check(a[1]))
    if a[0] == "selftest":
        sys.exit(selftest())
    print(__doc__)
