#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS for Termux  -  a private, phone-only personal assistant.
Version 1.0

Kya karta hai:
  - Aapki aawaz sunta hai (Termux:API speech-to-text) ya seedha audio Gemini ko bhejta hai.
  - Jawab Gemini se laata hai aur phone se bolwata hai (termux-tts-speak).
  - Phone control karta hai: battery, torch, volume, app kholna, notification,
    vibrate, clipboard, location, photo, URL kholna, SMS/call (confirm ke baad).
  - Yaad rakhta hai: ~/.jarvis/memory.json (sirf aapke phone me, local).

Privacy:
  - API key ~/.jarvis/key.txt me, chmod 600.
  - Koi telemetry, koi server, koi cloud storage nahi. Sirf jo aap bolte ho wahi
    Gemini API tak jaata hai. Baaki sab phone ke andar.
  - Poora code ek hi file me hai, aap khud padh aur badal sakte ho.

Chalane se pehle:  bash setup.sh   (ek hi baar)
Phir:              python jarvis.py

Zero pip dependency - sirf Python standard library + Termux:API.
"""

import base64
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import wave
from datetime import datetime

VERSION = "1.0"
HOME = os.path.expanduser("~")
JARVIS_DIR = os.path.join(HOME, ".jarvis")
CONFIG_PATH = os.path.join(JARVIS_DIR, "config.json")
MEMORY_PATH = os.path.join(JARVIS_DIR, "memory.json")
KEY_PATH = os.path.join(JARVIS_DIR, "key.txt")
LOG_PATH = os.path.join(JARVIS_DIR, "jarvis.log")
LLAMA_LOG = os.path.join(JARVIS_DIR, "llama.log")
AUDIO_PATH = os.path.join(JARVIS_DIR, "mic.m4a")
API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
UA = "JarvisTermux/1.0 (Android; Termux)"

DEFAULT_CONFIG = {
    "name": "Jarvis",
    "user_name": "Boss",
    "language": "hinglish",      # hinglish | hi | en
    "engine": "stt",             # stt (sasta, tez) | audio (Gemini ko aawaz bhejta hai)
    "listen_seconds": 8,
    "voice_lang": "hi-IN",
    "tts": "gemini",             # gemini (emotional) | phone (robotic, fast) | auto
    "tts_style": "a real human woman speaking naturally, not a text-to-speech engine. Sweet, warm, clear Hindi/Hinglish pronunciation with slight breath, natural intonation and a soft smile in the voice. Speak Hindi/Hinglish with correct, crisp pronunciation and a gentle smile in the voice. Natural emotion and small pauses at commas, moderate speed, never flat or robotic. Every word should be clearly understandable.",
    "gemini_voice": "Kore",      # Kore, Aoede, Leda, Zephyr (female-ish)
    "tts_model": "gemini-2.5-flash-preview-tts",
    "voice_pitch": 1.15,         # phone TTS ki awaaz thodi patli (ladki jaisi)
    "tts_rate": 0.98,
    "model": "",                 # khaali = auto (sabse achha flash model khud chunega)
    "providers": "gemini,groq,openrouter,local",   # is order me try karega
    "groq_model": "llama-3.3-70b-versatile",
    "openrouter_model": "meta-llama/llama-3.3-70b-instruct:free",
    "provider_timeout": 25,
    "speed": "balanced",         # fast | balanced | quality
    "brain": "gemini",           # gemini | local  (local = phone me hi model, zero internet, zero paisa)
    "local_model": "",          # khaali = <folder>/models/model.gguf
    "llama_port": 8080,
    "n_ctx": 4096,
    "data_dir": "~/jarvis/data", # aapka data yahan rakho - .txt .md .csv .json .srt .pdf
    "rag_top": 4,                # ek jawab me data ke kitne hisse padhe
    "auto_loop": False,          # True = Enter dabane ki zarurat nahi, lagataar sunta rahe
    "speak_actions": True,       # action ka result bolkar bataye
    "max_history": 8,            # kitni purani baatein prompt me jaayein
    "confirm_risky": True,       # SMS/call se pehle poochhe
    "briefing": True,            # shuru hote hi chhoti briefing
    "adb_serial": "",            # setup_adb.sh ke baad khud bhar jata hai
}

# ----------------------------------------------------------------------------
# Chhote helpers
# ----------------------------------------------------------------------------

STUB = False  # --selftest ke liye
QUIET = {"on": False}   # --serve mode me terminal audio band


def ensure_dirs():
    os.makedirs(JARVIS_DIR, exist_ok=True)
    try:
        os.chmod(JARVIS_DIR, 0o700)
    except OSError:
        pass


def log(msg):
    try:
        ensure_dirs()
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(default, dict) and isinstance(data, dict):
            merged = dict(default)
            merged.update(data)
            return merged
        return data
    except (OSError, ValueError):
        return json.loads(json.dumps(default))


def write_json(path, data):
    ensure_dirs()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


SELF_LOG = os.path.join(JARVIS_DIR, "selfedit.log")
BACKUP_DIR = os.path.join(JARVIS_DIR, "backups")
SELF_PATH = os.path.abspath(__file__)


def _self_log(text):
    try:
        ensure_dirs()
        with open(SELF_LOG, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M"), text))
    except OSError:
        pass


def self_backup():
    ensure_dirs()
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dst = os.path.join(BACKUP_DIR, "jarvis-%s.py" % datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copyfile(SELF_PATH, dst)
    return dst


def self_restore(path=""):
    if not os.path.isdir(BACKUP_DIR):
        return "Koi backup nahi hai"
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "jarvis-*.py")))
    if not backups:
        return "Koi backup nahi hai"
    src = path or backups[-1]
    if not os.path.exists(src):
        return "Backup nahi mila: %s" % src
    shutil.copyfile(src, SELF_PATH)
    _self_log("restored from %s" % src)
    return "Wapas restore kar diya: %s" % os.path.basename(src)


def self_verify(full=None):
    """(ok, message) - naya code chalega ya nahi. Default: fast (compile+import)."""
    if full is None:
        full = os.environ.get("JARVIS_SAFE") == "1"
    try:
        with open(SELF_PATH, "r", encoding="utf-8") as f:
            src = f.read()
        compile(src, SELF_PATH, "exec")
    except SyntaxError as exc:
        return False, "syntax error line %s: %s" % (exc.lineno, exc.msg)
    except OSError as exc:
        return False, "file padhi nahi: %s" % exc
    # fast check: file import ho rahi hai?
    try:
        proc = subprocess.run([sys.executable, "-c",
                               "import importlib.util,sys;"
                               "spec=importlib.util.spec_from_file_location('j',%r);"
                               "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)"
                               % SELF_PATH],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            return False, "import fail: %s" % ((proc.stderr or "")[-250:])
    except Exception as exc:
        return False, "import check fail: %s" % exc
    if not full:
        return True, "ok (fast check)"
    try:
        proc = subprocess.run([sys.executable, SELF_PATH, "--selftest"],
                              capture_output=True, text=True, timeout=240)
        if proc.returncode != 0:
            out = (proc.stdout or "") + (proc.stderr or "")
            return False, "selftest fail: %s" % out.strip()[-300:]
    except Exception as exc:
        return False, "selftest chala nahi: %s" % exc
    return True, "ok"


def self_apply(edits, reason="", confirm=True):
    """Safe self-modify: backup -> apply -> compile+selftest -> fail par rollback."""
    try:
        with open(SELF_PATH, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as exc:
        return False, "apni file padhi nahi: %s" % exc
    new = src
    done = []
    for e in (edits or [])[:8]:
        if not isinstance(e, dict):
            continue
        old = str(e.get("old", ""))
        rep = str(e.get("new", ""))
        if not old:
            return False, "edit me 'old' khaali hai"
        count = new.count(old)
        if count == 0:
            return False, "ye code apni file me nahi mila: %r" % old[:70]
        if count > 1:
            return False, "ye code %d jagah hai, unique nahi: %r" % (count, old[:70])
        new = new.replace(old, rep, 1)
        done.append(old.strip().splitlines()[0][:60])
    if new == src:
        return False, "koi badlav nahi mila"
    if confirm and not STUB:
        print("  %d badlav:" % len(done))
        for d in done:
            print("    - %s" % d)
        try:
            ans = input("  Ye code change karun? (y/n) > ").strip().lower()
        except EOFError:
            ans = "n"
        if not ans.startswith("y"):
            return False, "aapne cancel kar diya"
    bak = self_backup()
    try:
        with open(SELF_PATH, "w", encoding="utf-8") as f:
            f.write(new)
        ok, msg = self_verify()
        if not ok:
            shutil.copyfile(bak, SELF_PATH)
            _self_log("rollback: %s | reason=%s" % (msg, reason))
            return False, "naya code fail hua (%s) - purana wapas laga diya" % msg
    except OSError as exc:
        try:
            shutil.copyfile(bak, SELF_PATH)
        except OSError:
            pass
        return False, "likhne me dikkat: %s" % exc
    _self_log("applied: %s | %s" % (reason, "; ".join(done)))
    try:
        brain_add("lessons", "khud ko badla: %s" % reason[:120])
        brain_add("skills", "; ".join(done)[:150])
    except Exception:
        pass
    return True, "Code update ho gaya (backup: %s)" % os.path.basename(bak)


def groq_transcribe(wav_bytes, key, cfg=None):
    """Groq Whisper se audio -> text. Free tier, bahut fast. (text, err)"""
    if not wav_bytes or not key:
        return "", "audio/key nahi"
    boundary = "----jarvisboundary7x"
    parts = []
    def field(name, value):
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (boundary, name, value)).encode("utf-8"))
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\n"
                  "Content-Type: audio/wav\r\n\r\n" % boundary).encode("utf-8"))
    parts.append(wav_bytes)
    parts.append(b"\r\n")
    field("model", "whisper-large-v3-turbo")
    field("response_format", "json")
    field("prompt", "Hinglish conversation: user Hindi aur English mix karke bolta hai. "
                    "Names, numbers aur English words jaisa bola gaya hai waisa hi likho.")
    parts.append(("--%s--\r\n" % boundary).encode("utf-8"))
    body = b"".join(parts)
    req = urllib.request.Request("https://api.groq.com/openai/v1/audio/transcriptions",
                                 data=body, method="POST",
                                 headers={"Authorization": "Bearer %s" % key,
                                          "Content-Type": "multipart/form-data; boundary=%s" % boundary,
                                          "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
        return (data.get("text") or "").strip(), ""
    except urllib.error.HTTPError as exc:
        msg = ""
        try:
            msg = exc.read().decode("utf-8", "ignore")[:150]
        except Exception:
            pass
        log("groq stt fail: HTTP %s %s" % (exc.code, msg))
        return "", "HTTP %s" % exc.code
    except Exception as exc:
        log("groq stt fail: %s" % exc)
        return "", str(exc)[:60]


def web_fallback(query, cfg=None):
    """Koi API na chale to open web se seedha jawab. (text, sources)"""
    try:
        hits = ddg_search(query, limit=4) or wiki_search(query) or wiki_search(query, "hi")
    except Exception as exc:
        log("web fallback search fail: %s" % exc)
        hits = []
    if not hits:
        return "", []
    words = [w.lower() for w in _WORD.findall(query or "") if len(w) > 3]
    junk = ("main page", "create account", "log in", "donate", "random article",
            "privacy policy", "cookie", "jump to", "navigation", "subscribe",
            "sign in", "advertisement", "all rights reserved", "retrieved from")
    pieces, used = [], []
    for h in hits[:3]:
        page = fetch_page(h["url"], 8000)
        if not page:
            continue
        sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", page)]
        good = [x for x in sentences
                if 50 < len(x) < 320 and not any(j in x.lower() for j in junk)]
        if not good:
            continue
        scored = sorted(good, key=lambda x: -sum(1 for w in words if w in x.lower()))
        take = [x for x in scored[:2] if sum(1 for w in words if w in x.lower()) > 0] or scored[:1]
        if take:
            pieces.append(" ".join(take))
            used.append(h)
        if len(used) >= 2:
            break
    if not pieces:
        return "", used
    return " ".join(pieces).strip()[:700], used


def ask_text(cfg, key, system, user, max_tokens=1200):
    """Kisi bhi provider se seedha text (JSON edits ke liye)."""
    order = [x.strip() for x in str(cfg.get("providers", "gemini,groq,openrouter")).split(",") if x.strip()]
    for prov in order:
        try:
            if prov == "gemini" and key:
                payload = {"contents": [{"role": "user", "parts": [{"text": user}]}],
                           "systemInstruction": {"parts": [{"text": system}]},
                           "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens,
                                                "responseMimeType": "application/json"}}
                resp = api_call("/models/%s:generateContent" % pick_model(key, cfg), payload, key=key, timeout=120)
                if "_error" not in resp:
                    txt = model_text(resp)
                    if txt:
                        return txt
            elif prov in OPENAI_COMPAT:
                pkey = load_provider_key(prov)
                if not pkey:
                    continue
                msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
                txt = openai_chat(prov, msgs, cfg, pkey, timeout=90)
                if txt:
                    return txt
        except Exception as exc:
            log("ask_text %s fail: %s" % (prov, exc))
    return ""


def code_context(needle, lines_around=45):
    """Request se milta-julta code hissa nikaalo, taaki model exact old-string de sake."""
    try:
        with open(SELF_PATH, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return ""
    words = [w.lower() for w in _WORD.findall(needle or "") if len(w) > 3]
    best, best_hit = 0, 0
    for i in range(len(lines)):
        window = " ".join(lines[i:i + lines_around]).lower()
        hit = sum(1 for w in words if w in window)
        if hit > best_hit:
            best, best_hit = i, hit
    start = max(0, best - 5)
    chunk = lines[start:start + lines_around * 2]
    return "\n".join(chunk)


SELF_SYSTEM = """You edit a single Python file (jarvis.py) that runs a phone assistant.
You must answer ONLY with JSON:
{"note": "short Hinglish note", "edits": [{"old": "<exact existing code>", "new": "<replacement>"}]}
Rules:
- "old" must be copied EXACTLY from the file, character for character, and must appear only once.
- Keep edits small. Do not rewrite the whole file.
- Valid Python 3 only. No new pip dependencies (standard library only).
- Do not remove safety checks, key handling, backups or the selftest.
- If you cannot do it safely, return {"note": "nahi ho sakta kyunki ...", "edits": []}.
"""


PENDING_EDIT = {"edits": [], "reason": "", "preview": ""}


def self_prepare(request, cfg, key, use_research=True):
    """Model se edits maango (apply nahi). Browser me preview dikhane ke liye.
    (ok, note, pending_dict)"""
    ctx = code_context(request)
    if not ctx:
        return False, "apni file padhi nahi ja saki", {}
    sources = ""
    if use_research and len(request) > 18 and cfg.get("self_research", True):
        try:
            ans, used = research(request, cfg, key, sources_n=2)
            if used:
                sources = "\n\nRESEARCH (in sources se seekho, par code khud likho):\n" + \
                          "\n".join("[%d] %s - %s" % (i + 1, h.get("title", "")[:60], h.get("url", ""))
                                    for i, h in enumerate(used[:2]))
        except Exception as exc:
            log("self research fail: %s" % exc)
    user = ("USER REQUEST: %s%s\n\nFILE KA RELEVANT HISA:\n```python\n%s\n```\n\nAb JSON do (edits)."
            % (request, sources, ctx))
    raw = ask_text(cfg, key, SELF_SYSTEM, user, max_tokens=1500)
    plan = extract_json(raw)
    if not isinstance(plan, dict):
        return False, "model ne theek JSON nahi diya", {}
    edits = [e for e in (plan.get("edits") or []) if isinstance(e, dict)]
    note = str(plan.get("note", "")).strip()
    if not edits:
        return False, (note or "model ne koi badlav nahi diya"), {}
    # pehle se check: old strings file me hain?
    try:
        with open(SELF_PATH, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as exc:
        return False, "file padhi nahi: %s" % exc, {}
    lines = []
    for e in edits[:8]:
        old = str(e.get("old", ""))
        cnt = src.count(old)
        if cnt == 0:
            return False, "model ka code file me nahi mila (dobara try karo)", {}
        if cnt > 1:
            return False, "model ka code %d jagah hai (unique nahi)" % cnt, {}
        new = str(e.get("new", ""))
        lines.append("- %s\n  -> %s" % (old.strip().splitlines()[0][:70],
                                         (new.strip().splitlines()[0][:70] or "(hata diya)")))
    preview = "%d badlav\n%s" % (len(edits), "\n".join(lines))
    pend = {"edits": edits, "reason": request, "preview": preview}
    return True, (note or "Badlav taiyar hai"), pend


def self_request(request, cfg, key, confirm=True):
    """User ki request se code khud badlo (safe)."""
    ctx = code_context(request)
    if not ctx:
        return False, "apni file padhi nahi ja saki"
    user = ("USER REQUEST: %s\n\nFILE KA RELEVANT HISA: \n```python\n%s\n```\n\n"
            "Ab JSON do (edits)." % (request, ctx))
    raw = ask_text(cfg, key, SELF_SYSTEM, user)
    plan = extract_json(raw)
    if not isinstance(plan, dict):
        return False, "model ne theek JSON nahi diya"
    edits = plan.get("edits") or []
    note = str(plan.get("note", ""))
    if not edits:
        return False, note or "model ne koi badlav nahi diya"
    ok, msg = self_apply(edits, reason=request, confirm=confirm)
    return ok, ("%s | %s" % (note, msg)).strip(" |")


BRAIN_PATH = os.path.join(JARVIS_DIR, "brain.json")
BRAIN_DEFAULT = {"facts": [], "style": [], "lessons": [], "skills": [], "stats": {},
                 "updated": ""}


def load_brain():
    b = read_json(BRAIN_PATH, BRAIN_DEFAULT)
    for k in ("facts", "style", "lessons", "skills"):
        if not isinstance(b.get(k), list):
            b[k] = []
    if not isinstance(b.get("stats"), dict):
        b["stats"] = {}
    return b


def save_brain(b):
    b["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    for k in ("facts", "style", "lessons", "skills"):
        b[k] = b[k][-300:]
    write_json(BRAIN_PATH, b)


def brain_add(kind, text, limit=300):
    text = str(text).strip()
    if not text or len(text) < 3:
        return
    b = load_brain()
    lst = b.setdefault(kind, [])
    if text in lst:
        lst.remove(text)
    lst.append(text[:limit])
    b[kind] = lst[-300:]
    save_brain(b)


def learn_from_turn(user_text, reply, cfg):
    """Har baat se seekho - rules based, fast (koi API call nahi)."""
    t = (user_text or "").lower()
    ut = (user_text or "").strip()
    got = []
    for pat in (r"(?:yaad rakho|remember)[:\s]+(.{3,140})",):
        m = re.search(pat, ut, re.I)
        if m:
            got.append(("facts", m.group(1).strip()))
    for pat in (r"(?:hamesha|always|aage se|future me)[:\s]+(.{4,140})",
                r"(?:aisa bolo|aise bolo|aise jawab do|tone)[:\s]+(.{4,140})"):
        m = re.search(pat, ut, re.I)
        if m:
            got.append(("style", m.group(1).strip()))
    m = re.search(r"mera naam ([A-Za-z\u0900-\u097F ]{2,30})", ut, re.I)
    if m:
        got.append(("facts", "user ka naam %s hai" % m.group(1).strip()))
    if any(w in t for w in ("galat", "galti", "wrong")):
        got.append(("lessons", "user ne bataya galat tha: %s" % ut[:100]))
    if reply and len(reply) < 400:
        b = load_brain()
        b["stats"]["turns"] = int(b["stats"].get("turns", 0)) + 1
        save_brain(b)
    for kind, txt in got:
        brain_add(kind, txt)


def brain_summary(cfg, max_chars=700):
    """Prompt ke liye chhota summary - fast rakhne ke liye."""
    b = load_brain()
    parts = []
    if b["facts"]:
        parts.append("Yaadein: " + "; ".join(b["facts"][-12:]))
    if b["style"]:
        parts.append("Style: " + "; ".join(b["style"][-6:]))
    if b["lessons"]:
        parts.append("Sabak: " + "; ".join(b["lessons"][-5:]))
    if b["skills"]:
        parts.append("Skills: " + "; ".join(b["skills"][-6:]))
    txt = "\n".join(parts)
    return txt[-max_chars:] if len(txt) > max_chars else txt


def gh_brain_sync(cfg, direction="push"):
    """GitHub ko personal database banao: brain.json wahan rakho. (ok, msg)"""
    tok = gh_token()
    if not tok:
        return False, "GitHub token nahi (python jarvis.py --setkey github)"
    repo = cfg.get("brain_repo") or "bhupendarsingh785/toonistaan-studio"
    path = cfg.get("brain_path") or "jarvis-kit/brain/brain.json"
    url = "/repos/%s/contents/%s" % (repo, path)
    if direction == "pull":
        data, err = gh_api(url, token=tok)
        if not data or "content" not in data:
            return False, "remote brain nahi mila: %s" % (err or "khaali")
        try:
            raw = base64.b64decode(data["content"]).decode("utf-8", "ignore")
            remote = json.loads(raw)
        except Exception as exc:
            return False, "remote brain padha nahi: %s" % exc
        local = load_brain()
        for k in ("facts", "style", "lessons", "skills"):
            merged = list(dict.fromkeys((remote.get(k) or []) + (local.get(k) or [])))
            local[k] = merged[-300:]
        save_brain(local)
        return True, "GitHub se brain mila (%d facts, %d sabak)" % (len(local["facts"]), len(local["lessons"]))
    # push
    b = load_brain()
    content = base64.b64encode(json.dumps(b, ensure_ascii=False, indent=1).encode("utf-8")).decode()
    body = {"message": "brain sync %s" % datetime.now().strftime("%Y-%m-%d %H:%M"), "content": content}
    data, err = gh_api(url, "GET", None, tok)
    if data and data.get("sha"):
        body["sha"] = data["sha"]
    res, err2 = gh_api(url, "PUT", body, tok)
    if not res:
        return False, "push fail: %s" % (err2 or err)
    return True, "brain GitHub par save (%d facts, %d style, %d sabak)" % (
        len(b["facts"]), len(b["style"]), len(b["lessons"]))


def load_config():
    return read_json(CONFIG_PATH, DEFAULT_CONFIG)


def save_config(cfg):
    write_json(CONFIG_PATH, cfg)


def load_memory():
    mem = read_json(MEMORY_PATH, {"facts": [], "notes": [], "history": []})
    for k in ("facts", "notes", "history"):
        if not isinstance(mem.get(k), list):
            mem[k] = []
    return mem


def save_memory(mem):
    write_json(MEMORY_PATH, mem)


def load_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        with open(KEY_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def strip_markdown(text):
    """TTS ko saaf text do - koi *, #, backtick, emoji nahi."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"[*_`#>]+", " ", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"https?://\S+", "link", text)
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ----------------------------------------------------------------------------
# Termux:API bridge
# ----------------------------------------------------------------------------

def have(cmd):
    return shutil.which(cmd) is not None


def termux(cmd, *args, timeout=25, stdin=None):
    """Termux:API command chalao. (ok, output) lautata hai. Shell kabhi use nahi hota."""
    if STUB:
        return True, "stub:" + " ".join([cmd] + [str(a) for a in args])
    if not have(cmd):
        return False, "missing:" + cmd
    try:
        proc = subprocess.run(
            [cmd] + [str(a) for a in args],
            capture_output=True, text=True, timeout=timeout, input=stdin,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except OSError as exc:
        return False, "error:%s" % exc
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0 and not out:
        return False, err or ("exit %d" % proc.returncode)
    return True, out or err


def termux_json(cmd, *args, timeout=25):
    ok, out = termux(cmd, *args, timeout=timeout)
    if not ok:
        return None, out
    try:
        return json.loads(out), ""
    except ValueError:
        return None, out[:200]


# ----------------------------------------------------------------------------
# Aawaz - sunna aur bolna
# ----------------------------------------------------------------------------

def listen_text(seconds=None):
    """Termux:API ka speech-to-text. Khaali string = kuch samajh nahi aaya."""
    ok, out = termux("termux-speech-to-text", timeout=max(20, (seconds or 8) + 15))
    if not ok:
        return ""
    return out.strip()


def record_audio(seconds):
    """Mic se audio file banao (m4a/AAC). Gemini ise seedha samajh leta hai."""
    if STUB:
        return b"stub-audio"
    if os.path.exists(AUDIO_PATH):
        try:
            os.remove(AUDIO_PATH)
        except OSError:
            pass
    ok, out = termux("termux-microphone-record", "-f", AUDIO_PATH,
                     "-l", str(int(seconds)), "-e", "aac", timeout=int(seconds) + 20)
    if not ok:
        log("record fail: %s" % out)
        return b""
    # file likhne ka thoda waqt
    for _ in range(20):
        if os.path.exists(AUDIO_PATH) and os.path.getsize(AUDIO_PATH) > 2000:
            break
        time.sleep(0.25)
    try:
        with open(AUDIO_PATH, "rb") as f:
            return f.read()
    except OSError:
        return b""


def phone_speak(text, cfg):
    """Phone ka TTS - female-ish pitch. Free, offline."""
    pitch = str(cfg.get("voice_pitch", 1.15))
    rate = str(cfg.get("tts_rate", 0.98))
    lang = str(cfg.get("voice_lang", "hi-IN"))
    for args in (["-l", lang, "-p", pitch, "-r", rate, "-v", "female", text],
                 ["-l", lang, "-p", pitch, "-r", rate, text],
                 ["-l", lang, text]):
        ok, out = termux("termux-tts-speak", *args, timeout=180)
        if ok:
            return True
    log("phone tts fail: %s" % out)
    return False


def gemini_tts(text, cfg, key):
    """Gemini ka expressive voice - emotions ke saath. (path, error)"""
    ensure_dirs()
    voice = cfg.get("gemini_voice", "Kore")
    model = cfg.get("tts_model", "gemini-2.5-flash-preview-tts")
    style = cfg.get("tts_style") or "warm, friendly, smiling, expressive"
    prompt = ("Speak the following line like a real person, not a text-to-speech engine. "
              "Style: %s. Use real emotion, a smile in the voice, small natural pauses at commas, "
              "and vary the pitch like a human conversation. Language: Hindi/Hinglish. "
              "Say only this line:\n%s" % (style, text))
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    resp = api_call("/models/%s:generateContent" % model, payload, key=key, timeout=120)
    if "_error" in resp:
        return None, "%s %s" % (resp["_error"], str(resp.get("_body", ""))[:120])
    b64 = ""
    try:
        part = resp["candidates"][0]["content"]["parts"][0]
        b64 = (part.get("inlineData") or part.get("inline_data") or {}).get("data", "")
    except (KeyError, IndexError, TypeError):
        pass
    if not b64:
        return None, "audio nahi mila"
    try:
        raw = base64.b64decode(b64)
    except Exception as exc:
        return None, "decode fail: %s" % exc
    path = os.path.join(JARVIS_DIR, "tts.wav")
    try:
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(raw)
    except Exception as exc:
        return None, "wav fail: %s" % exc
    return path, ""


def play_audio(path, seconds=0):
    if STUB:
        return True
    if have("ffplay"):
        try:
            subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                           timeout=int(seconds) + 60)
            return True
        except Exception:
            pass
    ok, out = termux("termux-media-player", "play", path, timeout=20)
    if not ok:
        return False
    time.sleep(min(max(seconds, 0.5), 120))
    termux("termux-media-player", "stop", timeout=10)
    return True


def wav_seconds(path):
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return 0.0


def speak(text, cfg, force_gemini=False):
    """Text aur awaaz saath me: Gemini voice pehle banata hai, phir dono ek saath."""
    text = strip_markdown(text)
    if not text:
        return
    if QUIET["on"]:
        print("  %s: %s" % (cfg.get("name", "Jarvis"), text))
        return
    mode = str(cfg.get("tts", "auto"))
    key = load_key()
    use_gemini = (mode == "gemini") or (mode == "auto" and force_gemini)
    if STUB:
        print("\n%s: %s\n" % (cfg.get("name", "Jarvis"), text))
        return

    if use_gemini and key and TTS_COOL["until"] > time.time():
        use_gemini = False
        if not TTS_COOL["told"]:
            print("  (Gemini voice ka quota khatam hai - phone ki awaaz use kar rahi hoon)")
            TTS_COOL["told"] = True
    if use_gemini and key:
        print("  (awaaz ban rahi hai...)")
        path, err = gemini_tts(text, cfg, key)
        if path:
            print("\n%s: %s\n" % (cfg.get("name", "Jarvis"), text), end="", flush=True)
            if play_audio(path, wav_seconds(path)):
                print()
                return
            err = "play fail"
        if "429" in str(err) or "quota" in str(err).lower():
            TTS_COOL["until"] = time.time() + 1800
            print("  (Gemini voice quota khatam - 30 min phone voice. Billing on karo to wapas aayegi)")
        log("gemini tts fail (%s) - phone voice par ja raha hoon" % err)
        if mode == "gemini":
            print("  (Gemini voice fail: %s)" % err)

    print("\n%s: %s\n" % (cfg.get("name", "Jarvis"), text), flush=True)
    phone_speak(text, cfg)

def adb_serial(cfg):
    if cfg.get("adb_serial"):
        return str(cfg["adb_serial"])
    ok, out = termux("adb", "devices", timeout=20)
    if not ok:
        return ""
    for line in out.splitlines():
        if "\tdevice" in line:
            return line.split("\t")[0].strip()
    return ""


def adb_shell(cmd, cfg=None, timeout=25):
    """ADB ke through phone me shell command. (ok, output)"""
    cfg = cfg or load_config()
    if not have("adb"):
        return False, "adb nahi mila - pkg install android-tools"
    serial = adb_serial(cfg)
    if not serial:
        return False, "adb device connected nahi hai - bash setup_adb.sh"
    ok, out = termux("adb", "-s", serial, "shell", cmd, timeout=timeout)
    return ok, out


def adb_ready(cfg=None):
    cfg = cfg or load_config()
    if not have("adb"):
        return False, "adb install nahi hai"
    if not adb_serial(cfg):
        return False, "phone paired nahi hai"
    ok, out = adb_shell("echo jarvis_ok", cfg, timeout=15)
    return (ok and "jarvis_ok" in out), (out or "no answer")


APP_MAP = {
    "youtube": "com.google.android.youtube",
    "whatsapp": "com.whatsapp",
    "instagram": "com.instagram.android",
    "facebook": "com.facebook.katana",
    "chrome": "com.android.chrome",
    "camera": "com.android.camera",
    "settings": "com.android.settings",
    "gmail": "com.google.android.gm",
    "maps": "com.google.android.apps.maps",
    "spotify": "com.spotify.music",
    "telegram": "org.telegram.messenger",
    "playstore": "com.android.vending",
    "gallery": "com.google.android.apps.photos",
    "phone": "com.google.android.dialer",
    "messages": "com.google.android.apps.messaging",
    "x": "com.twitter.android",
    "twitter": "com.twitter.android",
    "netflix": "com.netflix.mediaclient",
    "hotstar": "in.startv.hotstar",
    "paytm": "net.one97.paytm",
    "phonepe": "com.phonepe.app",
    "gpay": "com.google.android.apps.nbu.paisa.user",
    "zomato": "com.application.zomato",
    "swiggy": "in.swiggy.android",
}

KEYS = {"home": "3", "back": "4", "recent": "187", "power": "26", "volume_up": "24",
        "volume_down": "25", "mute": "164", "play_pause": "85", "play": "126", "pause": "127",
        "next": "87", "prev": "88", "enter": "66", "delete": "67", "search": "84",
        "wake": "224", "sleep": "223", "screenshot": "120"}


def pkg_from(text):
    t = (text or "").lower()
    for name, pkg in APP_MAP.items():
        if name in t:
            return pkg
    return ""


def t_app_stop(a):
    pkg = str(a.get("package") or "").strip() or pkg_from(str(a.get("app", "")))
    if not pkg:
        return "Kaunsa app band karna hai? Naam bolo (youtube, whatsapp...)"
    ok, out = adb_shell("am force-stop %s" % pkg)
    if ok:
        return "%s band kar diya" % pkg
    # fallback: App info page khol do (wahan Force stop hota hai)
    ok2, out2 = termux("am", "start", "-a", "android.settings.APPLICATION_DETAILS_SETTINGS",
                       "-d", "package:%s" % pkg, timeout=20)
    if ok2:
        return ("%s ki App info khol di - neeche 'Force stop' dabao. "
                "(ADB pair karne ke baad ye khud ho jayega: bash pair_now.sh)" % pkg)
    return "Band nahi kar paya: %s" % (out or out2)


def t_app_info(a):
    pkg = str(a.get("package") or "").strip() or pkg_from(str(a.get("app", "")))
    if not pkg:
        return "Kaunsa app? Naam bolo"
    ok, out = termux("am", "start", "-a", "android.settings.APPLICATION_DETAILS_SETTINGS",
                     "-d", "package:%s" % pkg, timeout=20)
    return ("%s ki settings khol di" % pkg) if ok else "Nahi khula: %s" % out


def t_app_start(a):
    pkg = str(a.get("package") or "").strip() or pkg_from(str(a.get("app", "")))
    if not pkg:
        return "Kaunsa app kholna hai?"
    ok, out = adb_shell("monkey -p %s -c android.intent.category.LAUNCHER 1" % pkg)
    if ok and "No activities" not in out:
        return "%s khol diya" % pkg
    return t_open_app({"package": pkg})


def t_key(a):
    key = str(a.get("key") or a.get("name") or "").strip().lower()
    code = KEYS.get(key, key if key.isdigit() else "")
    if not code:
        return "Key samajh nahi aayi: %s" % key
    ok, out = adb_shell("input keyevent %s" % code)
    return ("%s dabaya" % (key or code)) if ok else "Key nahi chali: %s" % out


def t_media(a):
    act = str(a.get("action") or a.get("what") or "").strip().lower()
    code = {"pause": "127", "play": "126", "toggle": "85", "stop": "86",
            "next": "87", "prev": "88", "mute": "164"}.get(act, "85")
    ok, out = adb_shell("input keyevent %s" % code)
    return ("Media %s" % act) if ok else "Media control fail: %s" % out


def t_tap(a):
    try:
        x, y = int(a.get("x", 0)), int(a.get("y", 0))
    except (TypeError, ValueError):
        return "x aur y number chahiye"
    ok, out = adb_shell("input tap %d %d" % (x, y))
    return "Tap (%d,%d)" % (x, y) if ok else "Tap fail: %s" % out


def t_screen(a):
    """Screen par kya likha hai - uiautomator se padho."""
    ok, out = adb_shell("uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; cat /sdcard/ui.xml",
                        timeout=35)
    if not ok or "<" not in out:
        return "Screen padh nahi paya: %s" % (out or "khaali")[:120]
    texts = [t for t in re.findall(r'text="([^"]{2,60})"', out) if t.strip()]
    seen, uniq = set(), []
    for t in texts:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return "Screen par: " + " | ".join(uniq[:15]) if uniq else "Screen par koi text nahi"


def t_screenshot(a):
    path = os.path.join(HOME, "storage", "pictures", "screen_%s.png" %
                        datetime.now().strftime("%H%M%S"))
    ok, out = adb_shell("screencap -p /sdcard/screen.png && cp /sdcard/screen.png %s" % path)
    if not ok:
        return "Screenshot fail: %s" % out
    return "Screenshot: %s" % path


# ----------------------------------------------------------------------------
# RESEARCH - internet se source ke saath jawab (galat data se bachne ke liye)
# ----------------------------------------------------------------------------

def http_get(url, timeout=25, limit=400000):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) Jarvis/1.0",
        "Accept-Language": "en-IN,hi;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(limit).decode("utf-8", "ignore")


def html_to_text(html):
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    html = html.replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")
    return re.sub(r"\s+", " ", html).strip()


def ddg_search(query, limit=5):
    """DuckDuckGo HTML se results (koi API key nahi)."""
    out = []
    try:
        html = http_get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query))
    except Exception as exc:
        log("ddg fail: %s" % exc)
        return out
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        url, title = m.group(1), html_to_text(m.group(2))
        if "uddg=" in url:
            try:
                url = urllib.parse.unquote(re.search(r"uddg=([^&]+)", url).group(1))
            except Exception:
                pass
        if url.startswith("http") and not any(h["url"] == url for h in out):
            out.append({"title": title[:120] or url.split("/")[2], "url": url})
        if len(out) >= limit:
            break
    if out:
        return out
    # lite endpoint (alag HTML)
    try:
        lite = http_get("https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(query))
    except Exception as exc:
        log("ddg lite fail: %s" % exc)
        return out
    for enc in re.findall(r"uddg=([^&\"]+)", lite):
        url = urllib.parse.unquote(enc)
        if url.startswith("http") and not any(h["url"] == url for h in out):
            out.append({"title": url.split("/")[2], "url": url})
        if len(out) >= limit:
            break
    return out


def wiki_search(query, lang="en", limit=3):
    out = []
    try:
        data = json.loads(http_get(
            "https://%s.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=%d&srsearch=%s"
            % (lang, limit, urllib.parse.quote(query))))
        for item in (data.get("query", {}).get("search") or [])[:limit]:
            title = item.get("title", "")
            out.append({"title": title,
                        "url": "https://%s.wikipedia.org/wiki/%s" % (lang, urllib.parse.quote(title.replace(" ", "_")))})
    except Exception as exc:
        log("wiki fail: %s" % exc)
    return out


def fetch_page(url, chars=3500):
    try:
        return html_to_text(http_get(url))[:chars]
    except Exception as exc:
        log("fetch fail %s: %s" % (url, exc))
        return ""


def research(query, cfg, key, sources_n=3):
    """Search -> pages padho -> source ke saath jawab. (answer, sources)"""
    hits = ddg_search(query) or wiki_search(query) or wiki_search(query, "hi")
    if not hits:
        return ("Mujhe iske bare me koi bharosemand source nahi mila Boss, isliye kuch bana kar nahi bataungi.", [])
    notes, used = [], []
    for h in hits[:sources_n]:
        text = fetch_page(h["url"])
        if len(text) < 200:
            continue
        notes.append("[%d] %s (%s)\n%s" % (len(used) + 1, h["title"], h["url"], text[:1800]))
        used.append(h)
    if not notes:
        return ("Sources khule nahi Boss, abhi bata nahi sakti. Thodi der baad try karein?", [])
    ask = ("Sirf neeche diye sources ke aadhar par jawab do. Jo sources me nahi hai wo mat bolo. "
           "Har baat ke aage [1], [2] jaisa source number lagao. Agar sources me jawab nahi hai to "
           "saaf likho: 'sources me ye nahi mila'.\n\nSawaal: %s\n\nSources:\n%s" % (query, "\n\n".join(notes)))
    ans = ask_text(cfg, key, "Tum ek careful researcher ho. Sirf diye gaye sources par bharosa karo. "
                             "Bullet points nahi, chhoti Hinglish lines me bolo (max 5 line).", ask, max_tokens=900)
    if not ans:
        return ("Research ke liye koi brain available nahi tha Boss.", used)
    plan = extract_json(ans)
    if isinstance(plan, dict) and plan.get("say"):
        ans = str(plan["say"])
    return strip_markdown(ans)[:1200], used


# ----------------------------------------------------------------------------
# APP BUILDER - idea se chhoti app (single file HTML) phone me hi
# ----------------------------------------------------------------------------

def build_app(idea, cfg, key):
    """Idea se single-file HTML app banao aur browser me kholo."""
    projects = os.path.join(os.path.dirname(SELF_PATH), "projects")
    os.makedirs(projects, exist_ok=True)
    ask = ("Ek single-file HTML app banao is idea ke liye: %s\n"
           "Rules: ek hi HTML file, CSS aur JS andar inline, mobile-first, Hinglish UI labels, "
           "no external CDN, no build step. Sirf poora HTML code do, koi explanation nahi." % idea)
    code = ask_text(cfg, key, "You write complete, working single-file HTML apps. Output only HTML.",
                    ask, max_tokens=3000)
    if not code or "<html" not in code.lower():
        return None, "model se poora HTML nahi mila"
    code = re.sub(r"^```(?:html)?", "", code.strip())
    code = re.sub(r"```$", "", code).strip()
    slug = re.sub(r"[^a-z0-9]+", "-", idea.lower())[:40].strip("-") or "app"
    path = os.path.join(projects, slug + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    termux("termux-open-url", "file://" + path, timeout=20)
    return path, ""


# ----------------------------------------------------------------------------
# GITHUB - token se repos, files (REST API)
# ----------------------------------------------------------------------------

def gh_api(path, method="GET", body=None, token=""):
    url = "https://api.github.com" + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer %s" % token, "Accept": "application/vnd.github+json",
        "User-Agent": UA, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return json.loads(resp.read().decode("utf-8", "ignore")), ""
    except urllib.error.HTTPError as exc:
        msg = ""
        try:
            msg = exc.read().decode("utf-8", "ignore")[:200]
        except Exception:
            pass
        return None, "HTTP %s %s" % (exc.code, msg)
    except Exception as exc:
        return None, str(exc)


def gh_token():
    return load_provider_key("github")


def t_gh_repos(a):
    tok = gh_token()
    if not tok:
        return "GitHub token nahi hai (--setkey github)"
    data, err = gh_api("/user/repos?per_page=10&sort=updated", token=tok)
    if not data:
        return "GitHub: %s" % err
    return ", ".join(r.get("full_name", "?") for r in data[:10])


def t_gh_upload(a):
    tok = gh_token()
    if not tok:
        return "GitHub token nahi hai (--setkey github)"
    repo = str(a.get("repo", "")).strip()
    path = str(a.get("path", "")).strip()
    src = os.path.expanduser(str(a.get("file", "")))
    if not (repo and path and os.path.exists(src)):
        return "repo, path aur file chahiye"
    with open(src, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    body = {"message": a.get("message", "jarvis upload"), "content": content}
    data, err = gh_api("/repos/%s/contents/%s" % (repo, path), "PUT", body, tok)
    return "Upload ho gaya: %s/%s" % (repo, path) if data else "Upload fail: %s" % err


# ----------------------------------------------------------------------------
# LOCAL BRAIN - phone me hi model, zero internet, zero paisa, zero dependency
# ----------------------------------------------------------------------------

_LLAMA_PROC = None


def data_dir(cfg):
    d = os.path.expanduser(cfg.get("data_dir") or "~/jarvis/data")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def local_model_path(cfg):
    if cfg.get("local_model"):
        return os.path.expanduser(cfg["local_model"])
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "models", "model.gguf"),
                 os.path.expanduser("~/jarvis/models/model.gguf")):
        if os.path.exists(cand):
            return cand
    return os.path.join(here, "models", "model.gguf")


def llama_port(cfg):
    return int(cfg.get("llama_port", 8080))


def llama_alive(cfg):
    if STUB:
        return True
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/health" % llama_port(cfg),
                                    timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def find_server(cfg):
    """llama-server kahan hai - pehle apna shipped engine, phir PATH."""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = []
    if cfg.get("llama_binary"):
        cands.append(os.path.expanduser(cfg["llama_binary"]))
    for c in (os.path.join(here, "engine", "llama-server"),
              os.path.join(here, "bin", "llama-server"),
              os.path.expanduser("~/jarvis/engine/llama-server"),
              os.path.expanduser("~/jarvis/bin/llama-server")):
        cands.append(c)
    for c in cands:
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c
    for name in ("llama-server", "llama-server-static", "llamafile"):
        found = shutil.which(name)
        if found:
            return found
    return None


def server_env(binary):
    """Bundled engine ke .so files dhoondhne ke liye LD_LIBRARY_PATH."""
    env = dict(os.environ)
    if binary:
        d = os.path.dirname(os.path.abspath(binary))
        try:
            names = os.listdir(d)
        except OSError:
            names = []
        if any(n.startswith(("libllama", "libggml")) for n in names):
            old = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = d + (":" + old if old else "")
    return env


def server_version(binary):
    """(ok, text) - binary chal raha hai ya nahi."""
    if not binary:
        return False, ""
    try:
        proc = subprocess.run([binary, "--version"], capture_output=True, text=True,
                              timeout=25, env=server_env(binary))
        txt = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return (proc.returncode == 0 and "CANNOT LINK" not in txt), txt
    except Exception:
        return False, ""


def llama_tail(lines=6):
    try:
        with open(LLAMA_LOG, "r", encoding="utf-8", errors="ignore") as f:
            data = [l.strip() for l in f.read().splitlines() if l.strip()]
        return " | ".join(data[-lines:])[-400:]
    except OSError:
        return ""


def start_llama(cfg):
    """Local model server ko zarurat par shuru karo. (ok, message)"""
    global _LLAMA_PROC
    ensure_dirs()
    if llama_alive(cfg):
        return True, "already running"
    model = local_model_path(cfg)
    if not os.path.exists(model):
        return False, ("model file nahi mili: %s - chalao: bash setup_local.sh" % model)
    size_gb = os.path.getsize(model) / 1e9
    if size_gb < 0.3:
        return False, ("model file adhoori hai (%.2f GB) - download dobara karo: "
                       "bash setup_local.sh" % size_gb)
    binary = find_server(cfg)
    if not binary:
        return False, ("engine (llama-server) nahi mila - chalao: bash install_engine.sh "
                       "(ready-made binary, compile nahi)")
    threads = max(2, min(6, os.cpu_count() or 4))
    nctx = int(cfg.get("n_ctx", 4096))
    port = str(llama_port(cfg))
    attempts = [
        [binary, "-m", model, "-c", str(nctx), "--host", "127.0.0.1", "--port", port,
         "-t", str(threads), "-ngl", "0"],
        [binary, "-m", model, "-c", str(min(2048, nctx)), "--port", port, "-t", str(threads)],
        [binary, "-m", model, "-c", str(min(1024, nctx)), "--port", port, "-t", "2"],
    ]
    last_err = ""
    for i, cmd in enumerate(attempts, 1):
        try:
            with open(LLAMA_LOG, "w", encoding="utf-8") as logf:
                logf.write("CMD: %s\n" % " ".join(cmd))
                logf.flush()
                _LLAMA_PROC = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT,
                                               env=server_env(binary))
        except OSError as exc:
            last_err = "server start nahi hua: %s" % exc
            continue
        if i == 1:
            print("  (local model load ho raha hai, 10-60 second...)")
        for _ in range(120):
            if llama_alive(cfg):
                return True, "started"
            if _LLAMA_PROC.poll() is not None:
                last_err = llama_tail()
                break
            time.sleep(1)
        else:
            last_err = "server 2 minute me ready nahi hua"
        log("llama attempt %d fail: %s" % (i, last_err))
        stop_llama()
        if "CANNOT LINK" in last_err or "cannot locate symbol" in last_err:
            return False, ("llama-server binary toota hua hai (libc++ link error). "
                           "Fix: bash setup_local.sh --build")
    return False, "server band ho gaya. Error: %s (poora log: %s)" % (last_err or "unknown", LLAMA_LOG)


def stop_llama():
    global _LLAMA_PROC
    if _LLAMA_PROC is not None and _LLAMA_PROC.poll() is None:
        try:
            _LLAMA_PROC.terminate()
        except OSError:
            pass


TEXT_EXT = {".txt", ".md", ".markdown", ".csv", ".json", ".log", ".srt", ".vtt",
            ".html", ".htm", ".tsv"}


def _read_docx(path):
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        xml = re.sub(r"<[^>]+>", " ", xml)
        return re.sub(r"[ \t]+", " ", xml).strip()
    except Exception:
        return ""


def _read_xlsx(path):
    try:
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.startswith("xl/sharedStrings") or
                     re.match(r"xl/worksheets/sheet\d+\.xml", n)]
            out = []
            for n in names:
                xml = z.read(n).decode("utf-8", "ignore")
                out.append(re.sub(r"<[^>]+>", " ", xml))
            return re.sub(r"[ \t]+", " ", " ".join(out)).strip()
    except Exception:
        return ""


def _read_any(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return _read_docx(path)
    if ext in (".xlsx", ".xlsm"):
        return _read_xlsx(path)
    if ext in TEXT_EXT:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except OSError:
            return ""
    if ext == ".pdf" and have("pdftotext"):
        try:
            out = subprocess.run(["pdftotext", "-layout", path, "-"],
                                 capture_output=True, text=True, timeout=90)
            return out.stdout or ""
        except Exception:
            return ""
    return ""


DATA_EXT = (".txt", ".md", ".markdown", ".csv", ".json", ".log", ".srt", ".vtt",
            ".html", ".htm", ".tsv", ".pdf", ".docx")


def import_data(src, cfg):
    """Aapka data vault me laao - file, folder ya zip. (message, added_count)"""
    import shutil as _sh
    d = data_dir(cfg)
    src = os.path.expanduser(src)
    if not os.path.exists(src):
        return ("Path nahi mila: %s" % src), 0
    added = 0

    def _take(path, name=None):
        nonlocal added
        name = name or os.path.basename(path)
        if not name.lower().endswith(DATA_EXT):
            return
        dest = os.path.join(d, os.path.basename(name))
        base, ext = os.path.splitext(dest)
        i = 1
        while os.path.exists(dest):
            dest = "%s_%d%s" % (base, i, ext)
            i += 1
        try:
            _sh.copyfile(path, dest)
            added += 1
        except OSError:
            pass

    if os.path.isdir(src):
        for root, dirs, names in os.walk(src):
            dirs[:] = [x for x in dirs if not x.startswith(".")]
            for n in names:
                if not n.startswith("."):
                    _take(os.path.join(root, n), n)
    elif src.lower().endswith(".zip"):
        tmp = os.path.join(JARVIS_DIR, "_import")
        _sh.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp, exist_ok=True)
        try:
            with zipfile.ZipFile(src) as z:
                z.extractall(tmp)
        except Exception as exc:
            return ("Zip khol nahi paya: %s" % exc), 0
        for root, dirs, names in os.walk(tmp):
            for n in names:
                if not n.startswith("."):
                    _take(os.path.join(root, n), n)
        _sh.rmtree(tmp, ignore_errors=True)
    else:
        _take(src)
    chunks, nfiles, _ = build_index(cfg, force=True)
    return ("%d file vault me daali. Ab vault me %d file, %d hisse." % (added, nfiles, len(chunks))), added


def build_index(cfg, force=False):
    """Aapke data folder ko chhote hisson me todo. (chunks, file_count, from_cache)"""
    d = data_dir(cfg)
    cache_path = os.path.join(JARVIS_DIR, "index.json")
    files = []
    for root, dirs, names in os.walk(d):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for n in names:
            if not n.startswith("."):
                files.append(os.path.join(root, n))
    files.sort()
    sig = []
    for f in files:
        try:
            st = os.stat(f)
            sig.append("%s|%d|%d" % (f, st.st_size, int(st.st_mtime)))
        except OSError:
            pass
    if not force:
        cached = read_json(cache_path, {})
        if isinstance(cached, dict) and cached.get("sig") == sig and cached.get("chunks"):
            return cached["chunks"], len(files), True
    chunks = []
    for f in files:
        text = re.sub(r"\n{3,}", "\n\n", _read_any(f) or "").strip()
        if len(text) < 20:
            continue
        base = os.path.relpath(f, d)
        size, step = 700, 600
        for i in range(0, len(text), step):
            piece = text[i:i + size].strip()
            if len(piece) > 25:
                chunks.append({"file": base, "text": piece})
            if i + size >= len(text):
                break
    chunks = chunks[:4000]
    write_json(cache_path, {"sig": sig, "chunks": chunks})
    return chunks, len(files), False


_WORD = re.compile(r"[A-Za-z\u0900-\u097F]+|\d+")


def _tokens(text):
    return set(w.lower() for w in _WORD.findall(text or "") if len(w) > 2)


def retrieve(query, chunks, k=4):
    """Keyword overlap se sabse relevant hisse. Internet nahi, library nahi."""
    q = _tokens(query)
    if not q or not chunks:
        return []
    scored = []
    for ch in chunks:
        toks = _tokens(ch.get("text", ""))
        if not toks:
            continue
        hit = len(q & toks)
        if hit:
            scored.append((hit / (len(toks) ** 0.5), ch))
    scored.sort(key=lambda x: -x[0])
    return [ch for _, ch in scored[:k]]


LOCAL_SYSTEM = """You are {name}, {user}'s private assistant on an Android phone. Offline.
LANGUAGE RULE (most important): always answer in HINGLISH - Hindi written in English letters.
Never answer in English only. Example answer: "Battery 46% hai Boss, charging par rakho."
Style: one short sentence, maximum 20 words, no markdown, no emoji, no lists.
Examples:
  user: battery kitni hai  ->  Battery 46% hai Boss, abhi charging nahi lag rahi.
  user: time kya hua       ->  Dopahar 1:51 baje hain Boss.
  user: naam kya hai       ->  Mera naam {name} hai, main aapka assistant hoon.
Never invent numbers or facts. If you do not know, say: "Ye mujhe nahi pata Boss."
What you know about {user}: {facts}
"""


def local_prompt(cfg, mem, ctx):
    facts = "; ".join(mem.get("facts", [])[-10:]) or "nothing yet"
    base = LOCAL_SYSTEM.format(name=cfg.get("name", "Jarvis"),
                               user=cfg.get("user_name", "Boss"),
                               lang=LANG_LINE.get(cfg.get("language", "hinglish"), ""),
                               facts=facts)
    if ctx:
        base += "\nAapke apne data se ye hisse mile hain (sirf inhi par bharosa karo):\n" + ctx
    return base


def local_chat(messages, cfg, timeout=300):
    payload = {"messages": messages, "temperature": 0.35, "max_tokens": 300, "stream": False}
    for attempt in (1, 2):
        req = urllib.request.Request(
            "http://127.0.0.1:%d/v1/chat/completions" % llama_port(cfg),
            data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "ignore"))
            return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "") or ""
        except Exception:
            if attempt == 1:
                time.sleep(2)
                continue
            return ""
    return ""


ROUTES = [
    (("battery", "batteri", "charge kitna", "charging"), "battery"),
    (("torch", "flashlight", "batti"), "torch"),
    (("time kya", "kitne baje", "samay kya", "date kya", "tarikh"), "time"),
    (("kya hai ye", "ye kya hai", "dekho", "dekh kar batao", "padh kar batao", "camera se dekh"), "look"),
    (("research karo", "search karo", "internet se dekho", "khoj karo", "google karo"), "research"),
    (("dikkat", "problem", "kya gadbad", "check karo", "diagnose", "sun nahi", "kaam nahi kar",
      "error kyun", "theek karo apne"), "diagnose"),
    (("band karo", "band kar do", "close karo", "kill karo"), "app_stop"),
    (("pause karo", "rok do", "play karo", "next gaana", "pichhla gaana"), "media"),
    (("wifi", "internet kaisa"), "wifi"),
    (("location", "kahan hoon", "meri jagah"), "location"),
    (("vibrate", "hila do"), "vibrate"),
    (("clipboard", "copy kiya"), "clipboard_get"),
    (("photo", "camera", "tasveer"), "photo"),
    (("volume", "awaaz"), "volume"),
    (("notes sunao", "note sunao", "notes batao"), "note_list"),
    (("note likho", "note banao", "note add"), "note_add"),
    (("yaad rakho", "remember"), "remember"),
]


def local_route(text):
    """Chhota model JSON bhool jata hai - isliye phone ke kaam yahan seedha pakde jaate hain."""
    t = (text or "").lower()
    for keys, tool in ROUTES:
        if any(k in t for k in keys):
            args = {}
            if tool == "torch":
                args = {"on": not any(w in t for w in ("band", "off", "bujha"))}
            elif tool == "volume":
                nums = re.findall(r"\d+", t)
                args = {"level": int(nums[0]) if nums else 8}
            elif tool == "note_add":
                args = {"text": re.sub(r"(?i)(note likho|note banao|note add)", "", text).strip(" :,-")}
            elif tool == "remember":
                args = {"fact": re.sub(r"(?i)(yaad rakho|remember)", "", text).strip(" :,-")}
            elif tool == "vibrate":
                args = {"ms": 400}
            elif tool == "photo":
                args = {"camera": 0}
            return tool, args
    return None


HINGLISH_WORDS = ("hai", "hoon", "par", "karo", "kar ", "bata", "nahi", "aap", "boss",
                  "abhi", "gaya", "gayi", "raha", "rahi", "hua", "hain", "mujhe", "aapka")


def looks_hinglish(text):
    t = (text or "").lower()
    return any(w in t for w in HINGLISH_WORDS)


def hinglish_fallback(tool, result):
    res = str(result).strip()
    low = res.lower()
    if tool in ("battery", "time"):
        return "%s Boss." % res.rstrip(".")
    if tool == "torch":
        return "Torch %s Boss." % ("on" if "on" in low else "off")
    return "%s Boss." % res


def ask_local(cfg, mem, user_part, extra=None):
    ok, msg = start_llama(cfg)
    if not ok:
        return {"say": "Local brain taiyar nahi: %s" % msg, "do": []}
    query = user_part if isinstance(user_part, str) else ""
    routed = local_route(query) if query else None
    if routed:
        tool, args = routed
        result = run_tool(tool, args, cfg)
        msgs = [{"role": "system", "content": local_prompt(cfg, mem, "")},
                {"role": "user", "content": ("Asli tool result: %s\nIsko Hinglish me ek chhoti line me batao "
                                             "(max 20 words). Sirf baat likho, JSON nahi." % result)}]
        raw = local_chat(msgs, cfg)
        say = strip_markdown(raw or "").strip()
        parsed = extract_json(say)
        if isinstance(parsed, dict) and parsed.get("say"):
            say = strip_markdown(str(parsed["say"]))
        if (not say) or say.lower().startswith("{") or len(say) > 200 \
                or not looks_hinglish(say) or say.strip().rstrip(".") == str(result).strip().rstrip("."):
            say = hinglish_fallback(tool, result)
        return {"say": say, "do": []}
    chunks, _nfiles, _cached = build_index(cfg)
    picked = retrieve(query, chunks, int(cfg.get("rag_top", 4)))
    ctx = "\n---\n".join("[%s] %s" % (c["file"], c["text"][:600]) for c in picked)
    msgs = [{"role": "system", "content": local_prompt(cfg, mem, ctx)}]
    for turn in mem.get("history", [])[-4:]:
        msgs.append({"role": "assistant" if turn.get("role") == "model" else "user",
                     "content": str(turn.get("text", ""))[:400]})
    if isinstance(user_part, str):
        msgs.append({"role": "user", "content": user_part})
    else:
        msgs.append({"role": "user", "content": "[audio mode local brain ke saath nahi chalta]"})
    if extra:
        msgs.append({"role": "user", "content": extra})
    raw = local_chat(msgs, cfg)
    plan = extract_json(raw)
    if not isinstance(plan, dict):
        plan = {"say": strip_markdown(raw)[:400], "do": []}
    plan.setdefault("do", [])
    return plan


# ----------------------------------------------------------------------------
# Phone tools - model inhi ko bulata hai
# ----------------------------------------------------------------------------

def t_battery(a):
    data, err = termux_json("termux-battery-status")
    if data is None:
        return "Battery status nahi mila: %s" % err
    pct = data.get("percentage")
    plugged = str(data.get("plugged", "")).upper()
    status = str(data.get("status", "")).upper()
    charging = ("CHARG" in status) or (plugged not in ("UNPLUGGED", "", "NONE"))
    line = "Battery %s%% hai, %s" % (pct, "charging par hai" if charging else "charging par nahi hai")
    if data.get("temperature") not in (None, "?"):
        line += ", temperature %s C" % data.get("temperature")
    return line


def t_torch(a):
    state = "on" if str(a.get("on", True)).lower() not in ("false", "0", "off") else "off"
    ok, out = termux("termux-torch", state)
    return "Torch %s" % state if ok else "Torch nahi chala: %s" % out


def t_volume(a):
    level = max(0, min(15, int(a.get("level", 8))))
    ok, out = termux("termux-volume", "music", str(level))
    return "Volume %d/15" % level if ok else "Volume nahi badla: %s" % out


def t_open_app(a):
    pkg = str(a.get("package", "")).strip()
    if not pkg:
        return "Package name chahiye (jaise com.whatsapp)"
    if STUB:
        return "opened " + pkg
    if have("monkey"):
        ok, out = termux("monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1", timeout=20)
        if ok and "No activities found" not in out:
            return "%s khol diya" % pkg
    ok, out = termux("am", "start", "-n", pkg + "/.MainActivity", timeout=20)
    if ok:
        return "%s khol diya" % pkg
    return "%s nahi khula. Package name check karo." % pkg


def t_notify(a):
    title = str(a.get("title", "Jarvis"))
    body = str(a.get("text", a.get("body", "")))
    ok, out = termux("termux-notification", "--title", title, "--content", body)
    return "Notification bhej di" if ok else "Notification fail: %s" % out


def t_vibrate(a):
    ms = int(a.get("ms", 400))
    ok, out = termux("termux-vibrate", "-d", str(ms), "-f")
    return "Vibrate" if ok else "Vibrate fail: %s" % out


def t_clipboard_set(a):
    ok, out = termux("termux-clipboard-set", str(a.get("text", "")), timeout=15)
    return "Clipboard me daal diya" if ok else "Clipboard fail: %s" % out


def t_clipboard_get(a):
    ok, out = termux("termux-clipboard-get", timeout=15)
    return out if ok else "Clipboard nahi padha: %s" % out


def t_location(a):
    data, err = termux_json("termux-location", "-p", "network", timeout=40)
    if not data:
        return "Location nahi mili: %s" % err
    return "Latitude %s, Longitude %s" % (data.get("latitude"), data.get("longitude"))


def t_photo(a):
    path = os.path.join(HOME, "storage", "pictures", "jarvis_%s.jpg" %
                        datetime.now().strftime("%H%M%S"))
    ok, out = termux("termux-camera-photo", "-c", str(a.get("camera", 0)), path, timeout=40)
    return "Photo: %s" % path if ok else "Camera fail: %s" % out


def t_look(a):
    """Camera se dekho aur Gemini se Hinglish me batao (Mark-LVI ka vision, phone par)."""
    path = os.path.join(HOME, "storage", "pictures",
                        "look_%s.jpg" % datetime.now().strftime("%H%M%S"))
    ok, out = termux("termux-camera-photo", "-c", "0", path, timeout=45)
    if not ok:
        return "Camera nahi chala: %s" % out
    key = load_key()
    if not key:
        return "Photo le li (%s), par dekhne ke liye Gemini key chahiye" % path
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return "Photo padhi nahi ja saki"
    cfg = load_config()
    payload = {"contents": [{"role": "user", "parts": [
        {"text": "Is photo me kya hai? Hinglish me ek chhoti line me batao (max 20 words). "
                 "Agar photo me text likha hai to use padh kar batao."},
        {"inlineData": {"mimeType": "image/jpeg", "data": b64}}]}]}
    model = pick_model(key, cfg)
    resp = api_call("/models/%s:generateContent" % model, payload, key=key, timeout=120)
    if "_error" in resp:
        return "Dekh nahi paya: %s" % resp["_error"]
    txt = strip_markdown(model_text(resp))
    return txt or "Photo me kuch samajh nahi aaya"


def t_open_url(a):
    url = str(a.get("url", "")).strip()
    if not url.startswith(("http://", "https://", "mailto:", "tel:")):
        return "URL theek nahi hai"
    ok, out = termux("termux-open-url", url, timeout=15)
    return "Khol diya: %s" % url if ok else "URL nahi khula: %s" % out


def t_wifi(a):
    data, err = termux_json("termux-wifi-connectioninfo", timeout=20)
    if not data:
        return "WiFi info nahi mili: %s" % err
    return "WiFi: %s, IP %s, %s Mbps" % (data.get("ssid", "?"), data.get("ip", "?"),
                                         data.get("link_speed_mbps", "?"))


def t_sms(a):
    number = str(a.get("number", "")).strip()
    text = str(a.get("text", ""))
    if not number or not text:
        return "Number aur text dono chahiye"
    if STUB:
        return "sms stub"
    ok, out = termux("termux-sms-send", "-n", number, text, timeout=30)
    return "SMS bhej diya %s ko" % number if ok else "SMS fail: %s" % out


def t_call(a):
    number = str(a.get("number", "")).strip()
    if not number:
        return "Number chahiye"
    if STUB:
        return "call stub"
    ok, out = termux("termux-telephony-call", number, timeout=20)
    return "Call lagaya %s" % number if ok else "Call fail: %s" % out


def t_remember(a):
    fact = str(a.get("fact", "")).strip()
    if not fact:
        return "Yaad rakhne ke liye kuch nahi mila"
    mem = load_memory()
    mem["facts"].append(fact)
    mem["facts"] = mem["facts"][-200:]
    save_memory(mem)
    return "Yaad rakh liya"


def t_note_add(a):
    text = str(a.get("text", "")).strip()
    if not text:
        return "Note khaali hai"
    mem = load_memory()
    mem["notes"].append({"at": datetime.now().strftime("%d-%m-%Y %H:%M"), "text": text})
    mem["notes"] = mem["notes"][-300:]
    save_memory(mem)
    return "Note save ho gaya"


def t_note_list(a):
    mem = load_memory()
    notes = mem["notes"][-int(a.get("count", 5)):]
    if not notes:
        return "Koi note nahi hai"
    return " | ".join("%s: %s" % (n.get("at", ""), n.get("text", "")) for n in notes)


_DAYS = {"Monday": "Somwar", "Tuesday": "Mangalwar", "Wednesday": "Budhwar",
         "Thursday": "Guruwar", "Friday": "Shukrawar", "Saturday": "Shaniwar",
         "Sunday": "Ravivar"}


def t_time(a):
    now = datetime.now()
    h = now.hour
    period = "subah" if h < 12 else ("dopahar" if h < 17 else ("shaam" if h < 21 else "raat"))
    clock = now.strftime("%I:%M").lstrip("0")
    return "Abhi %s, %s, %s %s baje hain" % (
        _DAYS.get(now.strftime("%A"), now.strftime("%A")), now.strftime("%d %B %Y"), period, clock)


def t_self_edit(a):
    req = str(a.get("request") or a.get("text") or a.get("what") or "").strip()
    if not req:
        return "Kya badalna hai? Saaf bolo."
    cfg = load_config()
    ok_r, msg = self_request(req, cfg, load_key(), confirm=True)
    return ("Code update ho gaya: " if ok_r else "Nahi ho paya: ") + msg


def t_diagnose(a):
    deep = bool(a.get("deep"))
    txt, n = diagnose(load_config(), deep=deep)
    return txt


def t_research(a):
    q = str(a.get("query") or a.get("text") or "").strip()
    if not q:
        return "Kya research karna hai?"
    cfg = load_config()
    ans, used = research(q, cfg, load_key())
    if used:
        ans += " (sources: %s)" % ", ".join(h["url"] for h in used[:3])
    return ans


TOOLS = {
    "battery": t_battery,
    "torch": t_torch,
    "volume": t_volume,
    "open_app": t_open_app,
    "notify": t_notify,
    "vibrate": t_vibrate,
    "clipboard_set": t_clipboard_set,
    "clipboard_get": t_clipboard_get,
    "location": t_location,
    "photo": t_photo,
    "open_url": t_open_url,
    "wifi": t_wifi,
    "sms": t_sms,
    "call": t_call,
    "remember": t_remember,
    "note_add": t_note_add,
    "note_list": t_note_list,
    "time": t_time,
    "look": t_look,
    "research": t_research,
    "self_edit": t_self_edit,
    "diagnose": t_diagnose,
    "gh_repos": t_gh_repos,
    "gh_upload": t_gh_upload,
    "app_stop": t_app_stop,
    "app_info": t_app_info,
    "app_start": t_app_start,
    "key": t_key,
    "media": t_media,
    "tap": t_tap,
    "screen": t_screen,
    "screenshot": t_screenshot,
}

RISKY = {"sms", "call"}

TOOL_HELP = """Available tools (JSON me "do" list ke andar):
  {"tool":"battery"}
  {"tool":"torch","args":{"on":true}}
  {"tool":"volume","args":{"level":0-15}}
  {"tool":"open_app","args":{"package":"com.whatsapp"}}
  {"tool":"notify","args":{"title":"...","text":"..."}}
  {"tool":"vibrate","args":{"ms":400}}
  {"tool":"clipboard_set","args":{"text":"..."}} | {"tool":"clipboard_get"}
  {"tool":"location"} | {"tool":"photo","args":{"camera":0}} | {"tool":"wifi"}
  {"tool":"open_url","args":{"url":"https://..."}}
  {"tool":"sms","args":{"number":"+91...","text":"..."}}   (user confirm karega)
  {"tool":"call","args":{"number":"+91..."}}              (user confirm karega)
  {"tool":"remember","args":{"fact":"..."}}
  {"tool":"note_add","args":{"text":"..."}} | {"tool":"note_list","args":{"count":5}}
  {"tool":"time"}
  {"tool":"look"}          (camera se dekho aur batao)
  {"tool":"research","args":{"query":"..."}}   (internet se source ke saath jawab)
  {"tool":"self_edit","args":{"request":"kya badalna hai"}}   (apna code khud badalna)
  {"tool":"diagnose"}   (apna system check karke dikkat batao)
  {"tool":"gh_repos"} | {"tool":"gh_upload","args":{"repo":"user/repo","path":"a.txt","file":"/path"}}
  {"tool":"app_stop","args":{"app":"youtube"}}  | {"tool":"app_start","args":{"app":"whatsapp"}}
  {"tool":"media","args":{"action":"pause|play|next|prev|toggle"}} | {"tool":"key","args":{"key":"back|home|volume_up"}}
  {"tool":"screen"} (screen par kya likha hai) | {"tool":"tap","args":{"x":540,"y":1200}}"""


def run_tool(name, args, cfg):
    fn = TOOLS.get(name)
    if not fn:
        return "Aisa koi tool nahi hai: %s" % name
    if name in RISKY and cfg.get("confirm_risky", True) and not STUB:
        speak("Confirm chahiye: %s bhejna hai?" % name, cfg)
        try:
            ans = input("  [y/n] > ").strip().lower()
        except EOFError:
            ans = "n"
        if not ans.startswith("y"):
            return "User ne cancel kar diya"
    try:
        result = fn(args or {})
    except Exception as exc:  # tool kabhi poora loop na tode
        result = "Tool error: %s" % exc
    log("tool %s -> %s" % (name, str(result)[:160]))
    return str(result)


# ----------------------------------------------------------------------------
# Gemini
# ----------------------------------------------------------------------------

def api_call(path, payload=None, key="", timeout=90):
    if STUB:
        return {"candidates": [{"content": {"parts": [{"text": '{"say":"stub reply"}'}]}}]}
    url = API_ROOT + path
    data = None
    headers = {"x-goog-api-key": key, "Content-Type": "application/json", "User-Agent": UA}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "ignore")[:400]
        except Exception:
            pass
        return {"_error": "HTTP %s" % exc.code, "_body": body}
    except urllib.error.URLError as exc:
        return {"_error": "network: %s" % exc.reason}
    except (TimeoutError, OSError) as exc:
        return {"_error": "timeout: %s" % exc}
    except Exception as exc:
        return {"_error": "request fail: %s" % exc}


def load_provider_key(name):
    """Gemini ke alawa doosre providers ki key (file ya env)."""
    env = {"groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY",
           "mistral": "MISTRAL_API_KEY", "cerebras": "CEREBRAS_API_KEY"}.get(name)
    if env and os.environ.get(env):
        return os.environ[env].strip()
    path = os.path.join(JARVIS_DIR, "%s.txt" % name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


OPENAI_COMPAT = {
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "groq_model"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "openrouter_model"),
    "mistral": ("https://api.mistral.ai/v1/chat/completions", "mistral_model"),
}


PROVIDER_ERR = {}
PROVIDER_COOL = {}   # provider -> unix time tak skip
TTS_COOL = {"until": 0, "told": False}
LAST_PROVIDER = {"name": "", "trace": []}


def provider_models(provider, key, timeout=30):
    """Provider ke available model naam (groq/openrouter)."""
    base = {"groq": "https://api.groq.com/openai/v1/models",
            "openrouter": "https://openrouter.ai/api/v1/models",
            "mistral": "https://api.mistral.ai/v1/models"}[provider]
    req = urllib.request.Request(base, headers={"Authorization": "Bearer %s" % key, "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
        return [m.get("id", "") for m in (data.get("data") or []) if m.get("id")]
    except Exception as exc:
        PROVIDER_ERR[provider] = "models list: %s" % exc
        return []


def pick_groq_model(cfg, key):
    """Groq purane model retire kar deta hai - available list se chuno."""
    ids = provider_models("groq", key)
    if not ids:
        return cfg.get("groq_model", "")
    bad = ("whisper", "tts", "guard", "embed", "vision", "audio")
    chat = [i for i in ids if not any(b in i.lower() for b in bad)]
    prefs = ("llama-3.1-8b-instant", "llama-3.3-70b-versatile", "llama3-8b",
             "gemma2-9b", "mixtral") if cfg.get("speed") == "fast" else \
            ("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-70b",
             "mixtral", "gemma2", "qwen")
    for pref in prefs:
        for i in chat:
            if pref in i:
                cfg["groq_model"] = i
                save_config(cfg)
                return i
    if chat:
        cfg["groq_model"] = chat[0]
        save_config(cfg)
        return chat[0]
    return cfg.get("groq_model", "")


def pick_openrouter_model(cfg, key):
    """OpenRouter ke free models me se ek chuno."""
    ids = provider_models("openrouter", key)
    free = [i for i in ids if i.endswith(":free")]
    if not free:
        return cfg.get("openrouter_model", "")
    for pref in ("llama-3.3-70b", "qwen", "gemma", "mistral", "deepseek"):
        for i in free:
            if pref in i.lower():
                cfg["openrouter_model"] = i
                save_config(cfg)
                return i
    cfg["openrouter_model"] = free[0]
    save_config(cfg)
    return free[0]


def openrouter_try(cfg, key, messages):
    """429/404 par doosre free model par switch karke dobara try."""
    txt = openai_chat("openrouter", messages, cfg, key)
    if txt:
        return txt
    err = PROVIDER_ERR.get("openrouter", "")
    if not any(c in err for c in ("429", "404", "502", "503")):
        return ""
    tried = [cfg.get("openrouter_model", "")]
    ids = [i for i in provider_models("openrouter", key) if i.endswith(":free")]
    for mid in ids:
        if mid in tried:
            continue
        cfg["openrouter_model"] = mid
        save_config(cfg)
        txt = openai_chat("openrouter", messages, cfg, key)
        if txt:
            log("openrouter switched to %s" % mid)
            return txt
        tried.append(mid)
        if len(tried) >= 4:
            break
    return ""


def openai_chat(provider, messages, cfg, key, timeout=None):
    """Groq / OpenRouter / Mistral - sab OpenAI jaisa hi hai. Error PROVIDER_ERR me."""
    url, model_key = OPENAI_COMPAT[provider]
    model = cfg.get(model_key) or {
        "groq": "llama-3.3-70b-versatile",
        "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
        "mistral": "mistral-small-latest",
    }[provider]
    payload = {"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 400}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": UA,
                                          "Authorization": "Bearer %s" % key})
    try:
        with urllib.request.urlopen(req, timeout=timeout or int(cfg.get("provider_timeout", 45))) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "") or ""
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "ignore")[:220]
        except Exception:
            pass
        PROVIDER_ERR[provider] = "HTTP %s (model=%s) %s" % (exc.code, model, body.replace("\n", " "))
        log("%s fail: %s" % (provider, PROVIDER_ERR[provider]))
        return ""
    except Exception as exc:
        PROVIDER_ERR[provider] = "%s (model=%s)" % (exc, model)
        log("%s fail: %s" % (provider, exc))
        return ""


def list_models(key):
    data = api_call("/models?pageSize=200", key=key, timeout=45)
    if "_error" in data:
        return [], data
    out = []
    for m in data.get("models", []):
        methods = m.get("supportedGenerationMethods") or m.get("supportedActions") or []
        if "generateContent" in methods:
            name = m.get("name", "").replace("models/", "")
            out.append(name)
    return out, data


def pick_model(key, cfg):
    if cfg.get("model"):
        return cfg["model"]
    models, _ = list_models(key)
    if not models:
        return "gemini-2.5-flash"
    def score(n):
        n = n.lower()
        s = 0
        if "flash" in n:
            s += 50
        if "live" in n or "tts" in n or "embedding" in n or "image" in n:
            s -= 100
        if "pro" in n:
            s += 10
        if "latest" in n:
            s += 5
        nums = re.findall(r"\d+\.\d+", n)
        if nums:
            s += float(nums[0])
        return s
    ranked = sorted(models, key=score, reverse=True)
    chosen = ranked[0]
    cfg["model"] = chosen
    save_config(cfg)
    log("model auto-picked: %s" % chosen)
    return chosen


LANG_LINE = {
    "hinglish": "Reply in Hinglish (Hindi in Roman script) - warm, spoken style, like a close friend talking. Max 2 short lines. Use commas for natural pauses. Never sound like a manual.",
    "hi": "Reply in Hindi (Devanagari), short and natural.",
    "en": "Reply in simple English, short and natural.",
}


PERSONA_FILE = os.path.join(JARVIS_DIR, "persona.txt")
SERVE_MODE = {"on": False}


def system_prompt(cfg, mem):
    name = cfg.get("name", "Jarvis")
    user = cfg.get("user_name", "Boss")
    facts = mem.get("facts", [])[-25:]
    notes = mem.get("notes", [])[-8:]
    extra = ""
    try:
        with open(PERSONA_FILE, "r", encoding="utf-8") as f:
            extra = f.read().strip()[:1500]
    except OSError:
        extra = ""
    lang = LANG_LINE.get(cfg.get("language", "hinglish"), LANG_LINE["hinglish"])

    return """Tum {name} ho - {user} ki personal assistant, uske apne Android phone me rehti ho.
Insaan ki tarah baat karti ho, robot jaisa nahi. Ladki ho, dost jaisi - apnapan, halka humour, emotion.

{lang}

BAAT: 2 line, 35 shabd max. Empathy, chhoti reactions ("arre wah", "hmm", "acha"), kabhi follow-up sawaal.
Koi bullet, markdown, emoji nahi - sirf bolne wali baat. Jhooth nahi - nahi pata to bolo "ye mujhe nahi pata Boss".

TAQATEIN (kabhi "nahi kar sakti" mat bolo): phone control (battery, torch, volume, app band/chalu,
media, back/home, tap, screen, screenshot, notification, clipboard, wifi, location, photo, SMS, call),
yaad rakhna, research (source ke saath), app banana, apna code khud badalna (self_edit),
briefing, GitHub, aur diagnose (apni dikkat khud dekhna - "sun nahi rahe"/"problem" par chalao).

KAAM: kaam bole to tool chalao, sirf baat mat karo. Jawab sirf is JSON me:
{{"say": "jo bolna hai", "do": [{{"tool": "naam", "args": {{}}}}]}}
- "say" = bolo jaane wala text, chhota, bina markdown.
- "do" = asli kaam; warna [].
- Tool ka sach result aane ke baad hi "ho gaya" bolo.

{tools}

{user} ke baare me: {facts}
Notes: {notes}
{brain}
{mode}
{extra}
""".format(name=name, user=user, lang=lang, tools=TOOL_HELP,
           facts=("; ".join(facts) if facts else "abhi kuch nahi"),
           notes=("; ".join("%s %s" % (n.get("at", ""), n.get("text", "")) for n in notes) if notes else "koi nahi"),
           brain=brain_summary(cfg),
           mode=("AAPKI AWAAZ HAI: aap jo 'say' likhti ho wo phone TTS ya Gemini voice se bol kar sunaya jata hai. "
                 "Kabhi mat kaho ki 'main text hoon', 'awaaz nahi de sakti' ya 'awaaz ka code nahi hai' - "
                 "aap bol sakti ho. Phone ke hardware tools (battery, torch, app) bhi aapke paas hain. "
                 + ("Aap browser panel me ho, awaaz browser bajata hai." if SERVE_MODE["on"] else "")),
           extra=("\nExtra persona:\n" + extra) if extra else "")


def extract_json(text):
    """Model kabhi kabhi fence ya extra text bhej deta hai - usse nikaalo."""
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start:i + 1]
                    try:
                        return json.loads(chunk)
                    except ValueError:
                        break
        start = text.find("{", start + 1)
    return None


def model_text(resp):
    try:
        parts = resp["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return ""
    out = []
    for p in parts:
        if isinstance(p, dict) and p.get("text"):
            out.append(p["text"])
    return "\n".join(out).strip()


def ask_messages(cfg, mem, user_text, extra=None):
    """Kisi bhi provider ke liye system + history + user."""
    msgs = [{"role": "system", "content": system_prompt(cfg, mem)}]
    for turn in mem.get("history", [])[-int(cfg.get("max_history", 8)):]:
        msgs.append({"role": "assistant" if turn.get("role") == "model" else "user",
                     "content": str(turn.get("text", ""))[:600]})
    msgs.append({"role": "user", "content": user_text})
    if extra:
        msgs.append({"role": "user", "content": extra})
    return msgs


def data_context(query, cfg, k=None):
    """Vault se relevant hisse - har provider ke liye (source ke saath)."""
    if not query:
        return ""
    try:
        chunks, _n, _c = build_index(cfg)
        picked = retrieve(query, chunks, int(k or cfg.get("rag_top", 4)))
    except Exception as exc:
        log("data_context fail: %s" % exc)
        return ""
    if not picked:
        return ""
    lines = []
    for c in picked:
        lines.append("[%s] %s" % (c.get("file", "?"), c.get("text", "")[:700]))
    return ("USER KE APNE DATA SE (sirf inhi par bharosa karo, source naam ke saath bolo):\n"
            + "\n---\n".join(lines))


def ask_remote(cfg, mem, user_part, key, extra=None):
    """Gemini -> Groq -> OpenRouter -> local, jo pehle chale."""
    order = [p.strip() for p in str(cfg.get("providers",
             "gemini,groq,openrouter,local")).split(",") if p.strip()]
    text_part = user_part if isinstance(user_part, str) else ""
    dctx = data_context(text_part, cfg)
    if dctx:
        extra = (extra + "\n\n" + dctx) if extra else dctx
    last_err = ""
    LAST_PROVIDER["trace"] = []
    now_t = time.time()
    active = [p for p in order if PROVIDER_COOL.get(p, 0) < now_t]
    if not active:
        PROVIDER_COOL.clear()
        active = order
    for prov in active:
        t_prov = time.time()
        try:
            if prov == "local":
                res = ask_local(cfg, mem, user_part, extra)
                if isinstance(res, dict) and res.get("say"):
                    LAST_PROVIDER["name"] = "local"
                    return res
                last_err = "local: jawab nahi mila"
                continue
            if prov == "gemini":
                if not key:
                    continue
                plan = ask_gemini(cfg, mem, user_part, key, extra)
            elif prov in OPENAI_COMPAT:
                pkey = load_provider_key(prov)
                if not pkey:
                    continue
                if not text_part:
                    continue
                msgs = ask_messages(cfg, mem, text_part, extra)
                raw = openai_chat(prov, msgs, cfg, pkey)
                if not raw and "timed out" in PROVIDER_ERR.get(prov, ""):
                    raw = openai_chat(prov, msgs, cfg, pkey)
                if not raw and prov == "groq":
                    ids = [i for i in provider_models("groq", pkey)
                           if not any(b in i.lower() for b in ("whisper", "tts", "guard", "embed"))]
                    tried = [cfg.get("groq_model", "")]
                    for mid in ids[:4]:
                        if mid in tried:
                            continue
                        cfg["groq_model"] = mid
                        save_config(cfg)
                        raw = openai_chat(prov, msgs, cfg, pkey)
                        if raw:
                            log("groq switched to %s" % mid)
                            break
                        tried.append(mid)
                if not raw and prov == "openrouter":
                    if pick_openrouter_model(cfg, pkey):
                        raw = openrouter_try(cfg, pkey, msgs)
                plan = extract_json(raw) if raw else None
                if not isinstance(plan, dict) and raw:
                    plan = {"say": strip_markdown(raw)[:400], "do": []}
            else:
                continue
            if isinstance(plan, dict) and plan.get("say"):
                plan.setdefault("do", [])
                LAST_PROVIDER["trace"].append((prov, time.time() - t_prov, "ok"))
                LAST_PROVIDER["name"] = prov
                log("answered by %s" % prov)
                return plan
            last_err = "%s: khaali jawab" % prov
            err_txt = PROVIDER_ERR.get(prov, "")
            if "404" in err_txt:
                PROVIDER_COOL[prov] = time.time() + 1800   # model hi nahi hai - 30 min
            elif "429" in err_txt:
                PROVIDER_COOL[prov] = time.time() + 600    # rate limit - 10 min
            else:
                PROVIDER_COOL[prov] = time.time() + 180
            LAST_PROVIDER["trace"].append((prov, time.time() - t_prov, "khaali"))
        except Exception as exc:
            last_err = "%s: %s" % (prov, exc)
            LAST_PROVIDER["trace"].append((prov, time.time() - t_prov, "fail"))
            log("provider %s fail: %s" % (prov, exc))
    # aakhri raasta: open web se jawab (koi API nahi)
    txt, used = web_fallback(text_part)
    if txt:
        LAST_PROVIDER["name"] = "web"
        say = "Internet se mila Boss: " + txt
        if used:
            say += " (source: %s)" % used[0]["url"][:80]
        return {"say": say[:700], "do": []}
    return {"say": "Sabhi brain fail ho gaye (%s). Doctor chalao: python jarvis.py --doctor"
                   % (last_err or "koi provider available nahi"), "do": []}


def ask_model(cfg, mem, user_part, key, extra=None):
    """Ek turn: user_part (text ya inline audio) -> model JSON."""
    if cfg.get("brain") == "local":
        return ask_local(cfg, mem, user_part, extra)
    return ask_remote(cfg, mem, user_part, key, extra)


def ask_gemini(cfg, mem, user_part, key, extra=None):
    contents = []
    for turn in mem.get("history", [])[-int(cfg.get("max_history", 8)):]:
        role = "user" if turn.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": str(turn.get("text", ""))}]})
    if isinstance(user_part, str):
        contents.append({"role": "user", "parts": [{"text": user_part}]})
    else:
        contents.append({"role": "user", "parts": [user_part]})
    if extra:
        contents.append({"role": "user", "parts": [{"text": extra}]})

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt(cfg, mem)}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.65,
            "maxOutputTokens": 300,
            "responseMimeType": "application/json",
        },
    }
    model = pick_model(key, cfg)
    gtimeout = int(cfg.get("provider_timeout", 25))
    resp = api_call("/models/%s:generateContent" % model, payload, key=key, timeout=gtimeout)
    if "_error" in resp and "503" in str(resp.get("_error", "")):
        time.sleep(1)
        resp = api_call("/models/%s:generateContent" % model, payload, key=key, timeout=gtimeout)
    if "_error" in resp:
        # model purana ho gaya ho sakta hai - dobara chuno
        cfg["model"] = ""
        save_config(cfg)
        model = pick_model(key, cfg)
        resp = api_call("/models/%s:generateContent" % model, payload, key=key)
    if "_error" in resp:
        return None
    return extract_json(model_text(resp)) or {"say": strip_markdown(model_text(resp))[:300], "do": []}


def briefing(cfg, mem, key):
    """Subah ki chhoti briefing - Mark-LVI ka Morning Briefing, phone ke hisaab se."""
    now = datetime.now()
    facts = "; ".join(mem.get("facts", [])[-8:]) or "kuch nahi"
    notes = "; ".join(n.get("text", "") for n in mem.get("notes", [])[-4:]) or "koi note nahi"
    ask = ("Aaj %s, %s. User: %s. Purani yaadein: %s. Recent notes: %s. "
           "Ek chhoti Hinglish briefing do - 2 line max: aaj ka din kaisa hai aur ek cheez "
           "jo dhyaan rakhni chahiye. Sirf bolne wali baat likho." % (
               now.strftime("%d %B %Y"), now.strftime("%A"), cfg.get("user_name", "Boss"),
               facts, notes))
    if cfg.get("brain") == "local":
        ok, msg = start_llama(cfg)
        if not ok:
            return "Subah bakhair %s. Local brain taiyar nahi: %s" % (cfg.get("user_name", "Boss"), msg)
        raw = local_chat([{"role": "system", "content": local_prompt(cfg, mem, "")},
                          {"role": "user", "content": ask}], cfg)
        say = strip_markdown(raw or "").strip()
    else:
        if not key:
            return "Subah bakhair %s. Gemini key nahi hai - setup.sh chalao." % cfg.get("user_name", "Boss")
        payload = {"contents": [{"role": "user", "parts": [{"text": ask}]}],
                   "generationConfig": {"temperature": 0.7, "maxOutputTokens": 200}}
        resp = api_call("/models/%s:generateContent" % pick_model(key, cfg), payload, key=key)
        say = strip_markdown(model_text(resp)) if "_error" not in resp else ""
    if not say:
        say = "Subah bakhair %s. Aaj ka din shubh ho." % cfg.get("user_name", "Boss")
    return say


SELF_INTENT = ("apna code", "apne code", "khud ko modify", "khud ko theek", "khud ko update",
               "code me badal", "code me add", "code me theek", "khud ko sudhar", "apne aap ko theek",
               "apne function", "apne features", "function add", "feature add", "naya function",
               "naya feature", "apni memory", "khud me add", "apne andar add", "khud ko upgrade",
               "apne aap ko upgrade", "apni capability", "apni power",
               "technology builder", "khud ko capable", "apne aap ko capable",
               "apne andar", "naya tool", "tool add", "khud ko behtar")


def is_self_intent(text):
    t = (text or "").lower()
    return any(k in t for k in SELF_INTENT)


def handle_turn(user_part, cfg, mem, key, heard_text=""):
    t0 = time.time()
    if isinstance(user_part, str) and is_self_intent(user_part):
        ok, msg = self_request(user_part, cfg, key, confirm=True)
        say = ("Theek kar diya Boss. " if ok else "Nahi kar paya Boss. ") + msg
        print("  [%.1f second]" % (time.time() - t0))
        speak(say, cfg)
        mem["history"].append({"role": "user", "text": user_part})
        mem["history"].append({"role": "model", "text": say})
        save_memory(mem)
        return say
    plan = ask_model(cfg, mem, user_part, key)
    say = strip_markdown(str(plan.get("say", "")))
    actions = plan.get("do") or plan.get("actions") or []
    if not isinstance(actions, list):
        actions = []

    if actions:
        if say:
            speak(say, cfg)
        results = []
        for act in actions[:4]:
            if not isinstance(act, dict):
                continue
            name = str(act.get("tool", "")).strip()
            args = act.get("args") or {}
            if not isinstance(args, dict):
                args = {}
            results.append("%s -> %s" % (name, run_tool(name, args, cfg)))
        result_text = "Tool results (real, just executed):\n" + "\n".join(results)
        final = ask_model(cfg, mem, user_part, key, extra=result_text)
        final_say = strip_markdown(str(final.get("say", "")))
        if final_say:
            say = final_say
            if cfg.get("speak_actions", True):
                speak(final_say, cfg)
    elif say:
        speak(say, cfg)

    total = time.time() - t0
    print("  [%.1f second | %s]" % (total, LAST_PROVIDER["name"] or "?"))
    trace = LAST_PROVIDER.get("trace") or []
    if len(trace) > 1 or (trace and trace[0][2] != "ok"):
        print("  (%s)" % " -> ".join("%s %.1fs %s" % (p, d, st) for p, d, st in trace))
    try:
        learn_from_turn(heard_text or "", say, cfg)
    except Exception as exc:
        log("learn fail: %s" % exc)
    mem["history"].append({"role": "user", "text": heard_text or "[voice]"})
    mem["history"].append({"role": "model", "text": say})
    mem["history"] = mem["history"][-40:]
    save_memory(mem)
    return say


# ----------------------------------------------------------------------------
# Modes
# ----------------------------------------------------------------------------

def doctor(cfg):
    print("JARVIS doctor - v%s\n" % VERSION)
    problems = 0
    checks = []
    for cmd, why in (("termux-tts-speak", "bolne ke liye"),
                     ("termux-speech-to-text", "sunne ke liye"),
                     ("termux-microphone-record", "audio mode ke liye"),
                     ("termux-battery-status", "phone tools")):
        ok = have(cmd)
        checks.append(("  %-26s %s" % (cmd, "OK" if ok else "MISSING"), why))
        if not ok and cmd != "termux-microphone-record":
            problems += 1
    brain = cfg.get("brain", "gemini")
    key = load_key()
    if brain == "local":
        model = local_model_path(cfg)
        exists = os.path.exists(model)
        size = "%.2f GB" % (os.path.getsize(model) / 1e9) if exists else "-"
        checks.append(("  %-26s %s" % ("local model", "OK" if exists else "MISSING"),
                       "%s, %s" % (os.path.basename(model), size)))
        if not exists:
            problems += 1
        ver_ok, ver_txt = False, ""
        if have("llama-server") or have("llamafile"):
            try:
                proc = subprocess.run(["llama-server", "--version"], capture_output=True,
                                      text=True, timeout=25)
                ver_txt = ((proc.stdout or "") + (proc.stderr or "")).strip()
                ver_ok = proc.returncode == 0 and "CANNOT LINK" not in ver_txt
            except Exception:
                ver_ok = False
        state = "OK" if ver_ok else ("BROKEN" if have("llama-server") else "MISSING")
        checks.append(("  %-26s %s" % ("llama-server", state),
                       "chal raha hai" if ver_ok else "fix: bash setup_local.sh --build"))
        if not ver_ok:
            problems += 1
        d = data_dir(cfg)
        chunks, nfiles, _ = build_index(cfg)
        checks.append(("  %-26s %s" % ("aapka data", "OK" if chunks else "KHAALI"),
                       "%s (%d file, %d hisse)" % (d, nfiles, len(chunks))))
        checks.append(("  %-26s %s" % ("Gemini API key", "optional"), "local brain me zarurat nahi"))
    else:
        checks.append(("  %-26s %s" % ("Gemini API key", "optional" if brain == "local" else ("OK" if key else "MISSING")),
                       "local brain me zarurat nahi" if brain == "local" else "aistudio.google.com/apikey"))
        if not key and brain != "local":
            problems += 1
    for line, why in checks:
        print("%s  (%s)" % (line, why))
    if key and brain != "local":
        models, raw = list_models(key)
        if "_error" in raw:
            print("\n  API check FAIL: %s" % raw["_error"])
            print("  (key galat ya adhoori hai - local brain par isse farak nahi padta)")
            problems += 1
        else:
            print("\n  API OK. %d models available." % len(models))
            print("  Selected model: %s" % pick_model(key, cfg))
    elif brain == "local":
        print("\n  Gemini API check skip - aap local brain par ho (key ki zarurat nahi).")
    print("\n  Config : %s" % CONFIG_PATH)
    print("  Memory : %s (%d facts, %d notes)" % (MEMORY_PATH, len(load_memory()["facts"]),
                                                  len(load_memory()["notes"])))
    try:
        adb_ok, adb_msg = adb_ready(cfg)
    except Exception:
        adb_ok, adb_msg = False, "?"
    print("  Phone control: %s (%s)" % ("ADB ready" if adb_ok else "nahi", str(adb_msg)[:40]))
    print("  Voice  : %s (tts=%s, pitch=%s)" % (cfg.get("gemini_voice"), cfg.get("tts"), cfg.get("voice_pitch")))
    order = [x.strip() for x in str(cfg.get("providers", "gemini,groq,openrouter,local")).split(",") if x.strip()]
    print("  Brain chain: %s" % " -> ".join(order))
    for prov in order:
        if prov == "local":
            print("    %-12s %s" % ("local", "ready" if find_server(cfg) else "engine nahi mila"))
        elif prov == "gemini":
            print("    %-12s %s" % ("gemini", "key saved" if load_key() else "key nahi hai"))
        else:
            print("    %-12s %s" % (prov, "key saved" if load_provider_key(prov) else "key nahi hai (free)"))
    print("  Log    : %s" % LOG_PATH)
    if brain == "local":
        srv = find_server(cfg)
        ok_v, ver = server_version(srv)
        print("  llama-server: %s" % (ver.splitlines()[0][:70] if ver else ("nahi mila" if not srv else "?")))
        if not ok_v and srv:
            tail = llama_tail(2)
            if tail:
                print("  last llama log: %s" % tail[:200])
    if problems:
        print("\n%d cheez theek karni hai - upar dekho ya guide ka troubleshooting section." % problems)
        return 1
    print("\nSab theek. Ab: python jarvis.py")
    return 0


def diagnose(cfg=None, deep=False):
    """Apne system ko dekho aur saaf batao kya dikkat hai. (text, problem_count)"""
    cfg = cfg or load_config()
    lines, problems = [], 0

    def ok(name, good, detail="", fix=""):
        nonlocal problems
        mark = "OK  " if good else "DIKKAT"
        lines.append("%-14s %s%s" % (name, mark, (" - " + detail) if detail else ""))
        if not good:
            problems += 1
            if fix:
                lines.append("               fix: " + fix)

    ok("python", True, platform.python_version())
    cmds = ("termux-tts-speak", "termux-speech-to-text", "termux-microphone-record",
            "termux-battery-status", "termux-notification")
    missing = [c for c in cmds if not have(c)]
    ok("termux-api", not missing, "sab mil gaye" if not missing else "missing: " + ", ".join(missing),
       "pkg install -y termux-api (aur F-Droid se Termux:API app)")

    # mic test
    mic_ok, mic_detail = False, ""
    if have("termux-microphone-record"):
        test = os.path.join(JARVIS_DIR, "mic_test.m4a")
        try:
            if os.path.exists(test):
                os.remove(test)
            termux("termux-microphone-record", "-f", test, "-l", "2", "-e", "aac", timeout=25)
            time.sleep(0.5)
            size = os.path.getsize(test) if os.path.exists(test) else 0
            mic_ok = size > 2000
            mic_detail = "%d bytes" % size
        except Exception as exc:
            mic_detail = str(exc)[:40]
    ok("mic (record)", mic_ok, mic_detail,
       "Settings > Apps > Termux:API > Permissions > Microphone > Allow")

    ok("stt (sunna)", have("termux-speech-to-text"), "",
       "pkg install -y termux-api")

    # keys
    for prov, keyv in (("gemini", load_key()), ("groq", load_provider_key("groq")),
                       ("openrouter", load_provider_key("openrouter")),
                       ("github", gh_token())):
        ok("key " + prov, bool(keyv), ("%d bytes" % len(keyv)) if keyv else "nahi hai",
           "python jarvis.py --setkey " + prov)

    # providers reachable (fast)
    if deep:
        gkey = load_key()
        if gkey:
            t0 = time.time()
            try:
                r = api_call("/models?pageSize=1", key=gkey, timeout=10)
                ok("gemini net", "_error" not in r, "%.1fs" % (time.time() - t0),
                   "internet ya key check karo")
            except Exception as exc:
                ok("gemini net", False, str(exc)[:40])
        for prov in ("groq", "openrouter"):
            pk = load_provider_key(prov)
            if pk:
                t0 = time.time()
                txt = openai_chat(prov, [{"role": "user", "content": "hi"}], cfg, pk, timeout=12)
                ok(prov + " net", bool(txt), "%.1fs" % (time.time() - t0),
                   "key ya network check karo")

    # adb
    try:
        adb_ok, adb_msg = adb_ready(cfg)
    except Exception:
        adb_ok, adb_msg = False, "?"
    ok("phone control", adb_ok, str(adb_msg)[:40], "bash ~/pair_now.sh")

    # local engine
    srv = find_server(cfg)
    ver_ok, ver = server_version(srv)
    ok("local engine", ver_ok, os.path.basename(srv) if srv else "nahi mila",
       "bash install_engine.sh")
    model = local_model_path(cfg)
    ok("local model", os.path.exists(model),
       ("%.1f GB" % (os.path.getsize(model) / 1e9)) if os.path.exists(model) else "nahi mila",
       "bash setup_local.sh")

    # brain + data
    b = load_brain()
    ok("dimaag", True, "%d facts, %d style, %d sabak, %d turn" % (
        len(b["facts"]), len(b["style"]), len(b["lessons"]), int(b["stats"].get("turns", 0))))
    chunks, nfiles, _ = build_index(cfg)
    ok("data vault", True, "%d file, %d hisse" % (nfiles, len(chunks)))

    # log errors
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            tail = [l.strip() for l in f.read().splitlines()[-80:] if l.strip()]
        errs = [l for l in tail if ("fail" in l.lower() or "error" in l.lower())][-3:]
        ok("log", not errs, ("%d error lines" % len(errs)) if errs else "saaf")
        for e in errs:
            lines.append("               " + e[:110])
    except OSError:
        pass

    head = "System check: %d dikkat mili" % problems if problems else "System check: sab theek hai"
    return head + "\n" + "\n".join(lines), problems


def selftest():
    global STUB
    STUB = True
    print("Selftest...")
    assert extract_json('{"say":"hi"}')["say"] == "hi"
    assert extract_json('```json\n{"say":"hi","do":[]}\n```')["say"] == "hi"
    assert extract_json('bakwas {"say":"ok","do":[{"tool":"battery"}]} tail')["say"] == "ok"
    assert extract_json("no json here") is None
    assert strip_markdown("**Boss** _ji_ `code` 🚀 https://x.com") == "Boss ji code link"
    cfg = dict(DEFAULT_CONFIG)
    mem = {"facts": ["test fact"], "notes": [], "history": []}
    print("  json parse      OK")
    print("  markdown strip  OK")
    assert "test fact" in system_prompt(cfg, mem)
    print("  system prompt   OK")
    for name in TOOLS:
        res = run_tool(name, {"on": True, "level": 3, "package": "com.test", "title": "t",
                              "text": "hello", "ms": 100, "url": "https://example.com",
                              "number": "+911234567890", "fact": "f", "count": 3}, cfg)
        assert isinstance(res, str)
    print("  %d tools        OK" % len(TOOLS))
    say = handle_turn("battery kitna hai", cfg, mem, "fake-key")
    assert say
    print("  turn loop       OK -> %r" % say[:60])
    assert mem["history"]
    print("  memory write    OK")
    plan = ask_model(cfg, mem, "kuch karo", "fake-key")
    assert "say" in plan
    print("  model call      OK (stub)")
    print("\nAll good.")
    return 0


def banner(cfg):
    print("=" * 46)
    print("  %s v%s  -  private, phone-only" % (cfg.get("name", "Jarvis").upper(), VERSION))
    chain = str(cfg.get("providers", "gemini,groq,openrouter,local")) if cfg.get("brain") != "local" else "local"
    print("  brain: %s | input: %s | language: %s | voice: %s" % (
        chain, cfg.get("engine"), cfg.get("language"),
        (cfg.get("gemini_voice") if cfg.get("tts") in ("auto", "gemini") else "phone")))
    print("  'exit' bolo ya Ctrl+C dabao band karne ke liye")
    print("=" * 46)


def main_loop(cfg):
    key = load_key()
    if not key and cfg.get("brain", "gemini") != "local":
        print("API key nahi mili. Chalao: bash setup.sh  (ya ~/.jarvis/key.txt me daalo)")
        print("Ya local brain par switch karo: python jarvis.py --brain local")
        return 2
    mem = load_memory()
    banner(cfg)
    if cfg.get("briefing", True):
        speak(briefing(cfg, mem, key), cfg, force_gemini=True)
    else:
        speak("Systems online, %s. Boliye." % cfg.get("user_name", "Boss"), cfg)
    idle = 0
    while True:
        try:
            if not cfg.get("auto_loop"):
                input("\n[Enter dabao, phir boliye] ")
            print("  sun raha hoon...")
            heard = ""
            part = None
            if cfg.get("engine") == "audio":
                audio = record_audio(cfg.get("listen_seconds", 8))
                if not audio:
                    print("  (mic se kuch nahi aaya - permission check karo)")
                    continue
                part = {"inlineData": {"mimeType": "audio/mp4",
                                       "data": base64.b64encode(audio).decode("ascii")}}
                heard = "[voice note]"
            else:
                heard = listen_text(cfg.get("listen_seconds", 8))
                if not heard:
                    idle += 1
                    print("  (kuch sunai nahi diya)")
                    if idle >= 3:
                        print("  Mic band lag raha hai. Termux:API ko Microphone permission do,")
                        print("  ya doctor chalao: python jarvis.py --doctor")
                        idle = 0
                    continue
                idle = 0
                print("  aapne kaha: %s" % heard)
                part = heard
            low = (heard or "").lower()
            if any(w in low for w in ("exit", "band karo", "so jao", "bye jarvis", "shutdown")):
                speak("Theek hai, standby me ja raha hoon.", cfg)
                break
            handle_turn(part, cfg, mem, key, heard_text=heard)
        except KeyboardInterrupt:
            print()
            speak("Standby.", cfg)
            break
        except EOFError:
            break
    save_memory(mem)
    return 0


def set_config(args):
    cfg = load_config()
    changed = []
    pairs = [a.split("=", 1) for a in args if "=" in a]
    for k, v in pairs:
        if k not in DEFAULT_CONFIG:
            print("  unknown setting: %s" % k)
            continue
        cur = DEFAULT_CONFIG[k]
        if isinstance(cur, bool):
            val = v.lower() in ("1", "true", "yes", "on")
        elif isinstance(cur, int):
            val = int(v)
        elif isinstance(cur, float):
            val = float(v)
        else:
            val = v
        cfg[k] = val
        changed.append("%s = %s" % (k, val))
    save_config(cfg)
    print("Saved: " + (", ".join(changed) if changed else "kuch nahi"))
    for k, v in sorted(cfg.items()):
        print("  %-16s %s" % (k, v))
    return 0


USAGE = """JARVIS (Termux) - private phone assistant

  python jarvis.py                normal voice loop
  python jarvis.py --text         type karke baat karo (mic ke bina test)
  python jarvis.py --once "..."   ek hi command chalao, phir band
  python jarvis.py --doctor       sab dependency/permission/key check karo
  python jarvis.py --config       settings dekho / badlo
  python jarvis.py --config language=en voice_lang=en-IN
  python jarvis.py --reset-memory memory saaf karo
  python jarvis.py --selftest     offline test
  python jarvis.py --brain local  permanent free: phone ka apna model (no key, no internet)
  python jarvis.py --brain gemini wapas cloud brain par
  python jarvis.py --index        aapke data folder ka index banao/dikhao
  python jarvis.py --setkey groq  kisi bhi provider ki key save karo (gemini/groq/openrouter)
  python jarvis.py --test         kaunsi key chal rahi hai + kitni tez (seconds)
  python jarvis.py --voices       saaton female voices sun kar chuno
  python jarvis.py --say "text"   koi bhi line bol kar sunao (voice test)
  python jarvis.py --speed fast   sabse tez mode (fast|balanced|quality)
  python jarvis.py --persona "..." apni pasand ka behaviour likho (file me jodta hai)
  python jarvis.py --teach "..."  seedha sikhao (style ya yaad)
  python jarvis.py --diag         apna system check karo (kya dikkat hai)
  python jarvis.py --mind show    apna dimaag dekho (facts, style, sabak)
  python jarvis.py --mind push    dimaag GitHub par save (personal database)
  python jarvis.py --mind pull    GitHub se dimaag wapas laao
  python jarvis.py --update       naya version khud install karo (backup ke saath)
  python jarvis.py --serve        browser panel (http://127.0.0.1:8080) - saare tools browser se
  python jarvis.py --adb "command"     poore phone par adb command (setup_adb.sh ke baad)
  python jarvis.py --research "topic"  internet se source ke saath jawab
  python jarvis.py --build "idea"      chhoti app banao (single HTML, browser me khulegi)
  python jarvis.py --daily             subah ka routine: briefing + notes + vault
  python jarvis.py --self "kya badalna hai"   khud ka code badle (backup + test ke saath)
  python jarvis.py --selfcheck    apna code theek hai ya nahi
  python jarvis.py --restore      pichhla backup wapas laao
  python jarvis.py --briefing     subah ki chhoti briefing
  python jarvis.py --vault        vault me kaunsi files hain
  python jarvis.py --import <path>  file/folder/zip vault me daalo (data.txt, notes.zip...)
  python jarvis.py --version
"""


WEB_PAGE = """<!DOCTYPE html>
<html lang="hi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0b1416">
<meta http-equiv="cache-control" content="no-store, no-cache, must-revalidate">
<meta http-equiv="pragma" content="no-cache"><title>JARVIS</title>
<style>
:root{--bg:#0b1416;--pnl:#12212a;--acc:#37c2c9;--txt:#e8f4f6;--dim:#7fa0a8;--usr:#1b3a44}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--txt);font-family:system-ui,Roboto,sans-serif;height:100dvh;display:flex;flex-direction:column}
header{display:flex;gap:9px;align-items:center;padding:11px 13px;background:var(--pnl);border-bottom:1px solid #1d3540}
.dot{width:9px;height:9px;border-radius:50%;background:var(--acc);box-shadow:0 0 8px var(--acc)}
header h1{font-size:15px;margin:0;font-weight:600;letter-spacing:.4px}
header .sp{flex:1}
header button{background:transparent;border:1px solid #2a4a55;color:var(--dim);border-radius:8px;padding:6px 10px;font-size:12px}
#chat{flex:1;overflow-y:auto;padding:13px 11px;display:flex;flex-direction:column;gap:9px}
.msg{max-width:86%;padding:10px 13px;border-radius:14px;font-size:14.5px;line-height:1.45;white-space:pre-wrap;word-wrap:break-word}
.me{align-self:flex-end;background:var(--usr);border-bottom-right-radius:4px}
.bot{align-self:flex-start;background:var(--pnl);border:1px solid #1d3540;border-bottom-left-radius:4px}
.bot.think{color:var(--dim);font-style:italic}
.time{font-size:10.5px;color:var(--dim);margin:1px 6px}
footer{padding:9px 9px calc(9px + env(safe-area-inset-bottom));background:var(--pnl);border-top:1px solid #1d3540;display:flex;gap:7px;align-items:center}
#txt{flex:1;background:#0e1c22;border:1px solid #24414c;color:var(--txt);border-radius:22px;padding:12px 15px;font-size:15px;outline:none}
#mic,#send{width:47px;height:47px;border-radius:50%;border:none;display:grid;place-items:center;font-size:19px}
#mic{background:#1b3a44;color:var(--acc)}
#mic.rec{background:#c0392b;color:#fff;animation:pl 1.1s infinite}
@keyframes pl{0%,100%{box-shadow:0 0 0 0 rgba(192,57,43,.6)}50%{box-shadow:0 0 0 12px rgba(192,57,43,0)}}
#send{background:var(--acc);color:#04191c}
.pend{margin:0 10px 8px;padding:11px;border:1px solid #2a6b74;border-radius:12px;background:#0f2a30;display:none}
.pend.on{display:block}
.pend pre{margin:6px 0;font-size:11.5px;color:#bfe6ea;white-space:pre-wrap;max-height:150px;overflow:auto}
.pend .row{display:flex;gap:8px;margin-top:8px}
.pend button{flex:1;padding:9px;border-radius:9px;border:none;font-size:13px;font-weight:600}
.pend .yes{background:var(--acc);color:#04191c}
.pend .no{background:#1b3a44;color:var(--txt)}
.chips{display:flex;gap:6px;overflow-x:auto;padding:7px 10px 0;background:var(--pnl)}
.chip{flex:0 0 auto;font-size:12px;padding:7px 11px;border-radius:15px;background:#16303a;color:var(--acc);border:1px solid #22414c}
#sht{position:fixed;inset:0;background:rgba(3,10,12,.9);display:none;z-index:9;padding:16px;overflow-y:auto}
#sht.on{display:block}
.card{background:var(--pnl);border:1px solid #22414c;border-radius:14px;padding:15px;max-width:520px;margin:0 auto;font-size:13px;line-height:1.6}
.card h2{margin:0 0 10px;font-size:15px;color:var(--acc)}
.card code{background:#0e1c22;padding:1px 5px;border-radius:4px;font-size:12px}
.card button{margin-top:12px;width:100%;padding:11px;border-radius:10px;border:none;background:var(--acc);color:#04191c;font-weight:600}
</style></head><body>
<header><span class="dot"></span><h1>JARVIS</h1><span class="sp"></span><button id="gear">⚙</button></header>
<div id="chat"></div>
<div id="startbar" style="padding:10px 12px;background:#12212a;border-top:1px solid #1d3540;display:flex;gap:9px;align-items:center">
  <button id="startbtn" style="flex:1;padding:13px;border:none;border-radius:12px;background:#37c2c9;color:#04191c;font-weight:700;font-size:15px">🎙 Mic shuru karo (ek tap)</button>
</div>
<div id="levelwrap" style="display:none;height:6px;background:#0e1c22"><div id="level" style="height:6px;width:0%;background:#37c2c9;transition:width .08s"></div></div>
<div class="chips">
  <button class="chip" id="hf">🎧 handsfree: ON</button>
  <button class="chip" data-q="battery kitni hai">battery</button>
  <button class="chip" data-q="aaj kya karna chahiye">aaj ka plan</button>
  <button class="chip" data-q="torch on karo">torch</button>
  <button class="chip" data-q="screen par kya hai">screen</button>
  <button class="chip" data-q="research karo aaj ka gold rate">research</button>
</div>
<footer>
  <button id="mic">🎙</button>
  <input id="txt" placeholder="Likhо ya mic dabao..." autocomplete="off">
  <button id="send">➤</button>
</footer>
<div class="pend" id="pend"><b>Code badlav taiyar</b><pre id="pv"></pre>
 <div class="row"><button class="yes" id="apply">Lagao</button><button class="no" id="cancel">Cancel</button></div></div>
<div id="sht"><div class="card">
  <h2>Setup</h2>
  Ye page aapke phone me chal rahe JARVIS se juda hai (<code>Termux</code> me <code>python jarvis.py --serve</code>).
  <br><br>
  Brain: <b id="chain">?</b><br>Awaaz: <b id="voice">?</b><br>Server: <b id="srv">checking...</b>
  <br><br>
  Kuch badalna ho to Termux me karo (<code>--config</code>, <code>--speed</code>, <code>--voices</code>), phir ye page refresh karo.
  <br><br>
  Chrome menu → <b>Add to Home screen</b> → ek tap me app.
  <button id="ok">Theek hai</button>
</div></div>
<script>
const $=s=>document.querySelector(s); let busy=false, spk=null;
function bub(t,w,c){const d=document.createElement('div');d.className='msg '+w+(c?' '+c:'');d.textContent=t;
 $('#chat').appendChild(d);$('#chat').scrollTop=$('#chat').scrollHeight;return d;}
function tm(s){const d=document.createElement('div');d.className='time';d.textContent=s+'s';$('#chat').appendChild(d);}
async function ping(){try{const r=await fetch('/ping');const j=await r.json();
 $('#chain').textContent=j.chain||'?';$('#voice').textContent=j.voice||'phone';$('#srv').textContent='OK';}catch(e){$('#srv').textContent='band';}}
ping();
$('#gear').onclick=()=>{$('#sht').classList.add('on');ping();};
$('#ok').onclick=()=>$('#sht').classList.remove('on');
function say(text){
  speaking=true; buf=[]; silenceMs=0; window.__mute=true;
  if(spk){try{spk.pause();}catch(e){} spk=null;}
  const done=()=>{ setTimeout(()=>{speaking=false; window.__mute=false; buf=[]; silenceMs=0; if(handsfree && stream) $('#mic').classList.add('rec');},400); };
  fetch('/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})})
   .then(r=>r.json()).then(j=>{
     if(j.audio){
       const a=new Audio('data:audio/wav;base64,'+j.audio); spk=a;
       a.onended=done; a.onerror=()=>{fallback(text);};
       a.play().catch(()=>fallback(text));
     } else fallback(text);
   }).catch(()=>fallback(text));
}
function fallback(text){
  try{
    speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(text);
    const vs=speechSynthesis.getVoices()||[];
    const hi=vs.find(v=>/hi[-_]IN/i.test(v.lang) && /female|google/i.test(v.name)) || vs.find(v=>/hi[-_]IN/i.test(v.lang));
    if(hi)u.voice=hi;
    u.lang=hi?hi.lang:'hi-IN'; u.pitch=1.2; u.rate=0.98;
    u.onend=()=>{ setTimeout(()=>{speaking=false; window.__mute=false; buf=[]; silenceMs=0; if(handsfree && stream) $('#mic').classList.add('rec');},400); };
    speaking=true; speechSynthesis.speak(u);
  }catch(e){ speaking=false; window.__mute=false; }
}
async function send(text){
  text=(text||'').trim(); if(!text||busy)return; busy=true;
  bub(text,'me'); $('#txt').value='';
  const th=bub('soch rahi hoon...','bot','think'); const t0=Date.now();
  try{
    const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
    const j=await r.json(); th.remove();
    if(j.say){bub(j.say,'bot'); tm(((Date.now()-t0)/1000).toFixed(1)+' · '+(j.provider||'?')); say(j.say);}
    if(j.pending){$('#pv').textContent=j.preview||'';$('#pend').classList.add('on');}
    else if(j.error && j.error!=='khaali') bub('Dikkat: '+j.error,'bot');
  }catch(e){th.remove();bub('Server se baat nahi hui. Termux me --serve chal raha hai?','bot');}
  busy=false;
}
$('#send').onclick=()=>send($('#txt').value);
$('#txt').addEventListener('keydown',e=>{if(e.key==='Enter')send($('#txt').value);});
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>send(c.dataset.q));
let handsfree=false, speaking=false, stream=null, actx=null, proc=null, gain=null;
let buf=[], silenceMs=0, sending=false, noiseFloor=0.004;

function setChip(on){ handsfree=on; $('#hf').textContent='🎧 handsfree: '+(on?'ON':'OFF'); }

async function openMic(){
  if(stream) return true;
  try{
    if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
      bub('Is Chrome me mic API nahi hai - Chrome update karo.','bot'); return false;
    }
    stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    actx=new (window.AudioContext||window.webkitAudioContext)();
    try{ await actx.resume(); }catch(e){}
    const src=actx.createMediaStreamSource(stream);
    proc=actx.createScriptProcessor(4096,1,1);
    gain=actx.createGain(); gain.gain.value=0;
    proc.onaudioprocess=e=>{
      const d=e.inputBuffer.getChannelData(0);
      let sum=0; for(let i=0;i<d.length;i++) sum+=d[i]*d[i];
      const rms=Math.sqrt(sum/d.length);
      const le=$('#level'); if(le) le.style.width=Math.min(100,Math.round(rms*1600))+'%';
      if(speaking || sending || !handsfree || window.__mute) return;
      if(!buf.length) noiseFloor = noiseFloor*0.96 + rms*0.04;
      const trig = Math.max(0.005, noiseFloor*2.8);
      if(rms>trig){
        buf.push(new Float32Array(d)); silenceMs=0; $('#mic').classList.add('rec');
        if(!window.__t0) window.__t0=Date.now();
      } else if(buf.length){
        silenceMs+=(d.length/actx.sampleRate)*1000;
        if(silenceMs>1000) flushAudio();
      }
    };
    src.connect(proc); proc.connect(gain); gain.connect(actx.destination);
    $('#levelwrap').style.display='block';
    $('#mic').classList.add('rec');
    return true;
  }catch(e){
    const n=(e&&(e.name||e.message))||'error';
    bub('Mic nahi khula ('+n+'). Chrome > 127.0.0.1 > site settings > Microphone > Allow, phir reload karo.','bot');
    return false;
  }
}
function closeMic(){
  try{ if(proc) proc.disconnect(); if(stream) stream.getTracks().forEach(t=>t.stop()); if(actx) actx.close(); }catch(e){}
  stream=null; actx=null; proc=null; buf=[]; $('#mic').classList.remove('rec');
  $('#levelwrap').style.display='none';
}
function wavB64(samples, rate){
  const n=samples.length, ab=new ArrayBuffer(44+n*2), v=new DataView(ab);
  const ws=(o,str)=>{for(let i=0;i<str.length;i++)v.setUint8(o+i,str.charCodeAt(i));};
  ws(0,'RIFF'); v.setUint32(4,36+n*2,true); ws(8,'WAVE'); ws(12,'fmt ');
  v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,1,true);
  v.setUint32(24,rate,true); v.setUint32(28,rate*2,true); v.setUint16(32,2,true); v.setUint16(34,16,true);
  ws(36,'data'); v.setUint32(40,n*2,true);
  let o=44;
  for(let i=0;i<n;i++){ const x=Math.max(-1,Math.min(1,samples[i])); v.setInt16(o, x<0?x*0x8000:x*0x7FFF, true); o+=2; }
  const u8=new Uint8Array(ab); let bin='';
  for(let i=0;i<u8.length;i++) bin+=String.fromCharCode(u8[i]);
  return btoa(bin);
}
async function flushAudio(){
  if(!buf.length || sending) return;
  const rate = actx ? actx.sampleRate : 48000;
  const total=buf.reduce((a,b)=>a+b.length,0);
  if(total < rate*0.5){ buf=[]; silenceMs=0; window.__t0=0; return; }
  const all=new Float32Array(total); let off=0;
  for(const b of buf){ all.set(b,off); off+=b.length; }
  buf=[]; silenceMs=0; sending=true; $('#mic').classList.remove('rec');
  const tStt=Date.now();
  try{
    const r=await fetch('/stt',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({audio:wavB64(all, rate), mime:'audio/wav'})});
    const j=await r.json();
    const t=(j.text||'').trim();
    if(t) console.log('stt', ((Date.now()-tStt)/1000).toFixed(1)+'s via '+(j.via||'?'));
    if(t && /^(band karo|stop|chup|ruko)$/i.test(t)){ stopAll(); }
    else if(t && t.length>1 && !speaking) await send(t);
    else if(j.error) bub('Sunne me dikkat: '+j.error,'bot');
  }catch(e){ bub('Audio bhejne me dikkat: '+e.message,'bot'); }
  sending=false;
  if(handsfree && stream) $('#mic').classList.add('rec');
}
let serverMode=false, pollT=null;
async function pollNext(){
  clearTimeout(pollT);
  if(!handsfree || !serverMode) return;
  try{
    const r=await fetch('/next'); const j=await r.json();
    const t=(j.text||'').trim();
    if(t && !speaking && !sending){
      if(/^(band karo|stop|chup|ruko)$/i.test(t)){ stopAll(); return; }
      await send(t);
    }
  }catch(e){}
  pollT=setTimeout(pollNext, 300);
}
async function startAll(){
  // 1) browser mic + Groq Whisper (fast, free) - prefer
  const okB=await openMic();
  if(okB){
    serverMode=false; setChip(true);
    $('#startbar').style.display='none';
    bub('Mic chalu - boliye (level bar hilni chahiye).','bot');
    return true;
  }
  // 2) warna phone ka mic (Termux)
  try{
    const r=await fetch('/listen/start'); const j=await r.json();
    if(j.ok){
      serverMode=true; setChip(true);
      $('#startbar').style.display='none';
      $('#mic').classList.add('rec');
      bub('Phone mic chalu - boliye, main sun rahi hoon.','bot');
      pollNext();
      return true;
    }
  }catch(e){}
  // 2) warna browser mic
  serverMode=false;
  const okM=await openMic();
  setChip(okM);
  if(okM){ $('#startbar').style.display='none'; bub('Browser mic chalu - ab boliye.','bot'); }
  return okM;
}
function stopAll(){
  setChip(false); serverMode=false; clearTimeout(pollT); closeMic();
  fetch('/listen/stop').catch(()=>{});
}
$('#startbtn').onclick=async()=>{
  $('#startbtn').textContent='Mic khul raha hai...';
  const okM=await startAll();
  if(!okM) $('#startbtn').textContent='🎙 Dobara try karo';
};
$('#mic').onclick=()=>{ if(handsfree){ stopAll(); } else { startAll(); } };
$('#hf').onclick=()=>{ if(handsfree){ stopAll(); } else { startAll(); } };
setChip(false);
bub('Namaste Boss. Neeche 🎙 button dabao (ek tap). Mic khulega, phir lagataar sunta rahega.','bot');
</script></body></html>"""


LISTEN = {"thread": None, "q": None, "stop": True}


def listen_loop(cfg):
    """Phone ke mic se lagataar sunta rahe (Termux:API), text queue me daalta hai."""
    import queue as _q
    LISTEN["q"] = LISTEN.get("q") or _q.Queue()
    LISTEN["stop"] = False
    log("listen loop start")
    while not LISTEN["stop"]:
        try:
            txt = listen_text(int(cfg.get("listen_seconds", 8)))
        except Exception as exc:
            log("listen fail: %s" % exc)
            txt = ""
        if txt:
            try:
                LISTEN["q"].put_nowait(txt.strip())
            except Exception:
                pass
        time.sleep(0.2)
    log("listen loop stop")


def listen_start(cfg):
    if LISTEN["thread"] and LISTEN["thread"].is_alive():
        return True
    if not have("termux-speech-to-text"):
        return False
    LISTEN["thread"] = threading.Thread(target=listen_loop, args=(cfg,), daemon=True)
    LISTEN["thread"].start()
    return True


def listen_stop():
    LISTEN["stop"] = True


def serve(cfg, port=8080):
    """Browser control panel - Termux ke saare tools browser se chalte hain."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    key = load_key()
    mem = load_memory()
    lock = threading.Lock()
    QUIET["on"] = True
    SERVE_MODE["on"] = True
    if gh_token():
        try:
            ok_b, msg_b = gh_brain_sync(cfg, "pull")
            print("  brain: %s" % msg_b)
        except Exception:
            pass
    counter = {"n": 0}

    def maybe_push():
        counter["n"] += 1
        if counter["n"] % 10 == 0 and gh_token():
            try:
                gh_brain_sync(cfg, "push")
            except Exception:
                pass

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else str(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except Exception:
                pass

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                data = WEB_PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except Exception:
                    pass
            elif path == "/listen/start":
                ok_l = listen_start(cfg)
                self._send(200, json.dumps({"ok": ok_l,
                                            "why": "" if ok_l else "termux-api (termux-speech-to-text) nahi mila"}))
            elif path == "/listen/stop":
                listen_stop()
                self._send(200, json.dumps({"ok": True}))
            elif path == "/next":
                got = ""
                try:
                    if LISTEN.get("q"):
                        got = LISTEN["q"].get(timeout=1.2)
                except Exception:
                    got = ""
                self._send(200, json.dumps({"text": got}))
            elif path == "/ping":
                self._send(200, json.dumps({"ok": True, "chain": cfg.get("providers"),
                                            "voice": cfg.get("gemini_voice") if cfg.get("tts") != "phone" else "phone"}))
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                self._send(400, json.dumps({"error": "bad json"}))
                return
            if self.path == "/apply":
                if not PENDING_EDIT.get("edits"):
                    self._send(200, json.dumps({"error": "koi badlav pending nahi"}))
                    return
                ok_r, msg = self_apply(PENDING_EDIT.get("edits"), reason=PENDING_EDIT.get("reason", ""),
                                       confirm=False)
                PENDING_EDIT.update({"edits": [], "reason": "", "preview": ""})
                self._send(200, json.dumps({"ok": ok_r, "say": msg}))
                return
            if self.path == "/cancel":
                PENDING_EDIT.update({"edits": [], "reason": "", "preview": ""})
                self._send(200, json.dumps({"ok": True, "say": "Cancel kar diya"}))
                return
            if self.path == "/chat":
                text = str(body.get("text", "")).strip()
                if not text:
                    self._send(400, json.dumps({"error": "khaali"}))
                    return
                if is_self_intent(text):
                    t0 = time.time()
                    ok_r, note, pend = self_prepare(text, cfg, key)
                    if pend:
                        PENDING_EDIT.update(pend)
                    self._send(200, json.dumps({"say": note, "pending": bool(pend),
                                                "preview": pend.get("preview", ""),
                                                "provider": "self-edit",
                                                "seconds": round(time.time() - t0, 1)}))
                    return
                t0 = time.time()
                try:
                    with lock:
                        say = handle_turn(text, cfg, mem, key, heard_text=text)
                    maybe_push()
                except Exception as exc:
                    self._send(200, json.dumps({"error": str(exc)[:200]}))
                    return
                self._send(200, json.dumps({"say": say, "provider": LAST_PROVIDER.get("name", ""),
                                            "seconds": round(time.time() - t0, 1)}))
            elif self.path == "/stt":
                b64 = str(body.get("audio", ""))
                mime = str(body.get("mime", "audio/wav"))
                gkey = load_provider_key("groq")
                if b64 and gkey:
                    try:
                        wav = base64.b64decode(b64)
                    except Exception:
                        wav = b""
                    txt_g, err_g = groq_transcribe(wav, gkey, cfg)
                    if txt_g:
                        self._send(200, json.dumps({"text": txt_g, "via": "groq"}))
                        return
                if have("termux-speech-to-text"):
                    txt_t = listen_text(int(cfg.get("listen_seconds", 8)))
                    if txt_t:
                        self._send(200, json.dumps({"text": txt_t.strip(), "via": "phone"}))
                        return
                if not b64 or not key:
                    self._send(200, json.dumps({"error": "audio ya key nahi"}))
                    return
                payload = {"contents": [{"role": "user", "parts": [
                    {"text": "Transcribe exactly what is spoken. Output ONLY the spoken words in the same "
                             "language (Hindi/Hinglish/English). No commentary, no quotes."},
                    {"inlineData": {"mimeType": mime, "data": b64}}]}],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": 200}}
                resp = api_call("/models/%s:generateContent" % pick_model(key, cfg), payload, key=key, timeout=60)
                if "_error" in resp:
                    self._send(200, json.dumps({"error": resp["_error"]}))
                    return
                self._send(200, json.dumps({"text": model_text(resp).strip().strip('"').strip()}))
            elif self.path == "/tts":
                text = strip_markdown(str(body.get("text", "")).strip())
                if not text or not key or cfg.get("tts") == "phone":
                    self._send(200, json.dumps({"error": "phone voice"}))
                    return
                path, err = gemini_tts(text, cfg, key)
                if not path:
                    self._send(200, json.dumps({"error": err or "tts fail"}))
                    return
                try:
                    with open(path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("ascii")
                except OSError:
                    self._send(200, json.dumps({"error": "file"}))
                    return
                self._send(200, json.dumps({"audio": b64}))
            else:
                self._send(404, json.dumps({"error": "not found"}))

    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        print("Port %d busy hai: %s" % (port, exc))
        return 1
    print("=" * 52)
    print("  JARVIS browser panel chalu hai")
    print("  Chrome me kholo:  http://127.0.0.1:%d" % port)
    print("  Chain: %s | voice: %s" % (cfg.get("providers"), cfg.get("tts")))
    print("  Band karne ke liye Ctrl+C")
    print("=" * 52)
    try:
        termux("termux-open-url", "http://127.0.0.1:%d" % port, timeout=15)
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nBand kar diya.")
    finally:
        httpd.server_close()
        QUIET["on"] = False
        save_memory(mem)
    return 0


def main(argv):
    ensure_dirs()
    if not argv:
        return main_loop(load_config())

    if argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if argv[0] == "--version":
        print("jarvis.py %s" % VERSION)
        return 0
    if argv[0] == "--selftest":
        return selftest()
    if argv[0] == "--doctor":
        return doctor(load_config())
    if argv[0] == "--brain":
        cfg = load_config()
        want = (argv[1] if len(argv) > 1 else "").strip().lower()
        if want not in ("local", "gemini"):
            print("Use: python jarvis.py --brain local   |   --brain gemini")
            return 1
        cfg["brain"] = want
        save_config(cfg)
        print("Brain = %s" % want)
        if want == "local":
            model = local_model_path(cfg)
            print("  model : %s %s" % (model, "" if os.path.exists(model) else "(abhi nahi hai - bash setup_local.sh)"))
            print("  data  : %s" % data_dir(cfg))
            print("  key ki zarurat nahi. Internet ke bina chalega.")
        else:
            print("  Gemini key: %s" % ("saved" if load_key() else "missing - bash setup.sh"))
        return 0
    if argv[0] == "--index":
        cfg = load_config()
        chunks, nfiles, cached = build_index(cfg, force=True)
        print("Data folder : %s" % data_dir(cfg))
        print("Files       : %d" % nfiles)
        print("Hisse       : %d" % len(chunks))
        if not chunks:
            print("\nKhaali hai. Apni files is folder me daalo (.txt .md .csv .json .srt .pdf),")
            print("phir ye command dobara chalao. Example:")
            print("  cp /sdcard/Download/notes.txt ~/jarvis/data/")
        else:
            for ch in chunks[:3]:
                print("  - %s: %s..." % (ch["file"], ch["text"][:70].replace("\n", " ")))
        return 0
    if argv[0] == "--setkey":
        import getpass
        prov = (argv[1] if len(argv) > 1 else "").strip().lower()
        if prov not in ("gemini", "groq", "openrouter", "mistral", "github"):
            print("Use: python jarvis.py --setkey groq   (ya gemini / openrouter / mistral)")
            return 1
        try:
            k = getpass.getpass("%s key paste karo: " % prov).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        if not k:
            print("Khaali key - kuch nahi badla")
            return 1
        ensure_dirs()
        path = KEY_PATH if prov == "gemini" else os.path.join(JARVIS_DIR, "%s.txt" % prov)
        with open(path, "w", encoding="utf-8") as f:
            f.write(k)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        print("%s key save ho gayi (%d bytes): %s" % (prov, len(k), path))
        return 0
    if argv[0] == "--teach":
        cfg = load_config()
        text = " ".join(argv[1:]).strip()
        if not text:
            b = load_brain()
            print("Sikhane ka tareeka: python jarvis.py --teach \"hamesha chhoti line me jawab do\"")
            print("Agar 'hamesha/always/aise bolo' likhoge to STYLE me jayega, warna YAAD me.")
            print("\nAbhi dimaag me: %d facts, %d style, %d sabak" % (len(b["facts"]), len(b["style"]), len(b["lessons"])))
            return 0
        low = text.lower()
        kind = "style" if any(k in low for k in ("hamesha", "always", "aise bolo", "aisa bolo", "tone", "style")) else "facts"
        brain_add(kind, text)
        print("Sikh liya (%s): %s" % (kind, text))
        return 0
    if argv[0] == "--diag":
        deep = "--deep" in argv
        txt, n = diagnose(load_config(), deep=deep)
        print(txt)
        return 0 if n == 0 else 1
    if argv[0] == "--mind":
        cfg = load_config()
        sub = (argv[1] if len(argv) > 1 else "show").strip().lower()
        if sub == "show":
            b = load_brain()
            print("Brain: %s" % BRAIN_PATH)
            print("  turns   : %s" % b["stats"].get("turns", 0))
            for k in ("facts", "style", "lessons", "skills"):
                print("  %-8s: %d" % (k, len(b[k])))
                for x in b[k][-5:]:
                    print("      - %s" % x[:100])
            return 0
        if sub in ("push", "pull"):
            ok_r, msg = gh_brain_sync(cfg, sub)
            print(("OK: " if ok_r else "FAIL: ") + msg)
            return 0 if ok_r else 1
        print("Use: --mind show | push | pull")
        return 1
    if argv[0] == "--update":
        url = ("https://raw.githubusercontent.com/bhupendarsingh785/toonistaan-studio/"
               "main/jarvis-kit/jarvis.py")
        print("Naya version laa raha hoon...")
        try:
            new = http_get(url, timeout=45)
        except Exception as exc:
            print("Download fail: %s" % exc)
            return 1
        if "def main(argv)" not in new or len(new) < 50000:
            print("Download adhoora laga - kuch nahi badla")
            return 1
        bak = self_backup()
        try:
            with open(SELF_PATH, "w", encoding="utf-8") as f:
                f.write(new)
            ok_r, msg = self_verify()
        except OSError as exc:
            ok_r, msg = False, str(exc)
        if not ok_r:
            try:
                shutil.copyfile(bak, SELF_PATH)
            except OSError:
                pass
            print("Naya version fail hua (%s) - purana wapas" % msg)
            return 1
        print("Update ho gaya (%d bytes). Backup: %s" % (len(new), os.path.basename(bak)))
        print("Ab chalao: python jarvis.py --serve")
        return 0
    if argv[0] in ("--serve", "--web"):
        cfg = load_config()
        port = 8080
        for a in argv[1:]:
            if a.isdigit():
                port = int(a)
        return serve(cfg, port)
    if argv[0] == "--adb":
        cmd = " ".join(argv[1:]).strip()
        if not cmd:
            ok_r, out = adb_ready()
            print("ADB ready: %s (%s)" % (ok_r, out))
            print("Use: python jarvis.py --adb \"input keyevent 3\"")
            return 0 if ok_r else 1
        cfg = load_config()
        ok_r, out = adb_shell(cmd, cfg)
        print(out or ("OK" if ok_r else "fail"))
        return 0 if ok_r else 1
    if argv[0] == "--research":
        q = " ".join(argv[1:]).strip()
        if not q:
            print("Use: python jarvis.py --research \"topic\"")
            return 1
        cfg = load_config()
        print("Research: %s\n" % q)
        ans, used = research(q, cfg, load_key())
        print(ans)
        if used:
            print("\nSources:")
            for i, h in enumerate(used, 1):
                print("  [%d] %s\n      %s" % (i, h["title"][:70], h["url"]))
        return 0
    if argv[0] == "--build":
        idea = " ".join(argv[1:]).strip()
        if not idea:
            print("Use: python jarvis.py --build \"ek expense tracker app\"")
            return 1
        cfg = load_config()
        print("App ban raha hai: %s" % idea)
        path, err = build_app(idea, cfg, load_key())
        if path:
            print("Ban gaya: %s" % path)
            print("Browser me khul gaya hoga. Chaho to GitHub par bhejo: --gh-upload")
            return 0
        print("Nahi bana: %s" % err)
        return 1
    if argv[0] == "--daily":
        cfg = load_config()
        mem = load_memory()
        print(briefing(cfg, mem, load_key()))
        if mem.get("notes"):
            print("\nNotes:")
            for n in mem["notes"][-5:]:
                print("  - %s: %s" % (n.get("at", ""), n.get("text", "")))
        print("\nData vault: %s" % data_dir(cfg))
        return 0
    if argv[0] == "--persona":
        cfg = load_config()
        text = " ".join(argv[1:]).strip()
        if not text:
            cur = ""
            try:
                with open(PERSONA_FILE, "r", encoding="utf-8") as f:
                    cur = f.read().strip()
            except OSError:
                pass
            print("Persona file: %s" % PERSONA_FILE)
            print(cur or "(khaali - default persona chal raha hai)")
            print("\nBadalne ke liye: python jarvis.py --persona \"hamesha zyada pyaar se baat karo\"")
            return 0
        ensure_dirs()
        with open(PERSONA_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
        print("Persona me jod diya: %s" % text)
        return 0
    if argv[0] == "--speed":
        want = (argv[1] if len(argv) > 1 else "").strip().lower()
        if want not in ("fast", "balanced", "quality"):
            print("Use: python jarvis.py --speed fast | balanced | quality")
            print("  fast     = sabse tez (Groq 8B + phone voice)")
            print("  balanced = tez + emotional voice (default)")
            print("  quality  = smart + emotional voice, thoda dheema")
            return 1
        cfg = load_config()
        cfg["speed"] = want
        if want == "fast":
            cfg["providers"] = "groq,gemini,openrouter,local"
            cfg["groq_model"] = "llama-3.1-8b-instant"
            cfg["tts"] = "phone"
            cfg["max_history"] = 6
            cfg["provider_timeout"] = 12
        elif want == "balanced":
            cfg["providers"] = "groq,gemini,openrouter,local"
            cfg["groq_model"] = "llama-3.3-70b-versatile"
            cfg["tts"] = "auto"
            cfg["max_history"] = 8
            cfg["provider_timeout"] = 25
        else:
            cfg["providers"] = "gemini,groq,openrouter,local"
            cfg["tts"] = "gemini"
            cfg["max_history"] = 12
            cfg["provider_timeout"] = 40
        save_config(cfg)
        print("Speed = %s" % want)
        for k in ("providers", "groq_model", "tts", "max_history", "provider_timeout"):
            print("  %-16s %s" % (k, cfg.get(k)))
        return 0
    if argv[0] == "--say":
        text = " ".join(argv[1:]).strip() or "Namaste Boss, main Jarvis hoon. Kaisi lagi meri awaaz?"
        cfg = load_config()
        speak(text, cfg, force_gemini=True)
        return 0
    if argv[0] == "--voices":
        cfg = load_config()
        key = load_key()
        if not key:
            print("Gemini key nahi hai - pehle key daalo")
            return 1
        line = ("Namaste Boss, main Jarvis hoon. Aaj mausam kitna achha hai na? "
                "Bataiye, main aapki kya madad karun?")
        for v in ("Kore", "Aoede", "Leda", "Callirrhoe", "Sulafat", "Despina", "Zephyr"):
            cfg["gemini_voice"] = v
            print("\n  Voice: %s" % v)
            path, err = gemini_tts(line, cfg, key)
            if path and play_audio(path, wav_seconds(path)):
                print("    (suniye)")
            else:
                print("    fail: %s" % err)
        print("\nPasand aayi voice set karo: python jarvis.py --config gemini_voice=Aoede")
        return 0
    if argv[0] == "--test":
        cfg = load_config()
        gkey = load_key()
        order = [x.strip() for x in str(cfg.get("providers", "gemini,groq,openrouter,local")).split(",") if x.strip()]
        print("Provider test (har ek ko 'hi' bhej raha hoon):\n")
        for prov in order:
            if prov == "local":
                srv = find_server(cfg)
                ok_v, ver = server_version(srv)
                print("  %-12s %s" % ("local", "engine OK" if ok_v else "engine nahi mila"))
                continue
            t0 = time.time()
            try:
                if prov == "gemini":
                    if not gkey:
                        print("  %-12s key nahi hai" % prov)
                        continue
                    payload = {"contents": [{"role": "user", "parts": [{"text": "hi"}]}],
                               "generationConfig": {"maxOutputTokens": 20}}
                    resp = api_call("/models/%s:generateContent" % pick_model(gkey, cfg), payload, key=gkey, timeout=40)
                    ok = "_error" not in resp and bool(model_text(resp))
                    info = resp.get("_error", "") if not ok else model_text(resp)[:40]
                else:
                    pkey = load_provider_key(prov)
                    if not pkey:
                        print("  %-12s key nahi hai" % prov)
                        continue
                    print("  %-12s key %d bytes" % (prov, len(pkey)))
                    if prov == "groq":
                        pick_groq_model(cfg, pkey)
                    elif prov == "openrouter":
                        pick_openrouter_model(cfg, pkey)
                    if prov == "openrouter":
                        txt = openrouter_try(cfg, pkey, [{"role": "user", "content": "hi"}])
                    else:
                        txt = openai_chat(prov, [{"role": "user", "content": "hi"}], cfg, pkey, timeout=40)
                    ok = bool(txt)
                    info = txt[:40] if ok else PROVIDER_ERR.get(prov, "fail")[:90]
                print("  %-12s %s  %.1fs  %s" % (prov, "OK  " if ok else "FAIL", time.time() - t0,
                                                 info.replace("\n", " ")))
            except Exception as exc:
                print("  %-12s FAIL  %s" % (prov, exc))
        return 0
    if argv[0] == "--self":
        cfg = load_config()
        text = " ".join(argv[1:]).strip()
        if not text:
            print("Use: python jarvis.py --self \"torch tool me 5 second ka delay add karo\"")
            return 1
        ok, msg = self_request(text, cfg, load_key(), confirm=True)
        print(("OK: " if ok else "NAHI: ") + msg)
        return 0 if ok else 1
    if argv[0] == "--selfcheck":
        ok, msg = self_verify()
        print("Self check: %s (%s)" % ("OK" if ok else "FAIL", msg))
        print("Backups: %s" % (sorted(os.listdir(BACKUP_DIR))[-3:] if os.path.isdir(BACKUP_DIR) else "none"))
        return 0 if ok else 1
    if argv[0] == "--restore":
        print(self_restore(argv[1] if len(argv) > 1 else ""))
        return 0
    if argv[0] == "--briefing":
        cfg = load_config()
        say = briefing(cfg, load_memory(), load_key())
        speak(say, cfg, force_gemini=True)
        return 0
    if argv[0] == "--import":
        if len(argv) < 2:
            print("Use: python jarvis.py --import /sdcard/Download/notes.zip")
            return 1
        cfg = load_config()
        msg, added = import_data(argv[1], cfg)
        print(msg)
        print("Vault: %s" % data_dir(cfg))
        return 0 if added else 1
    if argv[0] == "--vault":
        cfg = load_config()
        d = data_dir(cfg)
        chunks, nfiles, _ = build_index(cfg)
        print("Vault   : %s" % d)
        print("Files   : %d" % nfiles)
        print("Hisse   : %d" % len(chunks))
        for root, dirs, names in os.walk(d):
            for n in sorted(names):
                print("  %s" % os.path.relpath(os.path.join(root, n), d))
        return 0
    if argv[0] == "--reset-memory":
        save_memory({"facts": [], "notes": [], "history": []})
        print("Memory saaf.")
        return 0
    if argv[0] == "--config":
        return set_config(argv[1:])
    if argv[0] == "--once":
        cfg = load_config()
        key = load_key()
        if not key and cfg.get("brain", "gemini") != "local":
            print("API key missing - bash setup.sh chalao, ya: python jarvis.py --brain local")
            return 2
        text = " ".join(argv[1:]).strip()
        if not text:
            print("Kuch likho: python jarvis.py --once \"battery kitna hai\"")
            return 1
        handle_turn(text, cfg, load_memory(), key, heard_text=text)
        return 0
    if argv[0] == "--text":
        cfg = load_config()
        key = load_key()
        if not key and cfg.get("brain", "gemini") != "local":
            print("API key missing - bash setup.sh chalao, ya: python jarvis.py --brain local")
            return 2
        mem = load_memory()
        banner(cfg)
        while True:
            try:
                line = input("\nyou > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            if line.lower() in ("exit", "quit", "band"):
                break
            handle_turn(line, cfg, mem, key, heard_text=line)
        return 0

    print(USAGE)
    return 1


if __name__ == "__main__":
    import atexit
    atexit.register(stop_llama)
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(0)
