FROM python:3.9-slim

WORKDIR /app

COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./invoice_uploader.py .

CMD ["python", "invoice_uploader.py"]