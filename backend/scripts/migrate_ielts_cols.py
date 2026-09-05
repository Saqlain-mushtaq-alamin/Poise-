"""
Quick SQLite migration for new ielts_sessions columns.
Run: python scripts/migrate_ielts_cols.py
"""
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "poise.db"

if not DB_PATH.exists():
    # Try env override
    DB_PATH = Path(os.environ.get("POISE_DB", "poise.db"))

if not DB_PATH.exists():
    print(f"Database not found at {DB_PATH} — skipping (fresh install will auto-create).")
    raise SystemExit(0)

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

new_columns = [
    ("dynamic_followup", "TEXT"),
    ("part2_answer_transcript", "TEXT"),
]

for col_name, col_type in new_columns:
    try:
        cur.execute(f"ALTER TABLE ielts_sessions ADD COLUMN {col_name} {col_type}")
        print(f"  Added column: ielts_sessions.{col_name}")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print(f"  Already exists: ielts_sessions.{col_name}")
        else:
            print(f"  ERROR: {e}")
            raise

conn.commit()
conn.close()
print("Migration complete.")
