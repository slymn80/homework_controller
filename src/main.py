# src/main.py
from __future__ import annotations
import os
import mimetypes
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

from .config import settings
from .drive_client import DriveClient
from .utils import read_file_to_text, normalize_download_filename
from .evaluator import evaluate_text
from .reporter import create_report_excel


# MIME ve uzantı eşleştirmesi
ALLOWED_MIMES = {
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/pdf",
    "image/jpeg",
    "image/png",
}

def is_allowed(name: str, mime_type: str) -> bool:
    """
    Dosya tipi filtreleme: MIME veya uzantı bazlı izin kontrolü
    """
    # 1) MIME kontrolü
    if mime_type in ALLOWED_MIMES or mime_type.startswith("image/"):
        return True
    # 2) Uzantı kontrolü
    ext = Path(name).suffix.lower()
    return (not settings.allowed_ext) or (ext in [e.strip().lower() for e in settings.allowed_ext])


def process_once(limit: int | None = None) -> dict:
    """
    Drive'daki dosyaları indirir, değerlendirir, Excel raporu oluşturur ve Drive'a yükler.
    """
    # Google Drive istemcisi
    drive = DriveClient.from_env(
        service_account_json=settings.service_account_json,
        oauth_client_secret_json=settings.oauth_client_secret_json,
        oauth_token_json=settings.oauth_token_json,
    )

    # Kaynak klasördeki dosyaları al
    files = drive.list_files_in_folder(settings.drive_source_folder_id)
    if limit:
        files = files[:limit]

    processed_rows = []
    out_dir = Path(settings.local_output_dir or "outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"🔍 Found {len(files)} files in source folder.")

    for f in tqdm(files, desc="Processing files"):
        fid = f["id"]
        fname = f["name"]
        mime = f.get("mimeType", "")

        # MIME/uzantı filtrele
        if not is_allowed(fname, mime):
            print(f"⏩ Skipping unsupported file: {fname} ({mime})")
            continue

        # Dosya adını MIME'a göre normalize et (ör. JPEG ama uzantısız)
        norm_name = normalize_download_filename(fname, mime)
        local_path = str(out_dir / norm_name)

        # Drive'dan indir
        try:
            drive.download_file(fid, local_path)
        except Exception as e:
            print(f"❌ Download failed for {fname}: {e}")
            continue

        # Dosyadan metin çıkar (OCR dahil)
        try:
            text = read_file_to_text(local_path, ocr_lang=settings.ocr_lang or "tur+eng", mime_type=mime)
        except Exception as e:
            print(f"❌ OCR/Text extraction failed for {fname}: {e}")
            text = ""

        if not text.strip():
            print(f"⚠️ No text extracted from {fname}, skipping.")
            continue

        # OpenAI değerlendirmesi
        try:
            res = evaluate_text(settings.openai_api_key, text, norm_name)
        except Exception as e:
            print(f"❌ Evaluation failed for {fname}: {e}")
            continue

        # Excel satırı
        bd = res.get("breakdown") or {}
        processed_rows.append({
            "filename": norm_name,
            "mime": mime,
            "total": res.get("total"),
            "content": bd.get("content"),
            "structure": bd.get("structure"),
            "language": bd.get("language"),
            "originality": bd.get("originality"),
            "feedback": res.get("feedback"),
        })

    # Rapor oluştur
    today = datetime.now().strftime("%Y-%m-%d")
    report_name = f"{settings.report_prefix}_{today}.xlsx"
    report_path = str(out_dir / report_name)

    if processed_rows:
        create_report_excel(report_path, processed_rows)
    else:
        print("⚠️ No files processed successfully.")
        return {"rows": 0, "local_report": None, "drive_report_link": None}

    # Drive'a yükle
    mime_type = mimetypes.guess_type(report_path)[0] or "application/octet-stream"
    try:
        uploaded_link = drive.upload_file(
            file_path=report_path,
            name=os.path.basename(report_path),
            mime_type=mime_type,
            parent_folder_id=settings.drive_reports_folder_id,
        )
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        uploaded_link = None

    return {
        "rows": len(processed_rows),
        "local_report": report_path,
        "drive_report_link": uploaded_link,
    }


if __name__ == "__main__":
    info = process_once(limit=settings.max_files_per_run or None)
    print("✅ Done:", info)
