#!/usr/bin/env python3
"""
ASTRA STORY CHECK — kahani banane se PEHLE samajh lo (galat cheez baad me pakadna mehnga hai).

Ye kya dekhta hai:
  1. Kirdaar ke naam sahi hain? (awaaz available hai?)
  2. Do kirdaar ki awaaz ek jaisi to nahi? (bhai-behen ek jaise na lagein)
  3. Har line me kaam (action) ka sound mila ya nahi? (darwaza khula = darwaza ki awaaz)
  4. Mahaul (env) sahi hai? us mahaul me wo sound allowed hai?
  5. Library me wo sound hai? nahi to Freesound/Mixkit se aayega?
  6. Kahani me koi "logic" gadbad? (train ka horn ghar par, etc.)

Chalao:
  python3 astra/story_check.py studio/series/user/story_demo.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "studio"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))


def _line_parts(line):
    """Return (speaker, text, emotion) for both string and list story formats."""
    if isinstance(line, str):
        return "madhur", line, None
    if isinstance(line, (list, tuple)):
        speaker = str(line[0]) if len(line) > 0 and line[0] else "madhur"
        text = str(line[1]) if len(line) > 1 else ""
        emotion = line[2] if len(line) > 2 else None
        return speaker, text, emotion
    return "madhur", "", None


def main():
    if len(sys.argv) < 2:
        print("usage: story_check.py story.json")
        return 1
    ep = json.load(open(sys.argv[1], encoding="utf-8"))

    import sfx_extra
    import library as L

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("vp", os.path.join(os.path.dirname(HERE), "tools", "voice_provider.py"))
        vp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vp)
        speakers = vp.SARVAM_SPEAKER
        pitches = vp.SARVAM_PITCH
        paces = vp.SARVAM_PACE
    except Exception:
        speakers, paces = {}, {}

    chars = []
    for sc in ep.get("scenes", []):
        for line in sc.get("lines", []):
            speaker, _text, _emotion = _line_parts(line)
            if speaker not in chars:
                chars.append(speaker)

    print("=" * 60)
    print("KAHANI CHECK:", ep.get("title", "?"))
    print("=" * 60)
    print(f"scenes: {len(ep.get('scenes', []))} | kirdaar: {len(chars)}")

    # 1) awaaz mapping
    missing_voice = [c for c in chars if speakers and c not in speakers]
    used = {}
    for c in chars:
        s = speakers.get(c)
        pch = pitches.get(c, 1.0) if 'pitches' in dir() else 1.0
        if s:
            used.setdefault((s, round(pch, 2)), []).append(c)
    same = {s: v for s, v in used.items() if len(v) > 1}
    print("\n[1] Awaaz")
    if missing_voice:
        print("   ❌ awaaz nahi mili:", missing_voice)
    if same:
        for s, v in same.items():
            print(f"   ⚠️  ek hi awaaz ({s}) in kirdaaron ke liye: {v}")
    if not missing_voice and not same:
        print("   ✅ har kirdaar ki alag awaaz")

    # 2) har line ka sound
    print("\n[2] Sound (kaam ke hisaab se)")
    total = nosound = 0
    for sc in ep.get("scenes", []):
        env = sc.get("env", "neutral")
        horror = any(x in (sc.get("music") or "") for x in ("horror", "suspense"))
        for line in sc.get("lines", []):
            total += 1
            _speaker, text, _emotion = _line_parts(line)
            got = sfx_extra.detect_smart(text, env, allow_horror=horror)
            if not got:
                nosound += 1
                print(f"   ⚠️  [{env}] {text[:52]}")
    print(f"   lines: {total} | bina sound: {nosound}")

    # 3) library me sound hai?
    print("\n[3] Library")
    names = set()
    for sc in ep.get("scenes", []):
        env = sc.get("env", "neutral")
        for line in sc.get("lines", []):
            _speaker, text, _emotion = _line_parts(line)
            for n in sfx_extra.detect_smart(text, env):
                names.add(n)
    def _ok(n):
        try:
            return bool(L._variant(n, ""))
        except Exception:
            return bool(L.find(n))
    have = sum(1 for n in sorted(names) if _ok(n))
    print(f"   chahiye {len(names)} tarah | library me mila {have}")
    for n in sorted(names):
        if not _ok(n):
            print(f"   ⚠️  library me nahi: {n} (Freesound/Mixkit se aayega)")

    # 4) mahaul
    print("\n[4] Mahaul")
    for sc in ep.get("scenes", []):
        print(f"   {sc.get('env', '?'):10s} | music: {sc.get('music', '-'):10s} | lines: {len(sc.get('lines', []))}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
