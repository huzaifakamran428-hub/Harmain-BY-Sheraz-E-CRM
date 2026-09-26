"""
Repository layer: the ONLY place in the application that writes raw
SQL. Every query is parameterized (never string-formatted) to prevent
SQL injection (NFR / SRS section 10). Presentation and application
layers call these classes instead of touching sqlite3 directly.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, date, time
from typing import Optional, List

from core.exceptions import DatabaseOperationError, DuplicateRecordError, NotFoundError
from core.logging_setup import get_logger
from infrastructure.db import get_connection, _in_explicit_transaction
from domain.models import (
    Party, Pilgrim, Payment, NotificationRecord, AuditEntry, ReturnHistoryEntry,
    User, Gender, PilgrimStatus, NotificationChannel, NotificationStatus,
)

logger = get_logger(__name__)


def _dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _d(value: Optional[str]) -> Optional[date]:
    return date.fromisoformat(value) if value else None


def _t(value: Optional[str]) -> Optional[time]:
    return time.fromisoformat(value) if value else None


def _iso(value) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _run(conn: sqlite3.Connection, sql: str, params: tuple = ()):
    try:
        return conn.execute(sql, params)
    except sqlite3.IntegrityError as e:
        raise DuplicateRecordError(str(e)) from e
    except sqlite3.Error as e:
        logger.error("Query failed [%s] params=%s: %s", sql, params, e)
        raise DatabaseOperationError() from e


class UserRepository:
    def get_by_username(self, username: str, conn=None) -> Optional[User]:
        conn = conn or get_connection()
        row = _run(conn, "SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return self._map(row) if row else None

    def create(self, user: User, conn=None) -> User:
        conn = conn or get_connection()
        cur = _run(
            conn,
            "INSERT INTO users (username, password_hash, salt, display_name, is_admin, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user.username, user.password_hash, user.salt, user.display_name,
             int(user.is_admin), _iso(datetime.now())),
        )
        if not _in_explicit_transaction():
            conn.commit()
        user.id = cur.lastrowid
        return user

    def any_exist(self, conn=None) -> bool:
        conn = conn or get_connection()
        row = _run(conn, "SELECT COUNT(*) c FROM users").fetchone()
        return row["c"] > 0

    def update_password(self, user_id: int, password_hash: str, salt: str, conn=None):
        conn = conn or get_connection()
        _run(conn, "UPDATE users SET password_hash=?, salt=? WHERE id=?", (password_hash, salt, user_id))
        if not _in_explicit_transaction():
            conn.commit()

    @staticmethod
    def _map(row) -> User:
        return User(
            id=row["id"], username=row["username"], password_hash=row["password_hash"],
            salt=row["salt"], display_name=row["display_name"], is_admin=bool(row["is_admin"]),
            created_at=_dt(row["created_at"]),
        )


class PartyRepository:
    def create(self, party: Party, conn=None) -> Party:
        conn = conn or get_connection()
        now = _iso(datetime.now())
        cur = _run(
            conn,
            "INSERT INTO parties (name, phone, address, cnic, active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (party.name, party.phone, party.address, party.cnic, int(party.active), now, now),
        )
        if not _in_explicit_transaction():
            conn.commit()
        party.id = cur.lastrowid
        return party

    def update(self, party: Party, conn=None) -> None:
        conn = conn or get_connection()
        _run(
            conn,
            "UPDATE parties SET name=?, phone=?, address=?, cnic=?, active=?, updated_at=? WHERE id=?",
            (party.name, party.phone, party.address, party.cnic, int(party.active),
             _iso(datetime.now()), party.id),
        )
        if not _in_explicit_transaction():
            conn.commit()

    def get(self, party_id: int, conn=None) -> Optional[Party]:
        conn = conn or get_connection()
        row = _run(conn, "SELECT * FROM parties WHERE id=?", (party_id,)).fetchone()
        return self._map(row) if row else None

    def list_active(self, search: str = "", conn=None) -> List[Party]:
        conn = conn or get_connection()
        if search:
            rows = _run(
                conn,
                "SELECT * FROM parties WHERE active=1 AND (name LIKE ? OR phone LIKE ?) ORDER BY name",
                (f"%{search}%", f"%{search}%"),
            ).fetchall()
        else:
            rows = _run(conn, "SELECT * FROM parties WHERE active=1 ORDER BY name").fetchall()
        return [self._map(r) for r in rows]

    def archive(self, party_id: int, conn=None) -> None:
        conn = conn or get_connection()
        _run(conn, "UPDATE parties SET active=0, updated_at=? WHERE id=?", (_iso(datetime.now()), party_id))
        if not _in_explicit_transaction():
            conn.commit()

    def delete(self, party_id: int, conn=None) -> None:
        """Permanently remove the party row. Callers must first deal with any
        pilgrims still pointing at this party (see PilgrimRepository.list_all_by_party) -
        the foreign key only sets their party_id to NULL, it does not remove them."""
        conn = conn or get_connection()
        _run(conn, "DELETE FROM parties WHERE id=?", (party_id,))
        if not _in_explicit_transaction():
            conn.commit()

    @staticmethod
    def _map(row) -> Party:
        return Party(
            id=row["id"], name=row["name"], phone=row["phone"], address=row["address"],
            cnic=row["cnic"], active=bool(row["active"]),
            created_at=_dt(row["created_at"]), updated_at=_dt(row["updated_at"]),
        )


class PilgrimRepository:
    def next_serial_number(self, party_id: Optional[int], conn=None) -> int:
        """Next free serial of this party: every party counts 1, 2, 3, ... on its own.
        Pilgrims sitting in the Free Account still belong to the party (party_id is kept),
        so their numbers are never handed out again."""
        conn = conn or get_connection()
        if party_id is None:
            row = _run(conn, "SELECT COALESCE(MAX(serial_number),0)+1 n FROM pilgrims").fetchone()
        else:
            row = _run(
                conn, "SELECT COALESCE(MAX(serial_number),0)+1 n FROM pilgrims WHERE party_id=?", (party_id,)
            ).fetchone()
        return row["n"]

    def next_free_serial(self, status: PilgrimStatus, conn=None) -> int:
        """Next serial inside the Free Account list (Male and Female each count from 1)."""
        conn = conn or get_connection()
        row = _run(
            conn, "SELECT COALESCE(MAX(free_serial),0)+1 n FROM pilgrims WHERE status=?", (status.value,)
        ).fetchone()
        return row["n"]

    def create(self, p: Pilgrim, conn=None) -> Pilgrim:
        conn = conn or get_connection()
        now = _iso(datetime.now())
        cur = _run(
            conn,
            """INSERT INTO pilgrims
               (party_id, serial_number, permit_date, permit_time, batch, name, passport_number,
                visa_number, gender, email, whatsapp_number, password, charge,
                passport_document_path, photo_path, status, original_party_id, moved_to_free_at, returned_at,
                created_at, updated_at, free_serial)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p.party_id, p.serial_number, _iso(p.permit_date), _iso(p.permit_time), p.batch, p.name,
             p.passport_number, p.visa_number, p.gender.value, p.email, p.whatsapp_number, p.password,
             p.charge, p.passport_document_path, p.photo_path, p.status.value, p.original_party_id,
             _iso(p.moved_to_free_at), _iso(p.returned_at), now, now, p.free_serial),
        )
        if not _in_explicit_transaction():
            conn.commit()
        p.id = cur.lastrowid
        return p

    def update(self, p: Pilgrim, conn=None) -> None:
        conn = conn or get_connection()
        _run(
            conn,
            """UPDATE pilgrims SET party_id=?, serial_number=?, free_serial=?, permit_date=?, permit_time=?,
               batch=?, name=?,
               passport_number=?, visa_number=?, gender=?, email=?, whatsapp_number=?, password=?,
               charge=?, passport_document_path=?, photo_path=?, status=?, original_party_id=?, moved_to_free_at=?,
               returned_at=?, updated_at=? WHERE id=?""",
            (p.party_id, p.serial_number, p.free_serial, _iso(p.permit_date), _iso(p.permit_time),
             p.batch, p.name, p.passport_number,
             p.visa_number, p.gender.value, p.email, p.whatsapp_number, p.password, p.charge,
             p.passport_document_path, p.photo_path, p.status.value, p.original_party_id, _iso(p.moved_to_free_at),
             _iso(p.returned_at), _iso(datetime.now()), p.id),
        )
        if not _in_explicit_transaction():
            conn.commit()

    def get(self, pilgrim_id: int, conn=None) -> Optional[Pilgrim]:
        conn = conn or get_connection()
        row = _run(conn, "SELECT * FROM pilgrims WHERE id=?", (pilgrim_id,)).fetchone()
        return self._map(row) if row else None

    def find_duplicates(self, passport_number: str, visa_number: str, exclude_id: Optional[int] = None, conn=None) -> List[Pilgrim]:
        conn = conn or get_connection()
        clauses, params = [], []
        if passport_number:
            clauses.append("passport_number = ?")
            params.append(passport_number)
        if visa_number:
            clauses.append("visa_number = ?")
            params.append(visa_number)
        if not clauses:
            return []
        sql = f"SELECT * FROM pilgrims WHERE ({' OR '.join(clauses)}) AND status != 'Archived'"
        if exclude_id:
            sql += " AND id != ?"
            params.append(exclude_id)
        rows = _run(conn, sql, tuple(params)).fetchall()
        return [self._map(r) for r in rows]

    def list_by_party(self, party_id: int, search: str = "", gender: Optional[Gender] = None, conn=None) -> List[Pilgrim]:
        conn = conn or get_connection()
        sql = "SELECT * FROM pilgrims WHERE party_id=? AND status='Active'"
        params: list = [party_id]
        sql, params = self._apply_filters(sql, params, search, gender)
        sql += " ORDER BY serial_number"
        rows = _run(conn, sql, tuple(params)).fetchall()
        return [self._map(r) for r in rows]

    def list_free(self, status: PilgrimStatus, search: str = "", conn=None) -> List[Pilgrim]:
        conn = conn or get_connection()
        sql = "SELECT * FROM pilgrims WHERE status=?"
        params: list = [status.value]
        sql, params = self._apply_filters(sql, params, search, None)
        sql += " ORDER BY free_serial, moved_to_free_at"
        rows = _run(conn, sql, tuple(params)).fetchall()
        return [self._map(r) for r in rows]

    def list_all_by_party(self, party_id: int, conn=None) -> List[Pilgrim]:
        """Every pilgrim ever attached to this party, whatever their status -
        Active, Free Account, whatever. Used before deleting a party, so no
        pilgrim is silently orphaned (party_id set to NULL) instead of removed."""
        conn = conn or get_connection()
        rows = _run(conn, "SELECT * FROM pilgrims WHERE party_id=?", (party_id,)).fetchall()
        return [self._map(r) for r in rows]

    def delete(self, pilgrim_id: int, conn=None) -> None:
        """Permanently remove the pilgrim. Their payments and notifications are
        removed with them (ON DELETE CASCADE in the schema)."""
        conn = conn or get_connection()
        _run(conn, "DELETE FROM pilgrims WHERE id=?", (pilgrim_id,))
        if not _in_explicit_transaction():
            conn.commit()

    def list_upcoming_active(self, conn=None) -> List[Pilgrim]:
        """All active pilgrims that have a permit date set (for reminder/highlight scanning)."""
        conn = conn or get_connection()
        rows = _run(
            conn,
            "SELECT * FROM pilgrims WHERE status='Active' AND permit_date IS NOT NULL AND permit_date != ''",
        ).fetchall()
        return [self._map(r) for r in rows]

    @staticmethod
    def _apply_filters(sql: str, params: list, search: str, gender: Optional[Gender]):
        if search:
            sql += " AND (name LIKE ? OR passport_number LIKE ? OR visa_number LIKE ?)"
            like = f"%{search}%"
            params += [like, like, like]
        if gender:
            sql += " AND gender = ?"
            params.append(gender.value)
        return sql, params

    @staticmethod
    def _map(row) -> Pilgrim:
        return Pilgrim(
            id=row["id"], party_id=row["party_id"], serial_number=row["serial_number"],
            permit_date=_d(row["permit_date"]), permit_time=_t(row["permit_time"]),
            batch=row["batch"], name=row["name"], passport_number=row["passport_number"],
            visa_number=row["visa_number"], gender=Gender(row["gender"]), email=row["email"],
            whatsapp_number=row["whatsapp_number"], password=row["password"], charge=row["charge"],
            passport_document_path=row["passport_document_path"],
            photo_path=(row["photo_path"] if "photo_path" in row.keys() else ""),
            status=PilgrimStatus(row["status"]),
            original_party_id=row["original_party_id"], moved_to_free_at=_dt(row["moved_to_free_at"]),
            returned_at=_dt(row["returned_at"]), created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
            free_serial=(row["free_serial"] or 0) if "free_serial" in row.keys() else 0,
        )


class PaymentRepository:
    def create(self, payment: Payment, conn=None) -> Payment:
        conn = conn or get_connection()
        cur = _run(
            conn,
            "INSERT INTO payments (pilgrim_id, amount, paid_at, note, created_by) VALUES (?,?,?,?,?)",
            (payment.pilgrim_id, payment.amount, _iso(payment.paid_at), payment.note, payment.created_by),
        )
        if not _in_explicit_transaction():
            conn.commit()
        payment.id = cur.lastrowid
        return payment

    def total_received_for_pilgrim(self, pilgrim_id: int, conn=None) -> float:
        conn = conn or get_connection()
        row = _run(conn, "SELECT COALESCE(SUM(amount),0) t FROM payments WHERE pilgrim_id=?", (pilgrim_id,)).fetchone()
        return row["t"]

    def totals_for_party(self, party_id: int, conn=None) -> float:
        conn = conn or get_connection()
        row = _run(
            conn,
            "SELECT COALESCE(SUM(p.amount),0) t FROM payments p "
            "JOIN pilgrims pl ON pl.id = p.pilgrim_id WHERE pl.party_id=? AND pl.status='Active'",
            (party_id,),
        ).fetchone()
        return row["t"]

    def history_for_pilgrim(self, pilgrim_id: int, conn=None) -> List[Payment]:
        conn = conn or get_connection()
        rows = _run(conn, "SELECT * FROM payments WHERE pilgrim_id=? ORDER BY paid_at DESC", (pilgrim_id,)).fetchall()
        return [
            Payment(id=r["id"], pilgrim_id=r["pilgrim_id"], amount=r["amount"],
                    paid_at=_dt(r["paid_at"]), note=r["note"], created_by=r["created_by"])
            for r in rows
        ]


class NotificationRepository:
    def exists_pending_or_sent(self, pilgrim_id: int, ntype: str, channel: NotificationChannel,
                                permit_dt: datetime, conn=None) -> bool:
        conn = conn or get_connection()
        row = _run(
            conn,
            "SELECT COUNT(*) c FROM notifications WHERE pilgrim_id=? AND type=? AND channel=? "
            "AND status NOT IN ('Failed', 'Replaced')",
            (pilgrim_id, ntype, channel.value),
        ).fetchone()
        return row["c"] > 0

    def create(self, n: NotificationRecord, conn=None) -> NotificationRecord:
        conn = conn or get_connection()
        cur = _run(
            conn,
            "INSERT INTO notifications (pilgrim_id, type, channel, scheduled_for, sent_at, read_at, "
            "status, retry_count, failure_reason) VALUES (?,?,?,?,?,?,?,?,?)",
            (n.pilgrim_id, n.type, n.channel.value, _iso(n.scheduled_for), _iso(n.sent_at),
             _iso(n.read_at), n.status.value, n.retry_count, n.failure_reason),
        )
        if not _in_explicit_transaction():
            conn.commit()
        n.id = cur.lastrowid
        return n

    def supersede_sent(self, pilgrim_id: int, ntype: str, channel: NotificationChannel, conn=None) -> int:
        """
        Mark an already-sent reminder as 'Replaced' so the next automatic check sends a fresh one
        (used when the pilgrim's Gmail is added or corrected after the first email went out).
        The old row stays in the list as history.
        """
        conn = conn or get_connection()
        cur = _run(
            conn,
            "UPDATE notifications SET status='Replaced' WHERE pilgrim_id=? AND type=? AND channel=? "
            "AND status='Sent'",
            (pilgrim_id, ntype, channel.value),
        )
        if not _in_explicit_transaction():
            conn.commit()
        return cur.rowcount

    def latest_failed_id(self, pilgrim_id: int, ntype: str, channel: NotificationChannel, conn=None) -> Optional[int]:
        """The earlier Failed row for this reminder, so a retry updates it instead of adding another."""
        conn = conn or get_connection()
        row = _run(
            conn,
            "SELECT id FROM notifications WHERE pilgrim_id=? AND type=? AND channel=? AND status='Failed' "
            "ORDER BY id DESC LIMIT 1",
            (pilgrim_id, ntype, channel.value),
        ).fetchone()
        return row["id"] if row else None

    def mark_sent(self, notification_id: int, conn=None):
        conn = conn or get_connection()
        _run(conn, "UPDATE notifications SET status='Sent', sent_at=?, failure_reason='' WHERE id=?",
             (_iso(datetime.now()), notification_id))
        if not _in_explicit_transaction():
            conn.commit()

    def mark_failed(self, notification_id: int, reason: str, conn=None):
        conn = conn or get_connection()
        _run(
            conn,
            "UPDATE notifications SET status='Failed', failure_reason=?, retry_count=retry_count+1 WHERE id=?",
            (reason[:500], notification_id),
        )
        if not _in_explicit_transaction():
            conn.commit()

    def list_recent(self, limit: int = 100, conn=None) -> List[NotificationRecord]:
        conn = conn or get_connection()
        rows = _run(
            conn,
            "SELECT n.*, p.name as pilgrim_name FROM notifications n "
            "JOIN pilgrims p ON p.id = n.pilgrim_id ORDER BY n.scheduled_for DESC LIMIT ?",
            (limit,),
        ).fetchall()
        results = []
        for r in rows:
            rec = NotificationRecord(
                id=r["id"], pilgrim_id=r["pilgrim_id"], type=r["type"],
                channel=NotificationChannel(r["channel"]), scheduled_for=_dt(r["scheduled_for"]),
                sent_at=_dt(r["sent_at"]), read_at=_dt(r["read_at"]), status=NotificationStatus(r["status"]),
                retry_count=r["retry_count"], failure_reason=r["failure_reason"],
            )
            rec.pilgrim_name = r["pilgrim_name"]  # type: ignore[attr-defined]
            results.append(rec)
        return results

    def count_pending(self, conn=None) -> int:
        conn = conn or get_connection()
        row = _run(conn, "SELECT COUNT(*) c FROM notifications WHERE status='Pending'").fetchone()
        return row["c"]


class AuditRepository:
    def log(self, entry: AuditEntry, conn=None) -> None:
        conn = conn or get_connection()
        _run(
            conn,
            "INSERT INTO audit_log (user, action, entity, entity_id, timestamp, details) VALUES (?,?,?,?,?,?)",
            (entry.user, entry.action, entry.entity, entry.entity_id, _iso(entry.timestamp), entry.details),
        )
        if not _in_explicit_transaction():
            conn.commit()

    def list_recent(self, limit: int = 200, conn=None) -> List[AuditEntry]:
        conn = conn or get_connection()
        rows = _run(conn, "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [
            AuditEntry(id=r["id"], user=r["user"], action=r["action"], entity=r["entity"],
                       entity_id=r["entity_id"], timestamp=_dt(r["timestamp"]), details=r["details"])
            for r in rows
        ]


class ReturnHistoryRepository:
    def create(self, entry: ReturnHistoryEntry, conn=None) -> None:
        conn = conn or get_connection()
        _run(
            conn,
            "INSERT INTO return_history (pilgrim_id, source_status, destination_party_id, administrator, "
            "timestamp, reason) VALUES (?,?,?,?,?,?)",
            (entry.pilgrim_id, entry.source_status, entry.destination_party_id, entry.administrator,
             _iso(entry.timestamp), entry.reason),
        )
        if not _in_explicit_transaction():
            conn.commit()


class SettingsRepository:
    def get(self, key: str, default: Optional[str] = None, conn=None) -> Optional[str]:
        conn = conn or get_connection()
        row = _run(conn, "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str, conn=None) -> None:
        conn = conn or get_connection()
        _run(conn, "INSERT INTO settings (key, value) VALUES (?, ?) "
                   "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        if not _in_explicit_transaction():
            conn.commit()

    def get_all(self, conn=None) -> dict:
        conn = conn or get_connection()
        rows = _run(conn, "SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
