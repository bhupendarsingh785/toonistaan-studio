"""astra-audio — Hugging Face Space (Gradio SDK + FastAPI routes).

GET  /health   -> {"ok": true}
POST /render   -> {"job": id, "state": "queued"}   (placeholder)
GET  /job/{id} -> job ka haal
/              -> chhota Gradio status page
"""
import os
import uuid

import gradio as gr
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

API = FastAPI(title="astra-audio")
JOBS = {}


@API.get("/health")
def health():
    return {"ok": True, "service": "astra-audio"}


@API.post("/render")
def render(body: dict | None = None):
    body = body or {}
    script = str(body.get("script") or "")
    if not script.strip():
        return JSONResponse({"error": "script khaali hai"}, status_code=400)
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"state": "queued", "chars": len(script)}
    return {"job": job_id, "state": "queued"}


@API.get("/job/{job_id}")
def job(job_id: str):
    return JOBS.get(job_id) or JSONResponse({"error": "job nahi mila"}, status_code=404)


def status_text():
    return f"astra-audio chal raha hai. Kul jobs: {len(JOBS)}"


with gr.Blocks(title="astra-audio") as demo:
    gr.Markdown("## astra-audio\nChhota API: `/health`, `/render`, `/job/{id}`")
    out = gr.Textbox(label="Status", value=status_text())
    gr.Button("Refresh").click(status_text, outputs=out)

app = gr.mount_gradio_app(API, demo, path="/")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
