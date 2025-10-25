from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, List, Dict

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as SA_Credentials
import io

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata",
]

GOOGLE_DOC_MIMES = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/pdf",
        ".pdf",
    ),
}

class DriveClient:
    def __init__(self, service):
        self.service = service

    # ── OAuth persist ─────────────────────────────────────────────────────────
    @staticmethod
    def _resolve_oauth_paths() -> tuple[Path, Path]:
        seed = os.getenv("GOOGLE_OAUTH_TOKEN_JSON", "/etc/secrets/oauth_token.json")
        persist_rel = os.getenv("OAUTH_TOKEN_PERSIST_PATH", "outputs/oauth_token.json")
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
        persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(Path(seed_path).read_text(encoding="utf-8"))
        persist_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def _build_oauth_creds(cls) -> Credentials:
        seed_path, persist_path = cls._resolve_oauth_paths()
        creds = cls._load_persistent_creds(persist_path)
        if creds is None:
            if not seed_path.exists():
                raise FileNotFoundError(f"OAuth token seed not found: {seed_path}")
            cls._bootstrap_persistent_token(seed_path, persist_path)
            creds = cls._load_persistent_creds(persist_path)
            if creds is None:
                raise RuntimeError("Failed to load persistent OAuth credentials.")
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
            persist_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    @classmethod
    def from_env(
        cls,
        service_account_json: Optional[str] = None,
        oauth_client_secret_json: Optional[str] = None,
        oauth_token_json: Optional[str] = None,
    ):
        oauth_secret = oauth_client_secret_json or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_JSON")
        oauth_token = oauth_token_json or os.getenv("GOOGLE_OAUTH_TOKEN_JSON")
        sa_json = service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

        if oauth_secret and oauth_token:
            creds = cls._build_oauth_creds()
            service = build("drive", "v3", credentials=creds, cache_discovery=False)
            return cls(service)

        if sa_json:
            creds = SA_Credentials.from_service_account_file(sa_json, scopes=SCOPES)
            service = build("drive", "v3", credentials=creds, cache_discovery=False)
            return cls(service)

        raise RuntimeError("No Google credentials provided. Set OAuth or Service Account envs.")

    # ── Public API ────────────────────────────────────────────────────────────
    def list_files_in_folder(self, folder_id: str, page_size: int = 100) -> List[Dict]:
        q = f"'{folder_id}' in parents and trashed = false"
        fields = "nextPageToken, files(id, name, mimeType, modifiedTime, size)"
        files: List[Dict] = []
        page_token = None
        while True:
            resp = self.service.files().list(
                q=q, spaces="drive", pageSize=page_size, fields=fields,
                orderBy="createdTime desc", pageToken=page_token,
            ).execute()
            files.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return files

    def download_file(self, file_id: str, dest_path: str) -> str:
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        p = Path(dest_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(fh.getvalue())
        return str(p)

    def export_file(self, file_id: str, export_mime: str, dest_path: str) -> str:
        data = self.service.files().export(fileId=file_id, mimeType=export_mime).execute()
        p = Path(dest_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return str(p)

    def download_any(self, file_obj: Dict, dest_path: str) -> str:
        fid = file_obj["id"]
        mime = file_obj.get("mimeType", "")
        if mime in GOOGLE_DOC_MIMES:
            export_mime, ext = GOOGLE_DOC_MIMES[mime]
            if not dest_path.lower().endswith(ext):
                dest_path = str(Path(dest_path).with_suffix(ext))
            return self.export_file(fid, export_mime, dest_path)
        return self.download_file(fid, dest_path)

    def ensure_in_folder(self, file_id: str, target_folder_id: str) -> None:
        """Dosyanın gerçekten hedef klasörde olduğundan emin ol (addParents)."""
        meta = self.service.files().get(fileId=file_id, fields="parents").execute()
        parents = set(meta.get("parents", []) or [])
        if target_folder_id not in parents:
            # mevcut parent'lar korunarak hedef eklenir
            self.service.files().update(
                fileId=file_id,
                addParents=target_folder_id,
                fields="id, parents",
            ).execute()

    def upload_file(self, file_path: str, name: str, mime_type: str, parent_folder_id: str) -> dict:
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        body = {"name": name, "parents": [parent_folder_id]}
        file = self.service.files().create(
            body=body, media_body=media, fields="id, webViewLink, parents"
        ).execute()

        # Dosyanın gerçekten doğru klasörde olduğundan emin ol
        try:
            self.service.files().update(
                fileId=file["id"],
                addParents=parent_folder_id,
                fields="id, parents"
            ).execute()
        except Exception as e:
            print(f"⚠️ Folder assignment failed: {e}")

        return file

