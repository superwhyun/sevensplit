"""Replay/backtest must stamp fills at their simulated (historical) time, not wall-clock
time. Regression test for: 1-day replay showing every trade as happening "just now".
"""
import os
import sys
import time
import unittest
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from exchange import PaperExchange
from services.simulation_service import _ReplayPaperExchange
from strategies.runtime_helpers import StrategyOrderManager

HISTORICAL_TS = 1_700_000_000.0  # 2023-11-14, far in the past relative to "now"
HISTORICAL_ISO = datetime.fromtimestamp(HISTORICAL_TS, tz=timezone.utc).isoformat()


class _PublicStub:
    def get_tick_size(self, price):
        return 1

    def normalize_price(self, price):
        return round(price)

    def get_current_price(self, ticker="KRW-BTC"):
        return 100_000_000.0

    def get_current_prices(self, tickers):
        return {t: 100_000_000.0 for t in tickers}

    def get_candles(self, ticker, count=200, interval="minutes/5", to=None):
        return []


class TestPaperExchangeDefaultClock(unittest.TestCase):
    def test_market_order_uses_wall_clock_by_default(self):
        exchange = PaperExchange(_PublicStub(), initial_krw=10_000_000.0)
        before = time.time()

        order = exchange.buy_market_order("KRW-BTC", 100_000.0)
        filled = exchange.get_order(order["uuid"])

        after = time.time()
        created_ts = datetime.fromisoformat(filled["created_at"]).timestamp()
        self.assertGreaterEqual(created_ts, before - 1)
        self.assertLessEqual(created_ts, after + 1)
        self.assertEqual(
            datetime.fromisoformat(filled["trades"][0]["created_at"]).timestamp(),
            created_ts,
        )


class TestReplayPaperExchangeClock(unittest.TestCase):
    def test_market_buy_during_replay_is_stamped_with_simulated_time_not_now(self):
        exchange = _ReplayPaperExchange(_PublicStub(), initial_krw=10_000_000.0)
        exchange.set_sim_time(HISTORICAL_TS)
        exchange.set_tick("KRW-BTC", 100_000_000.0)

        order = exchange.buy_market_order("KRW-BTC", 100_000.0)
        filled = exchange.get_order(order["uuid"])

        self.assertEqual(filled["created_at"], HISTORICAL_ISO)
        self.assertEqual(filled["trades"][0]["created_at"], HISTORICAL_ISO)

    def test_market_sell_during_replay_is_stamped_with_simulated_time(self):
        exchange = _ReplayPaperExchange(_PublicStub(), initial_krw=10_000_000.0)
        exchange.set_sim_time(HISTORICAL_TS)
        exchange.set_tick("KRW-BTC", 100_000_000.0)
        exchange.buy_market_order("KRW-BTC", 1_000_000.0)  # fund BTC balance for the sell

        order = exchange.sell_market_order("KRW-BTC", 0.005)
        filled = exchange.get_order(order["uuid"])

        self.assertEqual(filled["created_at"], HISTORICAL_ISO)
        self.assertEqual(filled["trades"][0]["created_at"], HISTORICAL_ISO)

    def test_limit_order_fills_at_the_simulated_time_it_actually_crosses(self):
        """A resting limit order placed on day 1 but filled on day 3 must record day 3,
        not day 1 (order creation) and not the wall-clock time the test runs at."""
        exchange = _ReplayPaperExchange(_PublicStub(), initial_krw=10_000_000.0)
        day1 = HISTORICAL_TS
        day3 = HISTORICAL_TS + 2 * 86400

        exchange.set_sim_time(day1)
        exchange.set_tick("KRW-BTC", 100_000_000.0)
        exchange.buy_market_order("KRW-BTC", 1_000_000.0)  # fund BTC so the sell lock succeeds
        order = exchange.sell_limit_order("KRW-BTC", 105_000_000.0, 0.005)

        # Price hasn't reached the target yet on day 1: must still be waiting.
        still_waiting = exchange.get_order(order["uuid"])
        self.assertEqual(still_waiting["state"], "wait")

        exchange.set_sim_time(day3)
        exchange.set_tick("KRW-BTC", 106_000_000.0)  # now crosses the sell target
        filled = exchange.get_order(order["uuid"])

        self.assertEqual(filled["state"], "done")
        expected_iso = datetime.fromtimestamp(day3, tz=timezone.utc).isoformat()
        self.assertEqual(filled["trades"][0]["created_at"], expected_iso)

    def test_real_time_phase_after_replay_falls_back_to_wall_clock(self):
        """Once set_sim_time(None) is used (real-time phase resumes), fills use wall time."""
        exchange = _ReplayPaperExchange(_PublicStub(), initial_krw=10_000_000.0)
        exchange.set_sim_time(HISTORICAL_TS)
        exchange.set_tick("KRW-BTC", 100_000_000.0)

        now_ts = time.time()
        exchange.set_sim_time(now_ts)
        order = exchange.buy_market_order("KRW-BTC", 100_000.0)
        filled = exchange.get_order(order["uuid"])

        created_ts = datetime.fromisoformat(filled["created_at"]).timestamp()
        self.assertAlmostEqual(created_ts, now_ts, delta=2)


class TestOrderManagerRecordsSimulatedFillTime(unittest.TestCase):
    """End-to-end: the order manager's bought_at/trade timestamp must reflect the
    exchange's simulated clock, confirming the fix all the way through resolve_fill_time."""

    def test_buy_fill_bought_at_matches_historical_sim_time(self):
        from models.strategy_state import SplitState, StrategyConfig

        class _Strategy:
            strategy_id = 1
            ticker = "KRW-BTC"

            def __init__(self, exchange):
                self.exchange = exchange
                self.config = StrategyConfig()
                self.adaptive_buy_controller = None

            def get_now_utc(self):
                # Deliberately return real "now" to prove resolve_fill_time prefers the
                # exchange's recorded fill time over this fallback during replay.
                return datetime.now(timezone.utc)

            def save_state(self):
                return None

        exchange = _ReplayPaperExchange(_PublicStub(), initial_krw=10_000_000.0)
        exchange.set_sim_time(HISTORICAL_TS)
        exchange.set_tick("KRW-BTC", 100_000_000.0)
        order = exchange.buy_market_order("KRW-BTC", 100_000.0)

        strategy = _Strategy(exchange)
        split = SplitState(id=1, status="PENDING_BUY", buy_order_uuid=order["uuid"], buy_price=100_000_000.0)
        manager = StrategyOrderManager()

        manager.check_buy_order(strategy, split)

        self.assertEqual(split.status, "BUY_FILLED")
        self.assertEqual(split.bought_at, HISTORICAL_ISO)


if __name__ == "__main__":
    unittest.main()
