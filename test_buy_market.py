import sys
import os
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from exchange import UpbitExchange

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_buy_market():
    exchange = UpbitExchange(
        access_key="mock_access_key",
        secret_key="mock_secret_key",
        server_url="http://localhost:5001"
    )

    ticker = "KRW-BTC"
    amount = 10000.0 # Float amount

    print(f"Testing buy_market_order with amount={amount} (type: {type(amount)})")
    try:
        result = exchange.buy_market_order(ticker, amount)
        print("Result:", result)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_buy_market()
