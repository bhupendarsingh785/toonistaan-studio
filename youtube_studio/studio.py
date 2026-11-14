#!/usr/bin/env python3
"""
YouTube Studio Autopilot - koi extra package nahi chahiye (sirf Python 3.9+).

Commands:
  python studio.py add-channel NAME            naya channel config mein jodo
  python studio.py auth-url NAME               login link banao (user browser mein khole)
  python studio.py auth-finish NAME "URL/CODE" login ke baad wala link/code paste karo
  python studio.py check NAME                  token aur channel ka naam check karo
  python studio.py enqueue NAME video.mp4 meta.json [thumb.jpg] [subs.srt]
  python studio.py plan NAME [--dry-run]       queue ke video agle khali slots par upload (scheduled)
  python studio.py status                      sab channels ka haal
  python studio.py branding NAME branding.json description/keywords/banner/playlists set karo
  python studio.py playlist NAME "Title" ["desc"] nayi playlist

Secrets (client secret, refresh token) sirf secrets/ folder mein rehte hain, kabhi print nahi hote.
"""
import json, os, sys, time, uuid, shutil, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(ROOT, "config.json")
SECRETS = os.path.join(ROOT, "secrets")
QUEUE = os.path.join(ROOT, "queue")
LOGS = os.path.join(ROOT, "logs")
IST = timezone(timedelta(hours=5, minutes=30))
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
REDIRECT = "http://localhost"
CHUNK = 8 * 1024 * 1024  # 256KB ka guna
UPLOAD_UNITS, THUMB_UNITS, CAPTION_UNITS = 1600, 50, 400
DAILY_QUOTA = 10000

DEFAULT_CHANNEL = {
    "client_secret_file": "secrets/client_secret.json",
    "slots_ist": ["10:00", "18:00"],
    "max_uploads_per_day": 2,
    "privacy_after_publish": "public",
    "category_id": "1",
    "default_language": "hi",
    "made_for_kids": False,
    "contains_synthetic_media": True,
    "default_tags": ["hindi", "cartoon", "kahani"],
}

# ---------- helpers ----------
def die(msg):
    print("❌ " + msg); sys.exit(1)

def load_config():
    if not os.path.exists(CONFIG):
        return {"channels": {}}
    with open(CONFIG) as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def channel(cfg, name):
    ch = cfg["channels"].get(name)
    if not ch:
        die(f"Channel '{name}' config mein nahi hai. Pehle: python studio.py add-channel {name}")
    return ch

def write_secret(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)

def client_creds(ch):
    p = os.path.join(ROOT, ch["client_secret_file"])
    if not os.path.exists(p):
        die(f"Client secret file nahi mili: {ch['client_secret_file']} (Google Cloud se download karke yahan rakho)")
    with open(p) as f:
        d = json.load(f)
    d = d.get("installed") or d.get("web") or d
    return d["client_id"], d["client_secret"]

def token_path(name):
    return os.path.join(SECRETS, f"token_{name}.json")

def http(method, url, data=None, headers=None, timeout=120):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()

def log(name, entry):
    os.makedirs(LOGS, exist_ok=True)
    entry["time_ist"] = datetime.now(IST).isoformat(timespec="seconds")
    with open(os.path.join(LOGS, f"{name}.jsonl"), "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def read_log(name):
    p = os.path.join(LOGS, f"{name}.jsonl")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return [json.loads(l) for l in f if l.strip()]

# ---------- auth ----------
def cmd_add_channel(name):
    cfg = load_config()
    if name in cfg["channels"]:
        print(f"ℹ️ '{name}' pehle se hai."); return
    cfg["channels"][name] = dict(DEFAULT_CHANNEL)
    save_config(cfg)
    print(f"✅ Channel '{name}' juda. config.json mein slots/limit badal sakte ho.")

def cmd_auth_url(name):
    ch = channel(load_config(), name)
    cid, _ = client_creds(ch)
    q = urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
        "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent select_account",
        "state": name,
    })
    print("👉 Yeh link browser mein kholo, SAHI Google ID chuno, aur jis channel par upload karna hai use chuno:\n")
    print("https://accounts.google.com/o/oauth2/v2/auth?" + q)
    print("\nAllow ke baad page 'nahi khula' dikhayega - koi baat nahi. Upar address bar ka POORA link copy karke bhejo.")

def cmd_auth_finish(name, pasted):
    ch = channel(load_config(), name)
    cid, csec = client_creds(ch)
    code = pasted.strip()
    if "code=" in code:
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query).get("code", [""])[0]
    if not code:
        die("Link mein code nahi mila. Poora address bar wala link bhejo.")
    body = urllib.parse.urlencode({"code": code, "client_id": cid, "client_secret": csec,
                                   "redirect_uri": REDIRECT, "grant_type": "authorization_code"}).encode()
    st, _, raw = http("POST", "https://oauth2.googleapis.com/token", body,
                      {"Content-Type": "application/x-www-form-urlencoded"})
    d = json.loads(raw or b"{}")
    if st != 200 or "refresh_token" not in d:
        die(f"Login fail ({st}): {d.get('error_description') or d.get('error') or 'refresh token nahi mila'}. auth-url dobara chalao.")
    write_secret(token_path(name), {"refresh_token": d["refresh_token"]})
    print("✅ Login safal. Token surakshit save hua.")
    cmd_check(name)

def access_token(name):
    ch = channel(load_config(), name)
    cid, csec = client_creds(ch)
    p = token_path(name)
    if not os.path.exists(p):
        die(f"'{name}' login nahi hai. Chalao: python studio.py auth-url {name}")
    with open(p) as f:
        rt = json.load(f)["refresh_token"]
    body = urllib.parse.urlencode({"refresh_token": rt, "client_id": cid, "client_secret": csec,
                                   "grant_type": "refresh_token"}).encode()
    st, _, raw = http("POST", "https://oauth2.googleapis.com/token", body,
                      {"Content-Type": "application/x-www-form-urlencoded"})
    d = json.loads(raw or b"{}")
    if st != 200:
        if d.get("error") == "invalid_grant":
            die("Token expire/radd ho gaya. Wajah aksar: OAuth app 'Testing' mode mein hai (7 din mein expire). "
                "Google Cloud > OAuth consent screen > 'Publish app' karo, phir auth-url dobara.")
        die(f"Token refresh fail ({st}): {d.get('error')}")
    return d["access_token"]

def cmd_check(name):
    tok = access_token(name)
    st, _, raw = http("GET", "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                      headers={"Authorization": "Bearer " + tok})
    d = json.loads(raw or b"{}")
    items = d.get("items") or []
    if st == 200 and items:
        print(f"✅ Juda hua channel: {items[0]['snippet']['title']} (id {items[0]['id']})")
    else:
        die(f"Channel nahi mila ({st}). Login ke waqt sahi channel chuna tha?")

# ---------- queue ----------
def cmd_enqueue(name, video, meta, thumb=None, subs=None):
    channel(load_config(), name)
    for p in [video, meta] + [x for x in (thumb, subs) if x]:
        if not os.path.exists(p):
            die(f"File nahi mili: {p}")
    with open(meta) as f:
        m = json.load(f)
    if not m.get("title"):
        die("meta.json mein 'title' zaroori hai.")
    if len(m["title"]) > 100:
        die("Title 100 akshar se lamba hai.")
    item = os.path.join(QUEUE, name, datetime.now(IST).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4])
    os.makedirs(item)
    shutil.copy(video, os.path.join(item, "video" + os.path.splitext(video)[1]))
    shutil.copy(meta, os.path.join(item, "meta.json"))
    if thumb: shutil.copy(thumb, os.path.join(item, "thumb" + os.path.splitext(thumb)[1]))
    if subs: shutil.copy(subs, os.path.join(item, "subs.srt"))
    print(f"✅ Queue mein juda: {os.path.basename(item)}")

def pending(name):
    d = os.path.join(QUEUE, name)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, x) for x in os.listdir(d)
                  if not os.path.exists(os.path.join(d, x, "uploaded.json")))

def find(item, prefix):
    for f in os.listdir(item):
        if f.startswith(prefix):
            return os.path.join(item, f)
    return None

# ---------- scheduling ----------
def used_today(name, day):
    units, uploads = 0, 0
    for e in read_log(name):
        if e.get("event") == "uploaded" and e["time_ist"][:10] == day:
            units += e.get("units", UPLOAD_UNITS); uploads += 1
    return units, uploads

def next_slots(ch, name, count):
    taken = {e["publish_at_ist"] for e in read_log(name) if e.get("event") == "uploaded" and e.get("publish_at_ist")}
    now = datetime.now(IST) + timedelta(minutes=20)
    out, day = [], now.date()
    while len(out) < count and (day - now.date()).days < 60:
        for s in sorted(ch["slots_ist"]):
            h, m = map(int, s.split(":"))
            t = datetime(day.year, day.month, day.day, h, m, tzinfo=IST)
            if t > now and t.isoformat() not in taken:
                out.append(t)
                if len(out) == count: break
        day += timedelta(days=1)
    return out

# ---------- upload ----------
def resumable_upload(tok, path, metadata):
    size = os.path.getsize(path)
    url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    st, hd, raw = http("POST", url, json.dumps(metadata).encode(), {
        "Authorization": "Bearer " + tok, "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/*"})
    if st != 200:
        raise RuntimeError(f"Upload shuru nahi hua ({st}): {raw[:300].decode(errors='ignore')}")
    session = hd.get("Location") or hd.get("location")
    sent, tries = 0, 0
    with open(path, "rb") as f:
        while True:
            f.seek(sent)
            chunk = f.read(CHUNK)
            end = sent + len(chunk) - 1
            try:
                st, hd, raw = http("PUT", session, chunk, {
                    "Authorization": "Bearer " + tok, "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {sent}-{end}/{size}"}, timeout=600)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                st, raw = 0, str(e).encode()
            if st in (200, 201):
                return json.loads(raw)
            if st == 308:
                rng = hd.get("Range") or hd.get("range")
                sent = int(rng.split("-")[1]) + 1 if rng else 0
                tries = 0
                print(f"   ⬆️ {sent * 100 // size}%")
                continue
            if st in (0, 500, 502, 503, 504) and tries < 6:
                tries += 1
                time.sleep(min(60, 2 ** tries))
                st2, hd2, body2 = http("PUT", session, b"", {"Authorization": "Bearer " + tok,
                                                         "Content-Range": f"bytes */{size}"})
                if st2 in (200, 201):
                    return json.loads(body2)
                rng = hd2.get("Range") or hd2.get("range")
                sent = int(rng.split("-")[1]) + 1 if rng else 0
                continue
            raise RuntimeError(f"Upload fail ({st}): {raw[:300].decode(errors='ignore')}")

def set_thumbnail(tok, vid, path):
    ctype = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    with open(path, "rb") as f:
        st, _, raw = http("POST", f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}&uploadType=media",
                          f.read(), {"Authorization": "Bearer " + tok, "Content-Type": ctype})
    return st == 200, raw[:200].decode(errors="ignore")

def add_captions(tok, vid, path, lang):
    b = "studio" + uuid.uuid4().hex
    meta = json.dumps({"snippet": {"videoId": vid, "language": lang, "name": "Hindi" if lang == "hi" else lang}})
    with open(path, "rb") as f:
        srt = f.read()
    body = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
            f"--{b}\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + srt + f"\r\n--{b}--".encode()
    st, _, raw = http("POST", "https://www.googleapis.com/upload/youtube/v3/captions?part=snippet&uploadType=multipart",
                      body, {"Authorization": "Bearer " + tok, "Content-Type": f"multipart/related; boundary={b}"})
    return st == 200, raw[:200].decode(errors="ignore")

def build_metadata(ch, m, publish_at):
    tags = list(dict.fromkeys((m.get("tags") or []) + ch.get("default_tags", [])))[:30]
    desc = m.get("description", "")
    if m.get("credits"):
        desc += "\n\nCredits:\n" + "\n".join(m["credits"])
    status = {"privacyStatus": "private", "selfDeclaredMadeForKids": m.get("made_for_kids", ch["made_for_kids"]),
              "containsSyntheticMedia": m.get("contains_synthetic_media", ch["contains_synthetic_media"])}
    if publish_at:
        status["publishAt"] = publish_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif ch["privacy_after_publish"] == "public":
        status["privacyStatus"] = "public"
    return {"snippet": {"title": m["title"], "description": desc[:5000], "tags": tags,
                        "categoryId": str(m.get("category_id", ch["category_id"])),
                        "defaultLanguage": ch["default_language"], "defaultAudioLanguage": ch["default_language"]},
            "status": status}

def cmd_plan(name, dry=False):
    cfg = load_config(); ch = channel(cfg, name)
    items = pending(name)
    if not items:
        print("ℹ️ Queue khali hai."); return
    slots = next_slots(ch, name, len(items))
    tok = None if dry else access_token(name)
    for item, slot in zip(items, slots):
        day = slot.strftime("%Y-%m-%d")
        units, ups = used_today(name, datetime.now(IST).strftime("%Y-%m-%d"))
        if not dry and (ups >= ch["max_uploads_per_day"] or units + UPLOAD_UNITS > DAILY_QUOTA - 500):
            print("⏸️ Aaj ki limit poori. Baaki kal."); break
        with open(os.path.join(item, "meta.json")) as f:
            m = json.load(f)
        md = build_metadata(ch, m, slot)
        print(f"📅 {m['title']}  →  {slot.strftime('%d %b %I:%M %p')} IST")
        if dry:
            continue
        try:
            res = resumable_upload(tok, find(item, "video"), md)
            vid = res["id"]; used = UPLOAD_UNITS; notes = []
            th = find(item, "thumb")
            if th:
                ok, msg = set_thumbnail(tok, vid, th); used += THUMB_UNITS
                notes.append("thumbnail ok" if ok else f"thumbnail fail (channel verify chahiye?): {msg}")
            sb = os.path.join(item, "subs.srt")
            if os.path.exists(sb):
                ok, msg = add_captions(tok, vid, sb, ch["default_language"]); used += CAPTION_UNITS
                notes.append("subtitles ok" if ok else f"subtitles fail: {msg}")
            if m.get("playlist"):
                ok = add_to_playlist(tok, ch, vid, m["playlist"]); used += 50
                notes.append("playlist ok" if ok else "playlist fail")
            info = {"video_id": vid, "url": f"https://youtu.be/{vid}", "publish_at_ist": slot.isoformat(), "notes": notes}
            write_secret(os.path.join(item, "uploaded.json"), info)
            log(name, {"event": "uploaded", "units": used, "title": m["title"], **info})
            print(f"✅ Upload: {info['url']} | {', '.join(notes) or 'done'}")
        except Exception as e:
            log(name, {"event": "error", "title": m["title"], "error": str(e)[:500]})
            print(f"❌ {m['title']}: {e}")
            if "quota" in str(e).lower():
                break


# ---------- channel branding / playlists ----------
def api_json(method, url, tok, body=None):
    st, _, raw = http(method, url, json.dumps(body).encode() if body is not None else None,
                      {"Authorization": "Bearer " + tok, "Content-Type": "application/json; charset=UTF-8"})
    d = json.loads(raw or b"{}")
    if st not in (200, 201):
        raise RuntimeError(f"{st}: {d.get('error', {}).get('message', d)}")
    return d

def cmd_branding(name, path):
    with open(path) as f:
        b = json.load(f)
    tok = access_token(name)
    me = api_json("GET", "https://www.googleapis.com/youtube/v3/channels?part=brandingSettings&mine=true", tok)["items"][0]
    bs = me.get("brandingSettings", {})
    chs = bs.get("channel", {})
    for k in ("description", "country", "defaultLanguage", "unsubscribedTrailer"):
        if b.get(k): chs[k] = b[k]
    if b.get("keywords"):
        chs["keywords"] = " ".join(f'"{k}"' if " " in k else k for k in b["keywords"])
    body = {"id": me["id"], "brandingSettings": {"channel": chs}}
    if b.get("banner") and os.path.exists(os.path.join(ROOT, b["banner"])):
        bp = os.path.join(ROOT, b["banner"])
        ctype = "image/png" if bp.lower().endswith(".png") else "image/jpeg"
        with open(bp, "rb") as f:
            st, _, raw = http("POST", "https://www.googleapis.com/upload/youtube/v3/channelBanners/insert?uploadType=media",
                              f.read(), {"Authorization": "Bearer " + tok, "Content-Type": ctype})
        if st == 200:
            body["brandingSettings"]["image"] = {"bannerExternalUrl": json.loads(raw)["url"]}
            print("✅ Banner upload hua")
        else:
            print(f"⚠️ Banner fail ({st}): {raw[:200].decode(errors='ignore')}")
    api_json("PUT", "https://www.googleapis.com/youtube/v3/channels?part=brandingSettings", tok, body)
    print("✅ Channel description, keywords, desh aur bhasha set ho gaye")
    for pl in b.get("playlists", []):
        cmd_playlist(name, pl["title"], pl.get("description", ""), tok)
    print("ℹ️ Profile photo (logo) API se nahi lagti; wo YouTube app se lagayein.")

def cmd_playlist(name, title, desc="", tok=None):
    tok = tok or access_token(name)
    cfg = load_config(); ch = channel(cfg, name)
    pls = ch.setdefault("playlists", {})
    if title in pls:
        print(f"ℹ️ Playlist pehle se: {title}"); return pls[title]
    d = api_json("POST", "https://www.googleapis.com/youtube/v3/playlists?part=snippet,status", tok,
                 {"snippet": {"title": title, "description": desc, "defaultLanguage": ch["default_language"]},
                  "status": {"privacyStatus": "public"}})
    pls[title] = d["id"]; save_config(cfg)
    print(f"✅ Playlist bani: {title}")
    return d["id"]

def add_to_playlist(tok, ch, vid, playlist):
    pid = ch.get("playlists", {}).get(playlist, playlist)
    st, _, raw = http("POST", "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet",
                      json.dumps({"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).encode(),
                      {"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    return st == 200

def cmd_status():
    cfg = load_config()
    if not cfg["channels"]:
        print("Koi channel nahi. python studio.py add-channel NAAM"); return
    today = datetime.now(IST).strftime("%Y-%m-%d")
    for n, ch in cfg["channels"].items():
        units, ups = used_today(n, today)
        login = "✅" if os.path.exists(token_path(n)) else "❌ login baaki"
        print(f"📺 {n}: login {login} | queue {len(pending(n))} | aaj upload {ups}/{ch['max_uploads_per_day']} | quota ~{units}/{DAILY_QUOTA} | slots {', '.join(ch['slots_ist'])} IST")

def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    c, rest = a[0], a[1:]
    try:
        if c == "add-channel": cmd_add_channel(rest[0])
        elif c == "auth-url": cmd_auth_url(rest[0])
        elif c == "auth-finish": cmd_auth_finish(rest[0], rest[1])
        elif c == "check": cmd_check(rest[0])
        elif c == "enqueue": cmd_enqueue(*rest)
        elif c == "plan": cmd_plan(rest[0], "--dry-run" in rest)
        elif c == "status": cmd_status()
        elif c == "branding": cmd_branding(rest[0], rest[1])
        elif c == "playlist": cmd_playlist(rest[0], rest[1], rest[2] if len(rest) > 2 else "")
        else: print(__doc__)
    except IndexError:
        print(__doc__)

if __name__ == "__main__":
    main()
