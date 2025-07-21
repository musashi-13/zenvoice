import json
import re
from typing import Dict
from zoho_api import ZohoAPI

zoho_api = ZohoAPI()

def match_invoice_with_purchase_order(scanned_data: Dict) -> Dict:
    """Match scanned invoice data with the corresponding purchase order and return validation result."""
    po_number = scanned_data.get("po_number")
    
    if not po_number:
        return {"match": False, "message": "PO number not found in scanned data", "purchase_order_id": None}

    # Fetch the purchase order ID
    purchase_order_id = zoho_api.get_purchaseorder_id_by_number(po_number)
    if not purchase_order_id:
        return {"match": False, "message": f"No purchase order found for PO number {po_number}", "purchase_order_id": None}

    # Fetch purchase order details
    purchase_order_details = zoho_api.get_purchase_order_details(purchase_order_id)
    if not purchase_order_details:
        return {"match": False, "message": f"No details found for PO ID {purchase_order_id}", "purchase_order_id": purchase_order_id}

    print("Purchase Order Details fetched from zoho: ", json.dumps(purchase_order_details, indent=4))
    vendor_name_po = purchase_order_details.get("vendor_name", "")
    vendor_name_po = re.sub(r'\.', '', vendor_name_po)
    total_po = float(purchase_order_details.get("total", 0))
    total_quantity_po = float(purchase_order_details.get("total_quantity", 0))
    line_items_po = purchase_order_details.get("line_items", [])

    # Extract scanned data details
    vendor_name_scanned = scanned_data.get("vendor_name")
    total_scanned = float(scanned_data.get("total", 0))
    items_scanned = scanned_data.get("items", [])
    total_quantity_scanned = sum(float(item.get("quantity", 0)) for item in items_scanned)

    # Initial match check
    match = True
    differences = []

    # Compare vendor name (note: may need to fetch from get_purchase_order_by_number if not in details)
    if re.sub(r'\.', '',vendor_name_po) != vendor_name_scanned:
        match = False
        differences.append(f"Vendor name mismatch: PO ({vendor_name_po}) vs Scanned ({vendor_name_scanned})")

    # Compare total
    if abs(total_po - total_scanned) > 0.01:  # Allow for small floating-point differences
        match = False
        differences.append(f"Total mismatch: PO ({total_po}) vs Scanned ({total_scanned})")

    # Compare total quantity
    if abs(total_quantity_po - total_quantity_scanned) > 0.01:
        match = False
        differences.append(f"Total quantity mismatch: PO ({total_quantity_po}) vs Scanned ({total_quantity_scanned})")

    # Compare line items
    line_items_po_dict = {re.sub(r'[\u2013] ', '', item.get("description")): item for item in line_items_po}
    for item_scanned in items_scanned:
        description = item_scanned.get("item_details")
        if description in line_items_po_dict:
            item_po = line_items_po_dict[description]
            quantity_po = float(item_po.get("quantity", 0))
            rate_po = float(item_po.get("rate", 0))
            amount_po = float(item_po.get("item_total", 0))
            quantity_scanned = float(item_scanned.get("quantity", 0))
            rate_scanned = float(item_scanned.get("rate", 0))
            amount_scanned = float(item_scanned.get("amount", 0))

            if abs(quantity_po - quantity_scanned) > 0.01:
                match = False
                differences.append(f"Quantity mismatch for {description}: PO ({quantity_po}) vs Scanned ({quantity_scanned})")
            if abs(rate_po - rate_scanned) > 0.01:
                match = False
                differences.append(f"Rate mismatch for {description}: PO ({rate_po}) vs Scanned ({rate_scanned})")
            if abs(amount_po - amount_scanned) > 0.01:
                match = False
                differences.append(f"Amount mismatch for {description}: PO ({amount_po}) vs Scanned ({amount_scanned})")
        else:
            match = False
            differences.append(f"Item {description} not found in purchase order")
    bill = {}
    if match:
        bill = zoho_api.create_bill_from_purchase_order(purchase_order_id)
        if bill and bill.get("bill_id"):
            print(f"Created draft bill {bill['bill_id']} for PO {purchase_order_id}")
        else:
            print(f"Failed to create draft bill for PO {purchase_order_id}")

    message = "Match successful" if match else "Match failed" + (f" due to: {', '.join(differences)}" if differences else "")
    return {
        "match": match,
        "message": message,
        "bill": bill,
        "purchase_order_id": purchase_order_id,
        "differences": differences if not match else [],
        "purchase_order_details": purchase_order_details  # Include all specified fields for future use
    }

# Example usage (for testing)
if __name__ == "__main__":
    sample_scanned_data = {
        "vendor_name": "Nvidia Inc",
        "invoice_number": "INV-NVD-2025-0001",
        "po_number": "PO-00001",
        "bill_date": "2025-07-09",
        "due_date": None,
        "items": [
            {"item_details": "NVIDIA A100 Tensor Core GPU", "quantity": 8, "rate": 1687400, "amount": 13499200},
            {"item_details": "NVIDIA CUDA Toolkit Support 1 year", "quantity": 1, "rate": 150000, "amount": 150000},
            {"item_details": "On-Site Installation & Testing Support", "quantity": 1, "rate": 96500, "amount": 96500},
            {"item_details": "Logistics & Secure Shipping (Bangalore)", "quantity": 1, "rate": 121349, "amount": 121349}
        ],
        "sub_total": 13867049,
        "discount": {"percentage": 0, "amount": 0},
        "tax": {"tds_percent": "0", "tds_amount": 0, "tds_tax_name": None},
        "total": 13867049
    }
    result = match_invoice_with_purchase_order(sample_scanned_data)
    print(json.dumps(result, indent=4))