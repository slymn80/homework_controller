# src/drive_client.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as SA_Credentials

# ---- SCOPES: token üretirken kullandıklarınla birebir aynı olsun ----
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.file",
]

class DriveClient:
    def __init__(self, service):
        self.service = service

    # ------------------------------------------------------------------
    # OAuth token'ı kalıcı diskte tutan yardımcılar
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_oauth_paths() -> tuple[Path, Path]:
        """
        Returns (seed_token_path, persistent_token_path)
        seed_token_path: Secret Files (read-only) -> GOOGLE_OAUTH_TOKEN_JSON
        persistent_token_path: Mounted disk (writable) -> OAUTH_TOKEN_PERSIST_PATH
        """
        seed = os.getenv("GOOGLE_OAUTH_TOKEN_JSON", "/etc/secrets/oauth_token.json")
        persist_rel = os.getenv("OAUTH_TOKEN_PERSIST_PATH", "outputs/oauth_token.json")
        # app çalışma kökü /app, o yüzden relatif yolu /app/ ile birleştiriyoruz
        persist_abs = Path("/app") / persist_rel
        return Path(seed), persist_abs

    @staticmethod
    def _load_persistent_creds(persist_path: Path) -> Optional[Credentials]:
        if persist_path.exists():
            try:
                return Credentials.from_authorized_user_file(str(persist_path), SCOPES)
            except Exception:
                return None
        return None

    @staticmethod
    def _bootstrap_persistent_token(seed_path: Path, persist_path: Path) -> None:
        """
        İlk çalışma: /etc/secrets'taki read-only token dosyasını
        writeable kalıcı diske kopyalar.
        """
        persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(Path(seed_path).read_text(encoding="utf-8"))
        persist_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def _build_oauth_creds(cls) -> Credentials:
        seed_path, persist_path = cls._resolve_oauth_paths()

        # 1) Kalıcı kopya varsa onu kullan
        creds = cls._load_persistent_creds(persist_path)

        # 2) Yoksa Secret Files'tan tohumla
        if creds is None:
            if not seed_path.exists():
                raise FileNotFoundError(f"OAuth token seed not found: {seed_path}")
            cls._bootstrap_persistent_token(seed_path, persist_path)
            creds = cls._load_persistent_creds(persist_path)
            if creds is None:
                raise RuntimeError("Failed to load persistent OAuth credentials.")

        # 3) Gerekirse refresh et ve HER ZAMAN kalıcı dosyaya geri yaz
        if not creds.valid:
            if creds.refresh_token:
                creds.refresh(Request())
            # güncel içeriği persist dosyasına yaz
            persist_path.write_text(creds.to_json(), encoding="utf-8")

        return creds

    # ------------------------------------------------------------------
    @classmethod
    def from_env(cls,
                 service_account_json: Optional[str] = None,
                 oauth_client_secret_json: Optional[str] = None,
                 oauth_token_json: Optional[str] = None):
        """
        Seçici: OAuth env varsa OAuth kullanır; yoksa Service Account.
        """
        oauth_secret = oauth_client_secret_json or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_JSON")
        oauth_token = oauth_token_json or os.getenv("GOOGLE_OAUTH_TOKEN_JSON")
        sa_json = service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

        if oauth_secret and oauth_token:
            # OAuth (kullanıcı hesabı)
            creds = cls._build_oauth_creds()
            service = build("drive", "v3", credentials=creds, cache_discovery=False)
            return cls(service)

        if sa_json:
            # Service Account
            creds = SA_Credentials.from_service_account_file(sa_json, scopes=SCOPES)
            service = build("drive", "v3", credentials=creds, cache_discovery=False)
            return cls(service)

        raise RuntimeError("No Google credentials provided. Set OAuth or Service Account envs.")

    # --- aşağıda kullandığın Drive işlemleri (örnek) ---
    def upload_file(self, file_path: str, name: str, mime_type: str, parent_folder_id: str) -> str:
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        body = {"name": name, "parents": [parent_folder_id]}
        file = self.service.files().create(body=body, media_body=media, fields="id, webViewLink").execute()
        return file["webViewLink"]
