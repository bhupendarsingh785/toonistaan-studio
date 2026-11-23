"""astra-audio — chhota FastAPI wrapper (Catalyst AppSail / kisi bhi host ke liye).

GET  /            status page
GET  /health      {"ok": true}
POST /render      {"script": "...", "bed_db": -16} -> job id
GET  /job/{id}    job ka haal
GET  /audio/{id}.wav  bani hui file
"""
from __future__ import annotations
import os, subprocess, sys, threading, uuid
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get("ASTRA_OUT", "/tmp/astra-out"))
OUT.mkdir(parents=True, exist_ok=True)
JOBS: dict = {}
app = FastAPI(title="astra-audio")


def _run(job_id: str, script: str) -> None:
    txt = OUT / f"{job_id}.txt"
    txt.write_text(script, encoding="utf-8")
    JOBS[job_id].update(state="running")
    try:
        cmd = [sys.executable, str(ROOT / "tools" / "sutradhar.py"), "run", str(txt), str(OUT / job_id)]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        ok = p.returncode == 0
        JOBS[job_id].update(state="done" if ok else "failed",
                            log=(p.stdout or "")[-4000:] + (p.stderr or "")[-2000:],
                            file=f"/audio/{job_id}.wav" if ok else None)
    except Exception as e:  # noqa: BLE001
        JOBS[job_id].update(state="failed", log=f"{type(e).__name__}: {e}")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/render")
def render(body: dict | None = None):
    body = body or {}
    script = str(body.get("script") or "")
    if not script.strip():
        return JSONResponse({"error": "script khaali hai"}, status_code=400)
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"state": "queued", "file": None, "log": ""}
    threading.Thread(target=_run, args=(job_id, script), daemon=True).start()
    return {"job": job_id}


@app.get("/job/{job_id}")
def job(job_id: str):
    return JOBS.get(job_id) or JSONResponse({"error": "job nahi mila"}, status_code=404)


@app.get("/audio/{job_id}.wav")
def audio(job_id: str):
    p = OUT / job_id / "kahani.wav"
    if not p.exists():
        return JSONResponse({"error": "file nahi bani"}, status_code=404)
    return FileResponse(str(p), media_type="audio/wav")


@app.get("/", response_class=HTMLResponse)
def home():
    return ("<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<body style='font-family:system-ui;background:#0b1020;color:#e8ecf8;padding:24px'>"
            "<h2>astra-audio chal raha hai</h2>"
            "<p>POST /render {'script':'...'} se kahani banao, GET /job/&lt;id&gt; se haal.</p></body>")
