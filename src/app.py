# src/app.py
from __future__ import annotations

from pathlib import Path
import traceback
from typing import Optional

from fastapi import FastAPI, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .main import process_once
from .config import settings

app = FastAPI(
    title="Homework Controller API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------- Models ----------
class RunRequest(BaseModel):
    # 0 veya None = sınırsız (settings.MAX_FILES_PER_RUN devreye girer)
    limit: Optional[int] = None


# ---------- Helpers ----------
def _check_writable(dir_path: Path) -> tuple[bool, str]:
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        p = dir_path / ".write_test.tmp"
        p.write_text("ok", encoding="utf-8")
        p.unlink(missing_ok=True)
        return True, ""
    except Exception as e:
        return False, str(e)


# ---------- Routes ----------
@app.get("/")
def root():
    return {
        "message": "Homework Controller API is running",
        "health": "/health",
        "run": {"GET": "/run?limit=0", "POST": "/run"},
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/diag")
def diag():
    """
    Prod ortamında hızlı teşhis: gizli içerik dökmez.
    """
    svc_path = Path(settings.service_account_json) if settings.service_account_json else None
    svc_exists = bool(svc_path and svc_path.exists())

    writable, werr = _check_writable(Path(settings.local_output_dir))

    return {
        "openai_key_present": bool(settings.openai_api_key and settings.openai_api_key.startswith("sk-")),
        "service_account_json_path": settings.service_account_json or "",
        "service_account_json_exists": svc_exists,
        "drive_source_folder_id_set": bool(settings.drive_source_folder_id),
        "drive_reports_folder_id_set": bool(settings.drive_reports_folder_id),
        "drive_backup_folder_id_set": bool(settings.drive_backup_folder_id),
        "outputs_dir": str(settings.local_output_dir),
        "outputs_writable": writable,
        "outputs_error": werr,
        "allowed_ext": settings.allowed_ext,
        "using_oauth": bool(settings.oauth_client_secret_json),
    }


@app.get("/run")
def run_get(limit: Optional[int] = Query(None, description="0 veya None = sınırsız")):
    """
    Tarayıcıdan kolay tetikleme için GET desteklenir.
    limit=None veya 0 -> tüm uygun dosyaları işler.
    """
    try:
        eff_limit = None if (limit is None or limit == 0) else max(0, int(limit))
        info = process_once(limit=eff_limit or (settings.max_files_per_run or None))
        return {"status": "done", "report": info}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "trace": traceback.format_exc()[:6000]},
        )


@app.post("/run")
def run_post(payload: RunRequest = Body(default=RunRequest())):
    """
    Programatik tetikleme için POST. Örn: { "limit": 5 }
    """
    try:
        limit = payload.limit
        eff_limit = None if (limit is None or limit == 0) else max(0, int(limit))
        info = process_once(limit=eff_limit or (settings.max_files_per_run or None))
        return {"status": "done", "report": info}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "trace": traceback.format_exc()[:6000]},
        )
