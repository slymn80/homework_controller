from __future__ import annotations
from fastapi import FastAPI
from .config import settings
from .main import process_once
from .schemas import RunRequest

app = FastAPI(title="Assignment Evaluator")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/run")
def run(req: RunRequest):
    report_info = process_once(limit=req.limit or settings.max_files_per_run)
    return {"status": "done", "report": report_info}
