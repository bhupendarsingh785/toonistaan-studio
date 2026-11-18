#!/usr/bin/env python3
"""
ASTRA CINEMA — kahani se "audio drama" (Pocket FM jaisa), ek hi command me.

Kahani likho (scene ke saath) -> ye khud:
  1. har scene ka mahaul chunta hai (gaon/kamra/jungle/sadak/mandir) + reverb
  2. dialogue ko kirdaar ki awaaz + bhaav se bolwata hai (tools/awaaz.py)
  3. har line ke shabdon se SFX nikalta hai (ASTRA generators) — doori/pan ke saath
  4. scene ka music (mood) lagata hai
  5. sab ko mix karta hai (ducking), master karta hai (-16 LUFS)
  6. cue-sheet JSON bhi deta hai (kaunsi awaaz kab)

Chalao:
  python3 astra/cinema.py banao story.json -o kahani.mp3

story.json:
{
 "title": "दो दीये",
 "scenes": [
   {"env": "village", "music": "calm", "lines": [
      ["madhur", "गाँव के छोटे से घर में दादी चूल्हा जला रही थीं।", "calm"],
      ["swara_bachcha", "दादी! देखो, मेरी गुल्लक में सौ रुपये हो गए!", "excited"],
      ["swara_dadi", "अरे वाह बेटा... इतने पैसे कहाँ से आए?", "surprised"]
   ]}
 ]
}
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "studio"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

SR = 44100
ENV_REVERB = {"room": 0.18, "village": 0.30, "jungle": 0.38, "street": 0.25,
              "temple": 0.55, "cave": 0.62, "hall": 0.45, "neutral": 0.20}


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def read_wav(p):
    import wave
    with wave.open(p) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    return x


def write_wav(p, x):
    """mono ya stereo (n,2) — dono chalti hain."""
    import wave
    x = np.clip(np.asarray(x, dtype=np.float32), -1, 1)
    ch = 2 if (x.ndim == 2 and x.shape[1] == 2) else 1
    with wave.open(p, "w") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def norm(x, pk=0.9):
    m = float(np.abs(x).max()) if len(x) else 0.0
    return (x / m * pk).astype(np.float32) if m > 0 else x.astype(np.float32)


def place(canvas, x, at_sec, gain=1.0):
    k = int(SR * max(0.0, at_sec))
    if k >= len(canvas):
        return
    m = min(len(x), len(canvas) - k)
    canvas[k:k + m] += x[:m] * gain


PAN_MAP = {
    "door": -0.35, "gate": -0.35, "knock": -0.30, "window": -0.45,
    "train": 0.40, "car": 0.35, "horn": 0.42, "crowd": 0.0,
    "footsteps": 0.0, "steps": 0.0, "run": 0.0, "heartbeat": 0.0,
    "rain": 0.0, "wind": 0.25, "leaves": -0.25, "birds": -0.30,
    "dog": 0.30, "cat": -0.28, "clock": -0.20, "cooker": 0.30,
    "coins": 0.15, "paper": -0.15, "chai": 0.20,
}


def _pan_for(name):
    n = str(name or "").lower()
    for k, v in PAN_MAP.items():
        if k in n:
            return v
    return 0.0


def place_pan(left, right, x, at_sec, gain=1.0, pan=0.0):
    """Awaaz ko baayein/daayein rakho (pan -1..+1) — asli duniya jaisa."""
    i = int(SR * at_sec)
    if i < 0 or i >= len(left) or len(x) == 0:
        return
    m = min(len(x), len(left) - i)
    if m <= 0:
        return
    gl = gain * (1.0 - max(0.0, pan)) * 0.5 ** 0.5
    gr = gain * (1.0 - max(0.0, -pan)) * 0.5 ** 0.5
    left[i:i + m] += x[:m] * gl
    right[i:i + m] += x[:m] * gr


def tts(text, kirdaar, bhaav, out_mp3):
    cmd = [sys.executable, os.path.join(ROOT, "tools", "awaaz.py"), "bolo", text, "--kirdaar", kirdaar, "-o", out_mp3, "--natural"]
    if bhaav:
        cmd += ["--bhaav", bhaav]
    r = sh(cmd)
    for line in (r.stdout or "").splitlines():
        if line.startswith(("ELEVEN_OK", "ELEVEN_FAIL", "ban gaya")):
            print("VOICE:", line.strip()[:110], flush=True)
    return r.returncode == 0 and os.path.exists(out_mp3)


# har SFX kitna lamba chal sakta hai (chhoti cheezein chhoti)
SFX_MAX = {
    "train": 7.0, "train_pass": 7.0, "train_horn": 6.0, "station": 8.0,
    "footsteps": 3.5, "steps": 3.5, "run": 3.0, "door": 4.0, "gate": 4.0, "knock": 3.0,
    "heartbeat": 4.0, "scream": 3.0, "roar": 3.5, "thunder": 5.0,
}


def sfx_limit(name):
    n = str(name or "").lower()
    for k, v in SFX_MAX.items():
        if k in n:
            return v
    return 5.0


SCENE_BED = {
    "village": ("birds", 0.42), "room": ("clock", 0.30), "street": ("crowd", 0.34),
    "night": ("crickets", 0.34), "station": ("crowd", 0.36), "jungle": ("leaves", 0.36),
    "hall": ("clock", 0.30), "cave": ("water", 0.34), "neutral": ("paper_1", 0.22),
}


def build(story_path, out_path, verbose=True, gap=0.28, scene_gap=0.45):
    import astra as A  # same folder
    import sfx as S

    data = json.load(open(story_path, encoding="utf-8"))
    scenes = data.get("scenes") or []
    if not scenes:
        sys.exit("story me 'scenes' nahi mila")

    tmp = tempfile.mkdtemp(prefix="cinema_")
    cue = {"title": data.get("title", ""), "scenes": [], "world_engine": None}
    actual_durations = []

    # pehle poora timeline banao (lambai pata chale)
    plan = []      # (kind, payload, start)
    t = 0.9
    for si, sc in enumerate(scenes):
        env = sc.get("env", "neutral")
        music = sc.get("music", "calm")
        sc_start = t
        cues = []
        scene_durations = [0.0] * len(sc.get("lines", []))
        # mahaul ka ambience (scene bhar)
        amb_event = {"env": env, "dur": 0.0, "start": sc_start}
        plan.append(("amb", amb_event, sc_start))

        for li, item in enumerate(sc.get("lines", [])):
            if isinstance(item, str):
                kirdaar, text, bhaav = "madhur", item, None
            else:
                kirdaar = item[0] if len(item) > 0 else "madhur"
                text = item[1] if len(item) > 1 else ""
                bhaav = item[2] if len(item) > 2 else None
            if not str(text).strip():
                continue

            line_start = t
            mp3 = os.path.join(tmp, f"s{si}_l{li}.mp3")
            ok = tts(text, kirdaar, bhaav, mp3)
            wav = os.path.join(tmp, f"s{si}_l{li}.wav")
            dur = 2.0
            if ok:
                sh(["ffmpeg", "-loglevel", "error", "-y", "-i", mp3, "-ac", "1", "-ar", str(SR), wav])
                if os.path.exists(wav):
                    a = read_wav(wav)
                    dur = len(a) / SR
                    plan.append(("line", {"wav": wav, "kirdaar": kirdaar, "bhaav": bhaav,
                                          "text": text, "start": t, "dur": dur}, t))
                    cues.append({"type": "dialogue", "who": kirdaar, "emotion": bhaav or "auto",
                                 "text": text, "start": round(t, 2), "dur": round(dur, 2)})
            else:
                if verbose:
                    print("TTS_FAIL", si, li, flush=True)
            line_end = line_start + dur
            scene_durations[li] = dur
            t = line_end + gap

            # line ke shabdon se SFX (max 2), dialogue ke turant baad.
            for name in A.detect(text) if hasattr(A, "detect") else []:
                pass
            try:
                import sfx_extra
                _env = sc.get("env", "neutral")
                _horror = any(x in (sc.get("music") or "") for x in ("horror", "suspense"))
                _sfx = sfx_extra.detect_smart(text, _env, allow_horror=_horror)[:2]
                if not _sfx and actions:
                    _sfx = list(actions.get(text, []))[:2]
                    if _sfx and verbose:
                        print("ACTION_BRAIN_USED", _sfx, text[:30], flush=True)
                if not _sfx and brain:
                    _sfx = list(brain.get(text, []))[:2]
                    if _sfx and verbose:
                        print("STORY_BRAIN_USED", _sfx, text[:34], flush=True)
                # Avoid a duplicate one-shot footsteps hit when the World Engine
                # is already creating a continuous, speaker-aware movement bed.
                try:
                    from world_engine import _event_matches
                    _has_world_movement = any(
                        ev in ("movement_start", "movement_run", "movement_stop")
                        for ev, _asset, _mode in _event_matches(text)
                    )
                    if _has_world_movement:
                        _sfx = [name for name in _sfx if name != "footsteps"]
                except Exception:
                    pass
                for name in _sfx:
                    sfx_start = line_end + 0.02
                    plan.append(("sfx", {"name": name, "start": sfx_start, "text": text,
                                       "scene_end": 0.0}, sfx_start))
                    cues.append({"type": "sfx", "name": name, "start": round(sfx_start, 2)})
            except Exception:
                pass
        actual_durations.append(scene_durations)
        # Scene ka ambience aur SFX agle scene me leak na hon.
        scene_end = t + 0.6
        amb_event["dur"] = max(0.5, scene_end - sc_start)
        for _kind, _payload, _start in plan:
            if _kind == "sfx" and _payload.get("scene_end") == 0.0 and _payload["start"] >= sc_start:
                _payload["scene_end"] = scene_end
        # scene ka music
        plan.append(("music", {"mood": music, "start": sc_start, "end": scene_end}, sc_start))
        # khaali scene na lage — ek mahaul ki awaaz
        try:
            import sfx_extra as _SE
            _env = sc.get("env", "neutral")
            _n = 0
            for _ln in sc.get("lines", []):
                _t = _ln[1] if isinstance(_ln, (list, tuple)) and len(_ln) > 1 else str(_ln)
                _n += len(_SE.detect_smart(_t, _env))
            if _n < 2 and _env in SCENE_BED:
                _nm, _vol = SCENE_BED[_env]
                plan.append(("sfx", {"name": _nm, "start": sc_start + 0.5, "text": "",
                                     "scene_end": scene_end, "vol": _vol}, sc_start + 0.5))
        except Exception:
            pass
        cue["scenes"].append({"env": env, "music": music, "start": round(sc_start, 2),
                              "end": round(scene_end, 2), "cues": cues})
        t = scene_end + scene_gap

    # Additive World Engine integration: use actual TTS durations and preserve
    # the legacy cue/render path. No legacy SFX, ambience, music or voice is removed.
    world_events = []
    try:
        from world_engine import plan_world
        world_scenes = []
        for sc in scenes:
            world_scenes.append({
                "env": sc.get("env", "neutral"),
                "lines": sc.get("lines", []),
                "line_gap": gap,
                # cinema.py adds 0.6s scene tail and then scene_gap
                "scene_gap": scene_gap + 0.6,
            })
        world_result = plan_world(
            {"title": data.get("title", ""), "scenes": world_scenes},
            line_durations=actual_durations,
            include_ambient=False,  # legacy Cinema already renders scene ambience
        )
        cue["world_engine"] = {
            "version": world_result.get("version"),
            "mode": "integrated_additive",
            "duration_source": "measured_tts_audio_or_existing_2s_tts_failure_fallback",
            "events": [],
        }
        for world_scene in world_result.get("scenes", []):
            for wc in world_scene.get("cues", []):
                if wc.get("type") == "state_start":
                    event = {
                        "kind": "world_state",
                        "asset": wc.get("asset"),
                        "start": 0.9 + float(wc.get("start", 0.0)),
                        "end": 0.9 + float(wc.get("end", wc.get("start", 0.0))),
                        "scene_end": 0.9 + float(world_scene.get("end", 0.0)),
                        "event": wc.get("event"),
                    }
                    world_events.append(event)
                elif wc.get("type") == "sfx":
                    event = {
                        "kind": "world_sfx",
                        "asset": wc.get("asset"),
                        "start": 0.9 + float(wc.get("start", 0.0)),
                        "end": 0.9 + float(wc.get("end", wc.get("start", 0.0))),
                        "scene_end": 0.9 + float(world_scene.get("end", 0.0)),
                        "event": wc.get("event"),
                    }
                    world_events.append(event)
        for event in world_events:
            event["cue_status"] = "pending"
            cue["world_engine"]["events"].append({
                "event": event["event"], "asset": event["asset"],
                "kind": event["kind"], "start": round(event["start"], 3),
                "end": round(event["end"], 3), "status": "pending",
            })
            plan.append((event["kind"], event, event["start"]))
        if verbose:
            print("WORLD_ENGINE_INTEGRATED", len(world_events), "events", flush=True)
    except Exception as e:
        # Fail open: the original cinema render must continue unchanged.
        cue["world_engine"] = {"mode": "integration_skipped", "error": str(e)[:180], "events": []}
        if verbose:
            print("WORLD_ENGINE_SKIPPED", str(e)[:120], flush=True)

    total = t + 0.35
    n = int(SR * total)
    voice = np.zeros(n, np.float32)
    fx = np.zeros(n, np.float32)
    fxL = np.zeros(n, np.float32)
    fxR = np.zeros(n, np.float32)
    amb_bus = np.zeros(n, np.float32)
    mus_bus = np.zeros(n, np.float32)

    for kind, p, start in plan:
        if kind == "line":
            a = read_wav(p["wav"])
            place(voice, a, p["start"], 1.0)
        elif kind == "world_state":
            # Continuous movement bed: footsteps persist until the planner's stop
            # point. Running uses a faster cadence. Keep it subtle under dialogue.
            status = "unavailable"
            try:
                import sfx_extra
                duration = max(0.0, min(180.0, float(p.get("end", p["start"])) - float(p["start"])))
                if duration > 0.05:
                    bpm = 148 if p.get("event") == "movement_run" else 108
                    snd = sfx_extra.footsteps(d=duration, bpm=bpm)
                    fade = min(int(SR * 0.08), len(snd) // 4)
                    if fade > 1:
                        snd[:fade] *= np.linspace(0, 1, fade)
                        snd[-fade:] *= np.linspace(1, 0, fade)
                    place_pan(fxL, fxR, snd, p["start"], 0.34 if bpm < 140 else 0.40, _pan_for(p["name"]))
                    status = "rendered_local_footsteps"
            except Exception as e:
                status = "failed:" + str(e)[:100]
            p["cue_status"] = status
            if verbose:
                print("WORLD_MOVEMENT", p.get("event"), status, flush=True)
        elif kind == "world_sfx":
            # Resolve exact semantic recordings first; use a local fallback only
            # when it is a defensible match. Never replace bangles/cloth/breathing
            # with an unrelated sound just to avoid silence.
            status = "asset_unavailable"
            aliases = {
                "door_open": "gate_open",
                "door_close": "gate_close",
                "vehicle_pass_by": "car",
                "water_splash": "water",
            }
            try:
                import real_audio
                import sfx_extra
                asset = str(p.get("asset", ""))
                alias = aliases.get(asset, asset)
                rp = real_audio.fetch(alias, context=p.get("event", ""))
                snd = None
                if rp:
                    snd = read_wav(rp)
                    status = "rendered_real_asset"
                elif alias in sfx_extra.ALL:
                    snd = sfx_extra.ALL[alias]()
                    status = "rendered_local_fallback"
                if snd is not None and len(snd):
                    cap = max(0.0, min(30.0, float(p.get("scene_end", p["start"])) - p["start"]))
                    if cap > 0:
                        snd = snd[:int(SR * cap)]
                    if len(snd):
                        snd = norm(snd, 0.55)
                        fade = min(int(SR * 0.04), len(snd) // 4)
                        if fade > 1:
                            snd[:fade] *= np.linspace(0, 1, fade)
                            snd[-fade:] *= np.linspace(1, 0, fade)
                        place_pan(fxL, fxR, snd, p["start"], 0.48, _pan_for(p["name"]))
                else:
                    status = "asset_unavailable_no_misleading_substitute"
            except Exception as e:
                status = "failed:" + str(e)[:100]
            p["cue_status"] = status
            if verbose:
                print("WORLD_SFX", p.get("asset"), status, flush=True)
        elif kind == "sfx":
            done = False
            # 1) pehle ASLI recording (Freesound) — key ho to
            try:
                import real_audio
                rp = real_audio.fetch(p["name"], context=p.get("text", ""))
                if rp:
                    rw = read_wav(rp)
                    rw = norm(rw, 0.85)
                    rw = A.reverb(rw, 0.10)
                    cap = max(0.0, float(p.get("scene_end", p["start"])) - p["start"])
                    cap = min(cap, sfx_limit(p["name"]))
                    if cap > 0:
                        rw = rw[:int(SR * cap)]
                        _f = min(int(SR * 0.3), max(1, len(rw) // 4))
                        rw = rw.copy()
                        rw[-_f:] *= np.linspace(1, 0, _f)
                    _pn = _pan_for(p["name"])
                    place_pan(fxL, fxR, rw, p["start"], p.get("vol", 0.88 if any(k in str(p["name"]) for k in ("door", "gate", "knock")) else 0.78), _pn)
                    done = True
                    if verbose:
                        print("SFX_REAL", p["name"], flush=True)
            except Exception:
                pass
            # 2) na mile to procedural
            if not done:
                try:
                    import sfx_extra
                    name = p["name"]
                    if name in sfx_extra.ALL:
                        snd = sfx_extra.ALL[name]()
                    else:
                        # Detected actions ko available local generator se map karo;
                        # missing key par sound ko chup-chaap drop na karo.
                        fallback = {"run": "footsteps", "stairs": "footsteps", "chair": "wood",
                                    "plate": "metal", "bed": "wood", "door": "door",
                                    "gate_open": "door", "gate_close": "door"}.get(name, name)
                        if fallback not in A.GENERATORS:
                            if verbose:
                                print("SFX_UNAVAILABLE", name, flush=True)
                            continue
                        snd = A.GENERATORS[fallback]()
                    snd = norm(snd, 0.85)
                    snd = A.reverb(snd, 0.25)
                    cap = max(0.0, float(p.get("scene_end", p["start"])) - p["start"])
                    if cap > 0:
                        snd = snd[:int(SR * cap)]
                    place_pan(fxL, fxR, snd, p["start"], 0.55, _pan_for(p["name"]))
                except Exception:
                    pass
        elif kind == "amb":
            env = p["env"]
            kind_amb = env if env in ("rain", "wind", "night", "village", "street", "jungle", "temple", "room") else "room"
            need = max(0.5, float(p.get("dur") or 1.0))
            seg = None
            # 1) asli recording (Freesound)
            try:
                import real_audio
                rp = real_audio.fetch(kind_amb)
                if rp:
                    rw = read_wav(rp)
                    if len(rw) > SR * 0.5:
                        reps = int(np.ceil((SR * need) / len(rw)))
                        seg = np.tile(rw, max(1, reps))[: int(SR * need)]
                        seg = norm(seg, 0.16)   # bahut dheema, peeche
                        if verbose:
                            print("AMB_REAL", kind_amb, flush=True)
            except Exception:
                pass
            # 2) na mile to synth
            if seg is None:
                seg = A.ambience(kind_amb, need)
            # fade in/out (achanak shuru na ho)
            _f = min(int(SR * 0.8), max(1, len(seg) // 4))
            seg = seg.astype(np.float32).copy()
            seg[:_f] *= np.linspace(0, 1, _f)
            seg[-_f:] *= np.linspace(1, 0, _f)
            seg = np.pad(seg, (0, max(0, n - int(SR * p["start"]) - len(seg))))[: max(0, n - int(SR * p["start"]))]
            amb_bus[int(SR * p["start"]):int(SR * p["start"]) + len(seg)] += seg * 0.9
        elif kind == "music":
            dur = max(2.0, p["end"] - p["start"])
            m = None
            try:
                import music_engine as ME
                import wave as _w
                path, _meta = ME.generate_music(p["mood"], max(8.0, dur + 1.0))
                with _w.open(str(path)) as wf:
                    raw = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float32) / 32768
                    ch = wf.getnchannels(); sr = wf.getframerate()
                if ch == 2:
                    raw = raw.reshape(-1, 2).mean(1)
                if sr != SR:
                    raw = np.interp(np.linspace(0, len(raw) - 1, int(len(raw) * SR / sr)),
                                    np.arange(len(raw)), raw).astype(np.float32)
                m = raw[: int(SR * dur)]
                if verbose:
                    print("MUSIC_ENGINE", p["mood"], len(m) / SR, "s", flush=True)
            except Exception as e:
                if verbose:
                    print("MUSIC_FALLBACK", str(e)[:60], flush=True)
                m = S.music(p["mood"], dur + 1.0)[: int(SR * dur)]
            m = norm(m, 0.9)
            f = min(int(SR * 0.6), len(m) // 3)
            if f > 1:
                m[:f] *= np.linspace(0, 1, f)
                m[-f:] *= np.linspace(1, 0, f)
            place(mus_bus, m, p["start"], 0.55)

    # ducking
    win = int(SR * 0.25)
    envl = np.convolve(np.abs(voice), np.ones(win) / win, "same")
    thr = max(0.01, float(np.percentile(envl, 55)))
    duck = np.where(envl > thr, 0.32, 1.0)
    duck = np.convolve(duck, np.ones(int(SR * 0.30)) / int(SR * 0.30), "same")

    # ---- stereo mix (duniya jaisa: awaaz beech me, cheezein aas-paas) ----
    amb_l = amb_bus * (0.62 + 0.38 * duck)
    amb_r = np.roll(amb_bus, int(SR * 0.011)) * (0.66 + 0.34 * duck)   # halka delay = chaurai
    mus_l = mus_bus * duck
    mus_r = np.roll(mus_bus, int(SR * 0.007)) * duck
    L = voice * 0.72 + fxL + amb_l * 0.30 + mus_l * 0.55
    R = voice * 0.72 + fxR + amb_r * 0.30 + mus_r * 0.55
    peak = max(1e-6, float(max(np.abs(L).max(), np.abs(R).max())))
    L = L / peak * 0.95
    R = R / peak * 0.95
    mix = np.stack([L, R], axis=1)

    premix = os.path.join(tmp, "premix.wav")
    write_wav(premix, mix)

    af = ("highpass=f=65,"
          "equalizer=f=180:t=q:w=1.0:g=-1.5,"
          "equalizer=f=3200:t=q:w=1.2:g=2.5,"
          "equalizer=f=9000:t=q:w=1.0:g=1.0,"
          "deesser=i=0.3,"
          "acompressor=threshold=0.10:ratio=2.6:attack=6:release=180:makeup=1.5,"
          "alimiter=limit=0.95,"
          "loudnorm=I=-16:TP=-1.5:LRA=11")
    codec = ["-c:a", "libmp3lame", "-b:a", "192k"] if out_path.lower().endswith(".mp3") else []
    r = sh(["ffmpeg", "-loglevel", "error", "-y", "-i", premix, "-af", af, "-ar", "44100", "-ac", "2", *codec, out_path])
    if r.returncode != 0:
        sys.exit("master fail: " + r.stderr[-300:])

    # ---- QA gate (technical jaanch — audio ko badalta nahi) ----
    try:
        import qa_gate as _QA
        _q = _QA.run_qa(out_path)
        cue["qa"] = _q
        if verbose:
            print("QA", _q.get("status"), _q.get("sample_peak_dbfs"), "dBFS",
                  "| true peak", _q.get("true_peak_dbtp"), "|", _q.get("reason", ""), flush=True)
    except Exception as _e:
        if verbose:
            print("QA_SKIP", str(_e)[:60], flush=True)

    if cue.get("world_engine"):
        rendered_status = {}
        for _kind, _payload, _start in plan:
            if _kind in ("world_state", "world_sfx"):
                rendered_status[(round(_payload["start"], 3), _payload.get("asset"), _kind)] = _payload.get("cue_status", "pending")
        for _event in cue["world_engine"].get("events", []):
            _key = (round(_event["start"], 3), _event.get("asset"), _event.get("kind"))
            _event["status"] = rendered_status.get(_key, "pending")
    cues_path = os.path.splitext(out_path)[0] + ".cues.json"
    json.dump(cue, open(cues_path, "w"), ensure_ascii=False, indent=1)
    print(f"TAIYAR {out_path} | {round(total,1)}s | {len(plan)} events | cues: {cues_path}")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="ASTRA Cinema — kahani se audio drama")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("banao")
    b.add_argument("story")
    b.add_argument("-o", "--out", default="kahani.mp3")
    a = ap.parse_args()
    build(a.story, a.out)


if __name__ == "__main__":
    main()
