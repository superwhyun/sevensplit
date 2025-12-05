import os
import jwt
import uuid
import hashlib
import urllib.parse
import requests
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv("backend/.env.real")

ACCESS_KEY = os.getenv("UPBIT_OPEN_API_ACCESS_KEY")
SECRET_KEY = os.getenv("UPBIT_OPEN_API_SECRET_KEY")
SERVER_URL = os.getenv("UPBIT_OPEN_API_SERVER_URL", "https://api.upbit.com")

if not ACCESS_KEY or not SECRET_KEY:
    print("Error: UPBIT_OPEN_API_ACCESS_KEY or UPBIT_OPEN_API_SECRET_KEY not found in backend/.env.real")
    sys.exit(1)

def get_order_status(order_uuid):
    payload = {
        'access_key': ACCESS_KEY,
        'nonce': str(uuid.uuid4()),
    }

    params = {'uuid': order_uuid}
    query_string = urllib.parse.urlencode(params)

    m = hashlib.sha512()
    m.update(query_string.encode())
    query_hash = m.hexdigest()

    payload['query_hash'] = query_hash
    payload['query_hash_alg'] = 'SHA512'

    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    headers = {'Authorization': f'Bearer {token}'}

    try:
        res = requests.get(f"{SERVER_URL}/v1/order", params=params, headers=headers)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_order_status.py <order_uuid>")
        sys.exit(1)
    
    order_uuid = sys.argv[1]
    print(f"Checking order {order_uuid}...")
    result = get_order_status(order_uuid)
    
    if result:
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("-" * 40)
        print(f"State: {result.get('state')}")
        print(f"Executed Volume: {result.get('executed_volume')}")
        print(f"Remaining Volume: {result.get('remaining_volume')}")
        print(f"Paid Fee: {result.get('paid_fee')}")
        print(f"Trades Count: {len(result.get('trades', []))}")
    else:
        print("Failed to fetch order.")
