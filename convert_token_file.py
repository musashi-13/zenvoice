import pickle
import json
from datetime import datetime

PICKLE_FILE = 'zoho_token.pickle'
JSON_FILE = 'zoho_tokens.json'

print(f"Attempting to convert {PICKLE_FILE} to {JSON_FILE}...")

try:
    # Read the data from the pickle file
    with open(PICKLE_FILE, 'rb') as f:
        pickle_data = pickle.load(f)

    # The 'expiry' key holds a Python datetime object. JSON needs a number (timestamp).
    # We convert it to a Unix timestamp in milliseconds, which JavaScript can easily use.
    expiry_datetime = pickle_data.get('expiry')
    if isinstance(expiry_datetime, datetime):
        # Calculate expiry_time in milliseconds for JavaScript's Date object
        expiry_timestamp_ms = int(expiry_datetime.timestamp() * 1000)
    else:
        # Fallback if expiry is not a datetime object for some reason
        expiry_timestamp_ms = None

    # Create the JSON structure that the TypeScript service expects
    json_data = {
        "access_token": pickle_data.get("access_token"),
        "refresh_token": pickle_data.get("refresh_token"),
        "expires_in": 3600, # This is just a placeholder, expiry_time is what matters
        "expiry_time": expiry_timestamp_ms
    }

    # Write the data to the JSON file
    with open(JSON_FILE, 'w') as f:
        json.dump(json_data, f, indent=2)

    print(f"✅ Successfully created {JSON_FILE}.")

except FileNotFoundError:
    print(f"❌ Error: The file '{PICKLE_FILE}' was not found.")
except Exception as e:
    print(f"❌ An unexpected error occurred: {e}")