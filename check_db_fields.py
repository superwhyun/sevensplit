from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from backend.database import Split, Trade, Base
import os

# Setup DB connection
db_path = os.path.join(os.getcwd(), 'backend', 'sevensplit_mock.db')
engine = create_engine(f'sqlite:///{db_path}')
Session = sessionmaker(bind=engine)
session = Session()

inspector = inspect(engine)

print("--- Table: splits ---")
columns = [col['name'] for col in inspector.get_columns('splits')]
print(f"Columns: {columns}")
if 'buy_filled_at' in columns:
    print("'buy_filled_at' column exists.")
    # Check if any data has it populated
    split = session.query(Split).filter(Split.buy_filled_at.isnot(None)).first()
    if split:
        print(f"Sample data found: id={split.id}, buy_filled_at={split.buy_filled_at}")
    else:
        print("No splits found with 'buy_filled_at' populated (might be empty DB or no filled buys yet).")
else:
    print("'buy_filled_at' column MISSING.")

print("\n--- Table: trades ---")
columns = [col['name'] for col in inspector.get_columns('trades')]
print(f"Columns: {columns}")
# Check for any buy timestamp related column
buy_time_cols = [c for c in columns if 'buy' in c and ('time' in c or 'date' in c or 'at' in c)]
print(f"Potential buy time columns: {buy_time_cols}")

session.close()
