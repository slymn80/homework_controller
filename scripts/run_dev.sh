#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export UVICORN_RELOAD=1
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
