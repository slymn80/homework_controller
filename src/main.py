from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm

from .config import settings
from .drive_client import DriveClient
from .extractor import extract_text
from .evaluator import evaluate_text
from .report_writer import write_excel_report
from .utils import (
    parse_meta_from_filename,
    safe_date_str,
    uniquify_path,
)

import os
import mimetypes


def _select_files(files: List[dict], allowed_ext: list[str]) -> List[dict]:
    """Google Drive dosya listesini uzantıya göre filtrele."""
    allowed = set(e.lower() for e in allowed_ext)
    return [f for f in files if Path(f["name"]).suffix.lower() in allowed]


def process_once(limit: int | None = None) -> Dict[str, Any]:
    """
    Tek geçişte:
      - Kaynak klasörden dosyaları al
      - Metni çıkar
      - OpenAI ile değerlendir
      - Excel'e yaz ve Drive'a yükle (+ opsiyonel yedek)
    """
    settings.ensure_dirs()

    # Google Drive istemcisi
    drive = DriveClient.from_env(
        settings.service_account_json,
        settings.oauth_client_secret_json,
        settings.oauth_token_json,
    )

    # Kaynak klasördeki aday dosyalar
    files = drive.list_files_in_folder(settings.drive_source_folder_id)
    files = _select_files(files, settings.allowed_ext)

    if limit and limit > 0:
        files = files[:limit]

    rows: List[Dict[str, Any]] = []
    tmpdir = Path(".tmp")
    tmpdir.mkdir(exist_ok=True)

    for f in tqdm(files, desc="Processing files"):
        fid = f["id"]
        fname = f["name"]
        local = tmpdir / fname

        # İndir
        drive.download_file(fid, local)

        # Metni çıkar
        text = extract_text(local)
        if not text.strip():
            # Boş/okunamaz ise atla
            continue

        # Dosya adından meta: Ad, Soyad, Sınıf
        first_name, last_name, grade_class = parse_meta_from_filename(fname)

        # Değerlendir
        res = evaluate_text(settings.openai_api_key, text, fname)
        total = res.get("total")
        br = res.get("breakdown", {}) or {}
        feedback = res.get("feedback", "")

        rows.append(
            {
                # Yeni sütunlar
                "first_name": first_name,
                "last_name": last_name,
                "class": grade_class,

                # Geriye dönük "student" alanı da dursun
                "student": (f"{first_name} {last_name}").strip() or first_name or last_name,

                # Dosya bilgileri
                "file_name": fname,
                "file_id": fid,
                "word_count": len(text.split()),

                # Puan kırılımı
                "total": total,
                "content": br.get("content"),
                "structure": br.get("structure"),
                "language": br.get("language"),
                "originality": br.get("originality"),

                # Yorum
                "feedback": feedback,
            }
        )

    if not rows:
        return {"message": "No files or no extractable text", "uploaded": None}

    # Rapor adını oluştur (tarih bazlı) ve benzersizleştir (_1, _2...)
    day = safe_date_str()
    local_name = f"{settings.report_prefix}_{day}.xlsx"
    local_path = settings.local_output_dir / local_name
    local_path = uniquify_path(local_path)

    # Excel'e yaz
    write_excel_report(rows, local_path)

    # Drive'a yükle (n8n tetikler)
    mime_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    uploaded = drive.upload_file(
        file_path=local_path,
        name=os.path.basename(local_path),
        mime_type=mime_type,
        parent_folder_id=settings.drive_reports_folder_id,
    )
    web_link = uploaded.get("webViewLink")

    # Opsiyonel yedek kopya
    backup_link = None
    if settings.drive_backup_folder_id:
        copy = drive.copy_file_to_folder(uploaded["id"], local_path.name, settings.drive_backup_folder_id)
        backup_link = copy.get("webViewLink")

    return {
        "local_report": str(local_path),
        "drive_report_link": web_link,
        "backup_link": backup_link,
        "rows": len(rows),
    }


if __name__ == "__main__":
    info = process_once(limit=settings.max_files_per_run or None)
    print(info)
