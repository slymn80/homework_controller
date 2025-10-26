# src/meta_extractor.py
from __future__ import annotations
from pathlib import Path
import re
from typing import Tuple, Optional

# Basit normalize
def _norm(s: str) -> str:
    s = s.replace("_", " ").replace("-", " ").replace(".", " ")
    s = re.sub(r"\s+", " ", s, flags=re.UNICODE).strip()
    return s

# 10A / 7-B / 9Г / 8Ә...
_CLASS_PATTERNS = [
    r"(\b\d{1,2}\s*[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ]\b)",
    r"(\b\d{1,2}\s*[-/]\s*[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ]\b)",
    r"(?:sınıfı|sınıf|sinif|grade|class|класс|сынып)\s*[:\-]?\s*(\d{1,2}\s*[-/]?\s*[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ])",
]

def _find_class(text: str) -> Optional[str]:
    for pat in _CLASS_PATTERNS:
        m = re.search(pat, text, re.I | re.UNICODE)
        if m:
            return _norm(m.group(1)).replace(" ", "")
    return None

def _split_name(line: str):
    parts = [p for p in _norm(line).split(" ") if p]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return (parts[0] if parts else ""), ""

# Dosya adından (varsa) çek
def from_filename(filename: str):
    stem = Path(filename).stem
    s = _norm(stem)
    cls = _find_class(s)
    if cls:
        s = re.sub(r"(?i)(sınıfı|sınıf|sinif|grade|class|класс|сынып)\s*[:\-]?\s*" + re.escape(cls), " ", s)
        s = s.replace(cls, " ")
    tokens = [t for t in s.split(" ") if re.search(r"[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ]", t)]
    first = tokens[0] if len(tokens) > 0 else ""
    last  = tokens[1] if len(tokens) > 1 else ""
    return first, last, (cls or "")

# Metin içinden (başlık/etiket) çek
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

def from_text(text: str):
    snippet = _norm(text[:800])
    cls = _find_class(snippet)
    if not cls:
        for pat in _TEXT_CLASS_PATTERNS:
            m = re.search(pat, snippet, re.I | re.UNICODE)
            if m:
                cls = _norm(m.group(1)).replace(" ", "")
                break
    first, last = "", ""
    for pat in _TEXT_NAME_PATTERNS:
        m = re.search(pat, snippet, re.I | re.UNICODE)
        if m:
            first, last = _split_name(m.group(1))
            break
    return first, last, (cls or "")

def extract_student_meta(filename: str, text: Optional[str] = None):
    """
    Önce dosya adından, yoksa metinden: (first_name, last_name, class, student_full)
    """
    f1, l1, c1 = from_filename(filename)
    f2 = l2 = c2 = ""
    if (not f1 or not l1 or not c1) and text:
        f2, l2, c2 = from_text(text)
    first = f1 or f2
    last  = l1 or l2
    cls   = c1 or c2
    student = (first + " " + last).strip()
    return first, last, cls, student
