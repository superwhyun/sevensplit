import sys
import os
import json
from datetime import datetime

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)

from database import get_db

def format_json(data):
    """Format JSON object for better readability"""
    if data is None:
        return "None"
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            pass
    return json.dumps(data, indent=2, ensure_ascii=False)

def check_db():
    print(f"Checking Database...")
    db = get_db()
    
    strategies = db.get_all_strategies()
    print(f"Found {len(strategies)} strategies in DB.\n")
    
    for s in strategies:
        print(f"==================================================")
        print(f"Strategy ID: {s.id} | Name: {s.name}")
        print(f"==================================================")
        print(f"Ticker: {s.ticker}")
        print(f"Status: {'Running' if s.is_running else 'Stopped'}")
        print(f"Mode: {s.strategy_mode}")
        print(f"Budget: {s.budget:,.0f} KRW")
        
        # Safe attribute access
        segments = getattr(s, 'price_segments', None)
        min_price = getattr(s, 'min_price', 0)
        max_price = getattr(s, 'max_price', 0)
        
        print(f"Grid Range: {min_price:,.0f} ~ {max_price:,.0f}")
        print(f"\n[Price Segments]")
        if segments:
            if isinstance(segments, list):
                print(f"Count: {len(segments)}")
                # Show first 3 and last 1 if too many
                if len(segments) > 5:
                    print(format_json(segments[:3]))
                    print("... (middle segments omitted) ...")
                    print(format_json(segments[-1:]))
                else:
                    print(format_json(segments))
            else:
                 print(f"Raw Value: {segments} (Type: {type(segments)})")
        else:
            print("❌ No segments found (Empty or None)")
            
        print(f"\n[RSI Config]")
        print(f"Period: {getattr(s, 'rsi_period', 'N/A')}")
        print(f"Buy Max: {getattr(s, 'rsi_buy_max', 'N/A')}")
        print(f"Sell Min: {getattr(s, 'rsi_sell_min', 'N/A')}")
        
        print("\n")

if __name__ == "__main__":
    check_db()
