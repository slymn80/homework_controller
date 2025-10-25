from __future__ import annotations
from pathlib import Path
import os

import pytesseract
from PIL import Image, ImageOps, ImageFilter

# pdf2image ve pypdf isteğe bağlı (taralı PDF için)
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except Exception:
    PDF2IMAGE_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except Exception:
    PYPDF_AVAILABLE = False

# .env ayarları
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

OCR_LANG = os.getenv("OCR_LANG", "eng").strip()  # öneri: tur+eng
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()

    if ext == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")

    if ext == ".docx":
        return _from_docx(path)

    if ext == ".pdf":
        # Önce metin katmanı var mı dene
        text = _from_pdf_textlayer(path)
        if text.strip():
            return text
        # Yoksa OCR'a düş
        return _from_scanned_pdf_ocr(path)

    if ext in IMAGE_EXTS:
        return _from_image_ocr(path)

    # Fallback: düz metin denemesi
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _from_docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _from_pdf_textlayer(path: Path) -> str:
    # pypdf ile metin katmanını dene
    if PYPDF_AVAILABLE:
        try:
            reader = PdfReader(str(path))
            chunks = []
            for page in reader.pages:
                t = page.extract_text() or ""
                chunks.append(t)
            text = "\n".join(chunks).strip()
            if text:
                return text
        except Exception:
            pass
    # pdfminer fallback
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        return (pdfminer_extract(str(path)) or "").strip()
    except Exception:
        return ""


def _from_scanned_pdf_ocr(path: Path) -> str:
    if not PDF2IMAGE_AVAILABLE:
        return ""
    try:
        images = convert_from_path(str(path), dpi=300)
    except Exception:
        return ""

    texts = []
    for img in images:
        texts.append(_ocr_preprocess_and_read(img))
    return "\n".join(texts)


def _from_image_ocr(path: Path) -> str:
    try:
        with Image.open(str(path)) as img:
            return _ocr_preprocess_and_read(img)
    except Exception:
        return ""


def _ocr_preprocess_and_read(img: Image.Image) -> str:
    """
    Basit ama etkili ön-işleme:
    - Gri ton
    - Kontrast artırma
    - Hafif keskinleştirme
    - Otomatik threshold (binarize)
    """
    # 1) Gri
    g = img.convert("L")
    # 2) Kontrast ve keskin
    g = ImageOps.autocontrast(g)
    g = g.filter(ImageFilter.SHARPEN)
    # 3) Basit binarizasyon
    bw = g.point(lambda x: 255 if x > 180 else 0, mode="1")

    try:
        return pytesseract.image_to_string(bw, lang=OCR_LANG)
    except Exception:
        # Dil paketi yoksa en azından İngilizce dene
        try:
            return pytesseract.image_to_string(bw, lang="eng")
        except Exception:
            return ""
