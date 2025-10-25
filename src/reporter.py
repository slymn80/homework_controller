from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill

HEADERS = [
    "first_name",
    "last_name",
    "class",
    "student",
    "file_name",
    "file_id",
    "word_count",
    "total",
    "content",
    "structure",
    "language",
    "originality",
    "feedback",
]

def create_report_excel(output_path: str, rows: List[Dict[str, Any]]) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Report"

    ws.append(HEADERS)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4F81BD")
    for col, _h in enumerate(HEADERS, 1):
        c = ws.cell(row=1, column=col)
        c.font = header_font
        c.fill = header_fill
        ws.column_dimensions[c.column_letter].width = 20
    ws.column_dimensions["M"].width = 80  # feedback geniş

    for r in rows:
        bd = r.get("breakdown") or {}
        ws.append([
            r.get("first_name", ""),
            r.get("last_name", ""),
            r.get("class", ""),
            r.get("student", ""),
            r.get("file_name", ""),
            r.get("file_id", ""),
            r.get("word_count", ""),
            r.get("total"),
            bd.get("content", r.get("content")),
            bd.get("structure", r.get("structure")),
            bd.get("language", r.get("language")),
            bd.get("originality", r.get("originality")),
            r.get("feedback", ""),
        ])

    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
