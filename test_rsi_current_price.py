import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv("backend/.env.real")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from utils.indicators import calculate_rsi

SERVER_URL = os.getenv("UPBIT_OPEN_API_SERVER_URL", "https://api.upbit.com")

def test_rsi_with_current_price():
    """Test RSI calculation with and without current price injection"""
    ticker = "KRW-BTC"
    interval = "minutes/5"
    count = 100

    print(f"Testing RSI calculation for {ticker} ({interval})")
    print("=" * 80)

    # Fetch candles from Upbit API
    url = f"{SERVER_URL}/v1/candles/{interval}"
    params = {'market': ticker, 'count': count}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        candles = response.json()

        # Sort by timestamp ascending (oldest first)
        sorted_candles = sorted(candles, key=lambda x: x.get('timestamp') or 0)

        # Extract closes
        closes = [float(c.get('trade_price', 0)) for c in sorted_candles]

        # Get current price (simulate real-time price)
        current_price_url = f"{SERVER_URL}/v1/ticker"
        current_price_resp = requests.get(current_price_url, params={'markets': ticker})
        current_price_data = current_price_resp.json()
        current_price = float(current_price_data[0]['trade_price'])

        print(f"\n1. Candle Data:")
        print("-" * 80)
        print(f"Total candles: {len(closes)}")
        print(f"Last candle close price: {closes[-1]:,.0f}")
        print(f"Current real-time price: {current_price:,.0f}")
        print(f"Price difference: {current_price - closes[-1]:,.0f} ({((current_price - closes[-1]) / closes[-1] * 100):.2f}%)")

        print(f"\n2. RSI Calculation WITHOUT current price injection:")
        print("-" * 80)
        rsi_14_original = calculate_rsi(closes, 14)
        rsi_5_original = calculate_rsi(closes, 5)
        print(f"RSI(14) from candle data: {rsi_14_original:.2f}" if rsi_14_original else "RSI(14): None")
        print(f"RSI(5) from candle data: {rsi_5_original:.2f}" if rsi_5_original else "RSI(5): None")

        print(f"\n3. RSI Calculation WITH current price injection (Backend method):")
        print("-" * 80)
        closes_modified = closes.copy()
        closes_modified[-1] = current_price  # ← This is what backend does
        rsi_14_modified = calculate_rsi(closes_modified, 14)
        rsi_5_modified = calculate_rsi(closes_modified, 5)
        print(f"RSI(14) with current price: {rsi_14_modified:.2f}" if rsi_14_modified else "RSI(14): None")
        print(f"RSI(5) with current price: {rsi_5_modified:.2f}" if rsi_5_modified else "RSI(5): None")

        print(f"\n4. Comparison:")
        print("-" * 80)
        if rsi_14_original and rsi_14_modified:
            diff_14 = rsi_14_modified - rsi_14_original
            print(f"RSI(14) difference: {diff_14:+.2f} ({diff_14 / rsi_14_original * 100:+.2f}%)")
        if rsi_5_original and rsi_5_modified:
            diff_5 = rsi_5_modified - rsi_5_original
            print(f"RSI(5) difference: {diff_5:+.2f} ({diff_5 / rsi_5_original * 100:+.2f}%)")

        print(f"\n5. Watch Mode Trigger Analysis:")
        print("-" * 80)
        rsi_threshold = 30.0
        print(f"Watch Mode Threshold: RSI < {rsi_threshold}")
        print(f"Chart RSI(14): {rsi_14_original:.2f} → {'✓ SAFE' if rsi_14_original >= rsi_threshold else '✗ TRIGGER'}")
        print(f"Backend RSI(14): {rsi_14_modified:.2f} → {'✓ SAFE' if rsi_14_modified >= rsi_threshold else '✗ TRIGGER'}")

        if (rsi_14_original >= rsi_threshold) and (rsi_14_modified < rsi_threshold):
            print(f"\n⚠️  DISCREPANCY DETECTED!")
            print(f"Chart shows SAFE (RSI {rsi_14_original:.2f}), but backend triggers WATCH MODE (RSI {rsi_14_modified:.2f})")
        elif (rsi_14_original < rsi_threshold) and (rsi_14_modified >= rsi_threshold):
            print(f"\n⚠️  DISCREPANCY DETECTED!")
            print(f"Chart shows TRIGGER (RSI {rsi_14_original:.2f}), but backend is SAFE (RSI {rsi_14_modified:.2f})")
        else:
            print(f"\n✓ Both chart and backend agree on watch mode status")

        print(f"\n6. Last 5 price changes:")
        print("-" * 80)
        for i in range(max(0, len(closes) - 5), len(closes)):
            if i > 0:
                change = closes[i] - closes[i-1]
                print(f"[{i}] {closes[i]:,.0f} (change: {change:+,.0f})")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rsi_with_current_price()
