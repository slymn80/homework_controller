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
from .reporter_plagiarism import create_plagiarism_excel  # 🔹 eklendi

try:
    from .similarity_checker import find_similar
except Exception:
    find_similar = None


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
            local_path = drive.download_any(f, local_path)
            stats["downloaded"] += 1
        except Exception as e:
            stats["skipped"].append({"name": fname, "reason": f"download error: {e}"})
            continue

        try:
            text_raw = read_file_to_text(local_path, ocr_lang=settings.ocr_lang or "rus+kaz+tur+eng", mime_type=mime)
        except Exception as e:
            stats["skipped"].append({"name": fname, "reason": f"extract error: {e}"})
            continue

        clean_text = (text_raw or "").replace("\x0c", " ").strip()
        if not clean_text or len(clean_text.split()) < 3:
            stats["skipped"].append({"name": fname, "reason": "empty or unreadable text"})
            continue
        stats["extracted"] += 1

        try:
            res = evaluate_text(settings.openai_api_key, clean_text, Path(local_path).name)
            stats["evaluated"] += 1
        except Exception as e:
            stats["skipped"].append({"name": fname, "reason": f"evaluate error: {e}"})
            continue

        # 🧠 Ad-soyad-sınıf bilgisi: dosya adında yoksa metinden bulmaya çalış
        first_name, last_name, cls, student_full = parse_student_meta(norm_name, clean_text)
        if not student_full and clean_text:
            import re
            m = re.search(r"(?i)\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\b", clean_text[:200])
            if m:
                first_name, last_name = m.group(1), m.group(2)
                student_full = f"{first_name} {last_name}"

        bd = res.get("breakdown") or {}

        processed_rows.append({
            "first_name": first_name,
            "last_name": last_name,
            "class": cls,
            "student": student_full,
            "file_name": Path(local_path).name,
            "file_id": fid,
            "word_count": word_count_of(clean_text),
            "total": res.get("total"),
            "content": bd.get("content"),
            "structure": bd.get("structure"),
            "language": bd.get("language"),
            "originality": bd.get("originality"),
            "feedback": res.get("feedback"),
            "breakdown": bd,
            "text": clean_text,
        })

    if not processed_rows:
        return {"rows": 0, "local_report": None, "drive_report_link": None, "stats": stats}

    today = datetime.now().strftime("%Y-%m-%d")
    base_name = f"{settings.report_prefix}_{today}.xlsx"
    unique_name = drive.unique_name_in_folder(base_name, settings.drive_reports_folder_id)

    report_path = out_dir / unique_name
    create_report_excel(str(report_path), processed_rows)

    mime_type = mimetypes.guess_type(str(report_path))[0] or \
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    uploaded = drive.upload_file(
        file_path=str(report_path),
        name=unique_name,
        mime_type=mime_type,
        parent_folder_id=settings.drive_reports_folder_id,
    )
    report_link = uploaded.get("webViewLink")

    # 🔍 Kopya (plagiarism) kontrolü
    plag_link = None
    if find_similar:
        lite = [
            {
                "file_name": r["file_name"],
                "student": r["student"],
                "text": r["text"][:6000],
            }
            for r in processed_rows
        ]
        try:
            pairs = find_similar(lite, threshold=80.0)
            if pairs:
                plag_name = drive.unique_name_in_folder(f"plagiarism_{today}.xlsx", settings.drive_reports_folder_id)
                plag_path = out_dir / plag_name
                create_plagiarism_excel(str(plag_path), pairs)

                up2 = drive.upload_file(
                    file_path=str(plag_path),
                    name=plag_name,
                    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    parent_folder_id=settings.drive_reports_folder_id,
                )
                plag_link = up2.get("webViewLink")
        except Exception as e:
            print(f"[warn] plagiarism check failed: {e}")

    return {
        "rows": len(processed_rows),
        "local_report": str(report_path),
        "drive_report_link": report_link,
        "plagiarism_drive_link": plag_link,
        "stats": stats,
    }


if __name__ == "__main__":
    info = process_once(limit=settings.max_files_per_run or None)
    print("✅ Done:", info)
