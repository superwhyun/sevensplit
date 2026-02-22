import sys
import os
import time
from datetime import datetime, timezone
from typing import List, Optional

# Basic setup for logic testing
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

from strategies.logic_rsi import RSIStrategyLogic
from models.strategy_state import StrategyConfig

class MockExchange:
    def get_candles(self, ticker, count, interval):
        # Mock daily candles
        return [
            {"timestamp": int(time.time() * 1000) - i * 86400000, "close": 50000}
            for i in range(count)
        ]
    def buy_market_order(self, ticker, amount):
        return {"uuid": "test-uuid"}

class MockStrategy:
    def __init__(self):
        self.ticker = "KRW-BTC"
        self.strategy_id = 99
        self.config = StrategyConfig()
        self.exchange = MockExchange()
        self.splits = []
        self.is_running = True
        self.last_buy_date = None
        self.last_sell_date = None
        self.last_status_msg = ""
        self.budget = 1000000
        self.next_split_id = 1
        self.last_buy_price = 0

    def get_now_utc(self):
        return datetime.now(timezone.utc)

    def save_state(self): pass
    def log_event(self, level, event_type, msg): print(f"[{event_type}] {msg}")
    
    def has_sufficient_budget(self, market_context=None): return True
    def check_trade_limit(self): return True
    def is_already_bought_on_path(self, price): return False

def test_rsi_piercing():
    strategy = MockStrategy()
    logic = RSIStrategyLogic(strategy)
    
    # Setup piercing scenario: Prev RSI 25, Current RSI 35, Buy Max 30
    logic.prev_rsi = 25.0
    logic.current_rsi_daily = 35.0
    strategy.config.rsi_buy_max = 30.0
    
    print(f"Testing Buy Piercing: Prev={logic.prev_rsi}, Current={logic.current_rsi_daily}, Max={strategy.config.rsi_buy_max}")
    
    # Execute buy plan
    # Execute buy plan
    today = datetime.now().strftime("%Y-%m-%d")
    buy_plan = logic._plan_rsi_buy(35000.0, today)
    
    # Execute action plan
    logic._execute_rsi_action_plan([buy_plan], 35000.0, today)
    
    if len(strategy.splits) > 0 and strategy.splits[-1].buy_rsi == 35.0:
        print("✅ Buy RSI Recording Works (Recorded Live RSI 35.0)!")
    else:
        print(f"❌ Buy RSI Recording Failed. Expected 35.0, got {strategy.splits[-1].buy_rsi if strategy.splits else 'N/A'}")

    # Setup sell piercing scenario: Prev RSI 75, Current RSI 65, Sell Min 70
    logic.prev_rsi = 75.0
    logic.current_rsi_daily = 65.0
    strategy.config.rsi_sell_min = 70.0
    
    # Mock a split to sell
    from models.strategy_state import SplitState
    split = SplitState(id=len(strategy.splits)+1, status="BUY_FILLED", buy_price=30000, actual_buy_price=30000, buy_amount=10000, buy_volume=0.3)
    strategy.splits.append(split)
    
    print(f"Testing Sell Piercing: Prev={logic.prev_rsi}, Current={logic.current_rsi_daily}, Min={strategy.config.rsi_sell_min}")
    
    # Execute sell plan
    sell_plan = logic._plan_rsi_sell(65000.0, today)
    
    if sell_plan and sell_plan["type"] == "sell":
        print("✅ Sell Piercing Logic Works!")
    else:
        print("❌ Sell Piercing Logic Failed.")

if __name__ == "__main__":
    test_rsi_piercing()
