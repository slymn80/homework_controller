# OCR için apt-get kullanabileceğimiz Debian tabanlı Python
FROM python:3.10-slim

# Sisteme OCR araçları: Tesseract (TR+EN dil paketleri) + Poppler
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-tur tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Çalışma dizini
WORKDIR /app

# Bağımlılıklar
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodu
COPY . /app

# Uvicorn ile FastAPI servis
EXPOSE 8000
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
