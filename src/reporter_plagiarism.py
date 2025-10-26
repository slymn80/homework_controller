from openpyxl import Workbook
from datetime import datetime
from pathlib import Path

def create_plagiarism_excel(path: str, pairs):
    if not pairs:
        return None
    wb = Workbook()
    ws = wb.active
    ws.title = "Plagiarism"

    ws.append(["file_a", "file_b", "student_a", "student_b",
               "combined(%)", "token_set(%)", "jaccard(%)"])

    for p in pairs:
        ws.append([
            p.get("file_a"), p.get("file_b"),
            p.get("student_a"), p.get("student_b"),
            round(p.get("combined", 0), 2),
            round(p.get("rf_token_set", 0), 2),
            round(p.get("jaccard_3gram", 0), 2)
        ])

    wb.save(path)
    return path
