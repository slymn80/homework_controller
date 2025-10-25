from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

def write_excel_report(rows: List[Dict[str, Any]], dest_path: Path) -> Path:
    df = pd.DataFrame(rows)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(dest_path, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Report")
    return dest_path
