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

# İsteğe bağlı modüller (varsa kullan, yoksa sessiz geç)
try:
    from .meta_extractor import extract_student_meta  # yeni yardımcı
except Exception:  # pragma: no cover
    extract_student_meta = None  # type: ignore

try:
    from .similarity_checker import find_similar  # opsiyonel
except Exception:  # pragma: no cover
    find_similar = None  # type: ignore


def _ensure_outputs_dir() -> Path:
    outdir = Path(settings.local_output_dir or "outputs")
    outdir.mkdir(parents=True, exist_ok=True)
    return outdir


def _unique_report_path(base_dir: Path, prefix: str = None) -> Path:
    """
    grading-report_YYYY-MM-DD.xlsx,
    aynı gün ikinci kez üretimde grading-report_YYYY-MM-DD_1.xlsx, _2.xlsx...
    """
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    pre = prefix or (settings.report_prefix or "grading-report")
    base_name = f"{pre}_{date_str}.xlsx"
    p = base_dir / base_name
    if not p.exists():
        return p
    # sırayı arttır
    k = 1
    while True:
        cand = base_dir / f"{pre}_{date_str}_{k}.xlsx"
        if not cand.exists():
            return cand
        k += 1


def _is_allowed(name: str) -> bool:
    ext = Path(name).suffix.lower()
    allowed = [e.strip().lower() for e in (settings.allowed_ext or []) if e.strip()]
    return (not allowed) or (ext in allowed)


def _word_count(text: str) -> int:
    return len((text or "").split())


def _download_candidates(
    drive: DriveClient, source_folder_id: str, limit: Optional[int]
) -> List[Dict[str, Any]]:
    """Kaynak klasördeki dosyaları listele."""
    files: List[Dict[str, Any]] = drive.list_files(source_folder_id)
    # filtrele uzantıya göre
    files = [f for f in files if _is_allowed(f.get("name", ""))]
    # normalize isim
    for f in files:
        name = f.get("name", "")
        mime = f.get("mimeType", "")
        f["normalized_name"] = normalize_download_filename(name, mime)
    # limitle
    if limit is not None and limit > 0:
        files = files[:limit]
    return files


def process_once(limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Ana işleyici: indir → metin çıkar → değerlendir → rapor yaz → Drive'a yükle.
    """
    outdir = _ensure_outputs_dir()

    # Drive istemcisi (OAuth token’lı)
    drive = DriveClient.from_env(
        # OAuth akışını kullanıyoruz (service account değil)
        use_service_account=False
    )

    stats = {"found": 0, "allowed": 0, "downloaded": 0, "extracted": 0, "evaluated": 0}
    skipped: List[Dict[str, str]] = []
    processed_rows: List[Dict[str, Any]] = []

    # İşlenecek dosyalar
    files = _download_candidates(drive, settings.drive_source_folder_id, limit)
    stats["found"] = len(files)
    stats["allowed"] = len(files)

    for f in files:
        file_id = f["id"]
        fname = f["normalized_name"]
        try:
            # 1) indir
            local_path = Path(outdir) / fname
            drive.download_file(file_id, str(local_path))
            stats["downloaded"] += 1

            # 2) metni çıkar (OCR dilini ayarlardan al)
            text = read_file_to_text(
                str(local_path),
                ocr_lang=(settings.ocr_lang or "tur+eng+rus+kaz"),
                mime_type=f.get("mimeType", ""),
            )
            if not text:
                skipped.append({"name": fname, "reason": "empty text (extract failed)"})
                continue
            stats["extracted"] += 1

            # 3) değerlendir
            result = evaluate_text(settings.openai_api_key, text, fname)
            # tolerans: total yoksa 0 yap
            total = int(result.get("total") or 0)
            b = result.get("breakdown") or {}
            content = int(b.get("content") or 0)
            structure = int(b.get("structure") or 0)
            language = int(b.get("language") or 0)
            originality = int(b.get("originality") or 0)
            feedback = result.get("feedback") or json.dumps(result, ensure_ascii=False)

            # 4) öğrenci meta (dosya adından; yoksa metinden)
            first_name = last_name = clazz = student_full = ""
            if extract_student_meta:
                first_name, last_name, clazz, student_full = extract_student_meta(
                    fname, text
                )

            # 5) rapor satırı
            row = {
                "first_name": first_name,
                "last_name": last_name,
                "class": clazz,
                "student": student_full,
                "file_name": fname,
                "file_id": file_id,
                "word_count": _word_count(text),
                "total": total,
                "content": content,
                "structure": structure,
                "language": language,
                "originality": originality,
                "feedback": feedback,
                # rapor dışında faydalı olabilecek ham veri
                "text": text,
            }
            processed_rows.append(row)
            stats["evaluated"] += 1

        except Exception as e:  # tek dosya hatası tüm akışı durdurmasın
            skipped.append(
                {"name": fname, "reason": f"{type(e).__name__}: {str(e)}"}
            )

    # Hiç satır yoksa rapor oluşturma
    drive_link = None
    local_report = None
    if processed_rows:
        report_path = _unique_report_path(outdir, settings.report_prefix or "grading-report")
        create_report_excel(str(report_path), processed_rows)
        local_report = str(report_path)

        # Drive'a yükle (raporlar klasörü zorunlu)
        if settings.drive_reports_folder_id:
            uploaded = drive.upload_file(
                local_path=str(report_path),
                name=os.path.basename(str(report_path)),
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                parent_folder_id=settings.drive_reports_folder_id,
            )
            # upload_file string döndürüyorsa link üret
            if isinstance(uploaded, dict):
                drive_link = uploaded.get("webViewLink") or uploaded.get("webViewURL")
            else:
                # sadece ID döndüyse linki kendimiz kurmaya çalışalım
                drive_link = drive.build_file_link(str(uploaded))

    # İsteğe bağlı: kopya/benzerlik analizi (modül varsa)
    plagiarism_pairs = []
    if find_similar and processed_rows:
        # sadece gerekli alanları geçir (metin uzun ise çok yer kaplamasın)
        lite = [
            {
                "file_name": r.get("file_name"),
                "file_id": r.get("file_id"),
                "student": r.get("student"),
                "text": r.get("text", "")[:6000],  # sınırla (performans)
            }
            for r in processed_rows
        ]
        try:
            plagiarism_pairs = find_similar(lite, threshold=80.0)
        except Exception:
            plagiarism_pairs = []

    return {
        "status": "done",
        "report": {
            "rows": len(processed_rows),
            "local_report": local_report,
            "drive_report_link": drive_link,
            "stats": {**stats, "skipped": skipped},
        },
        # opsiyonel bilgi (UI'de görmek istersen)
        "plagiarism_pairs": plagiarism_pairs,
    }


if __name__ == "__main__":
    # Lokal çalıştırma: .env okunur, limit ENV veya argümanla verilebilir.
    try:
        lim = settings.max_files_per_run or None
        info = process_once(limit=lim)
        print(json.dumps(info, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "trace": traceback.format_exc()
        }, ensure_ascii=False))
        raise
