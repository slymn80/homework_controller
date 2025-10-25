# src/app.py
from __future__ import annotations

from typing import Optional
from fastapi import FastAPI, Query, Body
from pydantic import BaseModel

# process_once fonksiyonunu main.py'den kullanıyoruz
from .main import process_once
from .config import settings

app = FastAPI(
    title="Homework Controller API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ---------- Models ----------
class RunRequest(BaseModel):
    # 0 veya None = sınırsız (settings.MAX_FILES_PER_RUN kullanılır)
    limit: Optional[int] = None


# ---------- Routes ----------
@app.get("/")
def root():
    return {
        "message": "Homework Controller API is running",
        "health": "/health",
        "run": {"GET": "/run?limit=0", "POST": "/run"},
        "docs": "/docs"
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/run")
def run_get(limit: Optional[int] = Query(None, description="0 veya None = sınırsız")):
    """
    Tarayıcıdan kolay tetikleme için GET desteklenir.
    limit=None veya 0 -> tüm uygun dosyaları işler.
    """
    eff_limit = None if (limit is None or limit == 0) else max(0, int(limit))
    info = process_once(limit=eff_limit or (settings.max_files_per_run or None))
    return {"status": "done", "report": info}


@app.post("/run")
def run_post(payload: RunRequest = Body(default=RunRequest())):
    """
    Programatik tetikleme için POST.
    Örn: { "limit": 5 }
    """
    limit = payload.limit
    eff_limit = None if (limit is None or limit == 0) else max(0, int(limit))
    info = process_once(limit=eff_limit or (settings.max_files_per_run or None))
    return {"status": "done", "report": info}
