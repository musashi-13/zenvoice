import requests
import pickle
import json

# File where tokens are stored
token_file = "zoho_token.pickle"

# Load tokens from the pickle file
try:
    with open(token_file, "rb") as f:
        tokens = pickle.load(f)
        access_token = tokens["access_token"]
        print(f"Loaded access token from {token_file}: {access_token[:10]}... (truncated)")
except FileNotFoundError:
    print(f"Error: {token_file} not found. Please run zoho-auth.py to generate it first.")
    exit(1)
except KeyError:
    print("Error: 'access_token' not found in pickle file. Check the file contents.")
    exit(1)
except Exception as e:
    print(f"Error loading token file: {str(e)}")
    exit(1)

organization_id = "60042953022"  # Your current organization ID
region = "in"  # Your current region

# Base URL
base_url = f"https://www.zohoapis.{region}/books/v3"

# Endpoint for fetching purchase orders
purchase_orders_endpoint = f"{base_url}/purchaseorders?purchaseorder_number=PO-00001"
#po_details_endpoint = f"{base_url}/purchaseorders/2702270000000036043"


headers = {
    "Authorization": f"Zoho-oauthtoken {access_token}",
    "Content-Type": "application/json"
}

# Fetch purchase orders and dump JSON
try:
    params = {
        "organization_id": organization_id
    }
    response = requests.get(purchase_orders_endpoint, headers=headers, params=params)
    response.raise_for_status()  # Raise an exception for bad status codes

    data = response.json()
    print(json.dumps(data, indent=4))  # Dump the raw JSON response to the console
except requests.exceptions.RequestException as e:
    print(f"Error fetching purchase orders: {e}")
except ValueError as e:
    print(f"Error parsing JSON response: {e}")