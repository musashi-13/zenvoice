import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import threading
from logger_config import setup_logger

# This allows the logger to be configured by the environment variable
# passed from docker-compose (e.g., EMAIL_MONITOR_LOG or INVOICE_PROCESSOR_LOG)
SERVICE_LOG_VAR = os.getenv('SERVICE_NAME_LOG_VAR', 'LOG') 
logger = setup_logger(__name__, SERVICE_LOG_VAR)

load_dotenv()

class ZohoAuth:
    def __init__(self):
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.organization_id = os.getenv("ZOHO_ORGANIZATION_ID")

        self.refresh_token = None
        self.access_token = None
        self.token_expiry = None
        
        self.token_file = "zoho_tokens.json" 
        self.region = "in"
        self._lock = threading.RLock()

        if not all([self.client_id, self.client_secret, self.organization_id]):
            logger.critical("Missing required Zoho credentials in environment variables.")
            raise ValueError("Missing required Zoho credentials.")

        # Initialize tokens
        self.load_tokens()
        if not self.access_token or self.is_token_expired():
            with self._lock:
                self.refresh_or_exchange_tokens()

    def get_auth_code(self):
        """Gets authorization code from environment variables."""
        
        auth_code = os.getenv("ZOHO_AUTH_CODE")
        if auth_code:
            logger.debug("Using ZOHO_AUTH_CODE from environment variables.")
            return auth_code
        
        logger.critical("ZOHO_AUTH_CODE is not set. Cannot generate new tokens. Check your environment variables.")
        raise Exception("ZOHO_AUTH_CODE is required for initial token generation in a non-interactive environment.")

    def exchange_code_for_tokens(self, auth_code):
        """Exchange authorization code for access and refresh tokens."""
        
        logger.debug("Attempting to exchange authorization code for new tokens...")
        url = f"https://accounts.zoho.{self.region}/oauth/v2/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": auth_code
        }
        try:
            response = requests.post(url, data=data, timeout=15)
            response.raise_for_status()
            tokens = response.json()
            
            with self._lock:
                self.access_token = tokens["access_token"]
                self.refresh_token = tokens["refresh_token"]
                self.token_expiry = datetime.now() + timedelta(seconds=tokens["expires_in"])
                self.save_tokens()
            logger.info("Successfully exchanged auth code for tokens.")
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to exchange code: {e.response.status_code} - {e.response.text}")
            raise Exception("Token exchange failed.")

    def refresh_tokens(self):
        """Refresh access token using refresh token."""
        
        if not self.refresh_token:
            logger.warning("No refresh token available. An auth code will be required.")
            return False
            
        logger.debug("Attempting to refresh access token...")
        url = f"https://accounts.zoho.{self.region}/oauth/v2/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token
        }
        try:
            response = requests.post(url, data=data, timeout=15)
            response.raise_for_status()
            tokens = response.json()

            with self._lock:
                self.access_token = tokens["access_token"]
                self.refresh_token = tokens.get("refresh_token", self.refresh_token)
                self.token_expiry = datetime.now() + timedelta(seconds=tokens["expires_in"])
                self.save_tokens()
            logger.info("Successfully refreshed access token.")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to refresh token: {e.response.status_code} - {e.response.text}. Re-authentication may be required.")
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
            logger.debug("Token expiry not set, assuming token is expired.")
            return True
        is_expired = datetime.now() >= (self.token_expiry - timedelta(seconds=300))
        logger.debug(f"Token expiration check: {'Expired' if is_expired else 'Valid'}.")
        return is_expired

    def save_tokens(self):
        logger.debug(f"Saving tokens to {self.token_file}...")
        tokens = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expiry_iso": self.token_expiry.isoformat() if self.token_expiry else None
        }
        try:
            with open(self.token_file, "w") as f:
                json.dump(tokens, f, indent=2)
            logger.info(f"Saved tokens to {self.token_file}")
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to save tokens to {self.token_file}: {e}")

    def load_tokens(self):
        if not os.path.exists(self.token_file):
            logger.info(f"Token file '{self.token_file}' not found. A new one will be created if needed.")
            return

        try:
            with open(self.token_file, "r") as f:
                tokens = json.load(f)
                with self._lock:
                    self.access_token = tokens.get("access_token")
                    self.refresh_token = tokens.get("refresh_token")
                    expiry_str = tokens.get("expiry_iso")
                    self.token_expiry = datetime.fromisoformat(expiry_str) if expiry_str else None
            logger.info(f"Loaded tokens from {self.token_file}")
        except (json.JSONDecodeError, IOError, TypeError) as e:
            logger.error(f"Failed to load or parse tokens from {self.token_file}: {e}. Will attempt to generate new tokens.")
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
                logger.critical("Failed to obtain a valid access token after all attempts.")
                raise Exception("Failed to obtain a valid access token after refresh.")
            return self.access_token
    
    def refresh_on_401(self):
        with self._lock:
            if self.refresh_tokens():
                return self.access_token
            raise Exception("Failed to refresh token after 401. Re-authentication required.")

if __name__ == "__main__":
    # This block allows you to run the script directly to test/generate a token
    try:
        # The logger needs to know which env var to check.
        # For local testing, we can just set it directly.
        os.environ['SERVICE_NAME_LOG_VAR'] = 'LOG'
        os.environ['LOG'] = 'DEV' # Set to DEV for detailed local testing
        
        # Re-initialize logger with test settings
        logger = setup_logger(__name__, 'LOG')

        auth = ZohoAuth()
        token = auth.get_access_token()
        logger.info(f"Successfully obtained access token: {token[:10]}...")
    except Exception as e:
        logger.critical(f"Authentication error: {e}", exc_info=True)

