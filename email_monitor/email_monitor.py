import os
import pickle
import time
import base64
import logging
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from kafka import KafkaProducer
from email import message_from_bytes
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from google.auth.transport.requests import Request
from zoho_api import ZohoAPI

# Load environment variables
from dotenv import load_dotenv
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

# Configure logging to send to Kafka
class KafkaHandler(logging.Handler):
    def __init__(self, producer, topic):
        super().__init__()
        self.producer = producer
        self.topic = topic

    def emit(self, record):
        log_message = self.format(record)
        log_data = {
            "timestamp": record.created,
            "level": record.levelname,
            "message": log_message,
            "module": record.module,
            "line": record.lineno
        }
        try:
            self.producer.send(self.topic, log_data)
        except Exception as e:
            print(f"Failed to send log to Kafka: {e}")

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Kafka Producer with retry
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    before_sleep=lambda retry_state: logger.info(f"Retrying Kafka connection (attempt {retry_state.attempt_number})...")
)
def init_kafka_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

try:
    producer = init_kafka_producer()
    kafka_handler = KafkaHandler(producer, KAFKA_LOGS_TOPIC)
    logger.addHandler(kafka_handler)
except Exception as e:
    logger.error(f"Kafka connection failed after retries: {e}")
    exit(1)

def authenticate_gmail():
    """Authenticate with Gmail API using OAuth 2.0."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if not os.path.exists(CREDENTIALS_FILE):
            logger.error(f"{CREDENTIALS_FILE} not found")
            return None
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

def fetch_allowed_senders():
    """Fetch vendor emails from Zoho Books."""
    zoho_api = ZohoAPI()
    allowed_senders = zoho_api.get_vendors()
    logger.info(f"Fetched {len(allowed_senders)} allowed senders from Zoho Books")
    if not allowed_senders:
        logger.warning("No vendor emails fetched from Zoho. Using empty list.")
    return allowed_senders

def fetch_emails(gmail_service):
    """Fetch unread emails with 'invoice' in subject from allowed senders."""
    allowed_senders = fetch_allowed_senders()
    if not allowed_senders:
        logger.warning("No allowed senders fetched from Zoho. Using empty list.")
        allowed_senders = []
    query = "from:(" + " OR ".join(allowed_senders) + ") invoice is:unread"
    try:
        results = gmail_service.users().messages().list(userId=USER_ID, q=query).execute()
        messages = results.get('messages', [])
        return messages
    except HttpError as error:
        logger.error(f"Error fetching emails: {error}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching emails: {e}")
        return []

def process_email(gmail_service, message_id):
    """Extract PDF attachments and send to Kafka."""
    try:
        message = gmail_service.users().messages().get(userId=USER_ID, id=message_id, format='raw').execute()
        msg_str = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))
        mime_msg = message_from_bytes(msg_str)

        sender_email = mime_msg['From']
        subject = mime_msg.get('Subject', '').strip()

        logger.info(f"Processing email {message_id} from {sender_email} with subject: '{subject}'")

        attachments = []
        for part in mime_msg.walk():
            if part.get_content_type() == 'application/pdf':
                file_data = part.get_payload(decode=True)
                file_name = part.get_filename() or f"attachment_{message_id}.pdf"
                attachments.append({
                    "file_name": file_name,
                    "file_data": base64.b64encode(file_data).decode('utf-8')
                })

        if not attachments:
            logger.info(f"No PDF attachments in email {message_id}")
            return

        email_data = {
            "email_id": message_id,
            "sender": sender_email,
            "subject": subject,
            "attachments": attachments
        }

        producer.send(KAFKA_INVOICES_TOPIC, email_data)
        logger.info(f"Sent email {message_id} with {len(attachments)} attachments to {KAFKA_INVOICES_TOPIC}")

        gmail_service.users().messages().modify(
            userId=USER_ID, id=message_id, body={'removeLabelIds': ['UNREAD']}
        ).execute()
        logger.info(f"Marked email {message_id} as read")

    except HttpError as error:
        logger.error(f"Error processing email {message_id}: {error}")
    except Exception as e:
        logger.error(f"Unexpected error processing email {message_id}: {e}")

def main():
    """Main loop to poll for emails and process them."""
    logger.info("Starting Gmail invoice processor")
    gmail_service = authenticate_gmail()
    if not gmail_service:
        logger.error("Failed to authenticate with Gmail API")
        return

    while True:
        messages = fetch_emails(gmail_service)
        if messages:
            for msg in messages:
                process_email(gmail_service, msg['id'])
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()