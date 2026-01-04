import sys
import os

files = [
    "backend/main.py",
    "backend/strategy.py",
    "backend/strategies/logic_watch.py",
    "backend/strategies/logic_rsi.py",
    "backend/strategies/logic_price.py"
]

for f in files:
    print(f"Checking {f}...")
    try:
        with open(f, "r") as source:
            compile(source.read(), f, "exec")
        print("OK")
    except Exception as e:
        print(f"Error in {f}: {e}")
        sys.exit(1)
