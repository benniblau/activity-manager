#!/usr/bin/env python3
"""
Multi-User Migration Script

Migrates the single-user Activity Manager database to support multiple users,
coach-athlete relationships, and per-user Strava connections.

Usage:
    python scripts/migrate_to_multiuser.py [database_path]

If database_path is not provided, uses activities.db in the current directory.
"""

import sqlite3
import sys
import os
import shutil
from datetime import datetime
from getpass import getpass
import bcrypt


def backup_database(db_path):
    """Create a timestamped backup of the database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.pre_multiuser_backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Database backed up to: {backup_path}")
    return backup_path


def get_admin_credentials():
    """Prompt for admin user credentials"""
    print("\n=== Create Admin User ===")
    print("This user will own all existing activities and have full access.")

    name = input("Admin name: ").strip()
    while not name:
        print("Name cannot be empty.")
        name = input("Admin name: ").strip()

    email = input("Admin email: ").strip()
    while not email or '@' not in email:
        print("Please enter a valid email address.")
        email = input("Admin email: ").strip()

    while True:
        password = getpass("Admin password (min 8 chars): ")
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            continue
        password_confirm = getpass("Confirm password: ")
        if password == password_confirm:
            break
        print("Passwords do not match. Please try again.")

    return name, email, password


def hash_password(password):
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_users_table(conn):
    """Create the users table"""
    print("\n📋 Creating users table...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT DEFAULT 'athlete' CHECK (role IN ('athlete', 'coach')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)')
    print("✓ Users table created")


def create_coach_athlete_table(conn):
    """Create the coach-athlete relationships table"""
    print("\n📋 Creating coach_athlete_relationships table...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS coach_athlete_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coach_id INTEGER NOT NULL,
            athlete_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'inactive')),
            invited_at TEXT DEFAULT CURRENT_TIMESTAMP,
            accepted_at TEXT,
            FOREIGN KEY (coach_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (athlete_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(coach_id, athlete_id)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_relationships_coach ON coach_athlete_relationships(coach_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_relationships_athlete ON coach_athlete_relationships(athlete_id)')
    print("✓ Coach-athlete relationships table created")


def migrate_strava_tokens_table(conn, admin_user_id):
    """Migrate strava_tokens to multi-user version"""
    print("\n📋 Migrating strava_tokens table...")

    # Check if old table exists
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strava_tokens'")
    if not cursor.fetchone():
        print("✓ No existing strava_tokens table - creating new one")
        create_new_strava_tokens_table(conn)
        return

    # Get existing token data
    cursor = conn.execute('SELECT * FROM strava_tokens WHERE id = 1')
    old_token = cursor.fetchone()

    # Rename old table
    conn.execute('ALTER TABLE strava_tokens RENAME TO strava_tokens_old')
    print("  - Renamed old table to strava_tokens_old")

    # Create new table
    create_new_strava_tokens_table(conn)

    # Migrate data if exists
    if old_token:
        conn.execute('''
            INSERT INTO strava_tokens (user_id, athlete_id, athlete_name, access_token, refresh_token, expires_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            admin_user_id,
            old_token[1],  # athlete_id
            old_token[2],  # athlete_name
            old_token[3],  # access_token
            old_token[4],  # refresh_token
            old_token[5],  # expires_at
            old_token[6],  # created_at
            old_token[7]   # updated_at
        ))
        print(f"  - Migrated existing Strava token to admin user (athlete: {old_token[2]})")

    print("✓ Strava tokens table migrated")


def create_new_strava_tokens_table(conn):
    """Create new multi-user strava_tokens table"""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS strava_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            athlete_id INTEGER,
            athlete_name TEXT,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_strava_tokens_user ON strava_tokens(user_id)')


def add_user_id_to_activities(conn, admin_user_id):
    """Add user_id column to activities table"""
    print("\n📋 Adding user_id to activities table...")

    # Check if column already exists
    cursor = conn.execute("PRAGMA table_info(activities)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'user_id' in columns:
        print("  - user_id column already exists")
    else:
        conn.execute('ALTER TABLE activities ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE')
        print("  - Added user_id column")

    # Update all existing activities to belong to admin
    result = conn.execute('UPDATE activities SET user_id = ? WHERE user_id IS NULL', (admin_user_id,))
    count = result.rowcount
    print(f"  - Assigned {count} activities to admin user")

    # Create index
    conn.execute('CREATE INDEX IF NOT EXISTS idx_activities_user_id ON activities(user_id)')
    print("✓ Activities table updated")


def add_user_id_to_days(conn, admin_user_id):
    """Add user_id column to days table"""
    print("\n📋 Adding user_id to days table...")

    # Check if column already exists
    cursor = conn.execute("PRAGMA table_info(days)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'user_id' in columns:
        print("  - user_id column already exists")
    else:
        conn.execute('ALTER TABLE days ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE')
        print("  - Added user_id column")

    # Update all existing days to belong to admin
    result = conn.execute('UPDATE days SET user_id = ? WHERE user_id IS NULL', (admin_user_id,))
    count = result.rowcount
    print(f"  - Assigned {count} day records to admin user")

    # Create index
    conn.execute('CREATE INDEX IF NOT EXISTS idx_days_user_id ON days(user_id)')
    print("✓ Days table updated")


def add_user_id_to_extended_types(conn, admin_user_id):
    """Add user_id column to extended_activity_types table"""
    print("\n📋 Adding user_id to extended_activity_types table...")

    # Check if table exists
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='extended_activity_types'")
    if not cursor.fetchone():
        print("  - Table does not exist, skipping")
        return

    # Check if column already exists
    cursor = conn.execute("PRAGMA table_info(extended_activity_types)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'user_id' in columns:
        print("  - user_id column already exists")
    else:
        conn.execute('ALTER TABLE extended_activity_types ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE')
        print("  - Added user_id column")

    # Update existing types - NULL user_id means system-wide types
    # Only assign to admin if they have activities using these types
    result = conn.execute('''
        UPDATE extended_activity_types
        SET user_id = NULL
        WHERE user_id IS NULL
    ''')
    print("  - Set existing types as system-wide (user_id = NULL)")

    # Create index
    conn.execute('CREATE INDEX IF NOT EXISTS idx_extended_types_user_id ON extended_activity_types(user_id)')
    print("✓ Extended activity types table updated")


def create_admin_user(conn, name, email, password):
    """Create the admin user"""
    print("\n👤 Creating admin user...")

    password_hash = hash_password(password)

    cursor = conn.execute('''
        INSERT INTO users (email, password_hash, name, role, is_active)
        VALUES (?, ?, ?, 'athlete', 1)
    ''', (email, password_hash, name))

    admin_user_id = cursor.lastrowid
    print(f"✓ Admin user created (ID: {admin_user_id}, Email: {email})")

    return admin_user_id


def verify_migration(conn, admin_user_id):
    """Verify migration was successful"""
    print("\n🔍 Verifying migration...")

    # Check users table
    cursor = conn.execute('SELECT COUNT(*) FROM users')
    user_count = cursor.fetchone()[0]
    print(f"  - Users: {user_count}")

    # Check activities
    cursor = conn.execute('SELECT COUNT(*) FROM activities WHERE user_id = ?', (admin_user_id,))
    activity_count = cursor.fetchone()[0]
    print(f"  - Activities assigned to admin: {activity_count}")

    # Check days
    cursor = conn.execute('SELECT COUNT(*) FROM days WHERE user_id = ?', (admin_user_id,))
    days_count = cursor.fetchone()[0]
    print(f"  - Days assigned to admin: {days_count}")

    # Check strava tokens
    cursor = conn.execute('SELECT COUNT(*) FROM strava_tokens WHERE user_id = ?', (admin_user_id,))
    token_count = cursor.fetchone()[0]
    print(f"  - Strava tokens: {token_count}")

    print("\n✓ Migration verification complete")


def main():
    """Main migration function"""
    print("=" * 60)
    print("Activity Manager - Multi-User Migration")
    print("=" * 60)

    # Get database path
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'activities.db'

    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)

    print(f"\nDatabase: {db_path}")

    # Confirm migration
    print("\nThis migration will:")
    print("  1. Backup your database")
    print("  2. Create multi-user tables")
    print("  3. Add user_id columns to existing tables")
    print("  4. Create an admin user")
    print("  5. Assign all existing data to the admin user")

    confirm = input("\nProceed with migration? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Migration cancelled.")
        sys.exit(0)

    # Backup database
    backup_path = backup_database(db_path)

    # Get admin credentials
    admin_name, admin_email, admin_password = get_admin_credentials()

    # Connect to database
    print("\n📂 Opening database...")
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON')

    try:
        # Begin transaction
        conn.execute('BEGIN')

        # Create new tables
        create_users_table(conn)
        create_coach_athlete_table(conn)

        # Create admin user
        admin_user_id = create_admin_user(conn, admin_name, admin_email, admin_password)

        # Migrate strava tokens
        migrate_strava_tokens_table(conn, admin_user_id)

        # Add user_id to existing tables
        add_user_id_to_activities(conn, admin_user_id)
        add_user_id_to_days(conn, admin_user_id)
        add_user_id_to_extended_types(conn, admin_user_id)

        # Verify migration
        verify_migration(conn, admin_user_id)

        # Commit transaction
        conn.commit()
        print("\n✓ Migration completed successfully!")

        print("\n" + "=" * 60)
        print("IMPORTANT: Next Steps")
        print("=" * 60)
        print("1. Install bcrypt: pip install bcrypt")
        print("2. Update your application code to use the new authentication system")
        print("3. Test login with:")
        print(f"   Email: {admin_email}")
        print(f"   Password: (the password you just set)")
        print("4. The old database backup is at:")
        print(f"   {backup_path}")
        print("=" * 60)

    except Exception as e:
        # Rollback on error
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        print(f"Database has been rolled back.")
        print(f"Backup available at: {backup_path}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
