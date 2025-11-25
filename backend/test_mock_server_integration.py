import threading
import time
import requests
import os
import sys

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from exchange import UpbitExchange
from mock_api_server import app as mock_app
import uvicorn

def run_mock_server():
    uvicorn.run(mock_app, host="0.0.0.0", port=5002)

def test_integration():
    # Start mock server in a thread
    server_thread = threading.Thread(target=run_mock_server, daemon=True)
    server_thread.start()
    time.sleep(2) # Wait for server to start

    print("Mock server started on port 5002")

    # Initialize Exchange pointing to mock server
    # Use dummy keys
    exchange = UpbitExchange("mock_access", "mock_secret", server_url="http://localhost:5002")

    # Test 1: Get Balance
    balance = exchange.get_balance("KRW")
    print(f"Initial KRW Balance: {balance}")
    assert balance == 10000000

    # Test 2: Get Current Price (should fetch from real Upbit via mock server)
    # This might fail if mock server fails to connect to Upbit, but let's see.
    # Mock server uses pyupbit.get_current_price.
    try:
        price = exchange.get_current_price("KRW-BTC")
        print(f"Real BTC Price via Mock: {price}")
    except Exception as e:
        print(f"Failed to get real price (expected if no internet or rate limit): {e}")

    # Test 3: Hold Price and Set Price
    print("Holding price...")
    exchange.hold_price("KRW-BTC", True)
    
    print("Setting mock price to 50000000...")
    exchange.set_mock_price("KRW-BTC", 50000000)

    price = exchange.get_current_price("KRW-BTC")
    print(f"Mocked BTC Price: {price}")
    assert price == 50000000

    # Test 4: Buy Order
    print("Placing buy order...")
    order = exchange.buy_limit_order("KRW-BTC", 49000000, 0.1)
    print(f"Order result: {order}")
    assert order is not None
    assert order['uuid'] is not None

    # Test 5: Check Balance after order
    # Cost = 49000000 * 0.1 = 4,900,000
    # Fee = 4,900,000 * 0.0005 = 2,450
    # Total = 4,902,450
    # Remaining = 10,000,000 - 4,902,450 = 5,097,550
    new_balance = exchange.get_balance("KRW")
    print(f"New KRW Balance: {new_balance}")
    assert new_balance == 5097550.0

    print("Integration Test Passed!")

if __name__ == "__main__":
    test_integration()
