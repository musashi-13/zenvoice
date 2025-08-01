import requests
import logging
from typing import Dict
from zoho_auth import ZohoAuth
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ZohoAPI:
    def __init__(self):
        self.auth = ZohoAuth()
        self.base_url = f"https://www.zohoapis.{self.auth.region}/books/v3"
        self.organization_id = self.auth.organization_id
        self._update_headers()  # Initialize headers with latest token
        logger.info(f"Initialized ZohoAPI with region: {self.auth.region}, organization_id: {self.organization_id}")

    def _update_headers(self):
        """Update the headers with the latest access token."""
        self.headers = {
            "Authorization": f"Zoho-oauthtoken {self.auth.get_access_token()}",
            "Content-Type": "application/json"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.exceptions.HTTPError, requests.exceptions.ConnectionError)),
        before_sleep=lambda retry_state: logger.info(f"Retrying API call (attempt {retry_state.attempt_number})...")
    )
    def make_api_call(self, method, endpoint, data=None, params=None):
        url = f"{self.base_url}/{endpoint}"
        self._update_headers()  # Ensure headers are fresh before each call
        try:
            response = requests.request(method, url, headers=self.headers, json=data, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.warning(f"401 Unauthorized detected. Refreshing token...")
                self._update_headers()  # Update headers with new token
                new_token = self.headers["Authorization"].split(" ")[1]
                if not new_token or not isinstance(new_token, str):
                    raise Exception("Failed to obtain a valid token after refresh.")
                raise  # Retry with updated headers
            logger.error(f"API call failed: {e.response.status_code} - {e.response.text}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise

    def get_vendors(self):
        """Fetch all vendors from Zoho Books and return their email addresses."""
        try:
            response = self.make_api_call("GET", "contacts", params={"contact_type": "vendor"})
            contacts = response.get("contacts", [])
            vendor_emails = [contact.get("email") for contact in contacts if contact.get("contact_type") == "vendor" and contact.get("email")]
            return vendor_emails
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to fetch vendors: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching vendors: {e}")
            return []

    def get_purchaseorder_id_by_number(self, po_number: str) -> str:
        """Fetch the purchaseorder_id for a given purchase order number."""
        params = {"organization_id": self.organization_id, "purchaseorder_number": po_number}
        try:
            response = self.make_api_call("GET", "purchaseorders", params=params)
            purchase_orders = response.get("purchaseorders", [])
            if purchase_orders and len(purchase_orders) > 0:
                purchase_order = purchase_orders[0]
                logger.info(f"Found purchaseorder_id for PO {po_number}")
                return purchase_order.get("purchaseorder_id", "")
            logger.warning(f"No purchase order found for PO number: {po_number}")
            return ""
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to fetch purchaseorder_id for {po_number}: {e.response.status_code} - {e.response.text}")
            return ""

    def get_purchase_order_details(self, purchaseorder_id: str) -> dict:
        """Fetch specific details for a purchase order using its purchaseorder_id."""
        try:
            response = self.make_api_call("GET", f"purchaseorders/{purchaseorder_id}")
            purchase_order = response.get("purchaseorder", {})
            details = {
                "purchaseorder_id": purchase_order.get("purchaseorder_id", ""),
                "purchaseorder_number": purchase_order.get("purchaseorder_number", ""),
                "vendor_name": purchase_order.get("vendor_name", ""),
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
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to fetch details for PO {purchaseorder_id}: {e.response.status_code} - {e.response.text}")
            return {}

    def create_bill_from_purchase_order(self, purchaseorder_id: str) -> Dict:
        """Fetch PO data and create a draft bill."""
        try:
            # Fetch purchase order details
            po_details = self.get_purchase_order_details(purchaseorder_id)
            if not po_details:
                logger.error(f"No purchase order data found for PO {purchaseorder_id}")
                return {}

            # Prepare bill data based on PO
            bill_data = {
                "purchaseorder_ids": [purchaseorder_id],
                "vendor_id": po_details.get("vendor_id"),
                "bill_number": f"{po_details.get('purchaseorder_number', purchaseorder_id)}",
                "date": po_details.get("purchaseorder_date"),
                "due_date": po_details.get("due_date"),
                "currency_id": po_details.get("currency_id"),
                "line_items": po_details.get("line_items", []),
                "reference_number": po_details.get("reference_number"),
                "status": "draft"
            }

            # Create the bill
            response = self.make_api_call("POST", "bills", data=bill_data)
            data = response.get("bill", {})
            bill_id = data.get("bill_id")
            logger.info(f"Created draft bill for PO {purchaseorder_id}: {bill_id}")
            return data
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error creating bill for PO {purchaseorder_id}: {e.response.status_code} - {e.response.text}")
            return {}

    def open_bill(self, bill_id: str) -> bool:
        """Update the bill status to 'open' in Zoho Books."""
        try:
            response = self.make_api_call("POST", f"bills/{bill_id}/status/open")
            data = response.get("message", "")
            logger.info(f"Opened bill {bill_id}: {data}")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error opening bill {bill_id}: {e.response.status_code} - {e.response.text}")
            return False

    def submit_bill_for_approval(self, bill_id: str) -> bool:
        """Submit a draft bill for pending approval."""
        try:
            response = self.make_api_call("POST", f"bills/{bill_id}/submit")
            data = response.get("message", "")
            logger.info(f"Submitted bill {bill_id} for approval: {data}")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error submitting bill {bill_id} for approval: {e.response.status_code} - {e.response.text}")
            return False

    def approve_bill(self, bill_id: str) -> bool:
        """Approve a bill after internal approval process."""
        try:
            response = self.make_api_call("POST", f"bills/{bill_id}/approve")
            data = response.get("message", "")
            logger.info(f"Approved bill {bill_id}: {data}")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error approving bill {bill_id}: {e.response.status_code} - {e.response.text}")
            return False

if __name__ == "__main__":
    zoho = ZohoAPI()
    vendors = zoho.get_vendors()
    print(f"Vendor emails: {vendors}")