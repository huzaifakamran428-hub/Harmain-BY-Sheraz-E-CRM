"""
Six-hour automatic transfer and the Return-to-Party workflow (SRS 4.9,
5.4, 20.2, 20.3). Both operations are atomic: SRS 16.6 explicitly
requires that "a failed transfer must never leave a pilgrim
half-moved", so every multi-step write here runs inside a single
infrastructure.db.transaction() block.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from core.exceptions import ValidationError, NotFoundError
from domain.models import Pilgrim, PilgrimStatus, Party, AuditEntry, ReturnHistoryEntry
from domain.rules import route_free_status, is_eligible_for_transfer
from infrastructure.repositories import (
    PilgrimRepository, PartyRepository, AuditRepository, ReturnHistoryRepository,
)
from infrastructure.db import transaction
from core.config import DEFAULT_TRANSFER_HOURS
from core.logging_setup import get_logger

logger = get_logger(__name__)


class FreeAccountService:
    def __init__(self):
        self.pilgrims = PilgrimRepository()
        self.parties = PartyRepository()
        self.audit = AuditRepository()
        self.return_history = ReturnHistoryRepository()

    def transfer_to_free(self, pilgrim_id: int, actor: str = "system") -> Pilgrim:
        with transaction() as conn:
            pilgrim = self.pilgrims.get(pilgrim_id, conn=conn)
            if not pilgrim:
                raise NotFoundError("Pilgrim not found.")
            if pilgrim.status != PilgrimStatus.ACTIVE:
                raise ValidationError("Only active pilgrims can be transferred to a Free Account.")

            pilgrim.status = route_free_status(pilgrim.gender)
            pilgrim.moved_to_free_at = datetime.now()
            # The Free Account counts on its own, from 1 (Male and Female separately).
            pilgrim.free_serial = self.pilgrims.next_free_serial(pilgrim.status, conn=conn)
            self.pilgrims.update(pilgrim, conn=conn)
            self.audit.log(
                AuditEntry(id=None, user=actor, action="Transfer", entity="Pilgrim", entity_id=pilgrim.id,
                           timestamp=datetime.now(),
                           details=f"Moved to Free Account ({pilgrim.status.value}) after 6-hour rule"),
                conn=conn,
            )
        return pilgrim

    def run_six_hour_transfer_sweep(self, actor: str = "system", now: Optional[datetime] = None) -> int:
        """
        Idempotent sweep: only ACTIVE pilgrims whose permit datetime is
        >= 6 hours in the past are affected, and each is moved exactly
        once because a successful transfer flips status away from
        ACTIVE, taking it out of scope for the next sweep (NFR-04 / 16.7).
        """
        moved = 0
        hours = self._transfer_hours()
        candidates = self.pilgrims.list_upcoming_active()
        for p in candidates:
        # Do not automatically transfer pilgrims who were returned to a party.
            if p.returned_at is not None:
                continue

            if is_eligible_for_transfer(p.permit_date, p.permit_time, now, hours=hours):
                try:
                    self.transfer_to_free(p.id, actor=actor)
                    moved += 1
                except Exception as e:
                    logger.error("Six-hour transfer failed for pilgrim %s: %s", p.id, e)
        return moved

    def _transfer_hours(self) -> int:
        """Read the configured window (Settings -> General), default 6."""
        try:
            from application.settings_service import SettingsService
            return int(SettingsService().get("transfer_hours") or DEFAULT_TRANSFER_HOURS)
        except Exception:
            return DEFAULT_TRANSFER_HOURS

    def return_to_party(self, pilgrim_id: int, destination_party_id: int, actor: str, reason: str = "") -> Pilgrim:
        with transaction() as conn:
            pilgrim = self.pilgrims.get(pilgrim_id, conn=conn)
            if not pilgrim:
                raise NotFoundError("Pilgrim not found.")
            if pilgrim.status not in (PilgrimStatus.FREE_MALE, PilgrimStatus.FREE_FEMALE):
                raise ValidationError("Only pilgrims currently in a Free Account can be returned.")

            destination = self.parties.get(destination_party_id, conn=conn)
            if not destination or not destination.active:
                raise ValidationError("Please select a valid, active destination party.")

            source_status = pilgrim.status.value
            # Back on a party ledger the pilgrim takes that party's NEXT serial number
            # (the old one may already belong to somebody else there).
            pilgrim.serial_number = self.pilgrims.next_serial_number(destination_party_id, conn=conn)
            pilgrim.free_serial = 0
            pilgrim.party_id = destination_party_id
            pilgrim.status = PilgrimStatus.ACTIVE
            pilgrim.moved_to_free_at = None
            pilgrim.returned_at = datetime.now()

            self.pilgrims.update(pilgrim, conn=conn)

            self.return_history.create(
                ReturnHistoryEntry(id=None, pilgrim_id=pilgrim.id, source_status=source_status,
                                    destination_party_id=destination_party_id, administrator=actor,
                                    timestamp=datetime.now(), reason=reason),
                conn=conn,
            )
            self.audit.log(
                AuditEntry(id=None, user=actor, action="Return", entity="Pilgrim", entity_id=pilgrim.id,
                           timestamp=datetime.now(),
                           details=f"Returned from {source_status} to party '{destination.name}'"),
                conn=conn,
            )
        return pilgrim
