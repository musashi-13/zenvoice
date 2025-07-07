import requests
import pickle

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

# Test endpoints
endpoints = [
    f"{base_url}/organizations",  # List all organizations
    f"{base_url}/contacts",  # List all contacts
    f"{base_url}/contacts?contact_type=vendor"  # List vendors
]

headers = {
    "Authorization": f"Zoho-oauthtoken {access_token}",
    "Content-Type": "application/json"
}

for endpoint in endpoints:
    print(f"\nTesting URL: {endpoint}")
    try:
        response = requests.get(endpoint, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")