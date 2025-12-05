import sqlite3
import os

# Define DB paths
backend_dir = os.path.join(os.getcwd(), 'backend')
db_files = ['sevensplit_mock.db', 'sevensplit_real.db']

for db_file in db_files:
    db_path = os.path.join(backend_dir, db_file)
    if os.path.exists(db_path):
        print(f"Checking {db_file}...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(trades)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'bought_at' not in columns:
            print(f"  Adding 'bought_at' column to {db_file}...")
            try:
                cursor.execute("ALTER TABLE trades ADD COLUMN bought_at DATETIME")
                conn.commit()
                print("  Success.")
            except Exception as e:
                print(f"  Failed: {e}")
        else:
            print("  Column 'bought_at' already exists.")
            
        conn.close()
