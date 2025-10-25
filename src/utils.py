from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple
import mimetypes

from PIL import Image
import pytesseract
from pdfminer.high_level import extract_text as pdf_extract_text
from pdf2image import convert_from_path
from docx import Document

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
PDF_MIME = "application/pdf"

def guess_ext_from_mime(mime: Optional[str]) -> str:
    if not mime:
        return ""
    if mime.startswith("image/jpeg"):
        return ".jpg"
    if mime.startswith("image/png"):
        return ".png"
    if mime == PDF_MIME:
        return ".pdf"
    return mimetypes.guess_extension(mime) or ""

def normalize_download_filename(name: str, mime_type: Optional[str]) -> str:
    p = Path(name)
    if p.suffix:
        return name
    ext = guess_ext_from_mime(mime_type) or ""
    return p.name + ext

def read_file_to_text(path: str, ocr_lang: str = "tur+eng", mime_type: Optional[str] = None) -> str:
    p = Path(path)
    ext = p.suffix.lower()

    if ext == ".txt":
        try:
            return p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return p.read_text(encoding="latin-1")

    if ext == ".docx":
        doc = Document(str(p))
        return "\n".join(para.text for para in doc.paragraphs)

    if ext == ".pdf" or (mime_type == PDF_MIME):
        try:
            text = pdf_extract_text(str(p)) or ""
        except Exception:
            text = ""
        if text.strip():
            return text
        try:
            pages = convert_from_path(str(p))
            chunks = [pytesseract.image_to_string(img, lang=ocr_lang) for img in pages]
            return "\n".join(chunks)
        except Exception:
            return ""

    if ext in IMAGE_EXTS or (mime_type and mime_type.startswith("image/")):
        img = Image.open(str(p))
        return pytesseract.image_to_string(img, lang=ocr_lang)

    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""

def parse_student_meta(filename: str) -> Tuple[str, str, str, str]:
    """
    Heuristik: 'Ad Soyad - Sınıf - ...'  veya  'ad_soyad_sinif_...' gibi
    Dönüş: (first_name, last_name, class, student_fullname)
    """
    stem = Path(filename).stem
    # dash formatı
    if " - " in stem:
        parts = [p.strip() for p in stem.split(" - ") if p.strip()]
        if len(parts) >= 2:
            name = parts[0]
            cls = parts[1]
            fn, ln = (name.split(" ", 1) + [""])[:2]
            return fn, ln, cls, name
    # underscore formatı
    parts = [p for p in stem.replace("-", "_").split("_") if p]
    if len(parts) >= 3:
        fn = parts[0].title()
        ln = parts[1].title()
        cls = parts[2]
        return fn, ln, cls, f"{fn} {ln}"
    return "", "", "", ""
