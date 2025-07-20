import requests
import logging
from typing import Dict
from zoho_auth import ZohoAuth

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ZohoAPI:
    def __init__(self):
        self.auth = ZohoAuth()
        self.base_url = f"https://www.zohoapis.{self.auth.region}/books/v3"
        self.organization_id = self.auth.organization_id
        logger.info(f"Initialized ZohoAPI with region: {self.auth.region}, organization_id: {self.organization_id}")

    def get_vendors(self):
        """Fetch all vendors from Zoho Books and return their email addresses."""
        url = f"{self.base_url}/contacts?contact_type=vendor"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.auth.get_access_token()}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                contacts = data.get("contacts", [])
                vendor_emails = [contact.get("email") for contact in contacts if contact.get("contact_type") == "vendor" and contact.get("email")]
                return vendor_emails
            else:
                logger.error(f"Failed to fetch vendors: {response.status_code} - {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching vendors: {e}")
            print(f"get_vendors Exception details: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching vendors: {e}")
            print(f"get_vendors Unexpected exception details: {str(e)}")
            return []

    def get_purchaseorder_id_by_number(self, po_number: str) -> str:
        """Fetch the purchaseorder_id for a given purchase order number."""
        url = f"{self.base_url}/purchaseorders"
        params = {
            "organization_id": self.organization_id,
            "purchaseorder_number": po_number
        }
        access_token = self.auth.get_access_token()
        if not access_token or not isinstance(access_token, str):
            logger.error(f"Invalid access token for PO {po_number}: {access_token}")
            return ""
        logger.info(f"Fetching purchaseorder_id for PO number: {po_number} from {url} with token: {access_token[:10]}...")
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            print(f"fetch po_id response contains: {response}, status_code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                purchase_orders = data.get("purchaseorders", [])  # Get the list of purchase orders
                if purchase_orders and len(purchase_orders) > 0:
                    purchase_order = purchase_orders[0]  # Take the first matching purchase order
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
            print(f"Exception details: {str(e)}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error fetching purchaseorder_id for {po_number}: {e}")
            print(f"Unexpected exception details: {str(e)}")
            return ""

    def get_purchase_order_details(self, purchaseorder_id: str) -> dict:
        """Fetch specific details for a purchase order using its purchaseorder_id."""
        url = f"{self.base_url}/purchaseorders/{purchaseorder_id}"
        access_token = self.auth.get_access_token()
        if not access_token or not isinstance(access_token, str):
            logger.error(f"Invalid access token for PO ID {purchaseorder_id}: {access_token}")
            return {}
        logger.info(f"Fetching details for purchase order ID: {purchaseorder_id} from {url} with token: {access_token[:10]}...")
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"fetch data with po_id response contains: {response}, status_code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Response.json contains: {data}")
                purchase_order = data.get("purchaseorder", {})
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
            else:
                logger.error(f"Failed to fetch details for PO {purchaseorder_id}: {response.status_code} - {response.text}")
                return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching details for PO {purchaseorder_id}: {e}")
            print(f"Exception details: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching details for PO {purchaseorder_id}: {e}")
            print(f"Unexpected exception details: {str(e)}")
            return {}
        
    def create_bill_from_purchase_order(self, purchaseorder_id: str) -> Dict:
        """Fetch PO data and create a draft bill."""
        url = f"{self.base_url}/bills/editpage/frompurchaseorders?purchaseorder_ids={purchaseorder_id}&organization_id={self.organization_id}"
        try:
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            bill_data = response.json().get("purchaseorder", {})
            filtered_bill_data = {
                "purchaseorder_ids": [purchaseorder_id],
                "vendor_id": bill_data.get("vendor_id"),
                "bill_number": f"{bill_data.get('reference_number', purchaseorder_id)}",
                "date": bill_data.get("date"),
                "due_date": bill_data.get("due_date"),
                "currency_id": bill_data.get("currency_id"),
                "line_items": bill_data.get("line_items", []),
                "reference_number": bill_data.get("reference_number"),
                "status": "draft"
            }
            create_url = f"{self.base_url}/bills?organization_id={self.organization_id}"
            create_response = requests.post(create_url, headers=self.headers, json=filtered_bill_data)
            create_response.raise_for_status()
            data = create_response.json()
            logger.info(f"Created draft bill for PO {purchaseorder_id}: {data.get('bill').get('bill_id')}")
            return data.get("bill", {})
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating bill for PO {purchaseorder_id}: {e.response.status_code} - {e.response.text}")
            return {}

    def open_bill(self, bill_id: str) -> bool:
        """Update the bill status to 'open' in Zoho Books."""
        url = f"{self.base_url}/bills/{bill_id}/status/open?organization_id={self.organization_id}"
        try:
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Opened bill {bill_id}: {data.get('message')}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error opening bill {bill_id}: {e.response.status_code} - {e.response.text}")
            return False
        
    def submit_bill_for_approval(self, bill_id: str) -> bool:
        """Submit a draft bill for pending approval."""
        url = f"{self.base_url}/bills/{bill_id}/submit?organization_id={self.organization_id}"
        try:
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Submitted bill {bill_id} for approval: {data.get('message')}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error submitting bill {bill_id} for approval: {e.response.status_code} - {e.response.text}")
            return False

    def approve_bill(self, bill_id: str) -> bool:
        """Approve a bill after internal approval process."""
        url = f"{self.base_url}/bills/{bill_id}/approve?organization_id={self.organization_id}"
        try:
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Approved bill {bill_id}: {data.get('message')}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error approving bill {bill_id}: {e.response.status_code} - {e.response.text}")
            return False

if __name__ == "__main__":
    zoho = ZohoAPI()
    vendors = zoho.get_vendors()
    print(f"Vendor emails: {vendors}")