import os
import json
import re
from typing import Dict
from zoho_api import ZohoAPI
from logger_config import setup_logger

SERVICE_LOG_VAR = os.getenv('SERVICE_NAME_LOG_VAR', 'LOG') 
logger = setup_logger(__name__, SERVICE_LOG_VAR)

zoho_api = ZohoAPI()

def match_invoice_with_purchase_order(scanned_data: Dict) -> Dict:
    """Match scanned invoice data with the corresponding purchase order and return validation result."""
    po_number = scanned_data.get("po_number")
    
    if not po_number:
        logger.warning("Validation failed: PO number not found in scanned data.")
        return {"match": False, "message": "PO number not found in scanned data", "purchase_order_id": None}

    logger.debug(f"Starting validation for PO number: {po_number}")

    purchase_order_id = zoho_api.get_purchaseorder_id_by_number(po_number)
    if not purchase_order_id:
        logger.error(f"Validation failed: No purchase order found in Zoho for PO number {po_number}.")
        return {"match": False, "message": f"No purchase order found for PO number {po_number}", "purchase_order_id": None}

    purchase_order_details = zoho_api.get_purchase_order_details(purchase_order_id)
    if not purchase_order_details:
        logger.error(f"Validation failed: Could not fetch details for PO ID {purchase_order_id}.")
        return {"match": False, "message": f"No details found for PO ID {purchase_order_id}", "purchase_order_id": purchase_order_id}

    logger.debug(f"Purchase Order Details from Zoho: {json.dumps(purchase_order_details, indent=2)}")

    # --- Start Validation Logic ---
    vendor_name_po = purchase_order_details.get("vendor_name", "")
    total_po = float(purchase_order_details.get("total", 0))
    line_items_po = purchase_order_details.get("line_items", [])

    items_scanned = scanned_data.get("items", [])
    
    match = True
    differences = []

    # 1. Compare Vendor Name
    vendor_name_po_clean = re.sub(r'\.', '', vendor_name_po).strip()
    vendor_name_scanned_clean = re.sub(r'\.', '', scanned_data.get("vendor_name", "")).strip()
    if vendor_name_po_clean.lower() != vendor_name_scanned_clean.lower():
        match = False
        differences.append(f"Vendor name mismatch: PO ('{vendor_name_po_clean}') vs Scanned ('{vendor_name_scanned_clean}')")

    # 2. Compare Total Amount
    total_scanned = float(scanned_data.get("total", 0))
    if abs(total_po - total_scanned) > 0.01:  # Allow for small floating-point differences
        match = False
        differences.append(f"Total amount mismatch: PO ({total_po}) vs Scanned ({total_scanned})")

    # 3. Compare Line Items
    cleaning_regex = r'[\u2013\s-]+' # Regex to clean hyphens, en-dashes, and spaces
    line_items_po_dict = {
        re.sub(cleaning_regex, '', item.get("description", "")).strip().lower(): item 
        for item in line_items_po
    }

    for item_scanned in items_scanned:
        scanned_desc_raw = item_scanned.get("item_details", "")
        scanned_desc_clean = re.sub(cleaning_regex, '', scanned_desc_raw).strip().lower()
        
        if scanned_desc_clean in line_items_po_dict:
            item_po = line_items_po_dict[scanned_desc_clean]
            # Compare quantity, rate, etc.
            quantity_po = float(item_po.get("quantity", 0))
            rate_po = float(item_po.get("rate", 0))
            quantity_scanned = float(item_scanned.get("quantity", 0))
            rate_scanned = float(item_scanned.get("rate", 0))

            if abs(quantity_po - quantity_scanned) > 0.01:
                match = False
                differences.append(f"Quantity mismatch for '{scanned_desc_raw}': PO ({quantity_po}) vs Scanned ({quantity_scanned})")
            if abs(rate_po - rate_scanned) > 0.01:
                match = False
                differences.append(f"Rate mismatch for '{scanned_desc_raw}': PO ({rate_po}) vs Scanned ({rate_scanned})")
        else:
            match = False
            differences.append(f"Item '{scanned_desc_raw}' not found in purchase order.")
    
    # --- End Validation Logic ---

    bill = {}
    if match:
        logger.info(f"Validation successful for PO {po_number}. Proceeding to create bill.")
        bill = zoho_api.create_bill_from_purchase_order(purchase_order_details, scanned_data)
        if not (bill and bill.get("bill_id")):
            logger.warning(f"Bill creation process for PO {po_number} did not return a valid bill ID. It might have failed or been skipped.")
    else:
        logger.error(f"Validation failed for PO {po_number}.")
        logger.debug(f"Differences found: {differences}")

    message = "Match successful" if match else "Match failed" + (f" due to: {', '.join(differences)}" if differences else "")
    return {
        "match": match,
        "message": message,
        "bill": bill,
        "purchase_order_id": purchase_order_id,
        "differences": differences if not match else [],
    }

if __name__ == "__main__":
    # This block allows for direct testing of this script.
    try:
        # Configure logger for local testing
        os.environ['SERVICE_NAME_LOG_VAR'] = 'LOG'
        os.environ['LOG'] = 'DEV'
        logger = setup_logger(__name__, 'LOG')

        logger.info("--- Running Invoice Validator in local test mode ---")
        
        sample_scanned_data = {
            "vendor_name": "Nvidia Inc.", # Added a period for testing cleaning logic
            "invoice_number": "INV-NVD-2025-0001",
            "po_number": "PO-00001",
            "bill_date": "2025-07-09",
            "due_date": None,
            "items": [
                {"item_details": "NVIDIA A100 Tensor Core GPU", "quantity": 8, "rate": 1687400, "amount": 13499200},
            ],
            "total": 13867049
        }
        
        # In a real test, you would mock the zoho_api calls
        logger.warning("Local test is running with LIVE Zoho API calls.")
        result = match_invoice_with_purchase_order(sample_scanned_data)
        
        print("\n--- Validation Result ---")
        print(json.dumps(result, indent=2))

    except Exception as e:
        logger.critical("Local test run failed.", exc_info=True)
