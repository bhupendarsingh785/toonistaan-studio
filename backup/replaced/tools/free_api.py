#!/usr/bin/env python3
"""Free API — bina key wali TTS (aaj: Google Translate TTS), ek hi darwaza.

Kyun: har nayi free API ke liye alag code nahi likhna pade — ek `PROVIDERS` table me
adapter jodo, baaki system waise hi chalta rahega.

Abhi chalta hai (asli test, bina key):
  • google  — Google Translate TTS (hi/en/…), 200 akshar ke tukdon me

Kaise jodna hai (naya provider):
  def my_api(text, out, lang, style) -> bool: ...
  PROVIDERS["mera"] = my_api

CLI:
  python tools/free_api.py "नमस्ते, यह परीक्षण है" --out /tmp/free.mp3
  python tools/free_api.py "..." --bhaav gussa
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import worktmp as wt
UA = "Mozilla/5.0 (X11; Linux x86_64) astra-free-tts/1.0"
MAX_CHUNK = 190


def _ff() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()


def _style(bhaav) -> dict:
    try:
        from tools import voice_provider as vp
        return vp._bhaav_style(bhaav)
    except Exception:
        return {"pitch": 1.0, "pace": 1.0, "energy": 1.0, "gap_ms": 220}


def _chunks(text: str, size: int = MAX_CHUNK) -> list[str]:
    """Lambe text ko chhote tukdon me — API ki limit ke liye (vakya tod kar)."""
    import re
    parts, cur = [], ""
    for sent in re.split(r"(?<=[।.!?])\s+", text.strip()):
        if len(cur) + len(sent) + 1 <= size:
            cur = (cur + " " + sent).strip()
        else:
            if cur:
                parts.append(cur)
            while len(sent) > size:
                cut = sent.rfind(" ", 0, size)
                cut = cut if cut > 40 else size
                parts.append(sent[:cut])
                sent = sent[cut:].strip()
            cur = sent
    if cur:
        parts.append(cur)
    return parts or [text[:size]]


def _apply_style(src: Path, dest: Path, style: dict) -> bool:
    """Bhaav ka asar — raftaar (atempo) aur sur (rubberband formant safe)."""
    pace = max(0.6, min(1.6, float(style.get("pace", 1.0))))
    pitch = max(0.85, min(1.2, float(style.get("pitch", 1.0))))
    vol = max(0.7, min(1.3, float(style.get("energy", 1.0))))
    filt = [f"atempo={pace:.3f}"]
    if abs(pitch - 1.0) > 0.01:
        filt.append(f"rubberband=pitch={pitch:.3f}:formant=preserved")
    filt.append(f"volume={vol:.2f}")
    cmd = [_ff(), "-loglevel", "error", "-y", "-i", str(src), "-af", ",".join(filt),
           "-ac", "1", "-ar", "24000", "-b:a", "64k", str(dest)]
    r = subprocess.run(cmd, capture_output=True)
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 1000


def _has_words(text: str) -> bool:
    """Asli shabd hain? (sirf '।।।' ya khaali par TTS nahi chalana)."""
    import re
    return bool(re.search(r"[^\W\d_]", text or "", re.UNICODE))


def google(text: str, out: Path, lang: str = "hi", style: dict | None = None) -> bool:
    """Google Translate TTS — free, bina key. Tukdon me laa kar jodta hai."""
    style = style or {}
    if not _has_words(text):
        return False
    tmp_dir = out.parent / "_gtts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for i, piece in enumerate(_chunks(text)):
        url = ("https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob"
               f"&tl={lang}&q={urllib.parse.quote(piece)}")
        data = b""
        for attempt in range(3):
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    data = r.read()
                if len(data) > 800:
                    break
            except Exception:
                data = b""
            time.sleep(0.8 * (attempt + 1))     # 429/network par thoda ruk kar dobara
        if len(data) < 800:
            continue
        if len(data) < 800:
            continue
        f = tmp_dir / f"part_{i:03d}.mp3"
        f.write_bytes(data)
        files.append(f)
    if not files:
        return False
    if len(files) == 1:
        raw = files[0]
    else:
        raw = tmp_dir / "joined.mp3"
        list_file = tmp_dir / "list.txt"
        list_file.write_text("".join(f"file '{f.name}'\n" for f in files), encoding="utf-8")
        r = subprocess.run([_ff(), "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                            "-i", str(list_file), "-c", "copy", str(raw)],
                           cwd=str(tmp_dir), capture_output=True)
        if r.returncode != 0 or not raw.exists():
            return False
    ext = out.suffix.lower()
    _style_needed = bool(style) and (abs(style.get("pace", 1.0) - 1) > 0.01
                                     or abs(style.get("pitch", 1.0) - 1) > 0.01
                                     or abs(style.get("energy", 1.0) - 1) > 0.01)
    if ext in (".wav", ".wav "):
        # pehle temp me convert, phir style laga kar asli naam par — warna src==dest ho jata hai
        wav_tmp = out.with_name(out.stem + ".raw.wav")
        r = subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", str(raw),
                            "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(wav_tmp)],
                           capture_output=True)
        if r.returncode != 0 or not wav_tmp.exists():
            return False
        if _style_needed:
            ok = _apply_style(wav_tmp, out, style)
            wav_tmp.unlink(missing_ok=True)
            return ok
        import shutil
        shutil.move(str(wav_tmp), str(out))
        return out.stat().st_size > 1000
    if style and (abs(style.get("pace", 1.0) - 1) > 0.01
                  or abs(style.get("pitch", 1.0) - 1) > 0.01
                  or abs(style.get("energy", 1.0) - 1) > 0.01):
        return _apply_style(raw, out, style)
    import shutil
    shutil.copy(raw, out)
    return out.stat().st_size > 1000


PROVIDERS = {"google": google}          # naya provider yahan jodo
DEFAULT = os.environ.get("FREE_TTS_PROVIDER", "google")


def have(provider: str | None = None) -> bool:
    """Kya ye provider chalta hai? (ek chhoti line ka asli test)"""
    name = provider or DEFAULT
    fn = PROVIDERS.get(name)
    if not fn:
        return False
    out = wt.work_tmp("free") / "probe.mp3"
    out.unlink(missing_ok=True)
    try:
        return bool(fn("नमस्ते", out, "hi", {}))
    except Exception:
        return False


def speak(text: str, out: str, bhaav=None, lang: str = "hi",
          provider: str | None = None) -> bool:
    name = provider or DEFAULT
    fn = PROVIDERS.get(name)
    if not fn:
        return False
    return bool(fn(text, Path(out), lang, _style(bhaav)))


def main() -> int:
    ap = argparse.ArgumentParser(description="bina key wali free TTS")
    ap.add_argument("text")
    ap.add_argument("--out", default=str(wt.work_tmp("free") / "tts.mp3"))
    ap.add_argument("--lang", default="hi")
    ap.add_argument("--bhaav", default="")
    ap.add_argument("--provider", default="")
    a = ap.parse_args()
    ok = speak(a.text, a.out, a.bhaav or None, a.lang, a.provider or None)
    size = Path(a.out).stat().st_size // 1024 if Path(a.out).exists() else 0
    print(json.dumps({"ok": ok, "file": a.out, "kb": size,
                      "provider": a.provider or DEFAULT}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
