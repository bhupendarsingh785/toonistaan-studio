"""astra-audio — HF Space (sirf FastAPI + uvicorn, koi gradio nahi).

GET  /health    -> {"ok": true}
POST /render    -> {"job": id, "state": "queued"}
GET  /job/{id}  -> job ka haal
/               -> status page
"""
import os
import uuid

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="astra-audio")
JOBS = {}


@app.get("/health")
def health():
    return {"ok": True, "service": "astra-audio"}


@app.post("/render")
def render(body: dict | None = None):
    body = body or {}
    script = str(body.get("script") or "")
    if not script.strip():
        return JSONResponse({"error": "script khaali hai"}, status_code=400)
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"state": "queued", "chars": len(script)}
    return {"job": job_id, "state": "queued"}


@app.get("/job/{job_id}")
def job(job_id: str):
    return JOBS.get(job_id) or JSONResponse({"error": "job nahi mila"}, status_code=404)


@app.get("/", response_class=HTMLResponse)
def home():
    return ("<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<body style='font-family:system-ui;background:#0b1020;color:#e8ecf8;padding:24px'>"
            "<h2>astra-audio chal raha hai</h2>"
            "<p>/health theek hai. Engine jodne par /render chalega.</p></body>")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
