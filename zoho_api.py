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
    python
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
        url = f"{self.base_url}/contacts?contact_type=vendor"
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
        
    def get_purchaseorder_id_by_number(self, po_number: str) -> str:
        """Fetch the purchaseorder_id for a given purchase order number."""
        url = f"{self.base_url}/purchaseorders"
        params = {
            "organization_id": self.organization_id,
            "purchaseorder_number": po_number
        }
        logger.info(f"Fetching purchaseorder_id for PO number: {po_number} from {url}")
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.auth.get_access_token()}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                purchase_order = data.get("purchaseorder", {})
                if purchase_order:
                    logger.info(f"Found purchaseorder_id for PO {po_number}")
                    return purchase_order.get("purchaseorder_id", "")
                else:
                    logger.warning(f"No purchase order found for PO number: {po_number}")
                    return ""
            else:
                logger.error(f"Failed to fetch purchaseorder_id for {po_number}: {response.status_code} - {response.text}")
                return ""
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching purchaseorder_id for {po_number}: {e}")
            return ""
        
        
    def get_purchase_order_details(self, purchaseorder_id: str) -> dict:
        """Fetch specific details for a purchase order using its purchaseorder_id."""
        url = f"{self.base_url}/purchaseorders/{purchaseorder_id}"
        logger.info(f"Fetching details for purchase order ID: {purchaseorder_id} from {url}")
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.auth.get_access_token()}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                purchase_order = data.get("purchaseorder", {})
                # Extract specified fields with defaults
                details = {
                    "total_quantity": float(purchase_order.get("total_quantity", 0)),
                    "line_items": purchase_order.get("line_items", []),
                    "adjustment": float(purchase_order.get("adjustment", 0.0)),
                    "sub_total": float(purchase_order.get("sub_total", 0.0)),
                    "sub_total_inclusive_of_tax": float(purchase_order.get("sub_total_inclusive_of_tax", 0.0)),
                    "tax_total": float(purchase_order.get("tax_total", 0.0)),
                    "discount_total": float(purchase_order.get("discount_total", 0.0)),
                    "total": float(purchase_order.get("total", 0.0)),
                    "taxes": purchase_order.get("taxes", []),
                    "tds_summary": purchase_order.get("tds_summary", [])
                }
                logger.info(f"Successfully fetched details for purchase order {purchaseorder_id}")
                return details
            else:
                logger.error(f"Failed to fetch details for PO {purchaseorder_id}: {response.status_code} - {response.text}")
                return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching details for PO {purchaseorder_id}: {e}")
            return {}

if __name__ == "__main__":
    zoho = ZohoAPI()
    vendors = zoho.get_vendors()
    print(f"Vendor emails: {vendors}")