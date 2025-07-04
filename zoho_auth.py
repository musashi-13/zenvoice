import os
import requests
import pickle
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ZohoAuth:
    def __init__(self):
        # Load environment variables
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.redirect_uri = os.getenv("ZOHO_REDIRECT_URI")
        self.refresh_token = os.getenv("ZOHO_REFRESH_TOKEN")  
        self.access_token = None
        self.token_expiry = None
        self.token_file = "zoho_token.pickle"
        self.region = os.getenv("ZOHO_REGION", "in")  # Default to India region
        self.organization_id = os.getenv("ZOHO_ORGANIZATION_ID", "60042953022")

        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            raise ValueError("Missing required Zoho credentials in environment variables (ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REDIRECT_URI).")

        # Initialize tokens
        self.load_tokens()
        if not self.access_token or self.is_token_expired():
            self.refresh_tokens()

    def get_auth_code(self):
        """Generate the Zoho authorization URL for re-authentication."""
        params = {
            "scope": "ZohoBooks.fullaccess.all",
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "access_type": "offline",
            "prompt": "consent"
        }
        return f"https://accounts.zoho.{self.region}/oauth/v2/auth?{requests.compat.urlencode(params)}"

    def exchange_code_for_tokens(self, auth_code):
        """Exchange authorization code for access and refresh tokens."""
        url = f"https://accounts.zoho.{self.region}/oauth/v2/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": auth_code
        }
        response = requests.post(url, data=data)
        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens["refresh_token"]
            self.token_expiry = datetime.now() + timedelta(seconds=tokens["expires_in"])
            self.save_tokens()
            logger.info("Successfully exchanged auth code for tokens.")
        else:
            logger.error(f"Failed to exchange code: {response.text}")
            raise Exception("Token exchange failed.")

    def refresh_tokens(self):
        """Refresh access token using refresh token."""
        if not self.refresh_token:
            logger.error("No refresh token available. Please re-authenticate.")
            print(f"Please visit this URL to get a new auth code: {self.get_auth_code()}")
            auth_code = input("Enter the new auth code: ")
            self.exchange_code_for_tokens(auth_code)
            return

        url = f"https://accounts.zoho.{self.region}/oauth/v2/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token
        }
        response = requests.post(url, data=data)
        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens["access_token"]
            self.token_expiry = datetime.now() + timedelta(seconds=tokens["expires_in"])
            self.save_tokens()
            logger.info("Successfully refreshed access token.")
        else:
            logger.error(f"Failed to refresh token: {response.text}. Re-authentication required.")
            print(f"Please visit this URL to get a new auth code: {self.get_auth_code()}")
            auth_code = input("Enter the new auth code: ")
            self.exchange_code_for_tokens(auth_code)

    def is_token_expired(self):
        """Check if the access token has expired."""
        if not self.token_expiry:
            return True
        return datetime.now() >= self.token_expiry

    def save_tokens(self):
        """Save tokens to a pickle file."""
        tokens = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expiry": self.token_expiry
        }
        with open(self.token_file, "wb") as f:
            pickle.dump(tokens, f)
        logger.info(f"Saved tokens to {self.token_file}")

    def load_tokens(self):
        """Load tokens from a pickle file if it exists."""
        if os.path.exists(self.token_file):
            with open(self.token_file, "rb") as f:
                tokens = pickle.load(f)
                self.access_token = tokens["access_token"]
                self.refresh_token = tokens["refresh_token"]
                self.token_expiry = tokens["expiry"]
            logger.info(f"Loaded tokens from {self.token_file}")

    def get_access_token(self):
        """Return the current access token, refreshing if necessary."""
        if self.is_token_expired():
            self.refresh_tokens()
        return self.access_token

# Example usage
if __name__ == "__main__":
    try:
        auth = ZohoAuth()
        token = auth.get_access_token()
        print(f"Current access token: {token}")
    except Exception as e:
        logger.error(f"Authentication error: {e}")