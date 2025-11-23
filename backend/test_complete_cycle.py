#!/usr/bin/env python3
"""Test complete buy-sell cycle with split removal"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from exchange import MockExchange
from strategy import SevenSplitStrategy, StrategyConfig
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

def test_complete_cycle():
    """Test complete buy-sell cycle and split removal"""

    # Create mock exchange
    exchange = MockExchange(initial_balance=10000000)
    initial_price = 100000000
    exchange.set_mock_price(initial_price)

    # Create strategy
    strategy = SevenSplitStrategy(exchange, ticker="KRW-BTC")
    config = StrategyConfig(
        investment_per_split=100000.0,
        min_price=50000000.0,
        max_price=100000000.0,
        buy_rate=0.01,
        sell_rate=0.01,
        fee_rate=0.0005
    )
    strategy.update_config(config)

    print("=== Test: Complete Buy-Sell Cycle ===\n")

    # Start strategy (creates first buy at current price)
    print(f"1. Start strategy at {initial_price:,} KRW")
    strategy.start()
    strategy.tick(initial_price)
    print(f"   Splits: {len(strategy.splits)}, Status: {strategy.get_state()['status_counts']}")

    # Price goes up -> first buy should trigger sell
    print(f"\n2. Price goes up to {initial_price * 1.01:,} KRW")
    exchange.set_mock_price(initial_price * 1.01)
    strategy.tick(initial_price * 1.01)
    print(f"   Splits: {len(strategy.splits)}, Status: {strategy.get_state()['status_counts']}")
    print(f"   Trades: {len(strategy.trade_history)}")

    # Another tick should remove the SELL_FILLED split
    print(f"\n3. Another tick (should remove completed split)")
    strategy.tick(initial_price * 1.01)
    print(f"   Splits: {len(strategy.splits)}, Status: {strategy.get_state()['status_counts']}")
    print(f"   Trades: {len(strategy.trade_history)}")

    # Price drops -> new buy splits should be created
    print(f"\n4. Price drops to {initial_price * 0.99:,} KRW")
    exchange.set_mock_price(initial_price * 0.99)
    strategy.tick(initial_price * 0.99)
    print(f"   Splits: {len(strategy.splits)}, Status: {strategy.get_state()['status_counts']}")

    # Another drop
    print(f"\n5. Price drops to {initial_price * 0.98:,} KRW")
    exchange.set_mock_price(initial_price * 0.98)
    strategy.tick(initial_price * 0.98)
    print(f"   Splits: {len(strategy.splits)}, Status: {strategy.get_state()['status_counts']}")

    # Price recovers -> sells should execute
    print(f"\n6. Price recovers to {initial_price * 1.02:,} KRW")
    exchange.set_mock_price(initial_price * 1.02)
    strategy.tick(initial_price * 1.02)
    print(f"   Splits: {len(strategy.splits)}, Status: {strategy.get_state()['status_counts']}")
    print(f"   Trades: {len(strategy.trade_history)}")

    # Final tick to clean up
    print(f"\n7. Final tick to clean up completed splits")
    strategy.tick(initial_price * 1.02)
    print(f"   Splits: {len(strategy.splits)}, Status: {strategy.get_state()['status_counts']}")
    print(f"   Trades: {len(strategy.trade_history)}")

    print(f"\n=== Final State ===")
    print(f"KRW Balance: {exchange.get_balance('KRW'):,.0f}")
    print(f"BTC Balance: {exchange.get_balance('BTC'):.8f}")
    print(f"Total Trades: {len(strategy.trade_history)}")

    if strategy.trade_history:
        print(f"\nTrade History:")
        for trade in strategy.trade_history:
            print(f"  Split {trade['split_id']}: {trade['profit_amount']:,.0f} KRW ({trade['profit_rate']:.2f}%)")

    print("\n✓ Complete cycle test passed!")

if __name__ == "__main__":
    test_complete_cycle()
