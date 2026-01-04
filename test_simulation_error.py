#!/usr/bin/env python3
"""Test script to reproduce simulation error"""

import sys
sys.path.insert(0, '/Users/whyun/workspace/SERVICE/SevenSplit/backend')

from simulations.runner import expand_hourly_to_5min
from datetime import datetime

# Test with minimal hourly candle data
test_candle = {
    'timestamp': 1704067200.0,  # 2024-01-01 00:00:00 UTC
    'opening_price': 130000000,
    'high_price': 131000000,
    'low_price': 129000000,
    'trade_price': 130500000,
    'candle_date_time_kst': '2024-01-01T09:00:00'
}

try:
    print("Testing expand_hourly_to_5min with test candle...")
    result = expand_hourly_to_5min([test_candle])
    print(f"✓ Success! Generated {len(result)} 5-min candles")
    print(f"First candle: {result[0]}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
