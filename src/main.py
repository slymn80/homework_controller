from __future__ import annotations
import os
import mimetypes
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

from .config import settings
from .drive_client import DriveClient
from .utils import read_file_to_text, normalize_download_filename, parse_student_meta
from .evaluator import evaluate_text
from .reporter import create_report_excel

ALLOWED_MIMES = {
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
}

def is_allowed(name: str, mime_type: str) -> bool:
    if mime_type in ALLOWED_MIMES or mime_type.startswith("image/"):
        return True
    ext = Path(name).suffix.lower()
    return (not settings.allowed_ext) or (ext in [e.strip().lower() for e in settings.allowed_ext])

def word_count_of(text: str) -> int:
    return len([w for w in (text or "").split() if w.strip()])

def process_once(limit: int | None = None) -> dict:
    drive = DriveClient.from_env(
        service_account_json=settings.service_account_json,
        oauth_client_secret_json=settings.oauth_client_secret_json,
        oauth_token_json=settings.oauth_token_json,
    )

    files = drive.list_files_in_folder(settings.drive_source_folder_id)
    stats = {"found": len(files), "allowed": 0, "downloaded": 0, "extracted": 0, "evaluated": 0, "skipped": []}
    if limit:
        files = files[:limit]

    processed_rows = []
    out_dir = Path(settings.local_output_dir or "outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    for f in tqdm(files, desc="Processing files"):
        fid = f["id"]
        fname = f["name"]
        mime = f.get("mimeType", "")

        if not is_allowed(fname, mime):
            stats["skipped"].append({"name": fname, "reason": f"not allowed ({mime})"})
            continue
        stats["allowed"] += 1

        norm_name = normalize_download_filename(fname, mime)
        local_path = str(out_dir / norm_name)

        try:
            local_path = drive.download_any(f, local_path)  # Google Docs export dahil
            stats["downloaded"] += 1
        except Exception as e:
            stats["skipped"].append({"name": fname, "reason": f"download error: {e}"})
            continue

        try:
            text = read_file_to_text(local_path, ocr_lang=settings.ocr_lang or "rus+kaz+tur+eng", mime_type=mime)
        except Exception as e:
            stats["skipped"].append({"name": fname, "reason": f"extract error: {e}"})
            continue

        if not text.strip():
            stats["skipped"].append({"name": fname, "reason": "empty text after extract"})
            continue
        stats["extracted"] += 1

        try:
            res = evaluate_text(settings.openai_api_key, text, Path(local_path).name)
            stats["evaluated"] += 1
        except Exception as e:
            stats["skipped"].append({"name": fname, "reason": f"evaluate error: {e}"})
            continue

        # Öğrenci meta (heuristik)
        first_name, last_name, cls, student_full = parse_student_meta(norm_name)

        bd = res.get("breakdown") or {}
        processed_rows.append({
            "first_name": first_name,
            "last_name": last_name,
            "class": cls,
            "student": student_full,
            "file_name": Path(local_path).name,
            "file_id": fid,
            "word_count": word_count_of(text),
            "total": res.get("total"),
            "content": bd.get("content"),
            "structure": bd.get("structure"),
            "language": bd.get("language"),
            "originality": bd.get("originality"),
            "feedback": res.get("feedback"),
        })

    if not processed_rows:
        return {"rows": 0, "local_report": None, "drive_report_link": None, "backup_report_link": None, "stats": stats}

    today = datetime.now().strftime("%Y-%m-%d")
    report_name = f"{settings.report_prefix}_{today}.xlsx"
    report_path = str(out_dir / report_name)
    create_report_excel(report_path, processed_rows)

    mime_type = mimetypes.guess_type(report_path)[0] or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    # Ana klasöre yükle
    uploaded = drive.upload_file(
        file_path=report_path,
        name=os.path.basename(report_path),
        mime_type=mime_type,
        parent_folder_id=settings.drive_reports_folder_id,
    )
    report_link = uploaded.get("webViewLink")
    # Yedek klasöre de yükle (varsa)
    backup_link = None
    if settings.drive_backup_folder_id:
        try:
            backup_file = drive.upload_file(
                file_path=report_path,
                name=os.path.basename(report_path),
                mime_type=mime_type,
                parent_folder_id=settings.drive_backup_folder_id,
            )
            backup_link = backup_file.get("webViewLink")
        except Exception as e:
            print(f"⚠️ Backup upload failed: {e}")

    return {
        "rows": len(processed_rows),
        "local_report": report_path,
        "drive_report_link": report_link,
        "backup_report_link": backup_link,
        "stats": stats,
    }

if __name__ == "__main__":
    info = process_once(limit=settings.max_files_per_run or None)
    print("✅ Done:", info)
