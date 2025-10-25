from __future__ import annotations
import re
from pathlib import Path
from typing import Tuple
from datetime import date

# Latin, Kiril ve Türkçe-Kazakça karakterleri kapsayan küme
CYR_LAT = "A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-яІіҰұӘәӨөҚқҒғҮүҺһÇĞİŞçğışÑñ"
IMAGE_CLASS_SEP = r"[_\-\s]+"  # Dosya adındaki ayırıcılar


def safe_date_str() -> str:
    """Bugünün tarihini ISO biçiminde döndürür."""
    return date.today().isoformat()


def split_camel(token: str) -> list[str]:
    """AhmetYildiz -> ['Ahmet', 'Yildiz']"""
    return re.findall(
        r'[A-ZА-ЯІҰӘӨҚҒҮҺ][a-zа-яіұәөқғүһ]+|[A-ZА-ЯІҰӘӨҚҒҮҺ]+(?=[A-ZА-ЯІҰӘӨҚҒҮҺ]|$)|[a-zа-яіұәөқғүһ]+',
        token,
    )


def parse_meta_from_filename(filename: str) -> tuple[str, str, str]:
    """
    Dosya adından (AhmetYildiz_10A_Tarih.pdf gibi) ad, soyad ve sınıf tahmin eder.
    Boş kalırsa '' döner.
    """
    stem = Path(filename).stem
    parts = [p for p in re.split(IMAGE_CLASS_SEP, stem) if p]

    first_name = ""
    last_name = ""
    grade_class = ""

    # Sınıf kalıbı: 10A, 9-B, 11Ә vb.
    klass_pat = re.compile(
        r'\b(\d{1,2}[A-Za-zА-Яа-яІіҰұӘәӨөҚқҒғҮүҺһ]?(?:[-–][A-Za-zА-Яа-яІіҰұӘәӨөҚқҒғҮүҺһ])?)\b'
    )
    for p in reversed(parts):
        m = klass_pat.search(p)
        if m:
            grade_class = m.group(1)
            break

    if not parts:
        return first_name, last_name, grade_class

    # Sınıf parçasını hariç tutarak aday ad parçalarını al
    name_candidates = [p for p in parts if p != grade_class]
    if not name_candidates:
        return first_name, last_name, grade_class

    # CamelCase durumunu kontrol et
    camel = split_camel(name_candidates[0])
    if len(camel) >= 2:
        return camel[0], camel[1], grade_class

    # İkinci parça varsa soyad olarak al
    if len(name_candidates) >= 2:
        second = name_candidates[1]
        if re.fullmatch(fr'[{CYR_LAT}]+', second):
            first_name, last_name = name_candidates[0], second
        else:
            first_name = name_candidates[0]
    else:
        first_name = name_candidates[0]

    return first_name, last_name, grade_class


def uniquify_path(path: Path) -> Path:
    """
    outputs/grading-report_2025-10-25.xlsx mevcutsa
    -> outputs/grading-report_2025-10-25_1.xlsx, _2.xlsx ... üretir.
    """
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    i = 1
    while True:
        candidate = path.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1
