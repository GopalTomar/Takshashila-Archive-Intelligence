# Backend image: FastAPI + document processing + OCR.
FROM python:3.11-slim

# System deps for OCR (Tesseract), PDF rasterisation (Ghostscript), and OCRmyPDF.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    ghostscript \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api /srv
COPY config /config

ENV PYTHONPATH=/srv \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1

# The app resolves REPO_ROOT relative to the package; make /config discoverable.
RUN mkdir -p /data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
