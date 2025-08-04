import os
import requests
import json
from datetime import datetime
from typing import Dict
from zoho_auth import ZohoAuth
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from logger_config import setup_logger

# This allows the logger to be configured by the environment variable
# passed from docker-compose (e.g., EMAIL_MONITOR_LOG or INVOICE_PROCESSOR_LOG)
SERVICE_LOG_VAR = os.getenv('SERVICE_NAME_LOG_VAR', 'LOG') 
logger = setup_logger(__name__, SERVICE_LOG_VAR)

# Custom exception for clearer error handling
class ZohoApiError(Exception):
    pass

class ZohoAPI:
    def __init__(self):
        self.auth = ZohoAuth()
        self.base_url = f"https://www.zohoapis.{self.auth.region}/books/v3"
        self.organization_id = self.auth.organization_id
        logger.info(f"Initialized ZohoAPI for organization ID: {self.organization_id}")

    def _get_headers(self) -> Dict[str, str]:
        """Gets fresh authorization headers for an API call."""
        
        return {
            "Authorization": f"Zoho-oauthtoken {self.auth.get_access_token()}",
            "Content-Type": "application/json"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.HTTPError, requests.exceptions.ConnectionError)),
        before_sleep=lambda retry_state: logger.warning(f"Retrying API call (attempt {retry_state.attempt_number})...")
    )
    def make_api_call(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """A robust, centralized method for making all Zoho API calls."""
        
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers()
        
        # Always ensure organization_id is included in the request parameters
        params = params or {}
        params['organization_id'] = self.organization_id
        
        logger.debug(f"Making API call: {method} {url}")
        if data:
            logger.debug(f"Payload: {json.dumps(data, indent=2)}")

        try:
            response = requests.request(method, url, headers=headers, json=data, params=params, timeout=20)
            response.raise_for_status()
            response_data = response.json()
            logger.debug(f"API call successful. Response code: {response_data.get('code')}")
            return response_data
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.warning("401 Unauthorized detected. The token may be invalid. Tenacity will retry.")
                # The auth handler will automatically refresh on the next call, so we just let tenacity retry.
            else:
                logger.error(f"API call failed: {e.response.status_code} - {e.response.text}")
            raise # Re-raise the exception to trigger the tenacity retry mechanism
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"A network connection error occurred: {e}")
            raise

    def get_vendors(self) -> list:
        """Fetch all vendors from Zoho Books and return their email addresses."""
        
        logger.debug("Fetching list of vendor emails from Zoho Books...")
        try:
            response = self.make_api_call("GET", "contacts", params={"contact_type": "vendor"})
            contacts = response.get("contacts", [])
            vendor_emails = [
                contact.get("email") for contact in contacts 
                if contact.get("contact_type") == "vendor" and contact.get("email")
            ]
            logger.info(f"Successfully fetched {len(vendor_emails)} vendor emails.")
            logger.debug(f"Vendor emails found: {vendor_emails}")
            return vendor_emails
        except Exception as e:
            logger.error(f"Failed to fetch vendors: {e}")
            return []

    def get_purchaseorder_id_by_number(self, po_number: str) -> str:
        """Fetch the purchaseorder_id for a given purchase order number."""
        
        logger.debug(f"Searching for purchase order ID for PO number: {po_number}")
        try:
            response = self.make_api_call("GET", "purchaseorders", params={"purchaseorder_number": po_number})
            purchase_orders = response.get("purchaseorders", [])
            if purchase_orders:
                po_id = purchase_orders[0].get("purchaseorder_id", "")
                logger.debug(f"Found purchase order ID: {po_id}")
                return po_id
            else:
                logger.warning(f"No purchase order found for PO number: {po_number}")
                return ""
        except Exception as e:
            logger.error(f"Failed to fetch purchase order ID for {po_number}: {e}")
            return ""

    def get_purchase_order_details(self, purchaseorder_id: str) -> dict:
        """Fetch the full details for a purchase order using its ID."""
        
        logger.debug(f"Fetching full details for purchase order ID: {purchaseorder_id}")
        try:
            response = self.make_api_call("GET", f"purchaseorders/{purchaseorder_id}")
            po_details = response.get("purchaseorder", {})
            logger.debug(f"Full PO details received: {json.dumps(po_details, indent=2)}")
            return po_details
        except Exception as e:
            logger.error(f"Failed to fetch details for PO ID {purchaseorder_id}: {e}")
            return {}

    def create_bill_from_purchase_order(self, po_details: Dict, scanned_invoice: Dict) -> Dict:
        """Creates a draft bill using the correct two-step process."""
        
        purchaseorder_id = po_details.get("purchaseorder_id")
        if not purchaseorder_id:
            logger.error("Purchase order ID is missing from details. Cannot create bill.")
            return {}

        logger.debug(f"Initiating bill creation process for PO ID: {purchaseorder_id}")
        try:
            # Step 1: Get a pre-filled bill template from Zoho.
            logger.debug("Fetching pre-filled bill template from Zoho...")
            response_template = self.make_api_call(
                "GET", "bills/editpage/frompurchaseorders", 
                params={'purchaseorder_ids': purchaseorder_id}
            )
            
            bill_template = response_template.get("bill")
            if not bill_template:
                raise ZohoApiError(f"Failed to generate bill template. Response: {response_template}")

            # Step 2: Create a clean, filtered payload for the new bill.
            logger.debug("Constructing filtered payload for bill creation...")
            filtered_payload = {
                "purchaseorder_ids": bill_template.get("purchaseorder_ids"),
                "vendor_id": bill_template.get("vendor_id"),
                "bill_number": scanned_invoice.get("invoice_number"),
                "date": scanned_invoice.get("bill_date") or datetime.now().strftime('%Y-%m-%d'),
                "due_date": scanned_invoice.get("due_date", ""),
                "currency_id": bill_template.get("currency_id"),
                "line_items": bill_template.get("line_items", []),
                "reference_number": po_details.get("purchaseorder_number"),
                "status": "draft"
            }

            # Step 3: Create the actual bill using the clean payload.
            logger.debug(f"Submitting request to create bill for PO {purchaseorder_id} with data: {filtered_payload}...")
            response_create = self.make_api_call("POST", "bills", data=filtered_payload)
            
            created_bill = response_create.get("bill", {})
            bill_id = created_bill.get("bill_id")
            logger.info(f"Successfully created draft bill {bill_id} for PO {purchaseorder_id}")
            return created_bill

        except requests.exceptions.HTTPError as e:
            try:
                error_response = e.response.json()
                error_message = error_response.get("message", "").lower()
                if "billed already" in error_message or "associated with a bill" in error_message:
                    logger.warning(f"PO {purchaseorder_id} has already been billed. Skipping bill creation.")
                    return {}
            except (ValueError, json.JSONDecodeError):
                pass # Fall through to generic error if response is not JSON
            
            logger.error(f"HTTP error during bill creation for PO {purchaseorder_id}: {e.response.status_code} - {e.response.text}")
            return {}
        except Exception as e:
            logger.error(f"An unexpected error occurred while creating bill for PO {purchaseorder_id}: {e}")
            return {}

    def open_bill(self, bill_id: str) -> bool:
        """Update the bill status to 'open' in Zoho Books."""
        
        logger.debug(f"Attempting to change status to 'open' for bill ID: {bill_id}")
        try:
            response = self.make_api_call("POST", f"bills/{bill_id}/status/open")
            message = response.get("message", "")
            logger.info(f"Successfully opened bill {bill_id}: {message}")
            return True
        except Exception as e:
            logger.error(f"Failed to open bill {bill_id}: {e}")
            return False

    def submit_bill_for_approval(self, bill_id: str) -> bool:
        """Submit a draft bill for pending approval."""
        
        logger.debug(f"Attempting to submit bill for approval: {bill_id}")
        try:
            response = self.make_api_call("POST", f"bills/{bill_id}/submit")
            message = response.get("message", "")
            logger.info(f"Successfully submitted bill {bill_id} for approval: {message}")
            logger.debug(f"Full response for submitting bill: {response}")
            return True
        except Exception as e:
            logger.error(f"Failed to submit bill {bill_id} for approval: {e}")
            return False

    def approve_bill(self, bill_id: str) -> bool:
        """Approve a bill after internal approval process."""
        logger.debug(f"Attempting to approve bill: {bill_id}")
        try:
            response = self.make_api_call("POST", f"bills/{bill_id}/approve")
            message = response.get("message", "")
            logger.info(f"Successfully approved bill {bill_id}: {message}")
            logger.debug(f"Full response for approving bill: {response}")
            return True
        except Exception as e:
            logger.error(f"Failed to approve bill {bill_id}: {e}")
            return False

if __name__ == "__main__":
    
    # This block allows you to run the script directly for testing purposes.
    try:
        # For local testing, we can set the log level directly in the environment.
        os.environ['SERVICE_NAME_LOG_VAR'] = 'LOG'
        os.environ['LOG'] = 'DEV' # Set to DEV for detailed local testing
        
        # Re-initialize the logger to apply the test settings
        logger = setup_logger(__name__, 'LOG')

        logger.info("--- Running ZohoAPI in local test mode ---")
        zoho = ZohoAPI()
        
        # Example test: Fetch vendors
        vendors = zoho.get_vendors()
        if vendors:
            logger.info(f"Test successful. Found {len(vendors)} vendors.")
        else:
            logger.warning("Test completed, but no vendors were found.")

    except Exception as e:
        logger.critical("Local test run failed with an unhandled exception.", exc_info=True)
