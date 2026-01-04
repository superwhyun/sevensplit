
import requests
import json

url = "http://localhost:8000/strategies/2/simulate"
payload = {
    "start_time": "2023-12-01T00:00:00.000Z"
}
headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    print(f"Status Code: {response.status_code}")
    print("Response Content:")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
