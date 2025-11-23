#!/usr/bin/env python3
"""Test script for the new dynamic split strategy"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from exchange import MockExchange
from strategy import SevenSplitStrategy, StrategyConfig
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_dynamic_splits():
    """Test the dynamic split creation and management"""

    # Create mock exchange with initial balance
    exchange = MockExchange(initial_balance=10000000)  # 10M KRW

    # Set a mock BTC price
    initial_price = 100000000  # 100M KRW
    exchange.set_mock_price(initial_price)

    # Create strategy
    strategy = SevenSplitStrategy(exchange, ticker="KRW-BTC")

    # Configure with buy_rate and sell_rate
    config = StrategyConfig(
        investment_per_split=100000.0,  # 100K KRW per split
        min_price=50000000.0,  # 50M KRW minimum
        max_price=100000000.0,  # 100M KRW (reference only)
        buy_rate=0.01,  # Buy every 1% drop
        sell_rate=0.01,  # Sell at 1% profit
        fee_rate=0.0005
    )
    strategy.update_config(config)

    print("\n=== Starting Strategy ===")
    print(f"Initial BTC Price: {initial_price:,} KRW")
    print(f"Buy Rate: {config.buy_rate * 100}%")
    print(f"Sell Rate: {config.sell_rate * 100}%")
    print(f"Investment per Split: {config.investment_per_split:,} KRW")

    # Start strategy
    strategy.start()
    strategy.tick(initial_price)

    state = strategy.get_state()
    print(f"\nAfter Start:")
    print(f"  Splits: {len(state['splits'])}")
    print(f"  Status Counts: {state['status_counts']}")

    # Simulate price drop by 1%
    print("\n=== Simulating 1% Price Drop ===")
    new_price = initial_price * 0.99  # 99M KRW
    exchange.set_mock_price(new_price)
    print(f"New BTC Price: {new_price:,} KRW")

    # Tick to check buy orders
    strategy.tick(new_price)

    state = strategy.get_state()
    print(f"\nAfter 1% Drop:")
    print(f"  Splits: {len(state['splits'])}")
    print(f"  Status Counts: {state['status_counts']}")

    # Check first split status
    if state['splits']:
        first_split = state['splits'][0]
        print(f"\n  First Split Details:")
        print(f"    ID: {first_split['id']}")
        print(f"    Status: {first_split['status']}")
        print(f"    Buy Price: {first_split['buy_price']:,} KRW")
        print(f"    Buy Order UUID: {first_split['buy_order_uuid']}")

    # Simulate another price drop to trigger the second buy
    print("\n=== Simulating Another 1% Price Drop ===")
    new_price = new_price * 0.99  # ~98M KRW
    exchange.set_mock_price(new_price)
    print(f"New BTC Price: {new_price:,} KRW")

    strategy.tick(new_price)

    state = strategy.get_state()
    print(f"\nAfter 2nd Drop:")
    print(f"  Splits: {len(state['splits'])}")
    print(f"  Status Counts: {state['status_counts']}")

    # Simulate price going up to trigger sell
    print("\n=== Simulating Price Recovery (to trigger sell) ===")
    recovery_price = initial_price * 1.01  # 101M KRW (above first buy + sell_rate)
    exchange.set_mock_price(recovery_price)
    print(f"Recovery BTC Price: {recovery_price:,} KRW")

    strategy.tick(recovery_price)

    state = strategy.get_state()
    print(f"\nAfter Price Recovery:")
    print(f"  Splits: {len(state['splits'])}")
    print(f"  Status Counts: {state['status_counts']}")
    print(f"  Trade History: {len(state['trade_history'])} trades")

    if state['trade_history']:
        print(f"\n  Recent Trades:")
        for trade in state['trade_history'][:3]:
            print(f"    Split {trade['split_id']}: Buy @ {trade['buy_price']:,.0f}, "
                  f"Sell @ {trade['sell_price']:,.0f}, "
                  f"Profit: {trade['profit_amount']:,.0f} KRW ({trade['profit_rate']:.2f}%)")

    # Final balance check
    print(f"\n=== Final Balances ===")
    print(f"  KRW Balance: {exchange.get_balance('KRW'):,.0f}")
    print(f"  BTC Balance: {exchange.get_balance('BTC'):.8f}")

    print("\n✓ Test completed successfully!")

if __name__ == "__main__":
    test_dynamic_splits()
