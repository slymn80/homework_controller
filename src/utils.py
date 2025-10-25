# src/utils.py
from __future__ import annotations

import io
import os
import mimetypes
from pathlib import Path
from typing import Tuple, Optional

from PIL import Image
import pytesseract

# PDF için iki aşama: pdfminer (metin katmanı) + pdf2image (OCR fallback)
from pdfminer.high_level import extract_text as pdf_extract_text
from pdf2image import convert_from_path

# DOCX
from docx import Document


IMAGE_MIME_PREFIXES = ("image/jpeg", "image/png", "image/jpg")
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
    """
    Drive'dan gelen dosya ismi uzantısız ise MIME tipine göre uzantı ekle.
    """
    p = Path(name)
    if p.suffix:
        return name
    ext = guess_ext_from_mime(mime_type) or ""
    return p.name + ext


def read_file_to_text(
    path: str,
    ocr_lang: str = "tur+eng",
    mime_type: Optional[str] = None,
) -> str:
    """
    Çok biçimli metin çıkarıcı:
      - .txt → düz okuma (utf-8)
      - .docx → python-docx
      - .pdf → pdfminer; boşsa pdf2image + OCR
      - .jpg/.jpeg/.png VEYA mime_type image/* → OCR
    """
    p = Path(path)
    ext = p.suffix.lower()

    # TXT
    if ext == ".txt":
        try:
            return p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return p.read_text(encoding="latin-1")

    # DOCX
    if ext == ".docx":
        doc = Document(str(p))
        return "\n".join(para.text for para in doc.paragraphs)

    # PDF
    if ext == ".pdf" or (mime_type == PDF_MIME):
        # 1) pdfminer ile metin katmanı dene
        try:
            text = pdf_extract_text(str(p)) or ""
        except Exception:
            text = ""
        if text.strip():
            return text

        # 2) OCR fallback: sayfaları görüntüye çevir ve OCR
        try:
            pages = convert_from_path(str(p))
            chunks = []
            for img in pages:
                chunks.append(pytesseract.image_to_string(img, lang=ocr_lang))
            return "\n".join(chunks)
        except Exception:
            return ""

    # GÖRÜNTÜ (jpg/png) — uzantı ya da mime ile
    if ext in IMAGE_EXTS or (mime_type and mime_type.startswith("image/")):
        img = Image.open(str(p))
        return pytesseract.image_to_string(img, lang=ocr_lang)

    # Bilinmeyen → dene
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""
