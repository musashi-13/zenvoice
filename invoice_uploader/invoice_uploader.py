import uuid
import boto3
import json
import base64
import logging
import os
from datetime import datetime, timezone
from kafka import KafkaConsumer
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json

# Load environment variables from .env file
load_dotenv()

# AWS S3 Config
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
METADATA_FILE = "metadata.json"

# Kafka Config
KAFKA_TOPIC = "email-invoices"
BOOTSTRAP_SERVERS = "kafka:9092"

# PostgreSQL Config
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "invoice-pipeline")
POSTGRES_USER = os.getenv("POSTGRES_USER", "user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

# Set up logging to console only
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)
logging.info("Invoice Uploader Script Started.")

# Initialize S3 client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# Initialize PostgreSQL connection
def init_postgres():
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        logging.info("Connected to PostgreSQL database.")
        return conn
    except Exception as e:
        logging.error(f"Failed to connect to PostgreSQL: {e}")
        raise

def fetch_metadata():
    """Fetches the existing metadata.json from S3."""
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=METADATA_FILE)
        return json.loads(response["Body"].read().decode("utf-8"))
    except s3_client.exceptions.NoSuchKey:
        return {"invoices": []}
    except Exception as e:
        logging.error(f"Error fetching metadata.json: {e}")
        return {"invoices": []}

def upload_metadata(metadata):
    """Uploads updated metadata.json back to S3."""
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=METADATA_FILE,
            Body=json.dumps(metadata, indent=4).encode("utf-8")
        )
        logging.info("Updated metadata.json in S3.")
    except Exception as e:
        logging.error(f"Error updating metadata.json: {e}")

def upload_to_s3(file_name, file_data):
    """Uploads the PDF to S3 and returns the file path."""
    year_month = datetime.now().strftime("%Y/%m")
    s3_key = f"raw/{year_month}/{file_name}"
    try:
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=file_data)
        logging.info(f"Successfully uploaded {file_name} to S3: s3://{S3_BUCKET_NAME}/{s3_key}")
        return f"s3://{S3_BUCKET_NAME}/{s3_key}"
    except Exception as e:
        logging.error(f"Failed to upload {file_name} to S3: {e}")
        return None

def insert_or_update_invoice(conn, invoice_data):
    invoice_id = str(uuid.uuid4())  # Generate a new UUID for invoice_id
    combined_key = invoice_data["message_id"]   
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO invoice_store (
                    invoice_id, message_id, sender, subject, created_at, updated_at, s3_url,
                    zoho_po_number, zoho_bill_number, scanned_data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO UPDATE
                SET s3_url = EXCLUDED.s3_url,
                    updated_at = EXCLUDED.updated_at
            """, (
                invoice_id,
                combined_key,
                invoice_data["sender"],
                invoice_data["subject"],
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
                invoice_data["s3_path"],
                "", "", Json({})
            ))
            if cur.rowcount > 0:
                logging.info(f"Inserted new invoice for {combined_key}.")
            else:
                logging.info(f"Updated invoice for {combined_key} with s3_url.")
        conn.commit()
    except Exception as e:
        logging.error(f"Error inserting/updating invoice for {combined_key}: {e}")
        conn.rollback()

def process_message(message, conn):
    """Processes a Kafka message containing an email invoice."""
    try:
        data = message.value
        email_id = data.get("email_id")
        sender = data.get("sender")
        subject = data.get("subject", "")

        metadata = fetch_metadata()
        processed_files = {(inv["email_id"], inv["file_name"]) for inv in metadata["invoices"]}
        new_entries = []

        for index, attachment in enumerate(data.get("attachments", [])):
            file_name = attachment["file_name"]
            attachment_index = index
            combined_key = f"{email_id}_{attachment_index}"

            if (email_id, file_name) in processed_files:
                logging.info(f"Skipping {file_name} from email {email_id}: Already processed.")
                continue

            file_data = base64.b64decode(attachment["file_data"])
            s3_path = upload_to_s3(file_name, file_data)
            if not s3_path:
                logging.error(f"Processing failed for attachment {file_name} from sender {sender} with subject '{subject}' due to S3 upload failure.")
                continue

            invoice_data = {
                "message_id": combined_key,
                "sender": sender,
                "subject": subject,
                "s3_path": s3_path,
                "file_name": file_name
            }

            # Insert or update the invoice in the database
            insert_or_update_invoice(conn, invoice_data)

            # Update metadata (optional, if still needed)
            metadata_entry = {
                "email_id": email_id,
                "sender": sender,
                "subject": subject,
                "received_at": datetime.now(timezone.utc).isoformat(),
                "file_name": file_name,
                "s3_path": s3_path,
                "status": "raw"
            }
            metadata["invoices"].append(metadata_entry)
            new_entries.append(metadata_entry)

            logging.info(f"Processed attachment {file_name} from email {email_id} with combined key {combined_key}")

        if new_entries:
            upload_metadata(metadata)
            logging.info(f"Processed email {email_id} with {len(new_entries)} new attachment(s).")

    except Exception as e:
        logging.error(f"Error processing message: {e}")

def consume_kafka():
    """Consumes messages from Kafka and processes them."""
    try:
        conn = init_postgres()
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=BOOTSTRAP_SERVERS,
            group_id="invoice_uploader_group",
            auto_offset_reset="latest",
            enable_auto_commit=False,
            value_deserializer=lambda v: json.loads(v.decode("utf-8"))
        )
        logging.info("Kafka Consumer started, waiting for messages...")
        for message in consumer:
            process_message(message, conn)
            consumer.commit()
    except Exception as e:
        logging.error(f"Kafka Consumer error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            logging.info("PostgreSQL connection closed.")

if __name__ == "__main__":
    consume_kafka()