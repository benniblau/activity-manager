"""Open a standalone sqlite3 connection for the MCP server (no Flask involved)."""

import os
import sqlite3
import sys
from pathlib import Path

# Ensure project root is on sys.path so app.* imports work
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

# Load .env from the project root
load_dotenv(_PROJECT_ROOT / ".env")


def open_db() -> sqlite3.Connection:
    """Open a sqlite3 connection with WAL mode and foreign keys enabled.

    Returns:
        sqlite3.Connection ready for use.

    Raises:
        SystemExit(2): If the database file cannot be opened.
    """
    db_path = os.environ.get("DATABASE_PATH", str(_PROJECT_ROOT / "activities.db"))

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn
    except Exception as exc:
        print(f"[mcp_server] Failed to open database at {db_path}: {exc}", file=sys.stderr)
        sys.exit(2)
