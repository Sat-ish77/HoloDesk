"""
Thread-safe SQLite database wrapper for HoloDesk.

Key design decisions:
- Each thread gets its own SQLite connection (threading.local) to avoid
  "SQLite objects created in a thread can only be used in that same thread" errors.
- WAL (Write-Ahead Logging) mode is enabled so multiple threads can read
  while a write is happening, without blocking.
- Plain SQLite only — no sqlcipher3 dependency (unreliable on Windows).
"""

import sqlite3
import threading
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"
_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "holodesk.db"


class Database:
    def __init__(self, db_path: str | Path = _DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self._local = threading.local()
        # Ensure data/ directory exists before first connection
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection management — one connection per thread
    # ------------------------------------------------------------------

    @property
    def conn(self) -> sqlite3.Connection:
        """Return this thread's dedicated SQLite connection, creating if needed."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,  # We manage thread safety ourselves
                timeout=30,
            )
            self._local.conn.row_factory = sqlite3.Row
            # WAL mode: allows concurrent reads while a write is in progress
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
            # Small cache for slightly faster repeated queries
            self._local.conn.execute("PRAGMA cache_size=-8000")  # ~8MB
        return self._local.conn

    def _init_schema(self):
        """Run schema.sql once to create all tables and indexes if missing."""
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
            sql = f.read()
        # Use a temporary connection on the calling thread for init
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(sql)
        conn.commit()
        conn.close()
        logger.info("Database schema initialized at %s", self.db_path)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def insert(self, table: str, data: dict) -> int:
        """Insert a row and return the new row id."""
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        cursor = self.conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
            list(data.values()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update(self, table: str, data: dict, where: str, params: tuple = ()):
        """Update rows matching the WHERE clause."""
        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
        self.conn.execute(
            f"UPDATE {table} SET {set_clause} WHERE {where}",
            list(data.values()) + list(params),
        )
        self.conn.commit()

    def execute(self, sql: str, params: tuple = ()):
        """Run arbitrary SQL (INSERT / UPDATE / DELETE)."""
        self.conn.execute(sql, params)
        self.conn.commit()

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Run a SELECT and return a list of plain dicts."""
        cursor = self.conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def query_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Return the first matching row as a dict, or None."""
        cursor = self.conn.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Preferences helper (simple key/value store)
    # ------------------------------------------------------------------

    def get_pref(self, key: str, default=None):
        row = self.query_one(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        )
        return row["value"] if row else default

    def set_pref(self, key: str, value: str):
        self.execute(
            """INSERT INTO preferences (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,
               updated_at=excluded.updated_at""",
            (key, str(value)),
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        """Close the current thread's connection (call at thread exit)."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# Global singleton — import this anywhere in the codebase
db = Database()
