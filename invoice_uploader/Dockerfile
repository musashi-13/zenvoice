FROM python:3.9-slim

WORKDIR /app

COPY invoice_uploader/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY invoice_uploader/invoice_uploader.py .
COPY .env .

CMD ["python", "invoice_uploader.py"]