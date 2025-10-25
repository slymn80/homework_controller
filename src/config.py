from __future__ import annotations
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

@dataclass
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    service_account_json: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    oauth_client_secret_json: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_JSON", "").strip()
    oauth_token_json: str = os.getenv("GOOGLE_OAUTH_TOKEN_JSON", "creds/oauth_token.json").strip()

    drive_source_folder_id: str = os.getenv("DRIVE_SOURCE_FOLDER_ID", "").strip()
    drive_reports_folder_id: str = os.getenv("DRIVE_REPORTS_FOLDER_ID", "").strip()
    drive_backup_folder_id: str = os.getenv("DRIVE_BACKUP_FOLDER_ID", "").strip()

    allowed_ext: list[str] = field(default_factory=lambda: [e.strip().lower() for e in os.getenv("ALLOWED_EXT", ".txt,.docx,.pdf").split(",")])
    local_output_dir: Path = Path(os.getenv("LOCAL_OUTPUT_DIR", "outputs"))
    max_files_per_run: int = int(os.getenv("MAX_FILES_PER_RUN", "0"))
    report_prefix: str = os.getenv("REPORT_PREFIX", "grading-report")

    def ensure_dirs(self) -> None:
        self.local_output_dir.mkdir(parents=True, exist_ok=True)
        Path("creds").mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_dirs()
