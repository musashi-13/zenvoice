import fitz
import pytesseract
import google.generativeai as genai
from PIL import Image
import logging
import io
import os
import json

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
        logging.error("JSON decode error for email %s, attachment %s: %s\nPayload repr: %r", email_id, attachment_index, e, invoicejsontext)
        return None
    except Exception as e:
        logging.error("Error processing with Gemini for email %s, attachment %s: %s", email_id, attachment_index, e, exc_info=True)
        return None