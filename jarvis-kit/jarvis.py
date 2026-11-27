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
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
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

DEFAULT_CONFIG = {
    "name": "Jarvis",
    "user_name": "Boss",
    "language": "hinglish",      # hinglish | hi | en
    "engine": "stt",             # stt (sasta, tez) | audio (Gemini ko aawaz bhejta hai)
    "listen_seconds": 8,
    "voice_lang": "hi-IN",
    "tts": "auto",               # auto | gemini | phone
    "gemini_voice": "Kore",      # Kore, Aoede, Leda, Zephyr (female-ish)
    "tts_model": "gemini-2.5-flash-preview-tts",
    "voice_pitch": 1.15,         # phone TTS ki awaaz thodi patli (ladki jaisi)
    "tts_rate": 0.98,
    "model": "",                 # khaali = auto (sabse achha flash model khud chunega)
    "providers": "gemini,groq,openrouter,local",   # is order me try karega
    "groq_model": "llama-3.3-70b-versatile",
    "openrouter_model": "meta-llama/llama-3.3-70b-instruct:free",
    "provider_timeout": 45,
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
}

# ----------------------------------------------------------------------------
# Chhote helpers
# ----------------------------------------------------------------------------

STUB = False  # --selftest ke liye


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
    prompt = ("Bolo jaise ek warm, friendly ladki dosti se baat kar rahi ho - natural emotion, "
              "halki muskurahat, saaf Hindi/Hinglish uchcharan, thoda dheere aur pyaar se. "
              "Sirf ye baat bolo: ") + text
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
    text = strip_markdown(text)
    if not text:
        return
    print("\n%s: %s\n" % (cfg.get("name", "Jarvis"), text))
    if STUB:
        return
    mode = str(cfg.get("tts", "auto"))
    key = load_key()
    use_gemini = (mode == "gemini") or (mode == "auto" and force_gemini)
    if use_gemini and key:
        path, err = gemini_tts(text, cfg, key)
        if path:
            if play_audio(path, wav_seconds(path)):
                return
            err = "play fail"
        log("gemini tts fail (%s) - phone voice par ja raha hoon" % err)
        if mode == "gemini":
            print("  (Gemini voice fail: %s)" % err)
    phone_speak(text, cfg)


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


def _read_any(path):
    ext = os.path.splitext(path)[1].lower()
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
            headers={"Content-Type": "application/json"})
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
  {"tool":"look"}          (camera se dekho aur batao)"""


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
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
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


def openai_chat(provider, messages, cfg, key, timeout=None):
    """Groq / OpenRouter / Mistral - sab OpenAI jaisa hi hai."""
    url, model_key = OPENAI_COMPAT[provider]
    model = cfg.get(model_key) or {
        "groq": "llama-3.3-70b-versatile",
        "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
        "mistral": "mistral-small-latest",
    }[provider]
    payload = {"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 400}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer %s" % key})
    try:
        with urllib.request.urlopen(req, timeout=timeout or int(cfg.get("provider_timeout", 45))) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "") or ""
    except Exception as exc:
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


def system_prompt(cfg, mem):
    name = cfg.get("name", "Jarvis")
    user = cfg.get("user_name", "Boss")
    facts = mem.get("facts", [])[-25:]
    notes = mem.get("notes", [])[-8:]
    return """You are {name}, a private personal assistant living inside {user}'s Android phone (Termux).
You are calm, quick and a little witty - never dramatic, never over-long. You address the user as "{user}".

{lang}

HOW YOU ANSWER - always strict JSON, nothing outside the JSON:
{{"say": "what you speak out loud", "do": [{{"tool": "name", "args": {{}}}}]}}

Rules:
- "say" is spoken by a TTS engine: plain sentences, no markdown, no emoji, no lists, under 45 words.
- Use "do" only when the user actually asks for a phone action. Omit or use [] otherwise.
- Never invent tool results. If a tool is needed, call it in "do" and say something short
  like "ek second, dekh raha hoon" - the real result comes back to you and you answer then.
- For anything you genuinely cannot do on this phone, say so in one line and suggest the closest thing you can do.
- Never claim you sent an SMS, made a call or opened an app unless the tool confirmed it.

{tools}

What you already know about {user}:
{facts}

Recent notes:
{notes}
""".format(name=name, user=user, lang=LANG_LINE.get(cfg.get("language", "hinglish"), LANG_LINE["hinglish"]),
           tools=TOOL_HELP, facts=("; ".join(facts) if facts else "nothing yet"),
           notes=("; ".join("%s %s" % (n.get("at", ""), n.get("text", "")) for n in notes) if notes else "none"))


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


def ask_remote(cfg, mem, user_part, key, extra=None):
    """Gemini -> Groq -> OpenRouter -> local, jo pehle chale."""
    order = [p.strip() for p in str(cfg.get("providers",
             "gemini,groq,openrouter,local")).split(",") if p.strip()]
    text_part = user_part if isinstance(user_part, str) else ""
    last_err = ""
    for prov in order:
        try:
            if prov == "local":
                res = ask_local(cfg, mem, user_part, extra)
                if isinstance(res, dict) and res.get("say"):
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
                raw = openai_chat(prov, ask_messages(cfg, mem, text_part, extra), cfg, pkey)
                plan = extract_json(raw) if raw else None
                if not isinstance(plan, dict) and raw:
                    plan = {"say": strip_markdown(raw)[:400], "do": []}
            else:
                continue
            if isinstance(plan, dict) and plan.get("say"):
                plan.setdefault("do", [])
                if prov != "gemini":
                    log("answered by %s" % prov)
                return plan
            last_err = "%s: khaali jawab" % prov
        except Exception as exc:
            last_err = "%s: %s" % (prov, exc)
            log("provider %s fail: %s" % (prov, exc))
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
            "maxOutputTokens": 900,
            "responseMimeType": "application/json",
        },
    }
    model = pick_model(key, cfg)
    resp = api_call("/models/%s:generateContent" % model, payload, key=key)
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


def handle_turn(user_part, cfg, mem, key, heard_text=""):
    t0 = time.time()
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

    print("  [%.1f second]" % (time.time() - t0))
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
    print("  brain: %s | input: %s | language: %s | voice: %s" % (
        cfg.get("brain", "gemini"), cfg.get("engine"), cfg.get("language"),
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
  python jarvis.py --briefing     subah ki chhoti briefing
  python jarvis.py --vault        vault me kaunsi files hain
  python jarvis.py --import <path>  file/folder/zip vault me daalo (data.txt, notes.zip...)
  python jarvis.py --version
"""


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
        if prov not in ("gemini", "groq", "openrouter", "mistral"):
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
