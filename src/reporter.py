# src/reporter.py
from __future__ import annotations
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from pathlib import Path
from typing import List, Dict, Any


def create_report_excel(output_path: str, rows: List[Dict[str, Any]]) -> str:
    """
    Değerlendirme sonuçlarını Excel dosyasına yazar.
    rows = [
        {
          "filename": "ödev1.docx",
          "mime": "application/vnd...",
          "total": 85,
          "content": 35,
          "structure": 18,
          "language": 17,
          "originality": 15,
          "feedback": "Metin başarılı, ancak daha net sonuçlar eklenmeli."
        },
        ...
    ]
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Evaluation Report"

    headers = [
        "Filename",
        "MIME Type",
        "Total (0–100)",
        "Content (0–40)",
        "Structure (0–20)",
        "Language (0–20)",
        "Originality (0–20)",
        "Feedback / Comments"
    ]
    ws.append(headers)

    # Başlık biçimi
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4F81BD")
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        ws.column_dimensions[cell.column_letter].width = 22

    # Satırları doldur
    for r in rows:
        ws.append([
            r.get("filename"),
            r.get("mime"),
            r.get("total"),
            (r.get("breakdown") or {}).get("content") if isinstance(r.get("breakdown"), dict) else r.get("content"),
            (r.get("breakdown") or {}).get("structure") if isinstance(r.get("breakdown"), dict) else r.get("structure"),
            (r.get("breakdown") or {}).get("language") if isinstance(r.get("breakdown"), dict) else r.get("language"),
            (r.get("breakdown") or {}).get("originality") if isinstance(r.get("breakdown"), dict) else r.get("originality"),
            r.get("feedback")
        ])

    # Hücre hizalaması
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
