# src/config.py
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List, Optional

def _split_csv(v: Optional[str]) -> List[str]:
    if not v:
        return []
    return [s.strip() for s in v.split(",") if s.strip()]

@dataclass
class Settings:
    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # Google creds (env'de yollar ya da /etc/secrets pathleri)
    service_account_json: Optional[str] = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    oauth_client_secret_json: Optional[str] = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_JSON")
    oauth_token_json: Optional[str] = os.getenv("GOOGLE_OAUTH_TOKEN_JSON")

    # Drive folders
    drive_source_folder_id: str = os.getenv("DRIVE_SOURCE_FOLDER_ID", "")
    drive_reports_folder_id: str = os.getenv("DRIVE_REPORTS_FOLDER_ID", "")
    drive_backup_folder_id: Optional[str] = os.getenv("DRIVE_BACKUP_FOLDER_ID")

    # App behavior
    local_output_dir: str = os.getenv("LOCAL_OUTPUT_DIR", "outputs")
    report_prefix: str = os.getenv("REPORT_PREFIX", "grading-report")

    # 0 = sınırsız (hepsini işle)
    max_files_str: str = os.getenv("MAX_FILES_PER_RUN", "0")
    max_files_per_run: int = 0

    # İzin verilen uzantılar (env’de virgüllü liste)
    allowed_ext: List[str] = field(default_factory=lambda: [".txt", ".docx", ".pdf", ".jpg", ".jpeg", ".png"])

    # 🔴 HATA SEBEBİ: eksikti → eklendi
    ocr_lang: str = os.getenv("OCR_LANG", "tur+eng")

    def __post_init__(self):
        # max_files_per_run sayısal değilse 0 yap
        try:
            self.max_files_per_run = int(self.max_files_str)
        except Exception:
            self.max_files_per_run = 0

        # allowed_ext'i env'den al (varsa)
        env_ext = _split_csv(os.getenv("ALLOWED_EXT"))
        if env_ext:
            # hepsini .küçük harfe çevir
            self.allowed_ext = [e.lower() if e.startswith(".") else f".{e.lower()}" for e in env_ext]

# tekil instance
settings = Settings()
