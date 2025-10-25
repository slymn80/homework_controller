
# Assignment Evaluator (Google Drive → OpenAI → Excel → Drive)

A small web service + CLI that:
1. Reads new assignment files from a Google Drive folder (`DRIVE_SOURCE_FOLDER_ID`).
2. Extracts text (`.txt`, `.docx`, `.pdf`).
3. Sends text to OpenAI for rubric-based evaluation (score + feedback).
4. Writes an Excel report named with **today's date** into `LOCAL_OUTPUT_DIR` (e.g., `outputs/2025-10-25.xlsx`).
5. Uploads the report into `DRIVE_REPORTS_FOLDER_ID` on Google Drive (so your n8n **Google Drive Trigger** can send it to Telegram).
6. Optionally uploads a second copy to `DRIVE_BACKUP_FOLDER_ID`.

> Designed to work well with n8n: point your **Google Drive Trigger** to the reports folder so any new report file triggers your Telegram flow automatically.

---

## 1) Directory Layout

```
assignment-evaluator/
├─ .env.example
├─ requirements.txt
├─ README.md
├─ creds/
│  ├─ service_account.json            # (recommended) put your service account JSON here
│  └─ oauth_client_secret.json        # (optional) if you use OAuth installed app
├─ scripts/
│  ├─ run_dev.sh
│  └─ run_once.sh
└─ src/
   ├─ app.py
   ├─ main.py
   ├─ config.py
   ├─ drive_client.py
   ├─ extractor.py
   ├─ evaluator.py
   ├─ report_writer.py
   ├─ utils.py
   └─ schemas.py
```

---

## 2) Setup

### A) Python env
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### B) Environment variables
1. Copy `.env.example` → `.env` and fill values.
2. Put your Google **service account** JSON into `creds/service_account.json` **(recommended)**.
   - Share the **source**, **reports**, and **backup** Drive folders with the service account email.
3. Alternatively, use **OAuth user auth** (installed app):
   - Put client secret at `creds/oauth_client_secret.json`.
   - First run will open a browser to grant access and save a token to `creds/oauth_token.json`.

### C) OpenAI
Set `OPENAI_API_KEY` in `.env`.

---

## 3) How to Run

### Option 1: FastAPI service (for manual triggers or platform schedulers)
```bash
uvicorn src.app:app --host 0.0.0.0 --port 8000
```
- Health check: `GET /health`
- Trigger a run now: `POST /run` (JSON body optional; see `src/schemas.py`)

### Option 2: CLI (cron-ready)
```bash
python -m src.main
# or limit processed files this run:
MAX_FILES_PER_RUN=10 python -m src.main
```

### Option 3: helper scripts
```bash
bash scripts/run_dev.sh    # starts FastAPI with autoreload
bash scripts/run_once.sh   # runs single grading pass then exits
```

---

## 4) n8n Integration

- Set your **Google Drive Trigger** to watch `DRIVE_REPORTS_FOLDER_ID`.
- Each run creates a file like:
  - `{REPORT_PREFIX}_{YYYY-MM-DD}.xlsx`
- In n8n, pass file name and created time to **Telegram** node along with the Drive file link.

---

## 5) Notes

- Supported inputs: `.txt`, `.docx`, `.pdf` (images via OCR are optional; add Tesseract if needed).
- Student name is parsed from file name up to the first `_` or `-` (fallback: whole name).
- The rubric is inside `src/evaluator.py`; adjust as you wish.
- If you expect huge files, consider chunking before sending to OpenAI.

---

## 6) Minimal Cron Example (Linux)

Edit crontab:
```
0 18 * * * cd /path/to/assignment-evaluator && . .venv/bin/activate && python -m src.main >> logs.txt 2>&1
```
This runs daily at 18:00 (Asia/Almaty).
