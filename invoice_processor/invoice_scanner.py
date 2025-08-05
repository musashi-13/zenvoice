import os
import json
import io
import sys
import fitz  # PyMuPDF
import pytesseract
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

from logger_config import setup_logger

# This allows the logger to be configured by the environment variable
# passed from docker-compose (e.g., INVOICE_PROCESSOR_LOG)
SERVICE_LOG_VAR = os.getenv('SERVICE_NAME_LOG_VAR', 'LOG') 
logger = setup_logger(__name__, SERVICE_LOG_VAR)

load_dotenv()

# Gemini API Config
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    logger.critical("GEMINI_API_KEY not set in environment variables. Service cannot function.")

def ocr_pdf(pdf_data: bytes) -> str:
    """
    Extract text from a PDF in memory. It first tries direct text extraction
    and falls back to Tesseract OCR for image-based pages.
    """
    full_text = ""
    logger.debug("Starting PDF text extraction...")
    try:
        # Load PDF from bytes
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        # logger.debug(f"PDF has {len(pdf_document)} page(s).")

        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            page_text = page.get_text()
            if len(page_text.strip()) < 10:
                # logger.debug(f"Using OCR for page {page_num + 1}...")
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.open(io.BytesIO(pix.tobytes()))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                page_text = pytesseract.image_to_string(img)
            text += f"\n\n--- Page {page_num + 1} ---\n\n" + page_text
        pdf_document.close()
        # logger.debug("Finished PDF text extraction.")
        return full_text

    except Exception as e:
        logger.error(f"A critical error occurred during PDF processing: {e}", exc_info=True)
        return "" # Return empty string on failure

def format_with_gemini(data, email_id, attachment_index):
    """Format extracted text into structured JSON using Gemini."""
    prompt = """
    You are a specialized AI assistant for extracting invoice data from text and converting it to a structured JSON format.

    I'll provide the text extracted from an invoice. Make sure you store the PO No. as bill_number in the extracted json. Please extract the following information and format it as JSON:
    - Vendor name (company issuing the invoice)
    - Vendor's invoice number
    - Purhcase Order number,
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
        "vendor_name": "",
        "invoice_number": "",
        "po_number": "",
        "bill_date": "",
        "due_date": "",
        "items": [
        {
            "item_details": "",
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
        invoicejsontext = response.text[8:-4]
        invoice_json = json.loads(invoicejsontext) 
        return invoice_json

    except json.JSONDecodeError as e:
        logger.error(
            "JSON decode error for email %s, attachment %s. Gemini response was not valid JSON.",
            email_id, attachment_index, exc_info=True
        )
        logger.error(f"Problematic Gemini response text: {response.text}")
        return None
    except Exception as e:
        logger.error(
            "An unexpected error occurred processing with Gemini for email %s, attachment %s: %s",
            email_id, attachment_index, e, exc_info=True
        )
        return None

if __name__ == '__main__':
    # This block allows for direct testing of this script.
    try:
        # Configure logger for local testing
        os.environ['SERVICE_NAME_LOG_VAR'] = 'LOG'
        os.environ['LOG'] = 'DEV'
        logger = setup_logger(__name__, 'LOG')

        logger.info("--- Running Invoice Scanner in local test mode ---")
        
        # Create a dummy PDF file for testing if it doesn't exist
        dummy_pdf_path = "dummy_invoice.pdf"
        if not os.path.exists(dummy_pdf_path):
            logger.warning(f"'{dummy_pdf_path}' not found. Please place a sample PDF in this directory to test.")
        else:
            with open(dummy_pdf_path, "rb") as f:
                pdf_bytes = f.read()
            
            # Test OCR
            extracted_text = ocr_pdf(pdf_bytes)
            if extracted_text:
                logger.info("OCR test successful.")
                
                # Test Gemini formatting
                formatted_data = format_with_gemini(extracted_text, "local_test", 0)
                if formatted_data:
                    logger.info("Gemini formatting test successful.")
                    print("\n--- Formatted JSON Data ---")
                    print(json.dumps(formatted_data, indent=2))
                else:
                    logger.error("Gemini formatting test failed.")
            else:
                logger.error("OCR test failed.")

    except Exception as e:
        logger.critical("Local test run failed.", exc_info=True)
