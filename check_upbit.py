import urllib.request
import json
from datetime import datetime
import time

url = "https://api.upbit.com/v1/candles/minutes/5?market=KRW-BTC&count=200"

with urllib.request.urlopen(url) as response:
    data = json.loads(response.read().decode())

print(f"Fetched {len(data)} candles")

# Upbit returns [Latest, ..., Oldest]
# Reverse to get chronological
data.reverse()

for c in data:
    utc = c['candle_date_time_utc']
    kst = c['candle_date_time_kst']
    print(f"UTC: {utc} | KST: {kst}")

# Check for specific target 00:00 KST
target = "2025-12-14T00:00:00"
found = False
for c in data:
    if c['candle_date_time_kst'] == target:
        print(f"\nFOUND TARGET: {c}")
        found = True
        break

if not found:
    print(f"\nTARGET {target} NOT FOUND in last 200 candles (Start: {data[0]['candle_date_time_kst']})")
