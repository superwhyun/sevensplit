import json
from datetime import datetime, timedelta

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

candles = [
    create_candle(100000, 0),         # Start
    create_candle(99400, 5),          # Drop -0.6% (Watch)
    create_candle(98000, 10),         # Drop -2.0% (Update Low)
    create_candle(98300, 15),         # Rebound +0.3% (Wait)
    create_candle(98600, 20),         # Rebound +0.6% (Buy Trigger)
    create_candle(100000, 25)         # Recovery
]

config = {
    "investment_per_split": 10000,
    "buy_rate": 0.005,
    "sell_rate": 0.005,
    "strategy_mode": "PRICE",
    "rsi_buy_max": 100.0,
    "min_price": 0.0,
    "max_price": 0.0 
}

payload = {
    "strategy_config": config,
    "candles": candles,
    "start_index": 0,
    "ticker": "SIM-TEST",
    "budget": 1000000
}

with open("simulation_payload.json", "w") as f:
    json.dump(payload, f, indent=2)

print("Generated simulation_payload.json")
