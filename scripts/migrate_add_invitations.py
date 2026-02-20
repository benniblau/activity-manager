#!/usr/bin/env python3
"""
Invitations Table Migration Script

Adds the invitations table for token-based invitation-only registration.

Usage:
    python scripts/migrate_add_invitations.py [database_path]
"""

import sqlite3
import sys
import os
import shutil
from datetime import datetime


def backup_database(db_path):
    """Create a timestamped backup of the database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.pre_invitations_backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Database backed up to: {backup_path}")
    return backup_path


def migrate_add_invitations(conn):
    """Add invitations table if it does not already exist"""
    print("\n📋 Adding invitations table...")

    # Check if table already exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='invitations'"
    )
    if cursor.fetchone():
        print("✓ invitations table already exists, skipping")
        return

    conn.execute('''
        CREATE TABLE invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            inviter_id INTEGER NOT NULL,
            invited_email TEXT NOT NULL,
            invited_role TEXT NOT NULL DEFAULT 'athlete'
                CHECK (invited_role IN ('athlete', 'coach')),
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'used', 'cancelled')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            used_by_user_id INTEGER,
            FOREIGN KEY (inviter_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (used_by_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')
    conn.execute('CREATE INDEX idx_invitations_token ON invitations(token)')
    conn.execute('CREATE INDEX idx_invitations_inviter ON invitations(inviter_id)')
    conn.execute('CREATE INDEX idx_invitations_email ON invitations(invited_email)')
    conn.execute('CREATE INDEX idx_invitations_status ON invitations(status)')
    conn.commit()
    print("✓ invitations table created successfully")


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
        migrate_add_invitations(conn)
        conn.close()

        print("\n✅ Migration completed successfully!")
        print(f"📁 Backup saved: {backup_path}")

    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        print(f"📁 Restore from backup: {backup_path}")
        sys.exit(1)


if __name__ == '__main__':
    main()
