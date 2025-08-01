import os
import requests
import pickle
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import threading

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ZohoAuth:
    def __init__(self):
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.organization_id = os.getenv("ZOHO_ORGANIZATION_ID")

        self.refresh_token = None
        self.access_token = None
        self.token_expiry = None
        
        self.token_file = "zoho_token.pickle"
        self.region = "in"
        # Use a Re-entrant Lock (RLock) to prevent deadlocks when a method
        # that already holds the lock calls another method that also needs the lock.
        self._lock = threading.RLock()

        if not all([self.client_id, self.client_secret, self.organization_id]):
            raise ValueError("Missing required Zoho credentials in environment variables.")

        # Initialize tokens
        self.load_tokens()
        if not self.access_token or self.is_token_expired():
            with self._lock:
                self.refresh_or_exchange_tokens()

    def get_auth_code(self):
        """Prompt user to enter authorization code manually or use env variable."""
        auth_code = os.getenv("ZOHO_AUTH_CODE")
        if auth_code:
            logger.debug("Using ZOHO_AUTH_CODE from environment variables.")
            return auth_code
        logger.debug("Please generate an authorization code manually from the Zoho Developer Console:")
        return input("Enter the new auth code: ")

    def exchange_code_for_tokens(self, auth_code):
        """Exchange authorization code for access and refresh tokens."""
        url = f"https://accounts.zoho.in/oauth/v2/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": auth_code
        }
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            tokens = response.json()
            with self._lock:
                self.access_token = tokens["access_token"]
                self.refresh_token = tokens["refresh_token"]
                self.token_expiry = datetime.now() + timedelta(seconds=tokens["expires_in"])
                self.save_tokens()
            logger.info("Successfully exchanged auth code for tokens.")
        else:
            logger.fatal(f"Failed to exchange code: {response.status_code} - {response.text}")
            raise Exception("Token exchange failed.")

    def refresh_tokens(self):
        """Refresh access token using refresh token."""
        if not self.refresh_token:
            logger.fatal("No refresh token available. Please provide an auth code.")
            return False
        url = f"https://accounts.zoho.in/oauth/v2/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token
        }
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            tokens = response.json()
            with self._lock:
                self.access_token = tokens["access_token"]
                self.refresh_token = tokens.get("refresh_token", self.refresh_token)
                self.token_expiry = datetime.now() + timedelta(seconds=tokens["expires_in"])
                self.save_tokens()
            logger.info("Successfully refreshed access token.")
            return True
        else:
            logger.fatal(f"Failed to refresh token: {response.status_code} - {response.text}. Re-authentication required.")
            return False

    def refresh_or_exchange_tokens(self):
        """Attempt to refresh tokens; fall back to exchanging a new auth code if refresh fails."""
        with self._lock:
            if not self.refresh_tokens():
                auth_code = self.get_auth_code()
                self.exchange_code_for_tokens(auth_code)

    def is_token_expired(self):
        """Check if the access token has expired with a 5-minute buffer."""
        if not self.token_expiry:
            return True
        return datetime.now() >= (self.token_expiry - timedelta(seconds=300))

    def save_tokens(self):
        """Save tokens to a pickle file with error handling."""
        tokens = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expiry": self.token_expiry
        }
        try:
            with open(self.token_file, "wb") as f:
                pickle.dump(tokens, f)
            logger.info(f"Saved tokens to {self.token_file}")
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to save tokens to {self.token_file}: {e}")

    def load_tokens(self):
        """Load tokens from a pickle file if it exists, with error handling."""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "rb") as f:
                    tokens = pickle.load(f)
                    with self._lock:
                        self.access_token = tokens["access_token"]
                        self.refresh_token = tokens["refresh_token"]
                        self.token_expiry = tokens["expiry"]
                    logger.info(f"Loaded tokens from {self.token_file}")
            except (pickle.UnpicklingError, EOFError, IOError) as e:
                logger.error(f"Failed to load tokens from {self.token_file}: {e}")
                # Clear invalid tokens to force refresh
                with self._lock:
                    self.access_token = None
                    self.refresh_token = None
                    self.token_expiry = None

    def get_access_token(self):
        """Return the current access token, refreshing or exchanging if necessary."""
        with self._lock:
            if self.is_token_expired():
                self.refresh_or_exchange_tokens()
            if not self.access_token:
                raise Exception("Failed to obtain a valid access token after refresh.")
            return self.access_token
    
    def refresh_on_401(self):
        with self._lock:
            if self.refresh_tokens():
                return self.access_token
            raise Exception("Failed to refresh token after 401. Re-authentication required.")

if __name__ == "__main__":
    try:
        auth = ZohoAuth()
        token = auth.get_access_token()
        logger.info(f"Obtained access token: {token[:10]}...")
    except Exception as e:
        logger.fatal(f"Authentication error: {e}")