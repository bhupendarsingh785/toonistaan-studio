#!/usr/bin/env python3
"""
ASTRA SERVER — kahani likho, audio drama banao (web app, FastAPI).

Uploaded v0.1 ke ideas (web UI + SQLite stories) + hamara engine (ASTRA generators,
awaaz.py kirdaar/bhaav, awaaz_studio mahaul+music+master, cinema timeline).

Chalao:
  uvicorn astra.server:app --host 0.0.0.0 --port 8000
  phir browser me: http://localhost:8000

Endpoints:
  GET  /api/health
  GET  /api/stories            (list)
  POST /api/stories            (create: title, scenes)
  GET  /api/stories/{id}
  PUT  /api/stories/{id}
  DELETE /api/stories/{id}
  POST /api/stories/{id}/render  -> mp3 + cue sheet
  GET  /api/sounds             (kaunsi awaazein bana sakte hain)
  POST /api/sound              (ek awaaz banao: text + params)
  GET  /media/<file>           (bani hui audio)
"""
import json
import os
import sqlite3
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MEDIA = os.path.join(ROOT, "storage", "audio")
STATIC = os.path.join(HERE, "static")
DB = os.path.join(ROOT, "storage", "astra.db")
os.makedirs(MEDIA, exist_ok=True)
os.makedirs(os.path.dirname(DB), exist_ok=True)
os.makedirs(STATIC, exist_ok=True)

import sys
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "studio"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

app = FastAPI(title="ASTRA Cinematic Audio", version="1.0.0")
app.mount("/media", StaticFiles(directory=MEDIA), name="media")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ------------------------------------------------------------------ db
def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS stories(
            id TEXT PRIMARY KEY, title TEXT, data TEXT, audio TEXT,
            cues TEXT, created REAL, updated REAL)""")


init_db()


# ------------------------------------------------------------------ models
class StoryIn(BaseModel):
    title: str = Field(default="Meri Kahani", max_length=200)
    scenes: list = Field(default_factory=list)


class SoundIn(BaseModel):
    text: str
    dur: float = 3.0
    dist: float = 1.0
    pan: float = 0.0
    reverb: float = 0.25


# ------------------------------------------------------------------ api
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ASTRA Cinematic Audio", "version": "1.0.0",
            "engine": "astra+awaaz+cinema"}


@app.get("/api/sounds")
def sounds():
    import astra as A
    return {"categories": A.CATEGORIES, "total": sum(len(v) for v in A.CATEGORIES.values())}


@app.post("/api/sound")
def make_sound(p: SoundIn):
    import astra as A
    req = A.SoundRequest(description=p.text, duration=p.dur, distance_m=p.dist,
                         pan=p.pan, reverb=p.reverb)
    arr, meta = A.build(req)
    name = f"sfx_{uuid.uuid4().hex[:8]}.wav"
    path = os.path.join(MEDIA, name)
    A.save_wav(path, arr)
    info = A.qa(arr)
    return {"file": f"/media/{name}", "generator": meta["generator"], "qa": info}


@app.get("/api/stories")
def list_stories():
    with conn() as c:
        rows = c.execute("SELECT id,title,audio,updated FROM stories ORDER BY updated DESC").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/stories")
def create_story(p: StoryIn):
    sid = uuid.uuid4().hex[:10]
    now = time.time()
    with conn() as c:
        c.execute("INSERT INTO stories(id,title,data,created,updated) VALUES(?,?,?,?,?)",
                  (sid, p.title, json.dumps({"scenes": p.scenes}, ensure_ascii=False), now, now))
    return {"id": sid}


@app.get("/api/stories/{sid}")
def get_story(sid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM stories WHERE id=?", (sid,)).fetchone()
    if not r:
        raise HTTPException(404, "story nahi mili")
    d = dict(r)
    d["data"] = json.loads(d["data"] or "{}")
    return d


@app.put("/api/stories/{sid}")
def update_story(sid: str, p: StoryIn):
    with conn() as c:
        c.execute("UPDATE stories SET title=?, data=?, updated=? WHERE id=?",
                  (p.title, json.dumps({"scenes": p.scenes}, ensure_ascii=False), time.time(), sid))
    return {"ok": True}


@app.delete("/api/stories/{sid}")
def delete_story(sid: str):
    with conn() as c:
        c.execute("DELETE FROM stories WHERE id=?", (sid,))
    return {"ok": True}


@app.post("/api/stories/{sid}/render")
def render_story(sid: str):
    """Kahani -> poora audio drama (dialogue + SFX + mahaul + music + master)."""
    with conn() as c:
        r = c.execute("SELECT * FROM stories WHERE id=?", (sid,)).fetchone()
    if not r:
        raise HTTPException(404, "story nahi mili")
    data = json.loads(r["data"] or "{}")
    scenes = data.get("scenes") or []
    if not scenes:
        raise HTTPException(400, "scenes khaali hain")

    import cinema
    tmp_json = os.path.join(MEDIA, f"story_{sid}.json")
    json.dump({"title": r["title"], "scenes": scenes}, open(tmp_json, "w"), ensure_ascii=False, indent=1)
    out = os.path.join(MEDIA, f"astra_{sid}.mp3")
    try:
        cinema.build(tmp_json, out)
    except SystemExit as e:
        raise HTTPException(500, f"render fail: {e}")
    cues = os.path.splitext(out)[0] + ".cues.json"
    with conn() as c:
        c.execute("UPDATE stories SET audio=?, cues=?, updated=? WHERE id=?",
                  (f"/media/astra_{sid}.mp3", f"/media/astra_{sid}.cues.json", time.time(), sid))
    return {"audio": f"/media/astra_{sid}.mp3", "cues": f"/media/astra_{sid}.cues.json"}


@app.get("/", response_class=HTMLResponse)
def home():
    idx = os.path.join(STATIC, "index.html")
    if os.path.exists(idx):
        return open(idx, encoding="utf-8").read()
    return "<h1>ASTRA</h1><p>static/index.html nahi mila</p>"
