# src/main.py
from __future__ import annotations

import os
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from .config import settings
from .drive_client import DriveClient
from .evaluator import evaluate_text
from .utils import read_file_to_text, normalize_download_filename
from .reporter import create_report_excel
from .reporter_plagiarism import create_plagiarism_excel  # 🔹 yeni satır

# Opsiyonel yardımcılar
try:
    from .meta_extractor import extract_student_meta
except Exception:
    extract_student_meta = None

try:
    from .similarity_checker import find_similar
except Exception:
    find_similar = None


def _ensure_outputs_dir() -> Path:
    outdir = Path(settings.local_output_dir or "outputs")
    outdir.mkdir(parents=True, exist_ok=True)
    return outdir


def _unique_name(base_dir: Path, prefix: str, ext: str) -> Path:
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    base = f"{prefix}_{date_str}{ext}"
    p = base_dir / base
    if not p.exists():
        return p
    k = 1
    while True:
        cand = base_dir / f"{prefix}_{date_str}_{k}{ext}"
        if not cand.exists():
            return cand
        k += 1


def _word_count(text: str) -> int:
    return len((text or "").split())


def _is_allowed(name: str) -> bool:
    ext = Path(name).suffix.lower()
    allowed = [e.strip().lower() for e in (settings.allowed_ext or []) if e.strip()]
    return (not allowed) or (ext in allowed)


def _download_candidates(drive: DriveClient, folder_id: str, limit: Optional[int]):
    files = drive.list_files(folder_id)
    files = [f for f in files if _is_allowed(f.get("name", ""))]
    for f in files:
        f["normalized_name"] = normalize_download_filename(f["name"], f.get("mimeType", ""))
    if limit and limit > 0:
        files = files[:limit]
    return files


def process_once(limit: Optional[int] = None) -> Dict[str, Any]:
    outdir = _ensure_outputs_dir()
    drive = DriveClient.from_env(use_service_account=False)

    stats = {"found": 0, "evaluated": 0, "skipped": []}
    processed_rows: List[Dict[str, Any]] = []

    files = _download_candidates(drive, settings.drive_source_folder_id, limit)
    stats["found"] = len(files)

    for f in files:
        file_id = f["id"]
        fname = f["normalized_name"]

        try:
            local_path = outdir / fname
            drive.download_file(file_id, str(local_path))

            text = read_file_to_text(
                str(local_path),
                ocr_lang=(settings.ocr_lang or "tur+eng+rus+kaz"),
                mime_type=f.get("mimeType", ""),
            )
            if not text:
                stats["skipped"].append({"name": fname, "reason": "empty text"})
                continue

            result = evaluate_text(settings.openai_api_key, text, fname)
            b = result.get("breakdown") or {}

            first_name = last_name = clazz = student_full = ""
            if extract_student_meta:
                first_name, last_name, clazz, student_full = extract_student_meta(fname, text)

            row = {
                "first_name": first_name,
                "last_name": last_name,
                "class": clazz,
                "student": student_full,
                "file_name": fname,
                "file_id": file_id,
                "word_count": _word_count(text),
                "total": int(result.get("total") or 0),
                "content": int(b.get("content") or 0),
                "structure": int(b.get("structure") or 0),
                "language": int(b.get("language") or 0),
                "originality": int(b.get("originality") or 0),
                "feedback": result.get("feedback") or "",
                "text": text,
            }
            processed_rows.append(row)
            stats["evaluated"] += 1

        except Exception as e:
            stats["skipped"].append({"name": fname, "reason": str(e)})

    # ---- Rapor oluşturma ----
    drive_link = plag_drive_link = None
    if processed_rows:
        # grading report
        grading_path = _unique_name(outdir, "grading-report", ".xlsx")
        create_report_excel(str(grading_path), processed_rows)

        if settings.drive_reports_folder_id:
            uploaded = drive.upload_file(
                str(grading_path),
                os.path.basename(grading_path),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                settings.drive_reports_folder_id,
            )
            drive_link = uploaded.get("webViewLink") if isinstance(uploaded, dict) else None

        # plagiarism report (opsiyonel)
        plagiarism_pairs = []
        if find_similar:
            lite = [
                {
                    "file_name": r["file_name"],
                    "file_id": r["file_id"],
                    "student": r["student"],
                    "text": r["text"][:6000],
                }
                for r in processed_rows
            ]
            try:
                plagiarism_pairs = find_similar(lite, threshold=80.0)
            except Exception:
                plagiarism_pairs = []

            if plagiarism_pairs:
                plag_path = _unique_name(outdir, "plagiarism-report", ".xlsx")
                create_plagiarism_excel(str(plag_path), plagiarism_pairs)

                if settings.drive_reports_folder_id:
                    up2 = drive.upload_file(
                        str(plag_path),
                        os.path.basename(plag_path),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        settings.drive_reports_folder_id,
                    )
                    plag_drive_link = up2.get("webViewLink") if isinstance(up2, dict) else None

    return {
        "status": "done",
        "report": {
            "evaluated": stats["evaluated"],
            "skipped": stats["skipped"],
            "grading_drive_link": drive_link,
            "plagiarism_drive_link": plag_drive_link,
        },
    }


if __name__ == "__main__":
    try:
        result = process_once(limit=settings.max_files_per_run or None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e), "trace": traceback.format_exc()}, ensure_ascii=False))
        raise
