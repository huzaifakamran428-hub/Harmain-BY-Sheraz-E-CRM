"""
Database access layer (SRS section 6 + 15: "Database access shall be
centralized... rather than scattered throughout the UI").

Uses the Python standard library's sqlite3 module - a single local
file database that needs zero server installation on either Windows
or macOS. All queries elsewhere in the app go through the repository
classes in infrastructure/repositories.py, never raw SQL from the UI.

NOTE ON ARCHITECTURE: the SRS's target stack is Python Django + MySQL.
That pairing is right for a networked, multi-computer deployment, but
requires a separately running database server, which fights the goal
of "just works on Windows and macOS". Because this layer is fully
isolated behind the repository classes, swapping it for Django ORM +
MySQL later (for a multi-user/server deployment) only touches this
file and repositories.py - nothing above it changes.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from core.config import get_db_path
from core.exceptions import DatabaseOperationError
from core.logging_setup import get_logger

logger = get_logger(__name__)

_local = threading.local()


def _in_explicit_transaction() -> bool:
    return getattr(_local, "explicit_transaction_depth", 0) > 0

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    is_admin INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT DEFAULT '',
    cnic TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pilgrims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    party_id INTEGER,
    serial_number INTEGER NOT NULL,
    permit_date TEXT,
    permit_time TEXT,
    batch TEXT DEFAULT '',
    name TEXT NOT NULL,
    passport_number TEXT DEFAULT '',
    visa_number TEXT DEFAULT '',
    gender TEXT NOT NULL DEFAULT 'Male',
    email TEXT DEFAULT '',
    whatsapp_number TEXT DEFAULT '',
    password TEXT DEFAULT '',
    charge REAL NOT NULL DEFAULT 200,
    passport_document_path TEXT DEFAULT '',
    photo_path TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Active',
    original_party_id INTEGER,
    moved_to_free_at TEXT,
    returned_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    free_serial INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pilgrim_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    paid_at TEXT NOT NULL,
    note TEXT DEFAULT '',
    created_by TEXT DEFAULT '',
    FOREIGN KEY (pilgrim_id) REFERENCES pilgrims(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pilgrim_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    channel TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    sent_at TEXT,
    read_at TEXT,
    status TEXT NOT NULL DEFAULT 'Pending',
    retry_count INTEGER DEFAULT 0,
    failure_reason TEXT DEFAULT '',
    FOREIGN KEY (pilgrim_id) REFERENCES pilgrims(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id INTEGER,
    timestamp TEXT NOT NULL,
    details TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS return_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pilgrim_id INTEGER NOT NULL,
    source_status TEXT NOT NULL,
    destination_party_id INTEGER NOT NULL,
    administrator TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    reason TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pilgrim_passport ON pilgrims(passport_number);
CREATE INDEX IF NOT EXISTS idx_pilgrim_visa ON pilgrims(visa_number);
CREATE INDEX IF NOT EXISTS idx_pilgrim_name ON pilgrims(name);
CREATE INDEX IF NOT EXISTS idx_pilgrim_status ON pilgrims(status);
CREATE INDEX IF NOT EXISTS idx_pilgrim_permit_date ON pilgrims(permit_date);
CREATE INDEX IF NOT EXISTS idx_pilgrim_party ON pilgrims(party_id);
CREATE INDEX IF NOT EXISTS idx_payment_pilgrim ON payments(pilgrim_id);
CREATE INDEX IF NOT EXISTS idx_notification_pilgrim ON notifications(pilgrim_id);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """
    One connection per thread (sqlite3 connections are not safe to share
    across threads). The background scheduler runs on its own thread and
    gets its own connection via this same function.
    """
    if not hasattr(_local, "conn") or _local.conn is None:
        path = db_path or get_db_path()
        try:
            conn = sqlite3.connect(str(path), timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error as e:
            logger.error("Failed to open database at %s: %s", path, e)
            raise DatabaseOperationError() from e
        _local.conn = conn
    return _local.conn


def initialize_database(db_path: Path | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        _run_migrations(conn)
        conn.commit()
    except sqlite3.Error as e:
        logger.error("Schema initialization failed: %s", e)
        raise DatabaseOperationError() from e


# Columns added after the first release. `CREATE TABLE IF NOT EXISTS` in
# SCHEMA above only creates a brand-new table - it does nothing to a
# pilgrims table that already exists on an administrator's computer from
# an earlier version, so any column added later must also be listed here
# and is added with ALTER TABLE if missing (existing data is kept as-is).
_PILGRIM_COLUMN_MIGRATIONS = (
    ("photo_path", "TEXT DEFAULT ''"),
    ("free_serial", "INTEGER NOT NULL DEFAULT 0"),
)


def _run_migrations(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(pilgrims)").fetchall()}
    for column, definition in _PILGRIM_COLUMN_MIGRATIONS:
        if column not in existing:
            conn.execute(f"ALTER TABLE pilgrims ADD COLUMN {column} {definition}")
    repair_serial_numbers(conn)


def repair_serial_numbers(conn: sqlite3.Connection) -> None:
    """
    Keeps every serial number honest. Safe to run on every start-up (it does nothing
    when the numbers are already right):

    1. Party ledger: two active pilgrims of one party must never share a serial. This
       happened when a pilgrim came back from the Free Account still carrying an old
       number (1, 2, 2, 5, ...). The pilgrim who was NOT returned (else the oldest
       record) keeps the number; the other one gets the party's next free number.
    2. Free Account: Male and Female each count 1, 2, 3, ... on their own. Pilgrims
       already in the Free Account without such a number get one, in the order they
       were moved there.
    """
    rows = conn.execute(
        "SELECT id, party_id, serial_number, returned_at FROM pilgrims "
        "WHERE status='Active' AND party_id IS NOT NULL ORDER BY party_id, serial_number, "
        "(returned_at IS NOT NULL), id"
    ).fetchall()
    seen: set = set()
    duplicates: list = []
    for row in rows:
        key = (row["party_id"], row["serial_number"])
        if key in seen:
            duplicates.append(row)
        else:
            seen.add(key)
    for row in duplicates:
        new_serial = conn.execute(
            "SELECT COALESCE(MAX(serial_number),0)+1 n FROM pilgrims WHERE party_id=?",
            (row["party_id"],),
        ).fetchone()["n"]
        conn.execute("UPDATE pilgrims SET serial_number=? WHERE id=?", (new_serial, row["id"]))
        logger.info("Serial repair: pilgrim %s in party %s moved from %s to %s",
                    row["id"], row["party_id"], row["serial_number"], new_serial)

    for status in ("FreeMale", "FreeFemale"):
        used = conn.execute(
            "SELECT COALESCE(MAX(free_serial),0) m FROM pilgrims WHERE status=?", (status,)
        ).fetchone()["m"]
        waiting = conn.execute(
            "SELECT id FROM pilgrims WHERE status=? AND (free_serial IS NULL OR free_serial=0) "
            "ORDER BY moved_to_free_at, id", (status,)
        ).fetchall()
        for row in waiting:
            used += 1
            conn.execute("UPDATE pilgrims SET free_serial=? WHERE id=?", (used, row["id"]))


@contextmanager
def transaction():
    """
    Wraps a block of repository calls in a single atomic transaction
    (SRS 16.6: multi-step writes, e.g. transferring a pilgrim to Free
    Account, must be atomic and roll back completely on failure).

    Repository methods check `_in_explicit_transaction()` and skip their
    own per-call commit while inside this block, so the whole block
    commits - or rolls back - as one unit. Depth-counted so nested
    `with transaction():` calls (e.g. a service calling another
    transactional service) still only commit once, at the outermost exit.

    Usage:
        with transaction() as conn:
            party_repo.update(..., conn=conn)
            pilgrim_repo.update(..., conn=conn)
    """
    conn = get_connection()
    depth = getattr(_local, "explicit_transaction_depth", 0)
    _local.explicit_transaction_depth = depth + 1
    try:
        yield conn
        if depth == 0:
            conn.commit()
    except Exception as e:
        if depth > 0:
            # Not the outermost block - let the outer transaction() decide
            # whether/how to roll back and translate the error.
            raise
        conn.rollback()
        logger.error("Transaction rolled back: %s", e)
        if isinstance(e, DatabaseOperationError):
            raise
        raise DatabaseOperationError() from e
    finally:
        _local.explicit_transaction_depth = depth
