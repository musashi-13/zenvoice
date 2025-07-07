import requests
import logging
from zoho_auth import ZohoAuth

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ZohoAPI:
    def __init__(self):
        self.auth = ZohoAuth()
        self.base_url = f"https://www.zohoapis.{self.auth.region}/books/v3"
        self.organization_id = self.auth.organization_id

    def get_vendors(self):
        """Fetch all vendors from Zoho Books and return their email addresses."""
        url = f"{self.base_url}/contacts?contact_type=vendor"  # Corrected URL
        logger.info(f"Fetching from URL: {url}")
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.auth.get_access_token()}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                contacts = data.get("contacts", [])
                vendor_emails = [contact.get("email") for contact in contacts if contact.get("contact_type") == "vendor" and contact.get("email")]
                logger.info(f"Fetched {len(vendor_emails)} vendor emails: {vendor_emails}")
                return vendor_emails
            else:
                logger.error(f"Failed to fetch vendors: {response.status_code} - {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching vendors: {e}")
            return []

if __name__ == "__main__":
    zoho = ZohoAPI()
    vendors = zoho.get_vendors()
    print(f"Vendor emails: {vendors}")