import sqlite3
import os

def check_and_update_db(db_path):
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return

    print(f"Checking database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if splits table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='splits'")
    if not cursor.fetchone():
        print("  - 'splits' table does not exist. It will be created automatically by the app.")
        conn.close()
        return

    # Get columns in splits table
    cursor.execute("PRAGMA table_info(splits)")
    columns = [info[1] for info in cursor.fetchall()]
    
    # Check for buy_filled_at
    if 'buy_filled_at' not in columns:
        print("  - 'buy_filled_at' column is MISSING in 'splits' table.")
        try:
            print("  - Adding 'buy_filled_at' column...")
            cursor.execute("ALTER TABLE splits ADD COLUMN buy_filled_at DATETIME")
            conn.commit()
            print("  - Successfully added 'buy_filled_at' column.")
        except Exception as e:
            print(f"  - Failed to add column: {e}")
    else:
        print("  - 'buy_filled_at' column already exists.")

    conn.close()

if __name__ == "__main__":
    import sys
    
    # If arguments are provided, check those specific files
    if len(sys.argv) > 1:
        for db_path in sys.argv[1:]:
            check_and_update_db(db_path)
    else:
        # Default behavior: check standard files in the backend directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check both mock and real databases
        mock_db = os.path.join(base_dir, "sevensplit_mock.db")
        real_db = os.path.join(base_dir, "sevensplit_real.db")
        
        check_and_update_db(mock_db)
        check_and_update_db(real_db)
