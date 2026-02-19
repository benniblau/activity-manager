#!/usr/bin/env python3
"""
Coach Invitation Migration Script

Updates the coach_athlete_relationships table to support inviting coaches
who haven't registered yet (email-based invitations).

Usage:
    python scripts/migrate_coach_invitations.py [database_path]
"""

import sqlite3
import sys
import os
import shutil
from datetime import datetime


def backup_database(db_path):
    """Create a timestamped backup of the database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.pre_coach_invite_backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Database backed up to: {backup_path}")
    return backup_path


def migrate_coach_invitations(conn):
    """Migrate coach_athlete_relationships to support email-based invitations"""
    print("\n📋 Migrating coach_athlete_relationships table...")

    # Check if migration already done
    cursor = conn.execute("PRAGMA table_info(coach_athlete_relationships)")
    columns = {row[1] for row in cursor.fetchall()}

    if 'coach_email' in columns:
        print("✓ Migration already completed")
        return

    # Step 1: Rename old table
    conn.execute('ALTER TABLE coach_athlete_relationships RENAME TO coach_athlete_relationships_old')

    # Step 2: Create new table with email support
    conn.execute('''
        CREATE TABLE coach_athlete_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coach_id INTEGER,
            coach_email TEXT,
            athlete_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'inactive')),
            invited_at TEXT DEFAULT CURRENT_TIMESTAMP,
            accepted_at TEXT,
            FOREIGN KEY (coach_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (athlete_id) REFERENCES users(id) ON DELETE CASCADE,
            CHECK ((coach_id IS NOT NULL AND coach_email IS NULL) OR (coach_id IS NULL AND coach_email IS NOT NULL))
        )
    ''')

    # Step 3: Copy data from old table
    # For existing relationships, we need to get the coach's email
    conn.execute('''
        INSERT INTO coach_athlete_relationships
        (id, coach_id, athlete_id, status, invited_at, accepted_at)
        SELECT id, coach_id, athlete_id, status, invited_at, accepted_at
        FROM coach_athlete_relationships_old
    ''')

    # Step 4: Drop old indexes if they exist
    conn.execute('DROP INDEX IF EXISTS idx_relationships_coach')
    conn.execute('DROP INDEX IF EXISTS idx_relationships_athlete')

    # Step 5: Create new indexes
    conn.execute('CREATE INDEX idx_relationships_coach ON coach_athlete_relationships(coach_id)')
    conn.execute('CREATE INDEX idx_relationships_athlete ON coach_athlete_relationships(athlete_id)')
    conn.execute('CREATE INDEX idx_relationships_email ON coach_athlete_relationships(coach_email)')

    # Step 6: Drop old table
    conn.execute('DROP TABLE coach_athlete_relationships_old')

    conn.commit()
    print("✓ Migration completed successfully")


def main():
    # Get database path
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'activities.db'

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    print(f"📦 Migrating database: {db_path}")

    # Backup database
    backup_path = backup_database(db_path)

    # Connect and migrate
    try:
        conn = sqlite3.connect(db_path)
        migrate_coach_invitations(conn)
        conn.close()

        print("\n✅ Migration completed successfully!")
        print(f"📁 Backup saved: {backup_path}")

    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        print(f"📁 Restore from backup: {backup_path}")
        sys.exit(1)


if __name__ == '__main__':
    main()
