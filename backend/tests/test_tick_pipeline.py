import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategies.tick_pipeline import TickPipeline


class _StubTickCoordinator:
    def dedupe_splits(self, strategy):
        return None

    def resolve_current_price(self, strategy, current_price):
        return current_price

    def build_open_order_uuids(self, strategy, open_orders=None):
        return {"sell-1"}

    def update_indicators(self, strategy, current_price, market_context=None):
        return {}


class _StubOrderManager:
    def __init__(self):
        self.calls = 0
        self.last_open_order_uuids = None

    def manage_orders(self, strategy, open_order_uuids):
        self.calls += 1
        self.last_open_order_uuids = open_order_uuids


class _StubConfig:
    strategy_mode = "PRICE"


class _StubRSILogic:
    def __init__(self):
        self.calls = 0

    def tick(self, current_price, market_context=None, indicators_updated=False):
        self.calls += 1


class _StubWatchLogic:
    def check_proceed_to_buy(self, current_price, rsi_5m):
        return True, False


class _StubPriceLogic:
    def __init__(self):
        self.plan_calls = 0
        self.execute_calls = 0

    def plan_buy(self, current_price, rsi_5m, just_exited_watch=False, market_context=None):
        self.plan_calls += 1
        return {"rsi_5m": rsi_5m}

    def execute_buy_logic(self, current_price, rsi_5m, market_context=None, planned_buy=None):
        self.execute_calls += 1


class _StubStrategy:
    def __init__(self, is_running):
        self.is_running = is_running
        self.tick_coordinator = _StubTickCoordinator()
        self.order_manager = _StubOrderManager()
        self.config = _StubConfig()
        self.rsi_logic = _StubRSILogic()
        self.watch_logic = _StubWatchLogic()
        self.price_logic = _StubPriceLogic()


class TestTickPipeline(unittest.TestCase):
    def test_stopped_strategy_still_syncs_orders_but_skips_buy_flow(self):
        strategy = _StubStrategy(is_running=False)
        pipeline = TickPipeline()

        pipeline.run(strategy, current_price=100.0, open_orders=[{"uuid": "sell-1"}], market_context={})

        self.assertEqual(strategy.order_manager.calls, 1)
        self.assertEqual(strategy.order_manager.last_open_order_uuids, {"sell-1"})
        self.assertEqual(strategy.rsi_logic.calls, 0)
        self.assertEqual(strategy.price_logic.plan_calls, 0)
        self.assertEqual(strategy.price_logic.execute_calls, 0)


if __name__ == "__main__":
    unittest.main()
