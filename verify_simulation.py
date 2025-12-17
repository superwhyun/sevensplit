import requests
import json
from datetime import datetime, timedelta

# Define the endpoint
url = "http://localhost:8000/simulate"

# Helper to create candle
def create_candle(price, time_offset_minutes):
    base_time = datetime(2025, 1, 1, 12, 0, 0)
    t = base_time + timedelta(minutes=time_offset_minutes)
    return {
        "timestamp": t.timestamp(),
        "candle_date_time_kst": t.isoformat(),
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "trade_price": price
    }

# Scenario:
# 1. Start: 100,000
# 2. Drop to 99,400 (-0.6%) -> Should Enter Watch (Buy Rate 0.5% = 99,500)
# 3. Drop to 98,000 (-2.0%) -> Should Update Low
# 4. Rebound to 98,600 (+0.6% from 98,000) -> Should Trigger Buy (Rebound 0.5%)
#    (98,000 * 1.005 = 98,490)

candles = [
    create_candle(100000, 0),   # Start
    create_candle(99400, 5),    # Drop -0.6% (Watch)
    create_candle(98000, 10),   # Drop -2.0% (Update Low)
    create_candle(98300, 15),   # Rebound +0.3% (Wait)
    create_candle(98600, 20),   # Rebound +0.6% (Buy Trigger)
    create_candle(100000, 25)   # Recovery
]

# Config
config = {
    "investment_per_split": 10000,
    "buy_rate": 0.005,      # 0.5% Drop
    "sell_rate": 0.005,
    "strategy_mode": "PRICE",
    "rsi_buy_max": 100.0    # Disable RSI filter (set high) logic for this test to focus on Price Logic
                            # Note: Strategy check is `if rsi > 30`. 
                            # But wait, my logic is `get_rsi_5m`.
                            # In simulation, if I don't precise daily candles, RSI might be 0 or 50.
                            # get_rsi_5m fallback is 50.0. So it should PASS (50 > 30).
}

payload = {
    "strategy_config": config,
    "candles": candles,
    "start_index": 0,
    "ticker": "SIM-TEST",
    "budget": 1000000
}

try:
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        result = response.json()
        print("Simulation Result:")
        print(f"Trade Count: {result.get('trade_count')}")
        print("\nLogs:")
        for log in result.get('logs', []):
            if "Trailing Buy" in log:
                print(log)
            # print(log) # Debug all
        
        print("\nSplits:")
        for s in result.get('splits', []):
            print(f"Split {s['id']}: Status={s['status']}, BoughtAt={s['buy_price']}")
            
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Exception: {e}")
