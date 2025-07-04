import json
import base64
import logging
import os
import fitz
import pytesseract
from PIL import Image
import io
import google.generativeai as genai
import psycopg2
from psycopg2.extras import Json
from datetime import datetime
from kafka import KafkaConsumer
from dotenv import load_dotenv

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

# Gemini API Config
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not set.")

genai.configure(api_key=API_KEY)

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

def check_invoice_exists(conn, invoice_id):
    """Check if an invoice with the given invoice_id exists."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM invoice_store WHERE invoice_id = %s", (invoice_id,))
            return cur.fetchone() is not None
    except Exception as e:
        logging.error(f"Error checking invoice existence: {e}")
        return False

def insert_or_update_invoice(conn, invoice_data):
    """Insert or update the invoice in the database based on invoice_id."""
    invoice_id = invoice_data["invoice_id"]
    exists = check_invoice_exists(conn, invoice_id)
    try:
        with conn.cursor() as cur:
            if exists:
                cur.execute("""
                    UPDATE invoice_store
                    SET scanned_data = %s, updated_at = %s
                    WHERE invoice_id = %s
                """, (
                    Json(invoice_data["scanned_data"]),
                    datetime.utcnow(),
                    invoice_id
                ))
                logging.info(f"Updated invoice {invoice_id} with scanned_data.")
            else:
                cur.execute("""
                    INSERT INTO invoice_store (
                        invoice_id, message_id, sender, subject, created_at, updated_at, 
                        s3_url, zoho_po_number, zoho_bill_number, scanned_data
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    invoice_id,
                    invoice_data["message_id"],
                    invoice_data["sender"],
                    invoice_data["subject"],
                    datetime.utcnow(),
                    datetime.utcnow(),
                    "", "", "", Json(invoice_data["scanned_data"])
                ))
                logging.info(f"Inserted new invoice {invoice_id}.")
        conn.commit()
    except Exception as e:
        logging.error(f"Error inserting/updating invoice {invoice_id}: {e}")
        conn.rollback()

def ocr_pdf(pdf_data):
    """Extract text from a PDF in memory using PyMuPDF and Tesseract OCR."""
    text = ""
    try:
        # Load PDF from bytes
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            page_text = page.get_text()
            if len(page_text.strip()) < 10:
                logging.info(f"Using OCR for page {page_num + 1}...")
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.open(io.BytesIO(pix.tobytes()))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                page_text = pytesseract.image_to_string(img)
            text += f"\n\n--- Page {page_num + 1} ---\n\n" + page_text
        pdf_document.close()
    except Exception as e:
        logging.error(f"Error performing OCR on PDF: {e}")
        raise
    return text

import re

import re

def format_with_gemini(data, email_id, attachment_index):
    """Format extracted text into structured JSON using Gemini."""
    prompt = """
    You are a specialized AI assistant for extracting invoice data from text and converting it to a structured JSON format.

    I'll provide the text extracted from an invoice. Make sure you store the PO No. as bill_number in the extracted json. Please extract the following information and format it as JSON:
    - Vendor name (company issuing the invoice)
    - PO number, not the invoice number
    - Bill/invoice date
    - Due date or payment terms
    - Bill-to information (name and address)
    - Ship-to information (address)
    - Line items (including item details, quantity, rate, and amount)
    - Subtotal
    - Tax information (rate and calculated amount)
    - Total amount
    - Any notes or terms

    The text from the invoice is as follows:

    """ + data + """

    Please return the data in this exact JSON structure:
    {
      "invoices": [
        {
          "vendor_name": "",
          "bill_number": "",
          "bill_date": "",
          "due_date": "",
          "items": [
            {
              "item_details": "",
              "account": "",
              "quantity": 0,
              "rate": 0,
              "amount": 0
            }
          ],
          "sub_total": 0,
          "discount": {
            "percentage": 0,
            "amount": 0
          },
          "tax": {
            "tds_percent": "0",
            "tds_amount": 0,
            "tds_tax_name": ""
          },
          "total": 0
        }
      ]
    }

    Don't include any explanations or markdown in your response, just the clean JSON output.
    """
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite-preview-06-17",
            generation_config=genai.types.GenerationConfig(
                candidate_count=1,
                stop_sequences=[],
                max_output_tokens=8192,
                temperature=0.7
            )
        )
        response = model.generate_content(prompt)

        print(f"Response: {response.text}")

        invoicejsontext = response.text[8:-4]
        print(invoicejsontext)
        invoicejson = json.loads(invoicejsontext)

        os.makedirs("/app/data", exist_ok=True)
        invoices_file = os.path.join("/app/data", "invoices.json")
        with open(invoices_file, "w") as json_file:
            json.dump(invoicejson, json_file, indent=4) 
        
        logging.info(f"Saved JSON for email {email_id}, attachment {attachment_index}")

        return invoicejson

    except json.JSONDecodeError as e:
        logging.error("JSON decode error for email %s, attachment %s: %s\nPayload repr: %r", email_id, attachment_index, e, invoicejsontext)
        return None
    except Exception as e:
        logging.error("Error processing with Gemini for email %s, attachment %s: %s", email_id, attachment_index, e, exc_info=True)
        return None

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
                logging.error(f"Skipping database update for attachment {index} due to OCR/Gemini failure.")
                continue

            # Update database with scanned_data
            combined_key = f"{email_id}_{index}"
            if not check_invoice_exists(conn, combined_key):
                db_invoice = {
                    "invoice_id": combined_key,
                    "message_id": email_id,
                    "sender": sender,
                    "subject": subject,
                    "scanned_data": invoice_data["invoices"][0]
                }
                insert_or_update_invoice(conn, db_invoice)
                logging.info(f"Processed and stored new invoice {combined_key}.")
            else:
                logging.info(f"Skipping invoice {combined_key}: Already processed.")

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