import os
import json
import base64
import uuid
import sys
import psycopg2
from psycopg2.extras import Json
from datetime import datetime, timezone
from kafka import KafkaConsumer
from dotenv import load_dotenv
from invoice_validator import match_invoice_with_purchase_order
from invoice_scanner import ocr_pdf, format_with_gemini
from logger_config import setup_logger

# This allows the logger to be configured by the environment variable
# passed from docker-compose (e.g., INVOICE_PROCESSOR_LOG)
SERVICE_LOG_VAR = os.getenv('SERVICE_NAME_LOG_VAR', 'LOG') 
logger = setup_logger(__name__, SERVICE_LOG_VAR)

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


def init_postgres():
    """Initialize PostgreSQL connection."""
    logger.debug("Connecting to PostgreSQL database...")
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        logger.info("Successfully connected to PostgreSQL.")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}", exc_info=True)
        raise

def check_invoice_exists(conn, combined_key):
    """Checks if an invoice with the given message_id already exists."""
    
    logger.debug(f"Checking for existing invoice with key: {combined_key}")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM invoice_store WHERE message_id = %s", (combined_key,))
            exists = cur.fetchone() is not None
            # logger.debug(f"Invoice with key '{combined_key}' {'exists' if exists else 'does not exist'}.")
            return exists
    except Exception as e:
        logger.error(f"Error checking invoice existence for key {combined_key}: {e}", exc_info=True)
        conn.rollback()
        return False

def insert_invoice(conn, db_invoice):
    """Insert a new invoice record into the database."""
    
    combined_key = db_invoice["combined_key"]
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
                    combined_key,
                    db_invoice["sender"],
                    db_invoice["subject"],
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                    "", "", "", Json(db_invoice["scanned_data"])
                )
            )
        conn.commit()
        logger.info(f"Successfully inserted new invoice with ID {invoice_id} for key {combined_key}.")
    except Exception as e:
        logger.error(f"Error inserting invoice for key {combined_key}: {e}", exc_info=True)
        conn.rollback()
        
def update_invoice_scanned_data(conn, combined_key, invoice_data):
    """Update an existing invoice with scanned data if it's currently empty."""
    logger.info(f"Attempting to update invoice with scanned data for key: {combined_key}")
    try:
        with conn.cursor() as cur:
            # Check if scanned_data is NULL or an empty JSON object before updating
            cur.execute(
                """
                UPDATE invoice_store
                SET scanned_data = %s, updated_at = %s
                WHERE message_id = %s AND (scanned_data IS NULL OR scanned_data = '{}'::jsonb)
                RETURNING invoice_id;
                """,
                (Json(invoice_data), datetime.now(timezone.utc), combined_key)
            )
            updated_row = cur.fetchone()
            if updated_row:
                logger.info(f"Successfully updated invoice {updated_row[0]} with new scanned_data.")
            else:
                logger.info(f"Skipping update for key {combined_key} as it already has scanned_data.")
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating invoice for key {combined_key}: {e}", exc_info=True)
        conn.rollback()

def update_invoice_bill_id(conn, combined_key, bill_id):
    """Updates an invoice record with the Zoho Bill ID after successful creation."""
    logger.info(f"Updating invoice record for key {combined_key} with Zoho Bill ID: {bill_id}")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE invoice_store
                SET zoho_bill_number = %s, updated_at = %s
                WHERE message_id = %s
                """,
                (bill_id, datetime.now(timezone.utc), combined_key)
            )
        conn.commit()
        logger.info(f"Database updated successfully for key {combined_key}.")
    except Exception as e:
        logger.error(f"Error updating invoice with Bill ID for key {combined_key}: {e}", exc_info=True)
        conn.rollback()


def process_message(message, conn):
    """Process a single Kafka message containing an email invoice."""
    try:
        data = message.value
        email_id = data.get("email_id")
        logger.info(f"Processing message for email_id: {email_id}")

        sender = data.get("sender", "")
        subject = data.get("subject", "")

        for index, attachment in enumerate(data.get("attachments", [])):
            combined_key = f"{email_id}_{index}"
            logger.info(f"Processing attachment {index} for email {email_id} (key: {combined_key})")

            file_data = base64.b64decode(attachment["file_data"])
            
            # Step 1: OCR and AI Formatting
            text = ocr_pdf(file_data)
            if not text:
                logger.error(f"OCR processing failed for {combined_key}. Skipping attachment.")
                continue
            
            # logger.debug(f"Raw text from OCR for {combined_key}:\n---START---\n{text}\n---END---")
            
            invoice_data = format_with_gemini(text, email_id, index)
            if not invoice_data:
                logger.error(f"Gemini formatting failed for {combined_key}. Skipping attachment.")
                continue
            
            logger.info(f"Successfully scanned data from Gemini for {combined_key}.")
            logger.debug(f"Scanned data JSON: {json.dumps(invoice_data, indent=2)}")

            # Step 2: Database Interaction
            if not check_invoice_exists(conn, combined_key):
                db_invoice = {
                    "combined_key": combined_key, "sender": sender, 
                    "subject": subject, "scanned_data": invoice_data
                }
                insert_invoice(conn, db_invoice)
            else:
                update_invoice_scanned_data(conn, combined_key, invoice_data)
            
            # Step 3: Validation and Bill Creation
            logger.debug(f"Starting validation against Zoho for {combined_key}...")
            validation_result = match_invoice_with_purchase_order(invoice_data)
            
            logger.debug(f"Validation result for {combined_key}: {json.dumps(validation_result, indent=2)}")

            if validation_result.get("match"):
                logger.info(f"Invoice {combined_key} successfully matched PO {validation_result['purchase_order_id']}")
                bill = validation_result.get("bill", {})
                if bill and bill.get("bill_id"):
                    update_invoice_bill_id(conn, combined_key, bill["bill_id"])
                else:
                    # This case handles when bill creation fails (e.g., already billed)
                    logger.warning(f"Validation matched, but no bill was created for {combined_key}. Check Zoho API logs for details.")
            else:
                logger.error(f"Invoice {combined_key} failed validation against PO.")
                logger.error(f"Reason: {validation_result.get('message')}")
                if validation_result.get("differences"):
                    logger.error(f"Differences: {validation_result['differences']}")

    except Exception as e:
        logger.error(f"An unexpected error occurred while processing Kafka message: {e}", exc_info=True)

def consume_kafka():
    """Consume messages from Kafka and process them."""
    conn = None
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
        logger.info("Kafka Consumer started. Waiting for messages...")
        for message in consumer:
            process_message(message, conn)
            consumer.commit()
    finally:
        if conn:
            conn.close()
            logger.info("PostgreSQL connection closed.")

if __name__ == "__main__":
    try:
        logger.info("--- Starting Invoice Processor Service ---")
        consume_kafka()
    except Exception as e:
        logger.critical("Invoice Processor service failed to start or crashed.", exc_info=True)
        sys.exit(1)
 