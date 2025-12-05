import sqlite3
import os
from datetime import datetime

def backfill_db(db_path):
    if not os.path.exists(db_path):
        print(f"Skipping {db_path} (not found)")
        return

    print(f"Backfilling {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if bought_at column exists
        cursor.execute("PRAGMA table_info(trades)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'bought_at' not in columns:
            print("  'bought_at' column missing in trades table. Skipping.")
            return

        # Find records with NULL bought_at
        cursor.execute("SELECT count(*) FROM trades WHERE bought_at IS NULL")
        count = cursor.fetchone()[0]
        print(f"  Found {count} trades with missing bought_at.")

        if count > 0:
            # Update bought_at = timestamp for these records
            cursor.execute("UPDATE trades SET bought_at = timestamp WHERE bought_at IS NULL")
            conn.commit()
            print(f"  ✅ Updated {cursor.rowcount} records.")
        else:
            print("  No updates needed.")

    except Exception as e:
        print(f"  ❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    backfill_db("backend/sevensplit_real.db")
    backfill_db("backend/sevensplit_mock.db")
