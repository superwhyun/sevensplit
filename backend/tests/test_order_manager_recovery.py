"""Order reconciliation after downtime: fills, 404s, cancels, partial fills."""
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.strategy_state import SplitState, StrategyConfig
from strategies.runtime_helpers import StrategyOrderManager

NOW = datetime(2026, 9, 15, 3, 0, 0, tzinfo=timezone.utc)
FILL_AT_KST = "2026-09-10T10:00:00+09:00"
FILL_AT_UTC = datetime(2026, 9, 10, 1, 0, 0, tzinfo=timezone.utc)


class _StubDB:
    def __init__(self):
        self.trades = []
        self.events = []

    def add_trade(self, strategy_id, ticker, trade_data):
        self.trades.append(dict(trade_data))

    def add_event(self, strategy_id, level, event_type, message):
        self.events.append((level, event_type, message))


class _StubExchange:
    def __init__(self):
        self.orders = {}
        self.get_order_calls = 0

    def get_order(self, uuid):
        self.get_order_calls += 1
        if uuid not in self.orders:
            raise Exception("Upbit API Error: 404 {'error': {'name': 'order_not_found'}}")
        return dict(self.orders[uuid])


class _StubAdaptive:
    def apply_sell_fill(self, sell_amount, reference_price):
        return 0.0

    def apply_buy_fill(self, buy_amount, reference_price):
        return 0.0


class _StubPriceLogic:
    def __init__(self):
        self.manage_calls = 0

    def manage_active_positions(self, open_order_uuids):
        self.manage_calls += 1

    def handle_split_cleanup(self, target_refresh_requested=False):
        return None


class _StubStrategy:
    ORDER_TIMEOUT_SEC = 1800

    def __init__(self, splits):
        self.strategy_id = 1
        self.ticker = "KRW-BTC"
        self.splits = splits
        self.config = StrategyConfig()
        self.trade_history = []
        self.last_sell_price = None
        self.db = _StubDB()
        self.exchange = _StubExchange()
        self.adaptive_buy_controller = _StubAdaptive()
        self.price_logic = _StubPriceLogic()
        self.save_calls = 0
        self.events = []
        self.now = NOW

    def save_state(self):
        self.save_calls += 1

    def get_now_utc(self):
        return self.now

    def log_event(self, level, event_type, message):
        self.events.append((level, event_type, message))


def _pending_sell(split_id=1, uuid="sell-1", buy_price=100.0, volume=1.0, target=100.5):
    return SplitState(
        id=split_id,
        status="PENDING_SELL",
        buy_order_uuid=f"buy-{split_id}",
        sell_order_uuid=uuid,
        buy_price=buy_price,
        actual_buy_price=buy_price,
        buy_amount=buy_price * volume,
        buy_volume=volume,
        target_sell_price=target,
        created_at="2026-09-01T00:00:00+00:00",
        bought_at="2026-09-01T00:00:00+00:00",
    )


def _done_sell_order(uuid="sell-1", price=100.5, volume=1.0, created_at=FILL_AT_KST):
    return {
        "uuid": uuid,
        "state": "done",
        "side": "ask",
        "ord_type": "limit",
        "price": str(price),
        "executed_volume": str(volume),
        "created_at": "2026-09-01T00:00:00+09:00",
        "trades": [{"price": str(price), "volume": str(volume), "funds": str(price * volume), "created_at": created_at}],
    }


class TestSellReconciliation(unittest.TestCase):
    def test_sell_filled_while_offline_is_finalized_with_actual_fill_time(self):
        split = _pending_sell()
        strategy = _StubStrategy([split])
        strategy.exchange.orders["sell-1"] = _done_sell_order()
        manager = StrategyOrderManager()

        manager.manage_orders(strategy, open_order_uuids=set(), current_price=101.0)

        self.assertEqual(strategy.splits, [])
        self.assertEqual(len(strategy.db.trades), 1)
        self.assertEqual(strategy.db.trades[0]["timestamp"], FILL_AT_UTC)
        self.assertEqual(strategy.trade_history[0]["timestamp"], FILL_AT_UTC.isoformat())
        self.assertEqual(strategy.last_sell_price, 100.5)

    def test_first_tick_checks_sells_even_when_price_is_below_target(self):
        split = _pending_sell(target=100.5)
        strategy = _StubStrategy([split])
        strategy.exchange.orders["sell-1"] = _done_sell_order()
        manager = StrategyOrderManager()

        manager.manage_orders(strategy, open_order_uuids=set(), current_price=90.0)

        self.assertEqual(strategy.splits, [], "offline fill must be reconciled on the first tick")
        self.assertEqual(strategy.exchange.get_order_calls, 1)

    def test_price_gate_skips_api_call_between_full_syncs(self):
        strategy = _StubStrategy([])
        manager = StrategyOrderManager()
        manager.manage_orders(strategy, open_order_uuids=set(), current_price=90.0)  # first tick = full sync

        strategy.splits.append(_pending_sell(split_id=2, uuid="sell-2", target=100.5))
        manager.manage_orders(strategy, open_order_uuids=set(), current_price=90.0)

        self.assertEqual(strategy.exchange.get_order_calls, 0)
        self.assertEqual(strategy.splits[0].status, "PENDING_SELL")

    def test_sell_404_keeps_position_until_threshold_then_relists(self):
        split = _pending_sell()
        strategy = _StubStrategy([split])
        manager = StrategyOrderManager()

        for _ in range(StrategyOrderManager.NOT_FOUND_DROP_THRESHOLD - 1):
            manager.check_sell_order(strategy, split)
            self.assertEqual(split.status, "PENDING_SELL")
            self.assertEqual(split.sell_order_uuid, "sell-1")

        manager.check_sell_order(strategy, split)

        self.assertIn(split, strategy.splits)
        self.assertEqual(split.status, "BUY_FILLED", "coins are still held; only the sell order is dropped")
        self.assertIsNone(split.sell_order_uuid)
        self.assertEqual(split.buy_volume, 1.0)
        self.assertTrue(any(e[1] == "SELL_ORDER_LOST" for e in strategy.events))

    def test_sell_404_counter_resets_when_order_is_found_again(self):
        split = _pending_sell()
        strategy = _StubStrategy([split])
        manager = StrategyOrderManager()

        for _ in range(StrategyOrderManager.NOT_FOUND_DROP_THRESHOLD - 1):
            manager.check_sell_order(strategy, split)
        strategy.exchange.orders["sell-1"] = {"uuid": "sell-1", "state": "wait", "executed_volume": "0"}
        manager.check_sell_order(strategy, split)
        del strategy.exchange.orders["sell-1"]
        manager.check_sell_order(strategy, split)

        self.assertEqual(split.status, "PENDING_SELL")

    def test_cancelled_sell_with_zero_fill_reverts_to_buy_filled(self):
        split = _pending_sell()
        strategy = _StubStrategy([split])
        strategy.exchange.orders["sell-1"] = {
            "uuid": "sell-1", "state": "cancel", "executed_volume": "0", "trades": [],
        }
        manager = StrategyOrderManager()

        manager.check_sell_order(strategy, split)

        self.assertEqual(split.status, "BUY_FILLED")
        self.assertIsNone(split.sell_order_uuid)
        self.assertEqual(strategy.db.trades, [])

    def test_cancelled_sell_with_partial_fill_records_trade_and_keeps_remainder(self):
        split = _pending_sell(buy_price=100.0, volume=1.0)
        strategy = _StubStrategy([split])
        strategy.exchange.orders["sell-1"] = {
            "uuid": "sell-1",
            "state": "cancel",
            "ord_type": "limit",
            "price": "100.5",
            "executed_volume": "0.4",
            "created_at": "2026-09-01T00:00:00+09:00",
            "trades": [{"price": "100.5", "volume": "0.4", "funds": "40.2", "created_at": FILL_AT_KST}],
        }
        manager = StrategyOrderManager()

        manager.check_sell_order(strategy, split)

        self.assertEqual(len(strategy.db.trades), 1)
        trade = strategy.db.trades[0]
        self.assertAlmostEqual(trade["coin_volume"], 0.4)
        self.assertAlmostEqual(trade["buy_amount"], 40.0)
        self.assertAlmostEqual(trade["sell_amount"], 40.2)
        self.assertEqual(trade["timestamp"], FILL_AT_UTC)
        self.assertEqual(split.status, "BUY_FILLED")
        self.assertIsNone(split.sell_order_uuid)
        self.assertAlmostEqual(split.buy_volume, 0.6)
        self.assertAlmostEqual(split.buy_amount, 60.0)
        self.assertTrue(any(e[1] == "SELL_PARTIAL" for e in strategy.events))

    def test_cancelled_sell_fully_executed_is_treated_as_done(self):
        split = _pending_sell(volume=1.0)
        strategy = _StubStrategy([split])
        order = _done_sell_order()
        order["state"] = "cancel"
        strategy.exchange.orders["sell-1"] = order
        manager = StrategyOrderManager()

        manager.check_sell_order(strategy, split)

        self.assertEqual(split.status, "SELL_FILLED")
        self.assertEqual(len(strategy.db.trades), 1)


class TestBuyReconciliation(unittest.TestCase):
    def _pending_buy(self):
        return SplitState(
            id=1,
            status="PENDING_BUY",
            buy_order_uuid="buy-1",
            buy_price=100.0,
            buy_amount=100.0,
            buy_volume=1.0,
            created_at=NOW.isoformat(),
        )

    def test_buy_404_keeps_split_until_threshold(self):
        split = self._pending_buy()
        strategy = _StubStrategy([split])
        manager = StrategyOrderManager()

        for _ in range(StrategyOrderManager.NOT_FOUND_DROP_THRESHOLD - 1):
            manager.check_buy_order(strategy, split)
            self.assertEqual(split.buy_order_uuid, "buy-1")

        manager.check_buy_order(strategy, split)

        self.assertIsNone(split.buy_order_uuid)
        self.assertEqual(split.status, "PENDING_BUY")

    def test_buy_fill_uses_exchange_trade_time_for_bought_at(self):
        split = self._pending_buy()
        strategy = _StubStrategy([split])
        strategy.exchange.orders["buy-1"] = {
            "uuid": "buy-1",
            "state": "done",
            "ord_type": "price",
            "executed_volume": "0.001",
            "trades": [{"price": "100000", "volume": "0.001", "funds": "100", "created_at": FILL_AT_KST}],
        }
        manager = StrategyOrderManager()

        manager.check_buy_order(strategy, split)

        self.assertEqual(split.status, "BUY_FILLED")
        self.assertEqual(split.bought_at, FILL_AT_UTC.isoformat())
        self.assertAlmostEqual(split.actual_buy_price, 100000.0)


class TestFillTimeResolution(unittest.TestCase):
    def test_falls_back_to_now_when_payload_has_no_times(self):
        resolved = StrategyOrderManager.resolve_fill_time({"trades": []}, NOW)
        self.assertEqual(resolved, NOW)

    def test_uses_latest_trade_time(self):
        order = {"trades": [
            {"created_at": "2026-09-10T10:00:00+09:00"},
            {"created_at": "2026-09-10T10:05:00+09:00"},
        ]}
        resolved = StrategyOrderManager.resolve_fill_time(order, NOW)
        self.assertEqual(resolved, datetime(2026, 9, 10, 1, 5, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()


class TestActualFeesFromExchange(unittest.TestCase):
    """P/L must use the fee the exchange actually charged (paid_fee) and fall back to the
    configured rate only when the payload lacks it."""

    def _bought_split(self, buy_fee=None):
        return SplitState(
            id=1,
            status="PENDING_SELL",
            buy_order_uuid="buy-1",
            sell_order_uuid="sell-1",
            buy_price=100.0,
            actual_buy_price=100.0,
            buy_amount=100.0,
            buy_volume=1.0,
            target_sell_price=101.0,
            bought_at="2026-09-01T00:00:00+00:00",
            buy_fee=buy_fee,
        )

    def test_buy_fill_stores_paid_fee_on_split(self):
        split = SplitState(id=1, status="PENDING_BUY", buy_order_uuid="buy-1", buy_price=100.0, buy_amount=100.0)
        strategy = _StubStrategy([split])
        strategy.exchange.orders["buy-1"] = {
            "uuid": "buy-1", "state": "done", "ord_type": "price", "executed_volume": "1",
            "paid_fee": "0.07",
            "trades": [{"price": "100", "volume": "1", "funds": "100", "created_at": FILL_AT_KST}],
        }

        StrategyOrderManager().check_buy_order(strategy, split)

        self.assertAlmostEqual(split.buy_fee, 0.07)

    def test_sell_uses_actual_fees_when_reported(self):
        split = self._bought_split(buy_fee=0.07)
        strategy = _StubStrategy([split])
        order = _done_sell_order(price=101.0, volume=1.0)
        order["paid_fee"] = "0.09"
        strategy.exchange.orders["sell-1"] = order

        StrategyOrderManager().check_sell_order(strategy, split)

        trade = strategy.db.trades[0]
        self.assertAlmostEqual(trade["total_fee"], 0.16)          # 0.07 buy + 0.09 sell, not 0.1005 estimate
        self.assertAlmostEqual(trade["net_profit"], 101.0 - 100.0 - 0.16)

    def test_sell_falls_back_to_configured_rate_without_paid_fee(self):
        split = self._bought_split(buy_fee=None)
        strategy = _StubStrategy([split])
        strategy.exchange.orders["sell-1"] = _done_sell_order(price=101.0, volume=1.0)  # no paid_fee key

        StrategyOrderManager().check_sell_order(strategy, split)

        trade = strategy.db.trades[0]
        expected = 100.0 * 0.0005 + 101.0 * 0.0005
        self.assertAlmostEqual(trade["total_fee"], expected)

    def test_partial_sell_prorates_stored_buy_fee(self):
        split = self._bought_split(buy_fee=0.10)
        strategy = _StubStrategy([split])
        strategy.exchange.orders["sell-1"] = {
            "uuid": "sell-1", "state": "cancel", "ord_type": "limit", "price": "101",
            "executed_volume": "0.4", "paid_fee": "0.02",
            "trades": [{"price": "101", "volume": "0.4", "funds": "40.4", "created_at": FILL_AT_KST}],
        }

        StrategyOrderManager().check_sell_order(strategy, split)

        trade = strategy.db.trades[0]
        self.assertAlmostEqual(trade["total_fee"], 0.10 * 0.4 + 0.02)
        self.assertAlmostEqual(split.buy_fee, 0.06)  # remaining 60% of the buy fee stays with the split
