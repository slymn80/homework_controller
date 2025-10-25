from __future__ import annotations
import re
import os
from pathlib import Path
from typing import Tuple, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Ad Soyad / Sınıf ayıklama
# ─────────────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    s = s.replace("_", " ").replace("-", " ").replace(".", " ")
    s = re.sub(r"\s+", " ", s, flags=re.UNICODE).strip()
    return s

# 10A / 7/B / 9Г / 8-Ә gibi
_CLASS_PATTERNS = [
    r"(\b\d{1,2}\s*[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ]\b)",
    r"(\b\d{1,2}\s*[-/]\s*[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ]\b)",
    r"(?:sınıfı|sınıf|sinif|grade|class|класс|сынып)\s*[:\-]?\s*(\d{1,2}\s*[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ])",
]

def _find_class(text: str) -> Optional[str]:
    for pat in _CLASS_PATTERNS:
        m = re.search(pat, text, flags=re.IGNORECASE | re.UNICODE)
        if m:
            return _norm(m.group(1)).replace(" ", "")
    return None

def _name_from_filename(name_wo_ext: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    s = _norm(name_wo_ext)
    cls = _find_class(s)
    if cls:
        s = re.sub(r"(?i)(sınıfı|sınıf|sinif|grade|class|класс|сынып)\s*[:\-]?\s*"+re.escape(cls), " ", s)
        s = s.replace(cls, " ")
    s = _norm(s)
    tokens = [t for t in s.split(" ") if re.search(r"[A-Za-zА-Яа-яЁёĞÜŞİÖÇğüşiöçӘәІіҚқҢңҰұҮүҺһ]", t)]
    first = tokens[0] if len(tokens) >= 1 else None
    last  = tokens[1] if len(tokens) >= 2 else None
    return first, last, cls

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
    parts = [p for p in line.split(" ") if p]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return (parts[0] if parts else None), None

def _name_class_from_text(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not text:
        return None, None, None
    snippet = _norm(text[:600])
    cls = _find_class(snippet)
    if not cls:
        for pat in _TEXT_CLASS_PATTERNS:
            m = re.search(pat, snippet, flags=re.IGNORECASE | re.UNICODE)
            if m:
                cls = _norm(m.group(1)).replace(" ", "")
                break
    first, last = None, None
    for pat in _TEXT_NAME_PATTERNS:
        m = re.search(pat, snippet, flags=re.IGNORECASE | re.UNICODE)
        if m:
            first, last = _split_name_line(m.group(1))
            break
    return first, last, cls

def parse_student_meta(filename: str, text: Optional[str] = None) -> Tuple[str, str, str, str]:
    """
    Dönüş: (first_name, last_name, class, student_full)
    Önce dosya adından, sonra metnin içinden dener.
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
# Dosya adı normalize (indirilen türlere uygun uzantı)
# ─────────────────────────────────────────────────────────────────────────────

def normalize_download_filename(name: str, mime_type: str) -> str:
    """
    Google Docs/Sheets/Slides export edildiğinde uygun uzantıyı eklemek için.
    """
    p = Path(name)
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return str(p.with_suffix(".docx").name)
    if mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        return str(p.with_suffix(".xlsx").name)
    if mime_type == "application/pdf":
        return str(p.with_suffix(".pdf").name)
    # images/text default
    return p.name

# ─────────────────────────────────────────────────────────────────────────────
# Metin çıkarma (TXT/DOCX/PDF/IMG)
# ─────────────────────────────────────────────────────────────────────────────

def read_file_to_text(path: str, ocr_lang: str = "tur+eng+rus+kaz", mime_type: Optional[str] = None) -> str:
    """
    TXT: utf-8 olarak oku
    DOCX: docx2txt varsa onu kullan; yoksa python-docx basit paragraf birleştir
    PDF: pdfminer.six varsa onu kullan; yoksa boş döner
    IMG: PIL+pytesseract ile OCR
    """
    p = Path(path)
    ext = p.suffix.lower()
    mime = (mime_type or "").lower()

    # --- TEXT ---
    if ext == ".txt" or mime.startswith("text/"):
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return p.read_text(errors="ignore")

    # --- DOCX ---
    if ext == ".docx" or "officedocument.wordprocessingml.document" in mime:
        try:
            import docx2txt  # type: ignore
            return docx2txt.process(str(p)) or ""
        except Exception:
            try:
                import docx  # type: ignore
                doc = docx.Document(str(p))
                return "\n".join([para.text for para in doc.paragraphs])
            except Exception:
                return ""

    # --- PDF ---
    if ext == ".pdf" or mime == "application/pdf":
        try:
            from pdfminer.high_level import extract_text  # type: ignore
            return extract_text(str(p)) or ""
        except Exception:
            return ""

    # --- IMAGES (jpg/jpeg/png) ---
    if ext in {".jpg", ".jpeg", ".png"} or (mime.startswith("image/")):
        try:
            from PIL import Image  # type: ignore
            import pytesseract  # type: ignore
            img = Image.open(str(p))
            # OCR dili: ortamdan gelen 'ocr_lang' formatı tesseract ile uyumlu olmalı
            # Örn: "tur+eng+rus+kaz" → "tur+eng+rus+kaz"
            text = pytesseract.image_to_string(img, lang=ocr_lang)
            return text or ""
        except Exception:
            return ""

    # Diğer türler: şimdilik boş
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
