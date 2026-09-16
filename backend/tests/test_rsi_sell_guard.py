"""RSI market sell must not double-sell when the existing limit sell cannot be cancelled."""
import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.strategy_state import SplitState, StrategyConfig
from strategies.logic_rsi import RSIStrategyLogic


class _StubExchange:
    def __init__(self, cancel_fails):
        self.cancel_fails = cancel_fails
        self.cancel_calls = []
        self.market_sell_calls = []

    def cancel_order(self, uuid):
        self.cancel_calls.append(uuid)
        if self.cancel_fails:
            raise Exception("Upbit API Error: 400 order already done")
        return {"uuid": uuid}

    def sell_market_order(self, ticker, volume):
        self.market_sell_calls.append((ticker, volume))
        return {"uuid": "market-sell-1"}


class _StubOrderManager:
    def __init__(self):
        self.check_calls = []

    def check_sell_order(self, strategy, split):
        self.check_calls.append(split.id)


class _StubStrategy:
    def __init__(self, cancel_fails):
        self.ticker = "KRW-BTC"
        self.config = StrategyConfig(strategy_mode="RSI")
        self.exchange = _StubExchange(cancel_fails)
        self.order_manager = _StubOrderManager()
        self.save_calls = 0

    def save_state(self):
        self.save_calls += 1


def _pending_sell_split():
    return SplitState(
        id=7,
        status="PENDING_SELL",
        buy_order_uuid="buy-7",
        sell_order_uuid="sell-7",
        buy_price=100.0,
        actual_buy_price=100.0,
        buy_amount=100.0,
        buy_volume=1.0,
        target_sell_price=110.0,
    )


class TestRSIMarketSellGuard(unittest.TestCase):
    def test_cancel_failure_skips_market_sell_and_reconciles_existing_order(self):
        strategy = _StubStrategy(cancel_fails=True)
        logic = RSIStrategyLogic(strategy)
        split = _pending_sell_split()

        logic._execute_market_sell(split)

        self.assertEqual(strategy.exchange.cancel_calls, ["sell-7"])
        self.assertEqual(strategy.exchange.market_sell_calls, [])
        self.assertEqual(strategy.order_manager.check_calls, [7])
        self.assertEqual(split.sell_order_uuid, "sell-7")

    def test_successful_cancel_proceeds_with_market_sell(self):
        strategy = _StubStrategy(cancel_fails=False)
        logic = RSIStrategyLogic(strategy)
        split = _pending_sell_split()

        logic._execute_market_sell(split)

        self.assertEqual(strategy.exchange.market_sell_calls, [("KRW-BTC", 1.0)])
        self.assertEqual(split.sell_order_uuid, "market-sell-1")
        self.assertEqual(split.status, "PENDING_SELL")


if __name__ == "__main__":
    unittest.main()
