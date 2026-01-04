
from database import get_db
import json

db = get_db()
s = db.get_strategy(2)
if s:
    print("Strategy ID 2 Data:")
    for col in s.__table__.columns:
        val = getattr(s, col.name)
        print(f"{col.name}: {val} ({type(val)})")
else:
    print("Strategy ID 2 not found")
