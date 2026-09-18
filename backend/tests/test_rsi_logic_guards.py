"""RSI strategy guards: candle close boundary, restart safety, paper sell tolerance."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from exchange import PaperExchange
from models.strategy_state import StrategyConfig
from strategies.logic_rsi import RSIStrategyLogic
from strategies.runtime_helpers import StrategyStateManager

KST = timezone(timedelta(hours=9))
DAY = 86400


class _Stub:
    def __init__(self, now_utc):
        self.config = StrategyConfig(strategy_mode="RSI", rsi_period=14)
        self.ticker = "KRW-BTC"
        self._now = now_utc
        self.exchange = None
        self.splits = []
        self.last_buy_date = None
        self.last_sell_date = None
        self.budget = 1e12
        self.saved = 0
        self.events = []

    def get_now_utc(self):
        return self._now

    def get_current_time_kst(self):
        return self._now.astimezone(KST)

    def save_state(self):
        self.saved += 1

    def log_event(self, level, event_type, message):
        self.events.append((event_type, message))


def _daily_candles(last_ts, n=40):
    return [{"timestamp": last_ts - i * DAY, "trade_price": 100.0 + (i % 7)} for i in range(n, -1, -1)]


class TestDailyCandleCloseBoundary(unittest.TestCase):
    """Upbit daily candles close at 09:00 KST (UTC midnight + 24h)."""

    def setUp(self):
        self.open_candle_ts = datetime(2026, 9, 17, tzinfo=timezone.utc).timestamp()  # closes 9/18 09:00 KST
        self.ctx = {"candles": {"KRW-BTC": {"days": _daily_candles(self.open_candle_ts)}}}

    def _latest_evaluated(self, now_utc):
        logic = RSIStrategyLogic(_Stub(now_utc))
        logic._update_daily_rsi(100.0, market_context=self.ctx)
        return logic._last_evaluated_candle_ts

    def test_before_0900_kst_the_current_candle_is_still_open(self):
        at_0300_kst = datetime(2026, 9, 17, 18, 0, tzinfo=timezone.utc)
        self.assertEqual(self._latest_evaluated(at_0300_kst), self.open_candle_ts - DAY)

    def test_after_0900_kst_the_candle_counts_as_closed(self):
        at_0930_kst = datetime(2026, 9, 18, 0, 30, tzinfo=timezone.utc)
        self.assertEqual(self._latest_evaluated(at_0930_kst), self.open_candle_ts)

    def test_new_candle_evaluation_persists_state(self):
        stub = _Stub(datetime(2026, 9, 18, 0, 30, tzinfo=timezone.utc))
        logic = RSIStrategyLogic(stub)
        logic._update_daily_rsi(100.0, market_context=self.ctx)
        logic._update_daily_rsi(100.0, market_context=self.ctx)
        self.assertEqual(stub.saved, 1, "save once when a new candle is evaluated, not every tick")


class TestRestartDoesNotRefireSignal(unittest.TestCase):
    def test_guards_round_trip_through_state_payload(self):
        stub = _Stub(datetime(2026, 9, 18, 0, 30, tzinfo=timezone.utc))
        stub.rsi_logic = RSIStrategyLogic(stub)
        stub.rsi_logic._last_evaluated_candle_ts = 1_700_000_000.0
        stub.last_buy_date = "2026-09-18"
        stub.last_sell_date = None
        # fields _build_state_payload also reads
        for k in ("is_running", "next_split_id", "last_buy_price", "last_sell_price", "next_buy_target_price",
                  "is_watching", "watch_lowest_price", "pending_buy_units", "adaptive_reentry_pressure"):
            setattr(stub, k, None)
        stub.strategy_id = 1

        payload = StrategyStateManager()._build_state_payload(stub)

        self.assertEqual(payload["rsi_last_buy_date"], "2026-09-18")
        self.assertIsNone(payload["rsi_last_sell_date"])
        self.assertEqual(payload["rsi_last_evaluated_candle_ts"], 1_700_000_000.0)

        fresh = _Stub(stub._now)
        fresh.rsi_logic = RSIStrategyLogic(fresh)
        state = SimpleNamespace(
            is_running=False, next_split_id=1, last_buy_price=None, last_sell_price=None, budget=1.0,
            rsi_last_buy_date="2026-09-18", rsi_last_sell_date=None, rsi_last_evaluated_candle_ts=1_700_000_000.0,
        )
        StrategyStateManager()._apply_runtime_state(fresh, state)

        self.assertEqual(fresh.last_buy_date, "2026-09-18")
        self.assertEqual(fresh.rsi_logic._last_evaluated_candle_ts, 1_700_000_000.0)

    def test_same_day_buy_is_blocked_after_reload(self):
        stub = _Stub(datetime(2026, 9, 18, 0, 30, tzinfo=timezone.utc))
        stub.last_buy_date = stub.get_current_time_kst().strftime("%Y-%m-%d")
        logic = RSIStrategyLogic(stub)
        logic.prev_prev_rsi, logic.prev_rsi = 28.0, 33.0  # a valid up-cross through 30
        self.assertIsNone(logic._plan_rsi_buy(100.0, stub.last_buy_date))


class _PublicStub:
    def get_tick_size(self, price): return 1
    def normalize_price(self, price): return round(price)
    def get_current_price(self, ticker="KRW-BTC"): return 100_000_000.0
    def get_current_prices(self, tickers): return {t: 100_000_000.0 for t in tickers}
    def get_candles(self, *a, **k): return []


class TestPaperMarketSellTolerance(unittest.TestCase):
    def test_last_split_sells_despite_float_rounding(self):
        ex = PaperExchange(_PublicStub(), initial_krw=10_000_000.0)
        vols = []
        for amount in (300_000.0, 300_000.0, 300_000.0):
            o = ex.buy_market_order("KRW-BTC", amount)
            vols.append(float(ex.get_order(o["uuid"])["executed_volume"]))
        for v in vols:  # each split sells its exact recorded volume
            ex.sell_market_order("KRW-BTC", v)
        self.assertEqual(ex.balances["BTC"]["balance"], 0.0)

    def test_genuinely_insufficient_still_rejected(self):
        ex = PaperExchange(_PublicStub(), initial_krw=10_000_000.0)
        ex.buy_market_order("KRW-BTC", 100_000.0)
        with self.assertRaises(Exception):
            ex.sell_market_order("KRW-BTC", 0.5)


class TestDefaults(unittest.TestCase):
    def test_sell_percent_defaults_to_all_profitable_splits(self):
        self.assertEqual(StrategyConfig().rsi_sell_first_amount, 100)


if __name__ == "__main__":
    unittest.main()
