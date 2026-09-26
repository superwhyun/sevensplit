"""Regression coverage for the 매수 상한가/하한가 (top-level min/max_price) fields
being silently ignored once a price_segments entry existed.

Root cause: _effective_segments() only fell back to config.min_price/max_price when
price_segments was empty. The frontend auto-generates a single segment the first
time the Config page loads, and kept reusing it on every later save unless the
user had split the ladder into 2+ segments. So editing the top-level 매수 상한가
field updated config.max_price but never touched that stale segment, and buy
gating (_find_matching_segment) only ever looks at segments.
"""
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.strategy_state import PriceSegment, StrategyConfig
from strategies.logic_price import PriceStrategyLogic


class _StrategyStub:
    def __init__(self, config):
        self.config = config
        self.splits = []
        self.last_status_msg = ""
        self.price_logic = PriceStrategyLogic(self)


class TestEffectiveSegmentBounds(unittest.TestCase):
    def _config(self, min_price, max_price, segments):
        return StrategyConfig(
            strategy_mode="PRICE",
            investment_per_split=100000.0,
            buy_rate=0.01,
            min_price=min_price,
            max_price=max_price,
            price_segments=segments,
        )

    def test_single_stale_segment_is_overridden_by_top_level_bounds(self):
        stale_segment = PriceSegment(
            min_price=50_000_000.0,
            max_price=70_000_000.0,  # old ceiling, no longer what the user configured
            investment_per_split=100000.0,
            max_splits=20,
        )
        config = self._config(min_price=50_000_000.0, max_price=90_000_000.0, segments=[stale_segment])
        strategy = _StrategyStub(config)

        effective = strategy.price_logic._effective_segments()

        self.assertEqual(len(effective), 1)
        self.assertEqual(effective[0].max_price, 90_000_000.0)
        # A price the stale segment would have rejected must now be accepted.
        self.assertIsNotNone(strategy.price_logic._find_matching_segment(80_000_000.0))

    def test_ceiling_trims_a_multi_segment_ladder(self):
        """매수 상한가/하한가 are the outer limits of the whole ladder; segments only
        subdivide that range. A segment sticking out past the ceiling is trimmed and
        one entirely above it is dropped, so the bot cannot buy above 매수 상한가."""
        segments = [
            PriceSegment(min_price=50_000_000.0, max_price=100_000_000.0, investment_per_split=100000.0, max_splits=5),
            PriceSegment(min_price=100_000_000.0, max_price=300_000_000.0, investment_per_split=200000.0, max_splits=7),
        ]
        config = self._config(min_price=50_000_000.0, max_price=100_000_000.0, segments=segments)
        strategy = _StrategyStub(config)

        effective = strategy.price_logic._effective_segments()

        self.assertEqual(len(effective), 1)
        self.assertEqual(effective[0].max_price, 100_000_000.0)
        self.assertIsNone(strategy.price_logic._find_matching_segment(150_000_000.0))
        self.assertIsNotNone(strategy.price_logic._find_matching_segment(99_000_000.0))

    def test_ladder_keeps_its_own_investment_and_splits_after_trimming(self):
        segments = [
            PriceSegment(min_price=50_000_000.0, max_price=100_000_000.0, investment_per_split=100000.0, max_splits=5),
            PriceSegment(min_price=100_000_000.0, max_price=300_000_000.0, investment_per_split=200000.0, max_splits=7),
        ]
        config = self._config(min_price=50_000_000.0, max_price=200_000_000.0, segments=segments)
        strategy = _StrategyStub(config)

        effective = strategy.price_logic._effective_segments()

        self.assertEqual(len(effective), 2)
        # Upper segment clipped to the ceiling, its own settings untouched.
        self.assertEqual(effective[1].max_price, 200_000_000.0)
        self.assertEqual(effective[1].investment_per_split, 200000.0)
        self.assertEqual(effective[1].max_splits, 7)
        self.assertEqual(effective[0].investment_per_split, 100000.0)
        self.assertEqual(effective[0].max_splits, 5)

    def test_unset_top_level_bounds_do_not_clobber_a_segment_only_setup(self):
        segment = PriceSegment(
            min_price=10_000_000.0,
            max_price=20_000_000.0,
            investment_per_split=100000.0,
            max_splits=20,
        )
        config = self._config(min_price=0.0, max_price=0.0, segments=[segment])
        strategy = _StrategyStub(config)

        effective = strategy.price_logic._effective_segments()

        self.assertEqual(effective, [segment])

    def test_zero_ceiling_means_no_upper_bound(self):
        """A 0 in 매수 상한가 is not "auto-fill +15%" -- the strategy only fills both
        bounds from the current price when 매수 하한가 is also 0 (strategy.py __init__).
        With a real floor and a 0 ceiling, buying is simply unbounded above."""
        segment = PriceSegment(
            min_price=50_000_000.0,
            max_price=1_000_000_000.0,
            investment_per_split=100000.0,
            max_splits=20,
        )
        config = self._config(min_price=50_000_000.0, max_price=0.0, segments=[segment])
        strategy = _StrategyStub(config)

        effective = strategy.price_logic._effective_segments()

        # No top-level ceiling is imposed, so the segment's own upper bound stands.
        self.assertEqual(effective[0].min_price, 50_000_000.0)
        self.assertEqual(effective[0].max_price, 1_000_000_000.0)
        self.assertIsNotNone(strategy.price_logic._find_matching_segment(200_000_000.0))
        self.assertIsNone(strategy.price_logic._find_matching_segment(40_000_000.0))

    def test_matching_single_segment_is_returned_as_is(self):
        segment = PriceSegment(
            min_price=50_000_000.0,
            max_price=90_000_000.0,
            investment_per_split=100000.0,
            max_splits=20,
        )
        config = self._config(min_price=50_000_000.0, max_price=90_000_000.0, segments=[segment])
        strategy = _StrategyStub(config)

        effective = strategy.price_logic._effective_segments()

        self.assertEqual(len(effective), 1)
        self.assertEqual(effective[0].min_price, 50_000_000.0)
        self.assertEqual(effective[0].max_price, 90_000_000.0)
        self.assertEqual(effective[0].investment_per_split, 100000.0)
        self.assertEqual(effective[0].max_splits, 20)


if __name__ == "__main__":
    unittest.main()
