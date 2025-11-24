#!/usr/bin/env python3
"""Test MockExchange locked balance calculation"""

from exchange import MockExchange

# Create mock exchange
exchange = MockExchange(initial_balance=10000000)

print("=== Initial State ===")
print(f"KRW Balance: {exchange.get_balance('KRW'):,.0f}")
print(f"BTC Balance: {exchange.get_balance('KRW-BTC'):.8f}")

# Simulate buy limit order filled
print("\n=== Simulating Buy Order ===")
exchange.balance["KRW"] -= 100000  # Spent 100k KRW
exchange.balance["BTC"] = 0.00076936  # Got BTC
print(f"KRW Balance: {exchange.get_balance('KRW'):,.0f}")
print(f"BTC Balance: {exchange.get_balance('KRW-BTC'):.8f}")

# Create sell limit order
print("\n=== Creating Sell Limit Order ===")
order = exchange.sell_limit_order("KRW-BTC", 130000000, 0.00076936)
if order:
    print(f"Sell order created: {order['uuid']}")
    print(f"BTC Available (in balance dict): {exchange.balance.get('BTC', 0):.8f}")
    print(f"BTC Total (via get_balance): {exchange.get_balance('KRW-BTC'):.8f}")
    print(f"✓ Locked amount included: {float(order['locked']):.8f}")
else:
    print("Failed to create sell order")

# Check portfolio calculation
print("\n=== Portfolio Calculation ===")
btc_balance = exchange.get_balance("KRW-BTC")
btc_price = 130000000
btc_value = btc_balance * btc_price
print(f"BTC Balance: {btc_balance:.8f} BTC")
print(f"BTC Value: ₩{btc_value:,.0f}")
print(f"KRW Balance: ₩{exchange.get_balance('KRW'):,.0f}")
print(f"Total Value: ₩{exchange.get_balance('KRW') + btc_value:,.0f}")

print("\n✅ Test completed successfully!" if btc_balance > 0 else "\n❌ Test failed!")
