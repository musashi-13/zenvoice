import boto3
import json
import base64
import logging
import os
from datetime import datetime
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

def check_invoice_exists(conn, invoice_id):
    """Checks if an invoice with the given invoice_id exists in the database."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM invoice_store WHERE invoice_id = %s", (invoice_id,))
            return cur.fetchone() is not None
    except Exception as e:
        logging.error(f"Error checking invoice existence: {e}")
        return False

def insert_or_update_invoice(conn, invoice_data):
    """Inserts or updates the invoice in the database based on the invoice_id."""
    invoice_id = invoice_data["invoice_id"]
    exists = check_invoice_exists(conn, invoice_id)
    try:
        with conn.cursor() as cur:
            if exists:
                # Update existing row with s3_url and updated_at
                cur.execute("""
                    UPDATE invoice_store
                    SET s3_url = %s, updated_at = %s
                    WHERE invoice_id = %s
                """, (
                    invoice_data["s3_path"],
                    datetime.utcnow(),
                    invoice_id
                ))
                logging.info(f"Updated invoice {invoice_id} with s3_url.")
            else:
                # Insert new row with all available data
                cur.execute("""
                    INSERT INTO invoice_store (
                        invoice_id, message_id, sender, subject, created_at, updated_at, s3_url,
                        zoho_po_number, zoho_bill_number, scanned_data
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    invoice_id,
                    invoice_data["message_id"],
                    invoice_data["sender"],
                    invoice_data["subject"],
                    datetime.utcnow(),
                    datetime.utcnow(),
                    invoice_data["s3_path"],
                    "", "", Json({})
                ))
                logging.info(f"Inserted new invoice {invoice_id}.")
        conn.commit()
    except Exception as e:
        logging.error(f"Error inserting/updating invoice {invoice_id}: {e}")
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
            attachment_index = index  # 0-based index
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
                "invoice_id": combined_key,
                "message_id": email_id,
                "sender": sender,
                "subject": subject,
                "s3_path": s3_path,
                "file abnorme": file_name
            }

            # Insert or update the invoice in the database
            insert_or_update_invoice(conn, invoice_data)

            # Update metadata (optional, if still needed)
            metadata_entry = {
                "email_id": email_id,
                "sender": sender,
                "subject": subject,
                "received_at": datetime.utcnow().isoformat(),
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