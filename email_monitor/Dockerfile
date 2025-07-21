# Dockerfile for email_monitor service
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY email_monitor.py .
COPY credentials.json .
COPY token.json .

CMD ["python", "email_monitor.py"]