import json
import base64
import logging
import os
import uuid
import psycopg2
from psycopg2.extras import Json
from datetime import datetime, timezone
from kafka import KafkaConsumer
from dotenv import load_dotenv
from invoice_validator import match_invoice_with_purchase_order
from invoice_scanner import ocr_pdf, format_with_gemini


# Load environment variables
load_dotenv()

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
logging.info("OCR Processor Script Started.")

def init_postgres():
    """Initialize PostgreSQL connection."""
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

def check_invoice_exists(conn, combined_key):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM invoice_store WHERE message_id = %s", (combined_key,))
            return cur.fetchone() is not None
    except Exception as e:
        logging.error(f"Error checking invoice existence: {e}")
        conn.rollback()
        return False

def insert_invoice(conn, db_invoice):
    """Insert a new invoice into the database."""
    try:
        with conn.cursor() as cur:
            invoice_id = str(uuid.uuid4()) 
            cur.execute(
                """
                INSERT INTO invoice_store (
                    invoice_id, message_id, sender, subject, created_at, updated_at, 
                    s3_url, zoho_po_number, zoho_bill_number, scanned_data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    invoice_id,
                    db_invoice["combined_key"],
                    db_invoice["sender"],
                    db_invoice["subject"],
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                    "", "", "", Json(db_invoice["scanned_data"])
                )
            )
            logging.info(f"Inserted new invoice {db_invoice['combined_key']}.")
        conn.commit()
    except Exception as e:
        logging.error(f"Error inserting invoice {db_invoice['combined_key']}: {e}")
        conn.rollback()
        
def update_invoice(conn, combined_key, invoice_data):
    """Update an existing invoice by adding scanned_data if it's empty or null, otherwise skip."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT invoice_id, scanned_data 
                FROM invoice_store 
                WHERE message_id = %s 
                AND (scanned_data IS NULL OR scanned_data = '{}'::jsonb)
                """,
                (combined_key,)
            )
            existing_row = cur.fetchone()
            if existing_row:
                invoice_id, _ = existing_row
                cur.execute(
                    """
                    UPDATE invoice_store
                    SET scanned_data = %s, updated_at = %s
                    WHERE invoice_id = %s
                    """,
                    (Json(invoice_data), datetime.now(timezone.utc), invoice_id)
                )
                logging.info(f"Updated invoice {invoice_id} with new scanned_data.")
            else:
                logging.info(f"Skipping update for {combined_key}: scanned_data exists.")
            conn.commit()
    except Exception as e:
        logging.error(f"Error updating invoice for {combined_key}: {e}")
        conn.rollback()



def process_message(message, conn):
    """Process a Kafka message containing an email invoice."""
    try:
        data = message.value
        email_id = data.get("email_id")
        sender = data.get("sender", "")
        subject = data.get("subject", "")

        for index, attachment in enumerate(data.get("attachments", [])):
            file_data = base64.b64decode(attachment["file_data"])
            # Process PDF in memory
            text = ocr_pdf(file_data)
            invoice_data = format_with_gemini(text, email_id, index)
            if not invoice_data:
                logging.error(f"Skipping database update for {email_id} attachment {index} due to OCR/Gemini failure.")
                continue

            # Update database with scanned_data
            combined_key = f"{email_id}_{index}"
            
            logging.info(f"Processing invoice for email {email_id}, attachment {index} with combined key {combined_key}")
            
            if not check_invoice_exists(conn, combined_key):
                db_invoice = {
                    "combined_key": combined_key,
                    "sender": sender,
                    "subject": subject,
                    "scanned_data": invoice_data
                }
                insert_invoice(conn, db_invoice)
            else:
                update_invoice(conn, combined_key, invoice_data)
            validation_result = match_invoice_with_purchase_order(invoice_data)
            if validation_result["match"]:
                print(f"Invoice email attachment {combined_key} matches Purchase Order {validation_result['purchase_order_id']}")
                bill = validation_result["bill"]
                if bill and bill.get("bill_id"):
                    # Update database with zoho_bill_number
                    cursor = conn.cursor()
                    update_query = """
                        UPDATE invoice_store
                        SET zoho_bill_number = %s,
                            updated_at = %s
                        WHERE message_id = %s
                    """
                    cursor.execute(update_query, (bill["bill_id"], datetime.now(), combined_key))
                    conn.commit()
                    logging.info(f"Updated database with Zoho bill ID {bill['bill_id']} for {combined_key}")
            else:
                logging.error(f"Invoice {combined_key} does not match Purchase Order {validation_result['purchase_order_id']}: {validation_result['message']}")
                logging.error(f"Differences: {validation_result['differences']}")
    except Exception as e:
        logging.error(f"Error processing message: {e}")

def consume_kafka():
    """Consume messages from Kafka and process them."""
    try:
        conn = init_postgres()
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=BOOTSTRAP_SERVERS,
            group_id="ocr_processor_group",
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