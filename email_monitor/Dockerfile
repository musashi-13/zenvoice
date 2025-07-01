FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY email_monitor.py .
COPY credentials.json .
COPY token.json .

# Optional: Run quickstart.py to generate token.json if not pre-generated
# RUN python quickstart.py && rm quickstart.py

CMD ["python", "email_monitor.py"]