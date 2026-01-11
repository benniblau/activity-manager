#!/usr/bin/env python3
"""Quick script to check database sport types"""

import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / 'activities.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== Recent activities with type and sport_type ===")
cursor.execute("""
    SELECT id, name, type, sport_type, start_date_local
    FROM activities
    ORDER BY start_date_local DESC
    LIMIT 20
""")

for row in cursor.fetchall():
    print(f"ID: {row['id']}")
    print(f"  Name: {row['name']}")
    print(f"  Type: {row['type']}")
    print(f"  Sport Type: {row['sport_type']}")
    print(f"  Date: {row['start_date_local']}")
    print()

conn.close()
