FROM python:3.9-slim

WORKDIR /app

# Install Tesseract and dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY invoice_validator.py .

RUN pip install -r requirements.txt

COPY ocr_processor.py .

CMD ["python", "ocr_processor.py"]