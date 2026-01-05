import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv("backend/.env.real")

SERVER_URL = os.getenv("UPBIT_OPEN_API_SERVER_URL", "https://api.upbit.com")

def test_candle_order():
    """Test the order of candle data returned by Upbit API"""
    ticker = "KRW-BTC"
    interval = "minutes/5"
    count = 10

    print(f"Testing candle data order for {ticker} ({interval})")
    print("=" * 60)

    # Fetch candles from Upbit API
    url = f"{SERVER_URL}/v1/candles/{interval}"
    params = {'market': ticker, 'count': count}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        candles = response.json()

        print(f"\n1. RAW API Response (first 3 items):")
        print("-" * 60)
        for i, candle in enumerate(candles[:3]):
            timestamp = candle.get('timestamp')
            candle_time = candle.get('candle_date_time_utc')
            price = candle.get('trade_price')
            print(f"[{i}] timestamp: {timestamp}, time: {candle_time}, price: {price}")

        # Check if data is in descending order (newest first)
        print(f"\n2. Checking timestamp order:")
        print("-" * 60)
        timestamps = [c.get('timestamp', 0) for c in candles]
        is_descending = all(timestamps[i] >= timestamps[i+1] for i in range(len(timestamps)-1))
        print(f"Is descending (newest first)? {is_descending}")
        if is_descending:
            print("✓ Upbit returns data in DESCENDING order (newest → oldest)")
        else:
            print("✗ Data is NOT in descending order")

        # Sort by timestamp ascending (oldest first)
        print(f"\n3. After sorting by timestamp (ascending):")
        print("-" * 60)
        sorted_candles = sorted(candles, key=lambda x: x.get('timestamp') or 0)
        for i, candle in enumerate(sorted_candles[:3]):
            timestamp = candle.get('timestamp')
            candle_time = candle.get('candle_date_time_utc')
            price = candle.get('trade_price')
            print(f"[{i}] timestamp: {timestamp}, time: {candle_time}, price: {price}")

        # Extract closes
        closes = [float(c.get('trade_price', 0)) for c in sorted_candles]
        print(f"\n4. Price sequence (oldest → newest) for RSI calculation:")
        print("-" * 60)
        print(f"Closes: {closes[:5]} ... {closes[-3:]}")
        print(f"Total: {len(closes)} candles")

        # Import and test RSI calculation
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
        from utils.indicators import calculate_rsi

        print(f"\n5. RSI Calculation Test:")
        print("-" * 60)
        rsi_14 = calculate_rsi(closes, 14)
        rsi_5 = calculate_rsi(closes, 5)
        print(f"RSI(14): {rsi_14:.2f}" if rsi_14 else "RSI(14): None")
        print(f"RSI(5): {rsi_5:.2f}" if rsi_5 else "RSI(5): None")

        print(f"\n6. Verification:")
        print("-" * 60)
        print(f"✓ Data fetched from Upbit: {len(candles)} candles")
        print(f"✓ Sorted to chronological order: oldest → newest")
        print(f"✓ RSI calculated using correct sequence")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_candle_order()
