from __future__ import annotations
from typing import List, Dict, Optional
from pathlib import Path
import io

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from pathlib import Path as _Path

SCOPES = ["https://www.googleapis.com/auth/drive"]

class DriveClient:
    def __init__(self, service=None):
        self.service = service

    @staticmethod
    def from_env(service_account_json: str, oauth_client_secret_json: str, oauth_token_json: str) -> "DriveClient":
        creds = None
        if service_account_json and _Path(service_account_json).exists():
            creds = service_account.Credentials.from_service_account_file(service_account_json, scopes=SCOPES)
        elif oauth_client_secret_json and _Path(oauth_client_secret_json).exists():
            creds = None
            if _Path(oauth_token_json).exists():
                creds = Credentials.from_authorized_user_file(oauth_token_json, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(oauth_client_secret_json, SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(oauth_token_json, "w") as f:
                    f.write(creds.to_json())
        else:
            raise RuntimeError("No Google auth config found. Provide service account or OAuth client secret.")

        service = build("drive", "v3", credentials=creds)
        return DriveClient(service)

    def list_files_in_folder(self, folder_id: str, mime_prefix: Optional[str]=None, page_size: int=100) -> List[Dict]:
        q = f"'{folder_id}' in parents and trashed = false"
        if mime_prefix:
            q += f" and mimeType contains '{mime_prefix}'"
        res = self.service.files().list(q=q, fields="files(id, name, mimeType, modifiedTime, createdTime, webViewLink)", pageSize=page_size).execute()
        return res.get("files", [])

    def download_file(self, file_id: str, dest_path: Path) -> Path:
        req = self.service.files().get_media(fileId=file_id)
        fh = io.FileIO(dest_path, "wb")
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return dest_path

    def upload_file(self, local_path: Path, parent_folder_id: str, mime_type: str="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") -> Dict:
        file_metadata = {"name": local_path.name, "parents": [parent_folder_id]}
        media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
        file = self.service.files().create(body=file_metadata, media_body=media, fields="id, name, webViewLink").execute()
        return file

    def copy_file_to_folder(self, file_id: str, new_name: str, parent_folder_id: str) -> Dict:
        body = {"name": new_name, "parents": [parent_folder_id]}
        return self.service.files().copy(fileId=file_id, body=body, fields="id,name,webViewLink").execute()
