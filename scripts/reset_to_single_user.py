#!/usr/bin/env python3
"""
Reset to Single User (Admin) Script

Drops all users except the first one (lowest ID), along with all their
coach-athlete relationships, Strava tokens, and invitations.
Useful when switching to invitation-only registration on an existing database
that has test users.

Usage:
    python scripts/reset_to_single_user.py [database_path]
"""

import sqlite3
import sys
import os
import shutil
from datetime import datetime


def backup_database(db_path):
    """Create a timestamped backup of the database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.pre_reset_backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Database backed up to: {backup_path}")
    return backup_path


def reset_to_single_user(conn):
    """Delete all users except the one with the lowest ID"""

    # Find the admin user (lowest ID)
    cursor = conn.execute("SELECT id, name, email, role FROM users ORDER BY id ASC LIMIT 1")
    admin = cursor.fetchone()

    if not admin:
        print("❌ No users found in database.")
        return

    admin_id, admin_name, admin_email, admin_role = admin
    print(f"\n👤 Keeping admin user: [{admin_id}] {admin_name} ({admin_email}, {admin_role})")

    # Show what will be deleted
    cursor = conn.execute(
        "SELECT id, name, email, role FROM users WHERE id != ? ORDER BY id",
        (admin_id,)
    )
    others = cursor.fetchall()

    if not others:
        print("✓ No other users to remove.")
        return

    print(f"\n🗑  Users to be deleted ({len(others)}):")
    for row in others:
        print(f"   [{row[0]}] {row[1]} ({row[2]}, {row[3]})")

    other_ids = [row[0] for row in others]
    placeholders = ','.join('?' * len(other_ids))

    # Delete dependent data first
    cursor = conn.execute(
        f"SELECT COUNT(*) FROM coach_athlete_relationships WHERE coach_id IN ({placeholders}) OR athlete_id IN ({placeholders})",
        other_ids + other_ids
    )
    rel_count = cursor.fetchone()[0]

    cursor = conn.execute(
        f"SELECT COUNT(*) FROM strava_tokens WHERE user_id IN ({placeholders})",
        other_ids
    )
    token_count = cursor.fetchone()[0]

    cursor = conn.execute(
        f"SELECT COUNT(*) FROM invitations WHERE inviter_id IN ({placeholders}) OR used_by_user_id IN ({placeholders})",
        other_ids + other_ids
    )
    inv_count = cursor.fetchone()[0]

    print(f"\n   Also deleting: {rel_count} coach relationships, {token_count} Strava tokens, {inv_count} invitations")

    confirm = input("\nProceed? [y/N] ").strip().lower()
    if confirm != 'y':
        print("Aborted.")
        return

    # Delete in dependency order
    conn.execute(
        f"DELETE FROM coach_athlete_relationships WHERE coach_id IN ({placeholders}) OR athlete_id IN ({placeholders})",
        other_ids + other_ids
    )
    conn.execute(
        f"DELETE FROM strava_tokens WHERE user_id IN ({placeholders})",
        other_ids
    )
    conn.execute(
        f"DELETE FROM invitations WHERE inviter_id IN ({placeholders}) OR used_by_user_id IN ({placeholders})",
        other_ids + other_ids
    )
    conn.execute(
        f"DELETE FROM users WHERE id IN ({placeholders})",
        other_ids
    )
    conn.commit()

    cursor = conn.execute("SELECT COUNT(*) FROM users")
    remaining = cursor.fetchone()[0]
    print(f"\n✅ Done. {len(others)} user(s) removed. {remaining} user(s) remaining.")


def main():
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'activities.db'

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    print(f"📦 Database: {db_path}")
    backup_path = backup_database(db_path)

    try:
        conn = sqlite3.connect(db_path)
        reset_to_single_user(conn)
        conn.close()
        print(f"📁 Backup saved: {backup_path}")

    except Exception as e:
        print(f"\n❌ Failed: {str(e)}")
        print(f"📁 Restore from backup: {backup_path}")
        sys.exit(1)


if __name__ == '__main__':
    main()
