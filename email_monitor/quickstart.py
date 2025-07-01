import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
USER_ID = "me"

def authenticate_gmail():
    """Authenticate with Gmail API using OAuth 2.0."""
    creds = None
    
    # Check if token.json exists to reuse credentials
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, initiate OAuth flow
    if not creds or not creds.valid:
        if not os.path.exists(CREDENTIALS_FILE):
            print(f"Error: {CREDENTIALS_FILE} not found. Please ensure it is in the same directory.")
            return None
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)

def test_gmail_api():
    """Test Gmail API"""
    try:
        service = authenticate_gmail()
        if not service:
            return
        
        print("✅ Successfully authenticated with Gmail API.")
    
    except HttpError as error:
        print(f"An error occurred: {error}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    test_gmail_api()