
import logging
import sys
from datetime import datetime, timezone

import sys
import os

# Add backend to sys path so 'models' can be imported directly
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from models.strategy_state import StrategyConfig
from simulations.base import SimulationStrategy
from simulations.mock import MockExchange

# Configure Logging
logging.basicConfig(level=logging.INFO)

def test_simulation_trailing_buy():
    print("--- Starting Trailing Buy Simulation Test ---")
    
    # 1. Setup Config
    config = StrategyConfig(
        use_trailing_buy=True,
        trailing_buy_rebound_percent=0.2, # 0.2%
        strategy_mode="PRICE",
        buy_rate=0.01 # 1% drop triggers watch
    )
    
    # 2. Setup Candles (Synthetic)
    # Price: 100 -> 98 (Drop 2%, triggers watch) -> 98.5 (Rebound 0.5% > 0.2%, triggers buy)
    candles = [
        {"timestamp": 1000, "close": 100.0, "high": 100.0, "low": 100.0, "open": 100.0},
        {"timestamp": 2000, "close": 98.0, "high": 100.0, "low": 98.0, "open": 100.0}, # Drop
        {"timestamp": 3000, "close": 98.5, "high": 98.5, "low": 98.0, "open": 98.0},  # Rebound
    ]
    
    # 3. Initialize Strategy
    strategy = SimulationStrategy(config, 1000000.0, candles)
    strategy.ticker = "KRW-BTC"
    
    # 4. Mock Exchange Logic
    # We need to manually feed candles to calling get_candles logic?
    # SimulationStrategy.exchange is MockExchange.
    # We need to ensure strategy.current_candle is set.
    
    # Tick 1: 100.0 (First Buy)
    strategy.current_candle = candles[0]
    # In runner.py, first split is created if last_buy_price is None.
    # Calling internal method to force state catchup
    strategy._handle_active_positions(100.0) 
    print(f"Tick 1 (100.0): Splits={len(strategy.splits)}, Watch={strategy.is_watching}, Pending={strategy.pending_buy_units}")
    
    # Tick 2: 98.0 (Drop 2% from 100.0)
    # 100 * (1-0.01) = 99.0. 98.0 <= 99.0. Trigger Watch.
    strategy.current_candle = candles[1]
    strategy._handle_active_positions(98.0)
    print(f"Tick 2 (98.0): Splits={len(strategy.splits)}, Watch={strategy.is_watching}, Pending={strategy.pending_buy_units}")

    # Tick 3: 98.5 (Rebound)
    # Lowest=98.0. Target = 98.0 * (1 + 0.002) = 98.196.
    # 98.5 > 98.196. Trigger Buy.
    # BUT RSI CHECK!
    # MockExchange.get_candles will likely return empty list or small list?
    # Strategy.get_rsi_5m calls exchange.get_candles.
    # If MockExchange logic fails, get_rsi_5m returns 50.0.
    strategy.current_candle = candles[2]
    strategy._handle_active_positions(98.5)
    print(f"Tick 3 (98.5): Splits={len(strategy.splits)}, Watch={strategy.is_watching}, Pending={strategy.pending_buy_units}")
    
    # Check Result
    if len(strategy.splits) > 1:
        print("SUCCESS: Buy triggered.")
    else:
        print("FAILURE: No buy triggered.")

if __name__ == "__main__":
    test_simulation_trailing_buy()
