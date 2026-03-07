import os
import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.strategy_state import PriceSegment, SplitState, StrategyConfig
from strategies.adaptive_buy import AdaptiveBuyController
from strategies.logic_price import PriceStrategyLogic
from strategies.runtime_helpers import StrategyStateManager


class _ExchangeStub:
    def __init__(self):
        self.orders = []

    def buy_market_order(self, ticker, amount):
        self.orders.append((ticker, amount))
        return {"uuid": f"buy-{len(self.orders)}"}

    def normalize_price(self, price):
        return price


class _StrategyStub:
    def __init__(self, config=None):
        self.config = config or StrategyConfig(
            strategy_mode="PRICE",
            investment_per_split=100000.0,
            buy_rate=0.01,
            price_segments=[
                PriceSegment(
                    min_price=0.0,
                    max_price=1_000_000_000.0,
                    investment_per_split=100000.0,
                    max_splits=20,
                )
            ],
            use_adaptive_buy_control=True,
            adaptive_pressure_cap=4.0,
            adaptive_probe_multiplier=0.5,
            adaptive_sell_pressure_step=1.0,
            adaptive_buy_relief_step=1.0,
            use_fast_drop_brake=True,
            fast_drop_trigger_levels=2,
            fast_drop_batch_cap=1,
            fast_drop_next_gap_levels=2,
            fast_drop_multiplier_cap=0.75,
            use_trailing_buy=True,
            trailing_buy_batch=True,
        )
        self.strategy_id = 1
        self.ticker = "KRW-BTC"
        self.exchange = _ExchangeStub()
        self.splits = []
        self.next_split_id = 1
        self.budget = 1_000_000.0
        self.last_buy_price = None
        self.last_sell_price = None
        self.next_buy_target_price = None
        self.last_status_msg = ""
        self.is_running = False
        self.is_watching = False
        self.watch_lowest_price = None
        self.pending_buy_units = 0
        self.adaptive_reentry_pressure = 0.0
        self.adaptive_effective_buy_multiplier = 1.0
        self.adaptive_fast_drop_active = False
        self.saved = 0
        self.events = []
        self.adaptive_buy_controller = AdaptiveBuyController(self)
        self.price_logic = PriceStrategyLogic(self)

    def has_sufficient_budget(self, market_context=None, required_amount=None):
        amount = self.config.investment_per_split if required_amount is None else required_amount
        active_total = sum(s.buy_amount for s in self.splits if s.status != "SELL_FILLED")
        return active_total + amount <= self.budget

    def check_trade_limit(self):
        return True

    def log_event(self, level, event_type, message):
        self.events.append((level, event_type, message))

    def save_state(self):
        self.saved += 1

    def get_now_utc(self):
        return datetime.now(timezone.utc)


class TestAdaptiveBuyController(unittest.TestCase):
    def test_multiplier_tracks_pressure_linearly(self):
        strategy = _StrategyStub()
        controller = strategy.adaptive_buy_controller

        strategy.adaptive_reentry_pressure = 0.0
        self.assertEqual(controller.get_pressure_multiplier(), 1.0)

        strategy.adaptive_reentry_pressure = 2.0
        self.assertAlmostEqual(controller.get_pressure_multiplier(), 0.75)

        strategy.adaptive_reentry_pressure = 4.0
        self.assertAlmostEqual(controller.get_pressure_multiplier(), 0.5)

    def test_pressure_updates_with_split_equivalent_amounts(self):
        strategy = _StrategyStub()
        controller = strategy.adaptive_buy_controller

        controller.apply_sell_fill(100000.0, 100.0)
        self.assertAlmostEqual(strategy.adaptive_reentry_pressure, 1.0)
        self.assertEqual(strategy.events[-1][1], "ADAPTIVE_PRESSURE")
        self.assertIn("Cause: SELL_FILL", strategy.events[-1][2])

        controller.apply_buy_fill(50000.0, 100.0)
        self.assertAlmostEqual(strategy.adaptive_reentry_pressure, 0.5)
        self.assertEqual(strategy.events[-1][1], "ADAPTIVE_PRESSURE")
        self.assertIn("Cause: BUY_FILL", strategy.events[-1][2])

        controller.apply_sell_fill(1_000_000.0, 100.0)
        self.assertAlmostEqual(strategy.adaptive_reentry_pressure, 4.0)

    def test_fast_drop_brake_caps_multiplier_batch_and_gap(self):
        strategy = _StrategyStub()
        controller = strategy.adaptive_buy_controller
        strategy.adaptive_reentry_pressure = 1.0

        controls = controller.resolve_execution_controls(raw_levels_crossed=3, allow_batch_buy=True)

        self.assertTrue(controls["fast_drop_active"])
        self.assertEqual(controls["batch_cap"], 1)
        self.assertEqual(controls["next_gap_levels"], 2)
        self.assertAlmostEqual(controls["buy_multiplier"], 0.75)

    def test_state_manager_includes_adaptive_fields(self):
        strategy = _StrategyStub()
        strategy.adaptive_reentry_pressure = 1.75
        state = StrategyStateManager()._build_state_payload(strategy)
        self.assertEqual(state["adaptive_reentry_pressure"], 1.75)

        fake_state = SimpleNamespace(
            investment_per_split=100000.0,
            min_price=0.0,
            max_price=0.0,
            buy_rate=0.01,
            sell_rate=0.01,
            fee_rate=0.0005,
            tick_interval=1.0,
            rebuy_strategy="reset_on_clear",
            max_trades_per_day=100,
            strategy_mode="PRICE",
            rsi_period=14,
            rsi_timeframe="minutes/60",
            rsi_buy_max=30.0,
            rsi_buy_cross_threshold=0.0,
            rsi_buy_first_amount=1,
            rsi_buy_next_amount=1,
            rsi_sell_min=70.0,
            rsi_sell_cross_threshold=0.0,
            rsi_sell_first_amount=1,
            rsi_sell_next_amount=1,
            stop_loss=-10.0,
            max_holdings=20,
            use_trailing_buy=False,
            trailing_buy_rebound_percent=0.2,
            trailing_buy_batch=True,
            use_adaptive_buy_control=True,
            adaptive_sell_pressure_step=1.0,
            adaptive_buy_relief_step=1.0,
            adaptive_pressure_cap=4.0,
            adaptive_probe_multiplier=0.5,
            use_fast_drop_brake=True,
            fast_drop_trigger_levels=2,
            fast_drop_batch_cap=1,
            fast_drop_next_gap_levels=2,
            fast_drop_multiplier_cap=0.75,
            price_segments=[],
            is_running=False,
            next_split_id=1,
            last_buy_price=None,
            last_sell_price=None,
            budget=1_000_000.0,
            next_buy_target_price=None,
            is_watching=False,
            watch_lowest_price=None,
            pending_buy_units=0,
            adaptive_reentry_pressure=2.5,
        )
        strategy = _StrategyStub()
        manager = StrategyStateManager()
        strategy.config = manager._build_config_from_state(fake_state)
        manager._apply_runtime_state(strategy, fake_state)

        self.assertTrue(strategy.config.use_adaptive_buy_control)
        self.assertEqual(strategy.config.fast_drop_next_gap_levels, 2)
        self.assertAlmostEqual(strategy.adaptive_reentry_pressure, 2.5)


class TestAdaptivePriceLogic(unittest.TestCase):
    def test_price_logic_ignores_global_max_holdings_when_segment_allows_more(self):
        config = StrategyConfig(
            strategy_mode="PRICE",
            investment_per_split=20000.0,
            buy_rate=0.01,
            max_holdings=20,
            price_segments=[
                PriceSegment(
                    min_price=0.0,
                    max_price=1_000_000_000.0,
                    investment_per_split=20000.0,
                    max_splits=50,
                )
            ],
        )
        strategy = _StrategyStub(config=config)
        strategy.splits = [
            SplitState(
                id=i + 1,
                status="BUY_FILLED",
                buy_price=100.0,
                actual_buy_price=100.0,
                buy_amount=20000.0,
                buy_volume=200.0,
            )
            for i in range(20)
        ]
        strategy.next_split_id = 21

        split = strategy.price_logic._execute_single_buy(100.0, buy_rsi=35.0)

        self.assertIsNotNone(split)
        self.assertEqual(split.id, 21)
        self.assertEqual(len(strategy.exchange.orders), 1)

    def test_last_sell_anchor_ignores_pending_buy_during_cleanup(self):
        config = StrategyConfig(
            strategy_mode="PRICE",
            investment_per_split=100000.0,
            buy_rate=0.01,
            rebuy_strategy="last_sell_price",
            price_segments=[
                PriceSegment(
                    min_price=0.0,
                    max_price=1_000_000_000.0,
                    investment_per_split=100000.0,
                    max_splits=20,
                )
            ],
        )
        strategy = _StrategyStub(config=config)
        strategy.is_running = True
        strategy.last_buy_price = 100.0
        strategy.last_sell_price = 110.0
        strategy.next_buy_target_price = 99.0
        strategy.splits = [
            SplitState(
                id=1,
                status="PENDING_BUY",
                buy_price=100.0,
                actual_buy_price=100.0,
                buy_amount=100000.0,
                buy_volume=1000.0,
            )
        ]

        strategy.price_logic.handle_split_cleanup(target_refresh_requested=True)

        self.assertEqual(strategy.last_buy_price, 110.0)
        self.assertAlmostEqual(strategy.next_buy_target_price, 108.9)
        self.assertIn(
            ("INFO", "TARGET_UPDATE", "Next Buy Target: 108.9"),
            strategy.events,
        )

    def test_fast_drop_brake_limits_buy_and_widens_next_target(self):
        strategy = _StrategyStub()
        strategy.last_buy_price = 100.0
        strategy.splits = [
            SplitState(
                id=99,
                status="BUY_FILLED",
                buy_price=100.0,
                actual_buy_price=100.0,
                buy_amount=100000.0,
                buy_volume=1000.0,
            )
        ]
        strategy.adaptive_reentry_pressure = 1.0

        plan = strategy.price_logic.plan_buy(
            current_price=97.0,
            rsi_5m=40.0,
            just_exited_watch=True,
            market_context={},
        )

        self.assertIsNotNone(plan)
        strategy.price_logic.execute_buy_logic(97.0, 40.0, planned_buy=plan)

        self.assertEqual(len(strategy.exchange.orders), 1)
        self.assertAlmostEqual(strategy.exchange.orders[0][1], 75000.0)
        self.assertAlmostEqual(strategy.next_buy_target_price, 97.0 * (1 - 0.02))
        self.assertTrue(strategy.adaptive_fast_drop_active)
        self.assertAlmostEqual(strategy.adaptive_effective_buy_multiplier, 0.75)

    def test_small_adaptive_order_is_skipped(self):
        config = StrategyConfig(
            strategy_mode="PRICE",
            investment_per_split=10000.0,
            buy_rate=0.01,
            price_segments=[
                PriceSegment(
                    min_price=0.0,
                    max_price=1_000_000_000.0,
                    investment_per_split=10000.0,
                    max_splits=20,
                )
            ],
            use_adaptive_buy_control=True,
            adaptive_pressure_cap=4.0,
            adaptive_probe_multiplier=0.4,
        )
        strategy = _StrategyStub(config=config)

        split = strategy.price_logic._execute_single_buy(100.0, buy_multiplier=0.4)

        self.assertIsNone(split)
        self.assertEqual(strategy.exchange.orders, [])
        self.assertIn("minimum order size", strategy.last_status_msg)

    def test_buy_amount_rounds_to_nearest_krw(self):
        config = StrategyConfig(
            strategy_mode="PRICE",
            investment_per_split=10001.0,
            buy_rate=0.01,
            price_segments=[
                PriceSegment(
                    min_price=0.0,
                    max_price=1_000_000_000.0,
                    investment_per_split=10001.0,
                    max_splits=20,
                )
            ],
            use_adaptive_buy_control=True,
            adaptive_probe_multiplier=0.5,
        )
        strategy = _StrategyStub(config=config)

        amount = strategy.price_logic._estimate_buy_amount(100.0, 0.5)

        self.assertEqual(amount, 5001.0)


if __name__ == "__main__":
    unittest.main()
