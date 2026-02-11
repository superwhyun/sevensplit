
from database import get_db
import json

db = get_db()
strategies = db.get_all_strategies()

print(f"Found {len(strategies)} strategies")

for s in strategies:
    print(f"\n[Strategy ID: {s.id}] {s.name}")
    print(f"  - Ticker: {s.ticker}")
    
    # Check price_segments specific column
    segments = getattr(s, 'price_segments', 'Not Found')
    print(f"  - Price Segments (Raw): {segments}")
    print(f"  - Type: {type(segments)}")
    
    if segments:
        print(f"  - Count: {len(segments)}")
