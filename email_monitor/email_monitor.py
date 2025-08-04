import os
import pickle
import time
import base64
import json
import sys
from threading import Thread
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from kafka import KafkaProducer
from email import message_from_bytes
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from google.auth.transport.requests import Request
from zoho_api import ZohoAPI
from dotenv import load_dotenv
from logger_config import setup_logger

# This allows the logger to be configured by the environment variable
# passed from docker-compose (e.g., EMAIL_MONITOR_LOG)
SERVICE_LOG_VAR = os.getenv('SERVICE_NAME_LOG_VAR', 'LOG') 
logger = setup_logger(__name__, SERVICE_LOG_VAR)

load_dotenv()

# Configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
USER_ID = "me"
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
KAFKA_INVOICES_TOPIC = "email-invoices"
KAFKA_LOGS_TOPIC = "logs"
POLL_INTERVAL = 30
SENDERS_UPDATE_INTERVAL = 3600  # 1 hour

# Initialize Kafka Producer with retry
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    before_sleep=lambda retry_state: logger.warning(f"Retrying Kafka connection (attempt {retry_state.attempt_number})...")
)
def init_kafka_producer():
    logger.debug("Initializing Kafka producer...")
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    logger.debug("Kafka producer initialized successfully.")
    return producer

def authenticate_gmail():
    """Authenticate with Gmail API using OAuth 2.0."""
    logger.debug("Authenticating with Gmail API...")
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
            logger.info("Loaded Gmail credentials from token.json.")
        except (pickle.UnpicklingError, EOFError) as e:
            logger.error(f"Could not load Gmail token file, it may be corrupted: {e}")
            creds = None

    if not creds or not creds.valid:
        if not os.path.exists(CREDENTIALS_FILE):
            logger.critical(f"'{CREDENTIALS_FILE}' not found. Cannot authenticate with Gmail.")
            return None
        
        if creds and creds.expired and creds.refresh_token:
            logger.debug("Gmail credentials expired. Refreshing token...")
            creds.refresh(Request())
        else:
            logger.debug("No valid Gmail credentials found. Starting local server for user authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
            logger.info("Saved new Gmail credentials to token.json.")
    
    logger.info("Gmail authentication successful.")
    return build('gmail', 'v1', credentials=creds)

def fetch_allowed_senders(zoho_api_instance: ZohoAPI):
    """Fetch vendor emails from Zoho Books."""
    
    logger.debug("Fetching allowed senders from Zoho Books...")
    allowed_senders = zoho_api_instance.get_vendors()
    if not allowed_senders:
        logger.warning("No vendor emails fetched from Zoho. The query for emails will be empty.")
    return allowed_senders

def update_allowed_senders(zoho_api_instance: ZohoAPI):
    """Periodically update the allowed senders list in a separate thread."""
    
    global allowed_senders
    while True:
        time.sleep(SENDERS_UPDATE_INTERVAL)
        logger.info("Scheduled update: Refreshing allowed senders list...")
        try:
            allowed_senders = fetch_allowed_senders(zoho_api_instance)
        except Exception as e:
            logger.error(f"Failed to update allowed senders: {e}", exc_info=True)

def fetch_emails(gmail_service):
    """Fetch unread emails with 'invoice' in subject from allowed senders."""
    
    global allowed_senders
    if not allowed_senders:
        logger.warning("Allowed senders list is empty. No emails will be fetched.")
        return []
    
    query = f"from:({ ' OR '.join(allowed_senders) }) subject:(invoice) is:unread"
    logger.info("Fetching new emails from Gmail...")
    logger.debug(f"Using Gmail query: {query}")

    try:
        results = gmail_service.users().messages().list(userId=USER_ID, q=query).execute()
        messages = results.get('messages', [])
        if messages:
            logger.info(f"Found {len(messages)} new email(s).")
        else:
            logger.info("No new emails found.")
        return messages
    except HttpError as error:
        logger.error(f"An HTTP error occurred while fetching emails: {error}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching emails: {e}", exc_info=True)
        return []

def process_email(gmail_service, message_id, kafka_producer):
    """Extract PDF attachments from an email and send its data to Kafka."""
    logger.info(f"Processing email with ID: {message_id}")
    try:
        message = gmail_service.users().messages().get(userId=USER_ID, id=message_id, format='raw').execute()
        msg_str = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))
        mime_msg = message_from_bytes(msg_str)

        sender_email = mime_msg['From']
        subject = mime_msg.get('Subject', '').strip()
        logger.debug(f"Email details - From: {sender_email}, Subject: '{subject}'")

        attachments = []
        for part in mime_msg.walk():
            if part.get_content_type() == 'application/pdf':
                file_data = part.get_payload(decode=True)
                file_name = part.get_filename() or f"attachment_{message_id}.pdf"
                logger.debug(f"Found PDF attachment: {file_name}")
                attachments.append({
                    "file_name": file_name,
                    "file_data": base64.b64encode(file_data).decode('utf-8')
                })

        if not attachments:
            logger.warning(f"Email {message_id} had no PDF attachments. Marking as read.")
        else:
            email_data = {
                "email_id": message_id,
                "sender": sender_email,
                "subject": subject,
                "attachments": attachments
            }
            logger.debug(f"Preparing to send message to Kafka topic '{KAFKA_INVOICES_TOPIC}': {json.dumps(email_data, indent=2)}")
            kafka_producer.send(KAFKA_INVOICES_TOPIC, email_data)
            logger.info(f"Sent email {message_id} with {len(attachments)} attachment(s) to Kafka.")

        # Mark email as read regardless of whether it had attachments
        gmail_service.users().messages().modify(
            userId=USER_ID, id=message_id, body={'removeLabelIds': ['UNREAD']}
        ).execute()
        logger.info(f"Marked email {message_id} as read.")

    except HttpError as error:
        logger.error(f"An HTTP error occurred while processing email {message_id}: {error}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while processing email {message_id}: {e}", exc_info=True)

def main():
    """Main loop to poll for emails and process them."""
    global allowed_senders
    logger.info("--- Starting Email Monitor Service ---")
    
    # Initialize services
    gmail_service = authenticate_gmail()
    if not gmail_service:
        raise Exception("Failed to authenticate with Gmail API. Service cannot start.")
        
    kafka_producer = init_kafka_producer()
    zoho_api = ZohoAPI()

    # Initialize allowed senders for the first time
    allowed_senders = fetch_allowed_senders(zoho_api)

    # Start the background thread to periodically update the senders list
    update_thread = Thread(target=update_allowed_senders, args=(zoho_api,), daemon=True)
    update_thread.start()
    logger.info("Started background thread for hourly sender list updates.")

    # Main polling loop
    while True:
        try:
            messages = fetch_emails(gmail_service)
            if messages:
                for msg in messages:
                    process_email(gmail_service, msg['id'], kafka_producer)
            
            logger.debug(f"Polling complete. Waiting for {POLL_INTERVAL} seconds...")
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            logger.error(f"An error occurred in the main polling loop: {e}", exc_info=True)
            time.sleep(POLL_INTERVAL) # Wait before retrying to prevent rapid-fire errors

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical("Email Monitor service failed to start or crashed.", exc_info=True)
        sys.exit(1)

