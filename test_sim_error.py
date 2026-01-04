#!/usr/bin/env python3
"""Test simulation to reproduce 500 error"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from simulations.runner import run_simulation
from simulations.config import SimulationConfig
from strategies import StrategyConfig
from datetime import datetime, timezone

# Create minimal config
strategy_config = StrategyConfig(
    investment_per_split=100000,
    min_price=80000000,
    max_price=120000000,
    buy_rate=0.005,
    sell_rate=0.005,
    fee_rate=0.0005,
    tick_interval=10,
    rebuy_strategy="reset_on_clear",
    max_trades_per_day=100,
    strategy_mode="PRICE",
    rsi_period=14,
    rsi_timeframe="minutes/60",
    rsi_buy_max=30.0,
    rsi_buy_first_threshold=5.0,
    rsi_buy_first_amount=1,
    rsi_buy_next_threshold=1.0,
    rsi_buy_next_amount=1,
    rsi_sell_min=70.0,
    rsi_sell_first_threshold=5.0,
    rsi_sell_first_amount=1,
    rsi_sell_next_threshold=1.0,
    rsi_sell_next_amount=1,
    stop_loss=-10.0,
    max_holdings=20,
    use_trailing_buy=False,
    trailing_buy_rebound_percent=0.2,
    trailing_buy_batch=True,
    price_segments=[]
)

# Create minimal candles
candles = []
base_price = 100000000
base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

for i in range(100):
    ts = base_time.timestamp() + (i * 3600)  # hourly
    candles.append({
        'timestamp': ts,
        'opening_price': base_price,
        'high_price': base_price * 1.01,
        'low_price': base_price * 0.99,
        'trade_price': base_price + (i * 10000),
        'candle_date_time_kst': datetime.fromtimestamp(ts + 32400).strftime('%Y-%m-%dT%H:%M:%S')
    })

sim_config = SimulationConfig(
    strategy_config=strategy_config,
    candles=candles,
    start_index=10,
    start_time=base_time.timestamp() + (10 * 3600),
    ticker="KRW-BTC",
    budget=1000000
)

try:
    print("Running simulation...")
    result = run_simulation(sim_config)
    print(f"✓ Success! Trades: {result['trade_count']}, Profit: {result['total_profit']}")
    if result.get('debug_logs'):
        print("\nDebug Logs:")
        for log in result['debug_logs'][:10]:
            print(f"  - {log}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
