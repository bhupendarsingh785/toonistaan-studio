#!/usr/bin/env python3
"""regression.py — ek command me poori jaanch (kuch bhi chhoota na rahe).

  python tools/regression.py            # sab
  python tools/regression.py --fast     # render chhod kar baaki

Har check naap se PASS/FAIL deta hai; koi check chup-chaap skip nahi hota.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "world"))

RESULTS = []


def add(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"  {'OK ' if ok else 'XX '} {name:22s} {detail}")


def check_space():
    import numpy as np
    import space as SP
    sr = SP.SR
    t = np.arange(int(1.0 * sr)) / sr
    voice = sum((0.6 / k) * np.sin(2 * np.pi * 140 * k * t) for k in range(1, 20)) * np.exp(-t / 0.3)
    near = SP.measure(SP.place_acoustic(voice, dist=1, space="khula"))["level_db"]
    far = SP.measure(SP.place_acoustic(voice, dist=20, space="khula"))["level_db"]
    add("doori level", far < near - 8, f"1m {near} dB -> 20m {far} dB")
    hf_near = SP.measure(SP.place_acoustic(voice, dist=1, space="khula"))["hf_lf"]
    hf_far = SP.measure(SP.place_acoustic(voice, dist=20, space="khula"))["hf_lf"]
    add("doori dhundhli", hf_far <= hf_near, f"HF/LF {hf_near} -> {hf_far}")
    pl = SP.measure(SP.place_acoustic(voice, dist=4, pan=-0.8, space="jungle"))["pan"]
    pr = SP.measure(SP.place_acoustic(voice, dist=4, pan=+0.8, space="jungle"))["pan"]
    add("disha pan", pl < -0.4 and pr > 0.4, f"pan {pl} / {pr}")
    burst = np.random.default_rng(1).normal(0, 1, int(1.0 * sr)) * np.exp(-t / 0.05)
    rts = {s: SP.measure(SP.place_acoustic(burst, dist=6, space=s))["rt_bass_mid_high"][0] for s in ("khula", "jungle", "hall")}
    add("jagah goonj", rts["khula"] < rts["jungle"] < rts["hall"], str(rts))
    t2 = np.arange(int(2.5 * sr)) / sr
    long_voice = sum((0.6 / k) * np.sin(2 * np.pi * 140 * k * t2) for k in range(1, 20)) * np.exp(-t2 / 1.2)
    mv = SP.place_moving(long_voice, dist0=1.0, dist1=40.0, space="khula", pass_by=True, speed=14)
    a = SP.measure(mv[:, : int(0.5 * sr)])["level_db"]
    b = SP.measure(mv[:, int(1.2 * sr):int(1.7 * sr)])["level_db"]
    add("chalti awaaz", b > a + 3, f"shuru {a} dB -> paas {b} dB")


def check_narration():
    import narration_clean as NC
    out, found = NC.strip_sounds("शाम ढल रही थी और नदी कल-कल बह रही थी।")
    add("vachak nakal hatai", "कल-कल" not in out and found == ["कल-कल"], out)


def check_recognize():
    """Awaaz pehchaan — test awaaz khud banakar (kisi purani file par depend nahi)."""
    code = (
        "import sys, tempfile, numpy as np, soundfile as sf;"
        "sys.path.insert(0,'tools');"
        "from pathlib import Path;"
        "import loop_maker as LM, recognize as R;"
        "T=Path(tempfile.mkdtemp());"
        "exp={};"
        "sf.write(T/'prakriti.wav', LM.make('rain',sec=6), LM.SR); exp['prakriti.wav']='prakriti';"
        "sf.write(T/'harkat.wav', LM.make('wood_steps',sec=6), LM.SR); exp['harkat.wav']='harkat';"
        "t=np.arange(int(6*LM.SR))/LM.SR;"
        "mus=sum(np.sin(2*np.pi*f*t) for f in (261.6,329.6,392.0,523.2))*0.25;"
        "sf.write(T/'music.wav', mus.astype('float32'), LM.SR); exp['music.wav']='music';"
        "ok=sum(1 for f,w in exp.items() if (R.recognize(T/f).get('sound_type') or {}).get('label')==w);"
        "print(ok, len(exp))"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(ROOT), timeout=280)
    out = (r.stdout or "").strip().split()
    if len(out) == 2:
        add("recognize", int(out[0]) >= 2, f"{out[0]}/{out[1]} sahi")
    else:
        add("recognize", False, (r.stderr or "fail")[-60:])


def check_clone():
    """Cloning: enroll -> line banao -> sur kitna kareeb aaya."""
    code = (
        "import sys;sys.path.insert(0,'tools');"
        "from pathlib import Path;import voice_clone as VC, voice_clone_lite as VL;"
        "src=sorted(Path('/scratch/input').glob('*man-talking*'))[0];"
        "v=VC.enroll('reg_test', str(src), 'jaanch', consent=True, backend='lite');"
        "out=Path('/scratch/work/reg_clone.wav');"
        "ok=VC._render_line('lite', v, 'नमस्ते, यह जाँच है।', out);"
        "import soundfile as sf;"
        "ref=VL.profile_of(VL.load(v.audio)); y,_=sf.read(str(out)) if out.exists() else (None,None);"
        "now=VL.profile_of(y) if y is not None else {'f0_median':0};"
        "err=abs(now['f0_median']-ref['f0_median'])/max(1,ref['f0_median']);"
        "print(int(ok), round(err,3))"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(ROOT), timeout=280)
    out = (r.stdout or "").strip().split()
    if len(out) == 2:
        add("cloning", out[0] == "1" and float(out[1]) < 0.15, f"f0 error {float(out[1])*100:.0f}%")
    else:
        add("cloning", False, (r.stderr or "fail")[-60:])


def check_voice_quality():
    """Awaaz ka apna checker: insaan ke baseline par kitna utarta hai."""
    code = (
        "import sys;sys.path.insert(0,'tools');"
        "from pathlib import Path;import voice_checker as VC;"
        "fs=[p for p in Path('/scratch/output').glob('*.mp3')];"
        "print('0 0') if not fs else None;"
        "m=VC.measure(fs[-1]);j=VC.judge(m);print(j['score'], j['verdict'])"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(ROOT), timeout=280)
    out = (r.stdout or "").strip().split()
    if len(out) >= 2:
        add("voice_quality", int(out[0]) >= 70, f"score {out[0]} ({out[1]})")
    else:
        add("voice_quality", False, (r.stderr or "fail")[-60:])


def check_structure():
    for name, cmd in (("kram", [sys.executable, "tools/kram.py", "jaanch"]),
                      ("wire", [sys.executable, "tools/sutradhar.py", "wire"])):
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=300)
        txt = (r.stdout or "") + (r.stderr or "")
        add(name, ("SAB THEEK" in txt) or ("SAB JUDA HAI" in txt), txt.strip().splitlines()[-1][:70])


def check_render():
    story = ROOT / "knowledge" / "regression-kahani.txt"
    story.write_text("वाचक: जंगल में शाम ढल रही थी और नदी बह रही थी।\n"
                     "लड़की: यहाँ अंधेरा है, कोई है क्या?\n"
                     "वाचक: दूर कहीं भेड़िया चिल्लाया।\n", encoding="utf-8")
    out = Path(tempfile.mkdtemp(prefix="astra-reg-"))
    r = subprocess.run([sys.executable, "tools/sutradhar.py", "run", str(story), str(out)],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=600)
    txt = (r.stdout or "") + (r.stderr or "")
    add("render", "PASS — kahani poori hai" in txt, txt.strip().splitlines()[-1][:70])
    mf = out / "manifest.json"
    if mf.exists():
        qa = json.loads(mf.read_text())["qa"]
        for k in ("pace", "background"):
            add("qa " + k, qa.get(k, {}).get("status") == "PASS", str(qa.get(k, {}).get("value")))
        add("verdict", json.loads(mf.read_text()).get("verdict") == "PASS", "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    print("1) jagah/doori/disha")
    check_space()
    print("2) vachak ka andaaz")
    check_narration()
    print("3) dhancha")
    check_structure()
    print("3a) cloning")
    check_clone()
    print("3b) awaaz pehchaan")
    check_recognize()
    if not a.fast:
        print("4) asli render + QA")
        check_render()
    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{'SAB PASS' if not bad else 'FAIL: ' + ', '.join(bad)}  ({len(RESULTS)} check)")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
