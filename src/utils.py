# src/utils.py
from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Tuple, Optional

# Basit normalleştirici
def _norm(s: str) -> str:
    s = s.replace("_", " ").replace("-", " ").replace(".", " ")
    s = re.sub(r"\s+", " ", s, flags=re.UNICODE).strip()
    return s

# Sınıf kodunu ayıkla (10A, 10-A, 7/B, 7B, 8-C, 11К vb.)
_CLASS_PATTERNS = [
    r"(\b\d{1,2}\s*[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ]\b)",   # 10A / 7B / 9Г / 8Ә
    r"(\b\d{1,2}\s*[-/]\s*[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ]\b)", # 10-A / 7/B
    r"(?:sınıfı|sınıf|sinif|grade|class|класс|сынып)\s*[:\-]?\s*(\d{1,2}\s*[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ])",
]

def _find_class(text: str) -> Optional[str]:
    for pat in _CLASS_PATTERNS:
        m = re.search(pat, text, flags=re.IGNORECASE | re.UNICODE)
        if m:
            return _norm(m.group(1)).replace(" ", "")
    return None

# Dosya adından ad-soyad yakala: "Ahmet_Yılmaz_10A", "Yılmaz Ahmet 10-A",
# "Ivan Petrov 7Б", "Aty Zhoni 8Ә" vb.
def _name_from_filename(name_wo_ext: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    s = _norm(name_wo_ext)

    # Önce sınıfı çek
    cls = _find_class(s)

    # Sınıf ibaresini atıp kalanını parçala
    if cls:
        s_wo_cls = re.sub(r"(?i)(sınıfı|sınıf|sinif|grade|class|класс|сынып)\s*[:\-]?\s*"+re.escape(cls), " ", s)
        s_wo_cls = s_wo_cls.replace(cls, " ")
    else:
        s_wo_cls = s

    s_wo_cls = _norm(s_wo_cls)

    # Harflerden oluşan tokenları al
    tokens = [t for t in s_wo_cls.split(" ") if re.search(r"[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ]", t)]

    # Çok sayıda token olabilir. En güvenlisi ilk iki anlamlı tokenı ad/soyad varsaymak.
    first = tokens[0] if len(tokens) >= 1 else None
    last  = tokens[1] if len(tokens) >= 2 else None

    # Tek token varsa soyadı boş bırak.
    return first, last, cls

# Metnin içinden yakala (Adı Soyadı, Name Surname, Имя Фамилия, Аты Жөні, Class/Sınıf/Класс/Sынып)
_TEXT_NAME_PATTERNS = [
    r"(?:adı\s*soyadı|adi\s*soyadi|ad[\s:]+soyad|isim\s*soyisim)\s*[:\-]?\s*([^\n\r,;]+)",
    r"(?:name\s*surname|student\s*name)\s*[:\-]?\s*([^\n\r,;]+)",
    r"(?:имя\s*фамилия)\s*[:\-]?\s*([^\n\r,;]+)",
    r"(?:аты\s*жөні|аты\s*жони|аты-жөні)\s*[:\-]?\s*([^\n\r,;]+)",
]

_TEXT_CLASS_PATTERNS = [
    r"(?:sınıfı|sınıf|sinif|grade|class)\s*[:\-]?\s*([0-9]{1,2}\s*[-/]?\s*[A-Za-z])",
    r"(?:класс)\s*[:\-]?\s*([0-9]{1,2}\s*[-/]?\s*[А-Яа-яЁё])",
    r"(?:сынып)\s*[:\-]?\s*([0-9]{1,2}\s*[-/]?\s*[ӘәІіҚқҢңҰұҮүҺһA-Za-z])",
]

def _split_name_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    line = _norm(line)
    # "Ahmet Yılmaz" / "İvan Петров" vb.
    parts = [p for p in line.split(" ") if p]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return parts[0] if parts else None, None

def _name_class_from_text(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not text:
        return None, None, None
    snippet = _norm(text[:500])  # İlk 500 karakter içinde ara

    # Önce sınıf
    cls = _find_class(snippet)
    if not cls:
        for pat in _TEXT_CLASS_PATTERNS:
            m = re.search(pat, snippet, flags=re.IGNORECASE | re.UNICODE)
            if m:
                cls = _norm(m.group(1)).replace(" ", "")
                break

    # Sonra ad-soyad
    first, last = None, None
    for pat in _TEXT_NAME_PATTERNS:
        m = re.search(pat, snippet, flags=re.IGNORECASE | re.UNICODE)
        if m:
            first, last = _split_name_line(m.group(1))
            break

    return first, last, cls

def parse_student_meta(filename: str, text: Optional[str] = None) -> Tuple[str, str, str, str]:
    """
    DÖNÜŞ: (first_name, last_name, class, student_full)
    - Önce dosya adından dener.
    - Bulamazsa metnin içinden dener.
    - Yine bulamazsa boş alanları "" döndürür.
    """
    name_wo_ext = Path(filename).stem

    f1, l1, c1 = _name_from_filename(name_wo_ext)

    f2, l2, c2 = (None, None, None)
    if (not f1 or not l1 or not c1) and text:
        f2, l2, c2 = _name_class_from_text(text)

    first = f1 or f2 or ""
    last  = l1 or l2 or ""
    cls   = (c1 or c2 or "")

    student_full = (first + " " + last).strip()
    return first, last, cls, student_full


# ─────────────────────────────────────────────────────────────────────────────
# Mevcut diğer yardımcılarınız burada durabilir; ör. normalize_download_filename, read_file_to_text vs.
# Bu dosyada onlar zaten vardıysa aynen bırakın.
