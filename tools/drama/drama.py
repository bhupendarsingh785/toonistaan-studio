#!/usr/bin/env python3
"""drama.py — poora local audio-drama engine (6 layers), ek hi command.

  python tools/drama/drama.py scene.json out.mp3 [--bed -7] [--praat 1]

Layers:
 1 script_parse  -> scene, kirdaar, bhaav
 2 characters    -> har kirdaar ki profile (voice, pace, gain, space)
 3 prosody       -> pitch curve, pace, stress, pause
 4 voice         -> piper (local); Praat se sur ka curve (--praat 1)
 5 scene_audio   -> base + close + far + movement layers
 6 mixer/master  -> voice centre, bed -7 dB, de-harsh, loudnorm -16, limiter
"""
from __future__ import annotations
import json, subprocess, sys, wave
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE.parent / "local_story"))
import script_parse, prosody, scene_audio
try:
    import praat_pitch
except Exception:
    praat_pitch = None

SR = 22050
VOICE_DIR = Path("/scratch/work/voices")
CHARS = json.loads((HERE / "characters.json").read_text(encoding="utf-8"))
_cache = {}


def _ff():
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()


def load(p, sr=SR):
    raw = subprocess.run([_ff(), "-v", "quiet", "-i", str(p), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def voice(model):
    if model not in _cache:
        from piper import PiperVoice
        p = VOICE_DIR / f"hi_IN-{model}-medium.onnx"
        _cache[model] = PiperVoice.load(str(p), config_path=str(p) + ".json")
    return _cache[model]


def say(text, model, ls, out):
    from piper.config import SynthesisConfig
    w = wave.open(str(out), "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    voice(model).synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=ls, noise_scale=0.62, noise_w_scale=0.75))
    w.close()
    return load(out)


def trim(y):
    a = np.abs(y); i = np.where(a > a.max() * 0.02)[0]
    return y[max(0, i[0] - 800): i[-1] + 800] if len(i) else y


def main():
    src = Path(sys.argv[1]); out = sys.argv[2]
    _fxp = {}
    for _c in ("/scratch/work/fix_plan.json", "fix_plan.json"):
        if Path(_c).exists():
            try:
                _fxp = json.loads(Path(_c).read_text(encoding="utf-8")).get("fix", {})
            except Exception:
                _fxp = {}
            break
    bed_db = float(sys.argv[sys.argv.index("--bed") + 1]) if "--bed" in sys.argv else float(_fxp.get("bed_level", -7.0))
    use_praat = ("--praat" in sys.argv) and (praat_pitch is not None)
    fx = _fxp
    if fx:
        print("fix_plan mila:", fx)
    sc = script_parse.load(src)
    plans = prosody.plan_all(sc["lines"], CHARS)
    work = Path("/scratch/work/drama"); work.mkdir(exist_ok=True)
    parts, marks, t = [], [], 0.0
    for i, pl in enumerate(plans):
        prof = CHARS.get(pl["who"], CHARS["narrator"])
        y = say(pl["text"], prof["voice"], round(1.0 / max(0.85, pl["pace"]), 3), work / f"l{i:02d}.wav")
        y = trim(y)
        if use_praat:
            y = praat_pitch.apply_curve(y, SR, pl["curve"], max_st=2.5)
        g = 10 ** ((prof.get("gain_db", 0) + float(fx.get("voice_gain", 0))) / 20)
        y = y * g
        pk = np.abs(y).max()
        if pk > 0: y = y / pk * 0.9
        parts.append(y)
        marks.append({"who": pl["who"], "text": pl["text"], "emotion": pl["emotion"],
                      "pace": pl["pace"], "curve": pl["curve"], "stress": pl["stress"],
                      "start": round(t, 2), "dur": round(len(y) / SR, 2)})
        gap = np.zeros(int(pl["pause_after"] * SR), dtype=np.float32)
        parts.append(gap); t += (len(y) + len(gap)) / SR
    voice_track = np.concatenate(parts)
    Lb, Rb, used = scene_audio.build(sc.get("scene", "nadi_kinare"), len(voice_track))
    _beq = float(fx.get("bed_eq", 0.0))
    if _beq < -0.2:                      # background ka bright hissa neecha (voice saaf)
        for _i in range(2):
            _arr = Lb if _i == 0 else Rb
            _n = len(_arr); _S = np.fft.rfft(_arr); _f = np.fft.rfftfreq(_n, 1 / SR)
            # 2.5-4.5k ko kaato + 3.4k se upar dheela lowpass (background ki chamak hataye)
            _g = 1 + (10 ** (_beq / 20) - 1) * np.exp(-((_f - 3300) ** 2) / (2 * 1100 ** 2))
            _g = _g / (1 + (_f / 3600.0) ** 3)
            _out = np.fft.irfft(_S * _g, _n).astype(np.float32)
            _arr[:] = _out[:len(_arr)]
    vr = float(np.sqrt((voice_track ** 2).mean())) + 1e-9
    br = float(np.sqrt(((Lb ** 2).mean() + (Rb ** 2).mean()) / 2)) + 1e-9
    k = (vr * 10 ** (bed_db / 20)) / br
    L = voice_track * 0.95 + Lb * k
    R = voice_track * 0.95 + Rb * k
    pk = max(np.abs(L).max(), np.abs(R).max()); L *= 0.90 / pk; R *= 0.90 / pk
    tmp = work / "pre.wav"
    w = wave.open(str(tmp), "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(np.stack([L, R], 1), -1, 1) * 32767).astype("<i2").tobytes()); w.close()
    hc = float(fx.get("harsh_cut", -1.8)); wm = float(fx.get("warmth", 0.0))
    mv = float(fx.get("master_vol", 0.85)); md = float(fx.get("mod_depth", 0.0))
    af = f"equalizer=f=3200:width_type=q:w=1.3:g={hc:.2f},equalizer=f=6200:width_type=q:w=1.5:g={hc*0.6:.2f},"
    if wm > 0.1: af += f"bass=g={wm:.1f}:f=250:w=0.7,"
    if md > 0.5: af += f"tremolo=f=4.3:d={min(0.35, md/100):.2f},"
    af += f"loudnorm=I=-16:TP=-2.5:LRA=11,volume={mv:.2f},alimiter=limit=0.80"
    subprocess.run([_ff(), "-v", "error", "-y", "-i", str(tmp), "-af", af,
                    "-c:a", "libmp3lame", "-b:a", "160k", out], check=True)
    (work / "plan.json").write_text(json.dumps({"scene": sc["scene"], "dur": round(len(voice_track) / SR, 2),
                                                "lines": marks, "bed": used, "praat": use_praat}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"out": out, "dur": round(len(voice_track) / SR, 2), "lines": len(marks),
                      "scene": sc["scene"], "praat": use_praat, "layers": len(used)}))


if __name__ == "__main__":
    main()
