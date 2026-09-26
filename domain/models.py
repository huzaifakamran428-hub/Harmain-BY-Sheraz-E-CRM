"""
Domain entities. Plain dataclasses only - no PyQt6, no sqlite3, no
reportlab imports here (SRS 15.3: "the domain layer shall not depend
on PyQt6, MySQL, OCR libraries or PDF libraries").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date, time
from enum import Enum
from typing import Optional


class Gender(str, Enum):
    MALE = "Male"
    FEMALE = "Female"


class PilgrimStatus(str, Enum):
    ACTIVE = "Active"           # in a party ledger
    FREE_MALE = "FreeMale"      # transferred, male
    FREE_FEMALE = "FreeFemale"  # transferred, female
    ARCHIVED = "Archived"


class NotificationChannel(str, Enum):
    DESKTOP = "Desktop"
    EMAIL = "Email"
    WHATSAPP = "WhatsApp"


class NotificationStatus(str, Enum):
    PENDING = "Pending"
    SENT = "Sent"
    FAILED = "Failed"
    READ = "Read"
    REPLACED = "Replaced"   # an earlier reminder that was re-sent because the Gmail was added/changed


@dataclass
class User:
    id: Optional[int]
    username: str
    password_hash: str
    salt: str
    display_name: str = ""
    is_admin: bool = True
    created_at: Optional[datetime] = None


@dataclass
class Party:
    id: Optional[int]
    name: str
    phone: str
    address: str = ""
    cnic: str = ""
    active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # aggregate figures, populated by services - not stored on the row
    total_people: int = 0
    total_charge: float = 0.0
    total_received: float = 0.0
    total_remaining: float = 0.0


@dataclass
class Pilgrim:
    id: Optional[int]
    party_id: Optional[int]
    serial_number: int
    permit_date: Optional[date]
    permit_time: Optional[time]
    batch: str = ""
    name: str = ""
    passport_number: str = ""
    visa_number: str = ""
    gender: Gender = Gender.MALE
    email: str = ""
    whatsapp_number: str = ""
    password: str = ""
    charge: float = 200.0
    passport_document_path: str = ""
    photo_path: str = ""
    status: PilgrimStatus = PilgrimStatus.ACTIVE
    original_party_id: Optional[int] = None
    moved_to_free_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Serial inside the Free Account (Male / Female list), counted from 1 there.
    # 0 while the pilgrim is on a party ledger; `serial_number` is the party serial.
    free_serial: int = 0
    # aggregate figures, populated by services
    total_received: float = 0.0
    remaining: float = 0.0

    @property
    def first_name(self) -> str:
        return (self.name or "").strip().split(" ")[0] if self.name else ""


@dataclass
class Payment:
    id: Optional[int]
    pilgrim_id: int
    amount: float
    paid_at: datetime
    note: str = ""
    created_by: str = ""


@dataclass
class NotificationRecord:
    id: Optional[int]
    pilgrim_id: int
    type: str
    channel: NotificationChannel
    scheduled_for: datetime
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    status: NotificationStatus = NotificationStatus.PENDING
    retry_count: int = 0
    failure_reason: str = ""


@dataclass
class AuditEntry:
    id: Optional[int]
    user: str
    action: str
    entity: str
    entity_id: Optional[int]
    timestamp: datetime
    details: str = ""


@dataclass
class ReturnHistoryEntry:
    id: Optional[int]
    pilgrim_id: int
    source_status: str
    destination_party_id: int
    administrator: str
    timestamp: datetime
    reason: str = ""
